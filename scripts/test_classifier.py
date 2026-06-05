"""
Phase 4 test script — LLM email classification.

Run with:
    uv run python scripts/test_classifier.py

Classifies 6 handcrafted test emails covering every intent category
and prints the result as a table. No Gmail connection needed.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from volley.agent.classifier import classify_email, needs_human_review

TEST_EMAILS = [
    {
        "label": "Inbound lead (clear)",
        "from": "sarah.johnson@acme.com",
        "subject": "Interested in your consulting services",
        "body": (
            "Hi, I came across your profile on LinkedIn and I'm really impressed by your work. "
            "We're a Series A startup and we're looking for a growth consultant to help us "
            "go from 5k to 50k users over the next 6 months. Could you share your rates and "
            "availability for a discovery call? We'd love to move quickly on this."
        ),
    },
    {
        "label": "Follow-up",
        "from": "tom.baker@ventures.io",
        "subject": "Re: Our proposal from last week",
        "body": (
            "Hey, just wanted to circle back on the proposal I sent over on Tuesday. "
            "The team is excited and we're ready to move forward. Let me know if you "
            "have any questions or want to hop on a quick call to finalize things."
        ),
    },
    {
        "label": "Referral",
        "from": "priya.nair@example.com",
        "subject": "Intro from Mike Chen",
        "body": (
            "Hi! Mike Chen suggested I reach out to you. I run a small D2C brand and "
            "we're struggling to figure out our retention strategy. Mike said you're "
            "the best person for this. Are you taking on new clients? Happy to share "
            "more context on a short call."
        ),
    },
    {
        "label": "Partnership",
        "from": "alex@contentco.com",
        "subject": "Co-marketing opportunity — 30k newsletter",
        "body": (
            "Hello! I run a newsletter with 30k subscribers in the SaaS and productivity "
            "space. I think there's a great fit between our audiences. Would you be open "
            "to a newsletter swap or a joint webinar? Happy to share our media kit."
        ),
    },
    {
        "label": "Cold outreach (should NOT be a lead)",
        "from": "sales@crm-tool.com",
        "subject": "Boost your sales pipeline by 3x",
        "body": (
            "Hi there, I wanted to reach out because I think our CRM platform could be "
            "a game-changer for your business. We help companies like yours close deals "
            "faster. Can I book 15 minutes to show you a quick demo? No obligation."
        ),
    },
    {
        "label": "Unrelated (newsletter)",
        "from": "noreply@substack.com",
        "subject": "Your weekly digest is ready",
        "body": (
            "This week in tech: AI regulation, the latest on OpenAI, and why Rust is "
            "eating the world. Click below to read the full issue."
        ),
    },
]

DIVIDER = "─" * 70


def main():
    print(f"\n{'=' * 70}")
    print("VOLLEY — Phase 4: Email Classification Test")
    print(f"{'=' * 70}\n")

    for email in TEST_EMAILS:
        label = email.pop("label")
        print(f"{DIVIDER}")
        print(f"TEST:    {label}")
        print(f"From:    {email['from']}")
        print(f"Subject: {email['subject']}")
        print(f"Body:    {email['body'][:100]}...")
        print()

        result = classify_email(email)

        lead_flag = "YES" if result.is_lead else "no"
        review_flag = " ← LOW CONFIDENCE, needs human review" if needs_human_review(result) else ""

        print(f"  intent:     {result.intent}")
        print(f"  is_lead:    {lead_flag}")
        print(f"  confidence: {result.confidence:.2f}{review_flag}")
        print(f"  reasoning:  {result.reasoning}")
        print()

    print(DIVIDER)
    print("Done.")


if __name__ == "__main__":
    main()
