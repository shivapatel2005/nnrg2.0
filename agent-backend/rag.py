"""
rag.py
------
Unified RAG pipeline.

1. Takes a user question.
2. Runs live website fetch AND PDF vector search in parallel.
3. Merges and ranks chunks by similarity.
4. Builds a grounded prompt and calls Groq LLM.
5. Returns structured answer + source attribution.

Website knowledge: fetched LIVE per query from nnrg.edu.in and
discarded immediately after ranking — nothing is ever written to disk
or ChromaDB for the website.
PDF knowledge: retrieved from ChromaDB (persisted from /upload endpoint
so re-asking questions about an uploaded PDF doesn't require re-uploading).
"""

import os
import logging
import concurrent.futures
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Out-of-domain detection ─────────────────────────────────────────────────

OUT_OF_DOMAIN_KEYWORDS = [
    "ipl", "cricket", "bollywood", "movie", "recipe", "joke",
    "weather", "stock", "bitcoin", "forex", "trump", "politics",
    "war", "fifa", "nba", "game of thrones", "netflix", "spotify",
]

NNRG_KEYWORDS = [
    "nnrg", "nalla", "narasimha", "reddy", "college", "admission",
    "btech", "b.tech", "mtech", "m.tech", "mba", "mca", "bca",
    "department", "faculty", "placement", "hostel", "campus", "fee",
    "syllabus", "exam", "semester", "principal", "dean", "course",
    "library", "laboratory", "scholarship", "affiliation", "naac",
    "jntuh", "autonomous", "engineering", "hyderabad", "ghatkesar",
    "internship", "project", "result", "notification", "calendar",
    "event", "sports", "nss", "club", "transport", "mess", "canteen",
]


def is_out_of_domain(question: str) -> bool:
    """
    Returns True if the question is clearly not about NNRG College.
    Uses a simple keyword heuristic — good enough for an internship chatbot.
    """
    q_lower = question.lower()

    # If the question mentions NNRG-related keywords, it's in-domain
    if any(kw in q_lower for kw in NNRG_KEYWORDS):
        return False

    # If it contains only out-of-domain keywords, reject
    if any(kw in q_lower for kw in OUT_OF_DOMAIN_KEYWORDS):
        return True

    return False


OUT_OF_DOMAIN_RESPONSE = (
    "I can only answer questions related to the **NNRG College website** "
    "(https://nnrg.edu.in/) or the **uploaded PDF**. "
    "Please ask me about admissions, courses, departments, faculty, placements, "
    "hostel, fees, the academic calendar, or other college-related topics."
)


# ─── Text chunking ────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks using LangChain's RecursiveCharacterTextSplitter."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)
    except Exception:
        # Fallback: simple fixed-size chunking
        chunks = []
        for i in range(0, len(text), chunk_size - chunk_overlap):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks


# ─── Website RAG ─────────────────────────────────────────────────────────────

def fetch_and_chunk_website(question: str) -> list[dict]:
    """
    Fetch relevant NNRG website pages live, extract text, chunk, and return
    as a list of {"text": str, "url": str, "source": "website"} dicts.

    Nothing is persisted to disk or ChromaDB — every call re-fetches the
    live pages so the website knowledge is always current.
    """
    from scraper import discover_candidate_urls, fetch_url, extract_html_text
    from pdf_loader import extract_text_from_bytes

    candidate_urls = discover_candidate_urls(question)
    logger.info("Fetching %d candidate URLs...", len(candidate_urls))

    all_chunks = []
    for url in candidate_urls:
        content_bytes, content_type = fetch_url(url)
        if not content_bytes:
            continue

        # Determine how to extract text
        ctype_lower = (content_type or "").lower()
        if "pdf" in ctype_lower or url.lower().endswith(".pdf"):
            text = extract_text_from_bytes(content_bytes)
        else:
            text = extract_html_text(content_bytes)

        if not text or len(text.strip()) < 50:
            continue

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append({"text": chunk, "url": url, "chunk_index": i, "source": "website"})

    return all_chunks


