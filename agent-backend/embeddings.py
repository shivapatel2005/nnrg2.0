"""
embeddings.py
-------------
Thin wrapper around HuggingFace SentenceTransformers (all-MiniLM-L6-v2).
384-dimensional embeddings, fast on CPU, strong semantic similarity.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # lazy singleton


class EmbeddingError(Exception):
    pass


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", MODEL_NAME)
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            raise EmbeddingError(
                f"Could not load embedding model '{MODEL_NAME}'. "
                f"Ensure sentence-transformers is installed and internet is available "
                f"for the first-time download. Error: {e}"
            )
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Embed a list of strings.
    Returns shape (N, 384) float32 numpy array with L2-normalized vectors.
    """
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = _get_model()
    try:
        vecs = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vecs.astype(np.float32)
    except Exception as e:
        raise EmbeddingError(f"Embedding failed: {e}")


def embed_query(query: str) -> np.ndarray:
    """Embed a single query. Returns shape (1, 384) float32 array."""
    return embed_texts([query])


def get_embedding_dim() -> int:
    return _get_model().get_sentence_embedding_dimension()
