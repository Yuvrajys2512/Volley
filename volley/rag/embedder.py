from openai import OpenAI
from volley.config import OPENAI_API_KEY, EMBEDDING_MODEL

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set in your .env file.")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single piece of text."""
    client = _get_client()
    text = text.replace("\n", " ").strip()
    response = client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call (more efficient than looping)."""
    client = _get_client()
    cleaned = [t.replace("\n", " ").strip() for t in texts]
    response = client.embeddings.create(
        input=cleaned,
        model=EMBEDDING_MODEL,
    )
    # API returns embeddings in the same order as input
    return [item.embedding for item in response.data]
