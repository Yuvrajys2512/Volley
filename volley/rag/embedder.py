from sentence_transformers import SentenceTransformer

# Runs locally — no API key, no cost, no rate limits.
# Downloaded once (~80MB) and cached on first use.
_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single piece of text."""
    text = text.replace("\n", " ").strip()
    return _get_model().encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in one pass (more efficient than looping)."""
    cleaned = [t.replace("\n", " ").strip() for t in texts]
    return _get_model().encode(cleaned, normalize_embeddings=True).tolist()
