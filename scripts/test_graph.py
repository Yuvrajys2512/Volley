"""
Phase 6 test script — full LangGraph agent loop.

Run with:
    uv run python scripts/test_graph.py

What it does:
  1. Seeds the tone corpus with 3 sample sent emails
  2. Runs 3 emails through the graph (2 leads, 1 not a lead)
  3. Prints the full state after each run so you can see every field

No Gmail connection needed.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from volley.rag.store import index_email
from volley.agent.graph import build_graph  # no checkpointer needed for testing

DIVIDER = "=" * 65

# ── Seed tone corpus ───────────────────────────────────────────────────────────

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
    {
        "id": "tone_003",
        "subject": "Re: Referral from Mike",
        "body": (
            "Hey Priya, Mike's the best — always connecting the right people!\n\n"
            "Tell me more about where you're at. What's your current churn rate "
            "and what have you already tried?\n\nAlex"
        ),
        "to": "priya@example.com",
        "date": "Wed, 3 Jan 2024",
    },
]

# ── Test emails ────────────────────────────────────────────────────────────────

TEST_EMAILS = [
    {
        "label": "Inbound lead → should draft",
        "email": {
            "id": "msg_001",
            "thread_id": "thread_001",
            "from": "james.wu@b2b.com",
            "to": "me@example.com",
            "subject": "Looking for a growth consultant",
            "body": (
                "Hi, I found you through a mutual connection. We're a SaaS company "
                "doing $500k ARR and trying to get to $2M. Lots of inbound interest "
                "but deals keep stalling mid-funnel. Would you be open to a conversation "
                "about potentially working together? Ready to move quickly.\n\nJames"
            ),
            "date": "Thu, 5 Jun 2026",
            "snippet": "Hi, I found you through a mutual connection...",
        },
    },
    {
        "label": "Referral → should draft",
        "email": {
            "id": "msg_002",
            "thread_id": "thread_002",
            "from": "nina.patel@ecom.co",
            "to": "me@example.com",
            "subject": "Intro from David Park",
            "body": (
                "Hi! David Park suggested I reach out. I run a small e-commerce brand "
                "doing about 200 orders/day and our repeat purchase rate is terrible — "
                "around 15%. David said you've helped brands like ours fix exactly this. "
                "Are you taking on new clients?\n\nNina"
            ),
            "date": "Thu, 5 Jun 2026",
            "snippet": "Hi! David Park suggested I reach out...",
        },
    },
    {
        "label": "Cold outreach → should skip",
        "email": {
            "id": "msg_003",
            "thread_id": "thread_003",
            "from": "sales@crm-software.com",
            "to": "me@example.com",
            "subject": "Boost your sales pipeline by 3x",
            "body": (
                "Hi there, I wanted to reach out because I think our CRM could be a "
                "game-changer for your business. We help companies close deals faster. "
                "Can I book 15 minutes to show you a quick demo? No obligation at all."
            ),
            "date": "Thu, 5 Jun 2026",
            "snippet": "Hi there, I wanted to reach out...",
        },
    },
]


def print_state(state: dict):
    print(f"\n  intent:     {state.get('intent')}")
    print(f"  is_lead:    {state.get('is_lead')}")
    print(f"  confidence: {state.get('confidence')}")
    print(f"  reasoning:  {state.get('classification_reasoning')}")
    if state.get("draft"):
        print(f"\n  DRAFT REPLY:")
        print("  " + "\n  ".join(state["draft"].splitlines()))


def main():
    print("Seeding tone corpus...")
    for email in SENT_EMAILS:
        index_email(email)
    print(f"Indexed {len(SENT_EMAILS)} tone examples.\n")

    app = build_graph()  # no checkpointer for this test

    for test in TEST_EMAILS:
        label = test["label"]
        email = test["email"]

        print(DIVIDER)
        print(f"TEST: {label}")
        print(f"From: {email['from']} | Subject: {email['subject']}")
        print()

        final_state = app.invoke({"email": email})

        print_state(final_state)
        print()


if __name__ == "__main__":
    main()
