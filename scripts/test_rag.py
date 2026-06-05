"""
Phase 3 test script — RAG tone corpus.

Run with:
    uv run python scripts/test_rag.py

What it does:
  1. Indexes a few hardcoded sample emails (no Gmail needed)
  2. Runs 3 retrieval queries and prints the closest matches
  3. Confirms cosine similarity is working correctly

This lets you verify the embedding + store pipeline before
connecting it to real Gmail data.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from volley.rag.store import index_email, retrieve_similar, corpus_size

SAMPLE_EMAILS = [
    {
        "id": "sample_001",
        "subject": "Interested in your consulting services",
        "body": (
            "Hi, I came across your work and I think you'd be a great fit for a project "
            "we're kicking off next quarter. We're a Series B startup looking for a growth "
            "consultant to help us scale from 10k to 100k users. Would love to hop on a call "
            "to discuss scope and rates. Let me know your availability. Best, Sarah"
        ),
        "to": "sarah@acme.com",
        "date": "Mon, 1 Jan 2024",
    },
    {
        "id": "sample_002",
        "subject": "Following up on our proposal",
        "body": (
            "Hey, just circling back on the proposal I sent last week. We're keen to move "
            "forward and the team is excited. Happy to jump on a quick call if you have "
            "questions. Cheers, Tom"
        ),
        "to": "tom@startup.io",
        "date": "Tue, 2 Jan 2024",
    },
    {
        "id": "sample_003",
        "subject": "Partnership opportunity — co-marketing",
        "body": (
            "Hello, I'm reaching out because I think there's a strong alignment between "
            "our audiences. We'd love to explore a co-marketing collaboration — guest posts, "
            "joint webinars, or a newsletter swap. Our list is ~25k engaged subscribers "
            "in the SaaS space. Would this be of interest? Regards, Priya"
        ),
        "to": "priya@company.com",
        "date": "Wed, 3 Jan 2024",
    },
    {
        "id": "sample_004",
        "subject": "Quick question about your availability",
        "body": (
            "Hi there! I was referred to you by Mike Chen. I run a small e-commerce brand "
            "and we're struggling with our email marketing strategy. Mike said you're the "
            "person to talk to. Are you taking on new clients? Happy to share more context "
            "over a 20-min call. Thanks!"
        ),
        "to": "referred@ecom.co",
        "date": "Thu, 4 Jan 2024",
    },
]

DIVIDER = "─" * 60

QUERIES = [
    "We're a startup looking to hire a consultant for growth strategy",
    "Following up on our previous conversation about working together",
    "Interested in a co-marketing partnership with your newsletter",
]


def main():
    print("Indexing sample emails into ChromaDB...")
    for email in SAMPLE_EMAILS:
        index_email(email)
        print(f"  Indexed: {email['subject']}")

    print(f"\nCorpus size: {corpus_size()} emails\n")

    for query in QUERIES:
        print("=" * 60)
        print(f"QUERY: \"{query}\"")
        print("=" * 60)

        results = retrieve_similar(query, n_results=2)
        for i, r in enumerate(results, 1):
            print(f"\n[Match {i}] Subject: {r['metadata']['subject']}")
            print(f"{r['body'][:300]}")
        print()


if __name__ == "__main__":
    main()
