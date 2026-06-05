"""
Phase 5 test script — draft generation with tone matching.

Run with:
    uv run python scripts/test_drafter.py

What it does:
  1. Indexes 3 sample "sent" emails as your tone corpus
  2. Takes 2 inbound lead emails
  3. Retrieves the closest tone examples for each
  4. Generates a draft reply and prints it

No Gmail connection needed — all sample data is hardcoded.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from volley.rag.store import index_email, retrieve_similar
from volley.agent.drafter import generate_draft

# ── Sample tone corpus (pretend these are YOUR past sent emails) ───────────────

SENT_EMAILS = [
    {
        "id": "tone_001",
        "subject": "Re: Consulting inquiry",
        "body": (
            "Hey Sarah, thanks for reaching out!\n\n"
            "Love what you're building at Acme. Happy to explore whether there's a fit.\n\n"
            "My availability opens up mid-month — would a 30-min call on the 15th or 16th work? "
            "Feel free to grab a slot: [calendly link]\n\n"
            "Talk soon,\nAlex"
        ),
        "to": "sarah@acme.com",
        "date": "Mon, 1 Jan 2024",
    },
    {
        "id": "tone_002",
        "subject": "Re: Working together",
        "body": (
            "Hi Tom,\n\n"
            "Good to hear from you. Sounds like an interesting project — "
            "I'd want to understand the scope a bit better before committing.\n\n"
            "Can you send over a brief with the key goals and timeline? "
            "That'll help me figure out whether I can add real value here.\n\n"
            "Best,\nAlex"
        ),
        "to": "tom@ventures.io",
        "date": "Tue, 2 Jan 2024",
    },
    {
        "id": "tone_003",
        "subject": "Re: Referral from Mike",
        "body": (
            "Hey Priya,\n\n"
            "Mike's the best — always connecting the right people. Nice to meet you!\n\n"
            "Retention is definitely an area I've spent a lot of time in. "
            "Tell me more about where you're at — what's your current churn rate "
            "and what have you already tried?\n\n"
            "Alex"
        ),
        "to": "priya@example.com",
        "date": "Wed, 3 Jan 2024",
    },
]

# ── Inbound emails to draft replies for ───────────────────────────────────────

INBOUND_EMAILS = [
    {
        "from": "james.wu@b2bstartup.com",
        "subject": "Looking for a growth consultant",
        "body": (
            "Hi there,\n\n"
            "I found you through a mutual connection and your work on B2B growth really stood out. "
            "We're a 2-year-old SaaS company doing about $500k ARR and trying to get to $2M. "
            "We're struggling with pipeline — lots of interest but deals are stalling mid-funnel.\n\n"
            "Would you be open to a conversation about potentially working together? "
            "We're ready to move quickly if there's a fit.\n\n"
            "Thanks,\nJames"
        ),
    },
    {
        "from": "nina.patel@ecomco.co",
        "subject": "Partnership idea — podcast + newsletter swap",
        "body": (
            "Hello!\n\n"
            "I host a podcast for e-commerce founders (8k listeners/episode) and run a "
            "companion newsletter (15k subscribers). I've been a fan of your content for a while "
            "and think our audiences would love an intro to each other.\n\n"
            "Would you be open to a guest swap? I'd interview you on the pod, "
            "and you'd feature us in your newsletter. Happy to chat more if interested!\n\n"
            "Nina"
        ),
    },
]

DIVIDER = "─" * 65


def main():
    print("Indexing tone corpus...")
    for email in SENT_EMAILS:
        index_email(email)
    print(f"Indexed {len(SENT_EMAILS)} tone examples.\n")

    for inbound in INBOUND_EMAILS:
        print("=" * 65)
        print(f"INBOUND EMAIL")
        print(f"From:    {inbound['from']}")
        print(f"Subject: {inbound['subject']}")
        print(f"\n{inbound['body']}")
        print(DIVIDER)

        query = f"{inbound['subject']}\n\n{inbound['body']}"
        tone_examples = retrieve_similar(query, n_results=2)

        print(f"Retrieved {len(tone_examples)} tone example(s).")
        print("Generating draft...\n")

        draft = generate_draft(inbound, tone_examples)

        print("DRAFT REPLY:")
        print(DIVIDER)
        print(draft)
        print()


if __name__ == "__main__":
    main()
