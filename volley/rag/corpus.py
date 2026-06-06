import json
import os
from datetime import datetime

from volley.config import CHROMA_DB_PATH
from volley.gmail.history import fetch_sent_emails, fetch_sent_emails_since, filter_for_corpus
from volley.rag.store import corpus_size, index_emails_batch

BATCH_SIZE = 50
INDEX_STATE_FILE = os.path.join(os.path.dirname(CHROMA_DB_PATH), "index_state.json")


# ── Index state (last_indexed_at persistence) ──────────────────────────────────

def _load_index_state() -> dict:
    if os.path.exists(INDEX_STATE_FILE):
        with open(INDEX_STATE_FILE) as f:
            return json.load(f)
    return {"last_indexed_at": None}


def _save_index_state(state: dict):
    with open(INDEX_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_last_indexed_at() -> str | None:
    return _load_index_state().get("last_indexed_at")


# ── Full corpus build ──────────────────────────────────────────────────────────

def build_corpus(service, max_fetch: int = 500) -> dict:
    """
    Full corpus build: fetch sent mail, filter, embed, and store.
    Call this once on first run.
    """
    print(f"Fetching up to {max_fetch} sent emails...")
    sent = fetch_sent_emails(service, max_results=max_fetch)
    print(f"Fetched {len(sent)} sent emails.")

    corpus = filter_for_corpus(sent)
    print(f"{len(corpus)} emails passed the corpus filter.")

    if not corpus:
        print("Nothing to index.")
        return {"fetched": len(sent), "filtered": 0, "indexed": 0}

    indexed = _index_in_batches(corpus)
    total = corpus_size()

    _save_index_state({"last_indexed_at": _today_str()})
    print(f"Indexed {indexed} emails. Corpus now has {total} total entries.")
    return {"fetched": len(sent), "filtered": len(corpus), "indexed": indexed}


# ── Incremental update ─────────────────────────────────────────────────────────

def incremental_update(service) -> dict:
    """
    Index only sent emails newer than the last full/incremental run.
    Fast — only fetches emails sent since last index date.
    """
    last = get_last_indexed_at()
    if not last:
        print("No prior index found. Run 'volley index' for a full build first.")
        return {"fetched": 0, "filtered": 0, "indexed": 0}

    print(f"Incremental update since {last}...")
    sent = fetch_sent_emails_since(service, after_date=last.replace("-", "/"))
    print(f"Fetched {len(sent)} new sent emails.")

    corpus = filter_for_corpus(sent)
    print(f"{len(corpus)} emails passed the corpus filter.")

    if not corpus:
        print("Nothing new to index.")
        _save_index_state({"last_indexed_at": _today_str()})
        return {"fetched": len(sent), "filtered": 0, "indexed": 0}

    indexed = _index_in_batches(corpus)
    _save_index_state({"last_indexed_at": _today_str()})
    print(f"Indexed {indexed} new emails. Corpus now has {corpus_size()} total entries.")
    return {"fetched": len(sent), "filtered": len(corpus), "indexed": indexed}


def index_single_email(email: dict):
    """Index one email immediately — called after a reply is sent."""
    from volley.gmail.history import filter_for_corpus
    from volley.rag.store import index_email

    eligible = filter_for_corpus([email])
    if eligible:
        index_email(eligible[0])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _index_in_batches(emails: list[dict]) -> int:
    total_indexed = 0
    batches = [emails[i:i + BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]

    for i, batch in enumerate(batches, 1):
        print(f"  Embedding batch {i}/{len(batches)} ({len(batch)} emails)...", end=" ", flush=True)
        n = index_emails_batch(batch)
        total_indexed += n
        print(f"done ({n} indexed)")

    return total_indexed


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")
