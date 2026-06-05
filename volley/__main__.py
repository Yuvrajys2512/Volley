import sys


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "watch":
        print("Volley watcher — not yet implemented (Phase 8)")
    elif command == "index":
        print("Volley indexer — not yet implemented (Phase 3)")
    elif command == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        print(f"Volley search: '{query}' — not yet implemented (Phase 3)")
    else:
        print("Volley is starting...")
        print()
        print("Commands:")
        print("  watch   — monitor inbox and process leads")
        print("  index   — build tone corpus from sent mail")
        print("  search  — search tone corpus by query")


if __name__ == "__main__":
    main()
