import chromadb
from chromadb.config import Settings

from volley.config import CHROMA_DB_PATH
from volley.rag.embedder import embed

COLLECTION_NAME = "sent_emails"

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_email(email: dict) -> None:
    """Embed and store a single sent email in the vector store."""
    collection = _get_collection()
    body = email.get("body", "").strip()
    if not body:
        return

    # Use subject + body as the indexed text so retrieval accounts for topic too
    text = f"{email.get('subject', '')}\n\n{body}"

    collection.upsert(
        ids=[email["id"]],
        embeddings=[embed(text)],
        documents=[body],
        metadatas=[{
            "subject": email.get("subject", ""),
            "date": email.get("date", ""),
            "to": email.get("to", ""),
        }],
    )


def index_emails_batch(emails: list[dict]) -> int:
    """
    Embed and store a batch of emails efficiently.
    Returns the number successfully indexed.
    """
    from volley.rag.embedder import embed_batch

    collection = _get_collection()
    valid = [e for e in emails if e.get("body", "").strip()]

    if not valid:
        return 0

    texts = [f"{e.get('subject', '')}\n\n{e['body']}" for e in valid]
    embeddings = embed_batch(texts)

    collection.upsert(
        ids=[e["id"] for e in valid],
        embeddings=embeddings,
        documents=[e["body"] for e in valid],
        metadatas=[{
            "subject": e.get("subject", ""),
            "date": e.get("date", ""),
            "to": e.get("to", ""),
        } for e in valid],
    )

    return len(valid)


def retrieve_similar(query: str, n_results: int = 5) -> list[dict]:
    """
    Find the most stylistically similar past emails to the given query.
    Returns a list of dicts with 'body' and 'metadata'.
    """
    collection = _get_collection()

    count = collection.count()
    if count == 0:
        return []

    # Can't ask for more results than exist
    n = min(n_results, count)

    results = collection.query(
        query_embeddings=[embed(query)],
        n_results=n,
    )

    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        output.append({"body": doc, "metadata": meta})

    return output


def corpus_size() -> int:
    """Return the number of emails currently indexed."""
    return _get_collection().count()
