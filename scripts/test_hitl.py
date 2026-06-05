"""
Phase 7 test script — human-in-the-loop approval.

Run with:
    uv run python scripts/test_hitl.py

What it does:
  1. Seeds the tone corpus with sample sent emails
  2. Runs ONE inbound lead email through the full graph
  3. Pauses at the approval step — YOU type A / E / S
  4. If approved: sends the email to yourself as a test
  5. Prints the final state

Requires: OPENAI_API_KEY in .env + credentials.json for Gmail send.
Gmail auth only triggers when you choose [A] or [E].
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from volley.rag.store import index_email
from volley.agent.graph import get_app
from volley.agent.runner import process_email

SENT_EMAILS = [
    {
        "id": "tone_001",
        "subject": "Re: Consulting inquiry",
        "body": (
            "Hey Sarah, thanks for reaching out!\n\n"
            "Love what you're building. My availability opens up mid-month — "
            "would a 30-min call on the 15th or 16th work?\n\nTalk soon,\nAlex"
        ),
        "to": "sarah@acme.com",
        "date": "Mon, 1 Jan 2024",
    },
    {
        "id": "tone_002",
        "subject": "Re: Working together",
        "body": (
            "Hi Tom,\n\nSounds interesting — can you send a brief with the key goals "
            "and timeline? That'll help me figure out whether I can add real value here.\n\nBest,\nAlex"
        ),
        "to": "tom@ventures.io",
        "date": "Tue, 2 Jan 2024",
    },
]

INBOUND_EMAIL = {
    "id": "test_hitl_001",
    "thread_id": "",  # no real thread — will send as standalone email
    "from": "yuvrajys2512@gmail.com",  # send to yourself so you can verify it arrives
    "to": "me@example.com",
    "subject": "Looking for a growth consultant",
    "body": (
        "Hi, I found you through a mutual connection. We're a SaaS company doing "
        "$500k ARR and trying to scale to $2M. Deals keep stalling mid-funnel and "
        "we're not sure why. Would you be open to a quick conversation about "
        "potentially working together?\n\nJames"
    ),
    "date": "Thu, 5 Jun 2026",
    "snippet": "Hi, I found you through a mutual connection...",
}


def main():
    print("Seeding tone corpus...")
    for email in SENT_EMAILS:
        index_email(email)
    print(f"Indexed {len(SENT_EMAILS)} tone examples.\n")

    print("Starting agent for inbound email...")
    print(f"From:    {INBOUND_EMAIL['from']}")
    print(f"Subject: {INBOUND_EMAIL['subject']}\n")

    app = get_app()
    final_state = process_email(app, INBOUND_EMAIL)

    print("\n" + "=" * 65)
    print("FINAL STATE")
    print("=" * 65)
    print(f"  intent:          {final_state.get('intent')}")
    print(f"  is_lead:         {final_state.get('is_lead')}")
    print(f"  approval_status: {final_state.get('approval_status')}")
    print(f"  final_reply:     {str(final_state.get('final_reply', ''))[:100]}")


if __name__ == "__main__":
    main()
