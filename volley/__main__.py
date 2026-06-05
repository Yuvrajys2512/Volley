import sys


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "watch":
        print("Volley watcher — not yet implemented (Phase 8)")

    elif command == "index":
        from volley.gmail.auth import get_gmail_service
        from volley.rag.corpus import build_corpus

        print("Connecting to Gmail...")
        service = get_gmail_service()
        build_corpus(service)

    elif command == "search":
        query = " ".join(sys.argv[2:])
        if not query:
            print("Usage: volley search <query>")
            sys.exit(1)

        from volley.rag.store import retrieve_similar, corpus_size

        size = corpus_size()
        if size == 0:
            print("Corpus is empty. Run 'volley index' first.")
            sys.exit(1)

        print(f"Corpus size: {size} emails")
        print(f"Query: \"{query}\"\n")

        results = retrieve_similar(query, n_results=3)
        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            print(f"{'─' * 60}")
            print(f"[{i}] Subject: {meta.get('subject', '(none)')}")
            print(f"    To:      {meta.get('to', '')}")
            print(f"    Date:    {meta.get('date', '')}")
            print(f"\n{r['body'][:500]}")
            print()

    else:
        print("Volley is starting...")
        print()
        print("Commands:")
        print("  watch         — monitor inbox and process leads")
        print("  index         — build tone corpus from sent mail")
        print("  search <text> — search tone corpus by query")


if __name__ == "__main__":
    main()
