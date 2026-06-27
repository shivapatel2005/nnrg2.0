"""
vector_db.py
------------
ChromaDB vector store integration.

Only ONE collection is maintained:
  - "nnrg_pdf" : chunks from user-uploaded PDFs

Website content is NEVER stored here. It is fetched live from
nnrg.edu.in on every chat request (see scraper.py / rag.py) and
discarded immediately after the answer is generated. This keeps the
website knowledge always fresh and avoids stale/duplicated data.
"""

import os
import logging
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

COLLECTION_PDF = "nnrg_pdf"

_client: Optional[chromadb.PersistentClient] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialized at: %s", CHROMA_DB_PATH)
    return _client


def _get_collection(name: str):
    client = _get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_pdf_chunks(chunks: list[dict], doc_id: str, filename: str) -> int:
    """
    Upsert PDF text chunks into ChromaDB.

    Each chunk dict must have: {"text": str, "page_number": int, "chunk_index": int}
    """
    if not chunks:
        return 0

    from embeddings import embed_texts

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts).tolist()

    collection = _get_collection(COLLECTION_PDF)
    ids = [f"pdf_{doc_id}_{c['chunk_index']}" for c in chunks]
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info("Upserted %d PDF chunks for doc_id=%s into ChromaDB", len(chunks), doc_id)
    return len(chunks)


def delete_pdf_doc(doc_id: str) -> None:
    """Remove all chunks belonging to a specific PDF document."""
    collection = _get_collection(COLLECTION_PDF)
    results = collection.get(where={"doc_id": doc_id})
    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info("Deleted %d chunks for doc_id=%s", len(results["ids"]), doc_id)


# ─── Query ────────────────────────────────────────────────────────────────────

def query_pdf(query_text: str, n_results: int = 4) -> list[dict]:
    """
    Semantic search against the PDF collection.
    Returns list of {"text": str, "filename": str, "page_number": int, "score": float, "source": "pdf"}
    """
    from embeddings import embed_query

    collection = _get_collection(COLLECTION_PDF)
    if collection.count() == 0:
        return []

    query_vec = embed_query(query_text).tolist()
    try:
        results = collection.query(
            query_embeddings=query_vec,
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("PDF query failed: %s", e)
        return []

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = 1.0 - dist
        output.append({
            "text": doc,
            "filename": meta.get("filename", "uploaded PDF"),
            "page_number": meta.get("page_number", 0),
            "score": round(score, 4),
            "source": "pdf",
        })
    return output


# ─── Status ───────────────────────────────────────────────────────────────────

def get_collection_counts() -> dict:
    pdf_count = _get_collection(COLLECTION_PDF).count()
    return {"pdf_chunks": pdf_count}


def list_pdf_documents() -> list[dict]:
    """List unique PDF filenames currently indexed."""
    collection = _get_collection(COLLECTION_PDF)
    if collection.count() == 0:
        return []
    results = collection.get(include=["metadatas"])
    seen_ids = {}
    for meta in results["metadatas"]:
        doc_id = meta.get("doc_id", "")
        if doc_id and doc_id not in seen_ids:
            seen_ids[doc_id] = {
                "doc_id": doc_id,
                "filename": meta.get("filename", ""),
            }
    return list(seen_ids.values())
