import sys


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    flags = sys.argv[2:]

    if command == "watch":
        dry_run = "--dry-run" in flags

        from volley.gmail.auth import get_gmail_service
        from volley.agent.graph import get_app
        from volley.gmail.watcher import watch

        print("Connecting to Gmail...")
        service = get_gmail_service()

        print("Loading agent graph...")
        app = get_app()

        watch(service, app, dry_run=dry_run)

    elif command == "index":
        incremental = "--incremental" in flags

        from volley.gmail.auth import get_gmail_service
        from volley.rag.corpus import build_corpus, incremental_update

        print("Connecting to Gmail...")
        service = get_gmail_service()

        if incremental:
            incremental_update(service)
        else:
            build_corpus(service)

    elif command == "search":
        query = " ".join(flags)
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
        print("Volley — Gmail-connected AI lead responder")
        print()
        print("Commands:")
        print("  watch                  — monitor inbox and process leads")
        print("  watch --dry-run        — classify and draft, never send")
        print("  index                  — full tone corpus build from sent mail")
        print("  index --incremental    — index only emails sent since last run")
        print("  search <text>          — search tone corpus by query")


if __name__ == "__main__":
    main()
