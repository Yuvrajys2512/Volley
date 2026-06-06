"""
Inbox watcher: polls Gmail for new unread emails on a configurable interval,
deduplicates against a local SQLite store, and fires the agent graph for each
new email it finds.
"""

# Path to the dedup database (same dir as the checkpointer DB)
import os
import signal
import sqlite3
import time
from datetime import datetime

from volley.config import CHROMA_DB_PATH, POLL_INTERVAL_SECONDS
from volley.gmail.reader import fetch_inbox_emails

SEEN_DB = os.path.join(os.path.dirname(CHROMA_DB_PATH), "seen_messages.db")


# ── Deduplication store ────────────────────────────────────────────────────────

def _init_seen_db():
    """Create the seen_messages table if it doesn't exist."""
    conn = sqlite3.connect(SEEN_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_messages (
            message_id TEXT PRIMARY KEY,
            seen_at     TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _is_seen(message_id: str) -> bool:
    conn = sqlite3.connect(SEEN_DB)
    row = conn.execute(
        "SELECT 1 FROM seen_messages WHERE message_id = ?", (message_id,)
    ).fetchone()
    conn.close()
    return row is not None


def _mark_seen(message_id: str):
    conn = sqlite3.connect(SEEN_DB)
    conn.execute(
        "INSERT OR IGNORE INTO seen_messages (message_id, seen_at) VALUES (?, ?)",
        (message_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


# ── Watcher ───────────────────────────────────────────────────────────────────

class GracefulExit(Exception):
    pass


def _handle_sigint(sig, frame):
    raise GracefulExit()


def watch(service, app, dry_run: bool = False):
    """
    Poll the inbox continuously and run the agent graph for each new email.

    Args:
        service:  Authorized Gmail API service client.
        app:      Compiled LangGraph app (with checkpointer).
        dry_run:  If True, classify and draft but never send.
    """

    _init_seen_db()
    signal.signal(signal.SIGINT, _handle_sigint)

    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}Volley watcher started. Polling every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")

    try:
        while True:
            _poll_once(service, app, dry_run)
            time.sleep(POLL_INTERVAL_SECONDS)

    except GracefulExit:
        print("\nWatcher stopped.")


def _poll_once(service, app, dry_run: bool):
    """Fetch new unread emails and process any that haven't been seen yet."""
    from volley.agent.runner import process_email

    timestamp = datetime.utcnow().strftime("%H:%M:%S")

    try:
        emails = fetch_inbox_emails(service, max_results=20, only_unread=True)
    except Exception as e:
        print(f"[{timestamp}] Gmail fetch error: {e}")
        return

    new_emails = [e for e in emails if not _is_seen(e["id"])]

    if not new_emails:
        print(f"[{timestamp}] No new emails.")
        return

    print(f"[{timestamp}] {len(new_emails)} new email(s) found.")

    for email in new_emails:
        # Mark seen immediately so a crash mid-process doesn't reprocess it
        _mark_seen(email["id"])

        print(f"\n→ Processing: {email['subject']!r} from {email['from']}")

        try:
            if dry_run:
                _dry_run_email(app, email)
            else:
                final_state = process_email(app, email)
                from volley.logger import log_email_processed
                log_email_processed(email, final_state)
        except Exception as e:
            from volley.logger import log_error
            log_error(email.get("id", "unknown"), e)
            print(f"  Error processing email {email['id']}: {e}")


def _dry_run_email(app, email: dict):
    """
    Run the graph up to (but not including) the send step.
    Prints the draft without sending or prompting for approval.
    """
    from volley.agent.graph import build_graph

    # Build a no-checkpointer, no-interrupt graph for dry run
    dry_app = build_graph(checkpointer=None)
    state = dry_app.invoke({"email": email})

    if state.get("draft"):
        print(f"\n  [DRY RUN] Draft for {email['from']}:")
        print("  " + "\n  ".join(state["draft"].splitlines()))
    else:
        print(f"  [DRY RUN] Skipped (intent={state.get('intent')})")
