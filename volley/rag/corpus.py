from volley.gmail.history import fetch_sent_emails, filter_for_corpus
from volley.rag.store import index_emails_batch, corpus_size

# Batch size for embedding API calls — stays within token limits
BATCH_SIZE = 50


def build_corpus(service, max_fetch: int = 500) -> dict:
    """
    Full corpus build: fetch sent mail, filter, embed, and store.
    Call this once on first run.
    Returns a summary dict with counts.
    """
    print(f"Fetching up to {max_fetch} sent emails...")
    sent = fetch_sent_emails(service, max_results=max_fetch)
    print(f"Fetched {len(sent)} sent emails.")

    corpus = filter_for_corpus(sent)
    print(f"{len(corpus)} emails passed the corpus filter (others too short or auto-generated).")

    if not corpus:
        print("Nothing to index.")
        return {"fetched": len(sent), "filtered": 0, "indexed": 0}

    indexed = _index_in_batches(corpus)
    total = corpus_size()

    print(f"Indexed {indexed} emails. Corpus now has {total} total entries.")
    return {"fetched": len(sent), "filtered": len(corpus), "indexed": indexed}


def _index_in_batches(emails: list[dict]) -> int:
    """Split emails into batches and index each, showing progress."""
    total_indexed = 0
    batches = [emails[i:i + BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]

    for i, batch in enumerate(batches, 1):
        print(f"  Embedding batch {i}/{len(batches)} ({len(batch)} emails)...", end=" ", flush=True)
        n = index_emails_batch(batch)
        total_indexed += n
        print(f"done ({n} indexed)")

    return total_indexed