def rank_chunks_for_query(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rank website chunks by cosine similarity to the query.
    Returns the top-k most relevant chunks.
    """
    if not chunks:
        return []

    try:
        from embeddings import embed_texts, embed_query
        import numpy as np

        texts = [c["text"] for c in chunks]
        chunk_vecs = embed_texts(texts)           # (N, 384)
        query_vec = embed_query(query)             # (1, 384)

        # cosine similarity (vectors already L2-normalized)
        scores = (chunk_vecs @ query_vec.T).squeeze()  # (N,)
        if scores.ndim == 0:
            scores = scores.reshape(1)

        top_indices = np.argsort(scores)[::-1][:top_k]
        ranked = []
        for idx in top_indices:
            c = dict(chunks[idx])
            c["score"] = float(scores[idx])
            ranked.append(c)
        return ranked
    except Exception as e:
        logger.warning("Chunk ranking failed: %s. Returning unranked.", e)
        return chunks[:top_k]


# ─── Full RAG pipeline ────────────────────────────────────────────────────────

def run_rag_pipeline(
    question: str,
    session_history: Optional[list] = None,
) -> dict:
    """
    Main RAG pipeline entry point.

    Returns:
        {
          "answer": str,
          "source": "website" | "pdf" | "both" | "none",
          "website_sources": [...],
          "pdf_sources": [...],
          "is_out_of_domain": bool,
        }
    """
    # ── Out-of-domain guard ───────────────────────────────────────────────────
    if is_out_of_domain(question):
        return {
            "answer": OUT_OF_DOMAIN_RESPONSE,
            "source": "none",
            "website_sources": [],
            "pdf_sources": [],
            "is_out_of_domain": True,
        }

    # ── Parallel retrieval ───────────────────────────────────────────────────
    website_chunks = []
    pdf_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Website: live fetch + rank
        def get_website_chunks():
            raw = fetch_and_chunk_website(question)
            return rank_chunks_for_query(question, raw, top_k=5)

        # PDF: ChromaDB semantic search
        def get_pdf_results():
            try:
                from vector_db import query_pdf
                return query_pdf(question, n_results=4)
            except Exception as e:
                logger.warning("PDF retrieval failed: %s", e)
                return []

        future_web = executor.submit(get_website_chunks)
        future_pdf = executor.submit(get_pdf_results)

        try:
            website_chunks = future_web.result(timeout=30)
        except Exception as e:
            logger.error("Website retrieval failed: %s", e)

        try:
            pdf_results = future_pdf.result(timeout=10)
        except Exception as e:
            logger.error("PDF retrieval failed: %s", e)

    # ── Determine source ─────────────────────────────────────────────────────
    has_web = bool(website_chunks)
    has_pdf = bool(pdf_results)
    if has_web and has_pdf:
        source = "both"
    elif has_web:
        source = "website"
    elif has_pdf:
        source = "pdf"
    else:
        source = "none"

    # ── Format website sources for citation ─────────────────────────────────
    web_sources = []
    seen_urls = set()
    for c in website_chunks:
        if c["url"] not in seen_urls:
            web_sources.append({"url": c["url"]})
            seen_urls.add(c["url"])

    pdf_sources = [
        {"filename": c["filename"], "page": c["page_number"]}
        for c in pdf_results
    ]

    # ── Generate answer ──────────────────────────────────────────────────────
    from prompts import build_prompt
    from llm import call_groq

    prompt_messages = build_prompt(
        question=question,
        website_chunks=website_chunks,
        pdf_chunks=pdf_results,
        session_history=session_history or [],
    )

    answer = call_groq(prompt_messages)

    return {
        "answer": answer,
        "source": source,
        "website_sources": web_sources,
        "pdf_sources": pdf_sources,
        "is_out_of_domain": False,
    }
