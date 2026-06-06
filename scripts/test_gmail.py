"""
Phase 2 test script.

Run with:
    uv run python scripts/test_gmail.py

What it does:
  1. Authenticates with Gmail (opens browser on first run)
  2. Fetches 5 unread inbox emails and prints them
  3. Fetches 5 sent emails (for corpus preview)
  4. Sends a test email to yourself

Set TEST_RECIPIENT in your .env or it defaults to your own address.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from volley.gmail.auth import get_gmail_service
from volley.gmail.history import fetch_sent_emails, filter_for_corpus
from volley.gmail.reader import fetch_inbox_emails, truncate_body
from volley.gmail.sender import send_email

DIVIDER = "─" * 60


def print_email(email: dict, index: int):
    print(f"\n{DIVIDER}")
    print(f"[{index}] From:    {email['from']}")
    print(f"    Subject: {email['subject']}")
    print(f"    Date:    {email['date']}")
    print(f"    Snippet: {email['snippet'][:120]}")
    body_preview = truncate_body(email["body"], max_chars=300)
    if body_preview:
        print(f"\n{body_preview}")


def main():
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    print("Authenticated.\n")

    # ── 1. Inbox emails ────────────────────────────────────────────
    print("=" * 60)
    print("INBOX — 5 most recent unread emails")
    print("=" * 60)

    inbox = fetch_inbox_emails(service, max_results=5, only_unread=True)
    if not inbox:
        print("No unread emails found.")
    for i, email in enumerate(inbox, 1):
        print_email(email, i)

    # ── 2. Sent mail preview ───────────────────────────────────────
    print(f"\n\n{'=' * 60}")
    print("SENT — 5 most recent sent emails (corpus preview)")
    print("=" * 60)

    sent = fetch_sent_emails(service, max_results=5)
    corpus = filter_for_corpus(sent)
    print(f"Fetched {len(sent)} sent emails. {len(corpus)} passed corpus filter.\n")
    for i, email in enumerate(sent[:5], 1):
        print_email(email, i)

    # ── 3. Send test email to self ─────────────────────────────────
    print(f"\n\n{'=' * 60}")
    print("SEND TEST")
    print("=" * 60)

    profile = service.users().getProfile(userId="me").execute()
    my_address = profile["emailAddress"]

    confirm = input(f"\nSend a test email to yourself ({my_address})? [y/N]: ").strip().lower()
    if confirm == "y":
        result = send_email(
            service,
            to=my_address,
            subject="Volley — Phase 2 test",
            body="If you're reading this, the Gmail send integration works.\n\nVolley",
        )
        print(f"Sent! Message ID: {result['id']}")
    else:
        print("Skipped send test.")


if __name__ == "__main__":
    main()
