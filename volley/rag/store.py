"""Tone corpus store.

Two backends live behind the same public functions:

- Legacy (CLI, single-user): a global ChromaDB collection on disk, used when
  no `user_id`/`repo` is given — this is the existing personal-project path
  and stays untouched so the CLI keeps working without a Postgres server.
- Phase 1 (server, multi-tenant): pgvector via `Repo(user_id)`, used whenever
  a `user_id` or `repo` is passed. Callers may pass a pre-built `repo` (the
  worker reuses one per graph invocation) or just a `user_id` (a fresh
  session is opened and closed for that one call).
"""

import chromadb
from chromadb.config import Settings

from volley.config import CHROMA_DB_PATH
from volley.rag.embedder import embed, embed_batch

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


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        return None


def _with_repo(user_id, repo, fn):
    """Call fn(repo) using the given repo, or a fresh one scoped to user_id."""
    if repo is not None:
        return fn(repo)

    from volley.db.engine import session_scope
    from volley.db.repo import Repo

    with session_scope() as session:
        return fn(Repo(session, user_id))


def index_email(email: dict, user_id=None, repo=None) -> None:
    """Embed and store a single sent email in the vector store."""
    body = email.get("body", "").strip()
    if not body:
        return

    if user_id is not None or repo is not None:
        text = f"{email.get('subject', '')}\n\n{body}"
        embedding = embed(text)
        _with_repo(
            user_id,
            repo,
            lambda r: r.upsert_corpus_entry(
                message_id=email["id"],
                body=body,
                subject=email.get("subject", ""),
                sent_to=email.get("to", ""),
                sent_at=_parse_date(email.get("date")),
                embedding=embedding,
            ),
        )
        return

    # Legacy single-user ChromaDB path (CLI).
    collection = _get_collection()
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


def index_emails_batch(emails: list[dict], user_id=None, repo=None) -> int:
    """
    Embed and store a batch of emails efficiently.
    Returns the number successfully indexed.
    """
    valid = [e for e in emails if e.get("body", "").strip()]
    if not valid:
        return 0

    texts = [f"{e.get('subject', '')}\n\n{e['body']}" for e in valid]
    embeddings = embed_batch(texts)

    if user_id is not None or repo is not None:
        entries = [
            {
                "message_id": e["id"],
                "body": e["body"],
                "subject": e.get("subject", ""),
                "sent_to": e.get("to", ""),
                "sent_at": _parse_date(e.get("date")),
                "embedding": emb,
            }
            for e, emb in zip(valid, embeddings, strict=False)
        ]
        return _with_repo(user_id, repo, lambda r: r.upsert_corpus_entries_batch(entries))

    # Legacy single-user ChromaDB path (CLI).
    collection = _get_collection()
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


def retrieve_similar(query: str, user_id=None, n_results: int = 5, repo=None) -> list[dict]:
    """
    Find the most stylistically similar past emails to the given query.
    Returns a list of dicts with 'body' and 'metadata'.
    """
    if user_id is not None or repo is not None:
        query_embedding = embed(query)
        rows = _with_repo(user_id, repo, lambda r: r.retrieve_similar(query_embedding, n_results))
        return [
            {
                "body": row["body"],
                "metadata": {
                    "subject": row["subject"],
                    "sent_to": row["sent_to"],
                    "date": row["sent_at"].isoformat() if row["sent_at"] else "",
                },
            }
            for row in rows
        ]

    # Legacy single-user ChromaDB path (CLI).
    collection = _get_collection()

    count = collection.count()
    if count == 0:
        return []

    n = min(n_results, count)  # can't ask for more results than exist

    results = collection.query(
        query_embeddings=[embed(query)],
        n_results=n,
    )

    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0], strict=False):
        output.append({"body": doc, "metadata": meta})

    return output


def corpus_size(user_id=None, repo=None) -> int:
    """Return the number of emails currently indexed."""
    if user_id is not None or repo is not None:
        return _with_repo(user_id, repo, lambda r: r.corpus_size())

    return _get_collection().count()
