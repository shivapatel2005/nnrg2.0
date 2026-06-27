"""
app.py
------
FastAPI backend for the NNRG AI Assistant.

Endpoints:
    POST /chat           — Ask a question (RAG over website + uploaded PDF)
    POST /upload         — Upload a PDF to index into ChromaDB
    GET  /health         — Health check (for Render)
    GET  /sources        — List indexed PDF documents
    DELETE /session      — Clear session chat history (client-managed)

Session history is accepted as part of each /chat request (stateless server).
"""

import os
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nnrg-backend")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
ALLOWED_EXTENSIONS = {".pdf"}

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")


# ─── Lifespan (startup) ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NNRG AI Assistant backend starting up...")
    # Warm up ChromaDB collections
    try:
        from vector_db import get_collection_counts
        counts = get_collection_counts()
        logger.info("ChromaDB ready — PDF chunks: %d", counts["pdf_chunks"])
    except Exception as e:
        logger.warning("ChromaDB warm-up failed (non-fatal): %s", e)
    yield
    logger.info("Shutting down.")


# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NNRG AI Assistant API",
    description="Web Knowledge Bot + PDF RAG for NNRG College",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & templates
BASE_DIR = Path(__file__).parent.parent / "frontend"
if BASE_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")

templates_dir = Path(__file__).parent.parent / "frontend"


# ─── Pydantic models ─────────────────────────────────────────────────────────

class SessionMessage(BaseModel):
    role: str          # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    session_history: list[SessionMessage] = []


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check for Render deployment."""
    return {"status": "ok", "service": "nnrg-ai-assistant"}


@app.get("/api/sources")
async def list_sources():
    """List all indexed PDF documents. (Website content is never stored — live fetch only.)"""
    try:
        from vector_db import list_pdf_documents, get_collection_counts
        docs = list_pdf_documents()
        counts = get_collection_counts()
        return {
            "pdf_documents": docs,
            "stats": counts,
        }
    except Exception as e:
        logger.exception("Failed to list sources")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.

    Accepts a question and optional session history.
    Returns a grounded answer with source attribution.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question is too long (max 1000 characters).")

    history = [{"role": m.role, "content": m.content} for m in req.session_history]

    try:
        from rag import run_rag_pipeline
        result = run_rag_pipeline(question, session_history=history)
        return result
    except Exception as e:
        err_str = str(e)
        logger.exception("Chat pipeline failed for question: %r", question)
        if "GROQ_API_KEY" in err_str:
            raise HTTPException(
                status_code=503,
                detail="LLM service is unavailable: GROQ_API_KEY is not configured.",
            )
        raise HTTPException(status_code=500, detail=f"Internal error: {err_str}")


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file and index its contents into ChromaDB.
    """
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()

    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are supported. Got: '{ext}'.",
        )

    # Save to disk
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}_{filename}"
    save_path = UPLOAD_DIR / safe_name

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_MB} MB.",
        )

    save_path.write_bytes(content)
    logger.info("Saved uploaded PDF: %s (%d bytes)", save_path, len(content))

    # Extract text
    try:
        from pdf_loader import extract_text_from_pdf, PDFLoadError
        pages = extract_text_from_pdf(str(save_path))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        logger.error("PDF extraction failed for %s: %s", filename, e)
        raise HTTPException(status_code=422, detail=f"Failed to read PDF: {e}")

    # Chunk text
    try:
        from rag import chunk_text
        chunks = []
        chunk_idx = 0
        for page in pages:
            if not page["text"].strip():
                continue
            page_chunks = chunk_text(page["text"])
            for chunk in page_chunks:
                chunks.append({
                    "text": chunk,
                    "page_number": page["page_number"],
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Chunking failed: {e}")

    if not chunks:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="PDF produced no text chunks.")

    # Embed + store in ChromaDB
    try:
        from vector_db import upsert_pdf_chunks
        n_stored = upsert_pdf_chunks(chunks, doc_id=doc_id, filename=filename)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        logger.exception("ChromaDB upsert failed")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

    logger.info(
        "Indexed PDF '%s': %d pages → %d chunks (doc_id=%s)",
        filename, len(pages), n_stored, doc_id,
    )
    return {
        "status": "indexed",
        "doc_id": doc_id,
        "filename": filename,
        "num_pages": len(pages),
        "num_chunks": n_stored,
        "message": f"✅ PDF '{filename}' indexed successfully with {n_stored} chunks.",
    }


@app.delete("/session")
async def clear_session():
    """
    Session is managed client-side. This endpoint is a no-op that the
    frontend can call to signal a new conversation.
    """
    return {"status": "cleared", "message": "Session cleared. Start a new conversation!"}


@app.delete("/api/pdf/{doc_id}")
async def delete_pdf(doc_id: str):
    """Delete an indexed PDF from ChromaDB."""
    try:
        from vector_db import delete_pdf_doc
        delete_pdf_doc(doc_id)
        # Also remove the file from disk
        for f in UPLOAD_DIR.glob(f"{doc_id}_*"):
            f.unlink(missing_ok=True)
        return {"status": "deleted", "doc_id": doc_id}
    except Exception as e:
        logger.exception("Failed to delete PDF doc_id=%s", doc_id)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True, log_level="info")
