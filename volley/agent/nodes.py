from volley.agent.state import VolleyState
from volley.agent.classifier import classify_email
from volley.agent.drafter import generate_draft
from volley.rag.store import retrieve_similar


def extract_fields(state: VolleyState) -> dict:
    """
    Pull sender/subject/body/thread_id out of the raw email dict
    so every subsequent node can access them directly from state.
    """
    email = state["email"]
    return {
        "sender": email.get("from", ""),
        "subject": email.get("subject", ""),
        "body": email.get("body", ""),
        "thread_id": email.get("thread_id", ""),
    }


def classify(state: VolleyState) -> dict:
    """Call the LLM classifier and write classification fields into state."""
    print(f"  [classify] From: {state['sender']} | Subject: {state['subject']}")

    result = classify_email(state["email"])

    print(f"  [classify] → intent={result.intent} | is_lead={result.is_lead} | confidence={result.confidence:.2f}")
    print(f"  [classify] → reasoning: {result.reasoning}")

    return {
        "intent": result.intent,
        "is_lead": result.is_lead,
        "confidence": result.confidence,
        "classification_reasoning": result.reasoning,
    }


def retrieve_tone(state: VolleyState) -> dict:
    """Query ChromaDB for the most similar past emails to use as tone context."""
    print(f"  [retrieve_tone] Searching tone corpus...")

    query = f"{state['subject']}\n\n{state['body']}"
    examples = retrieve_similar(query, n_results=5)

    print(f"  [retrieve_tone] → {len(examples)} example(s) retrieved")

    return {"tone_examples": examples}


def draft_reply(state: VolleyState) -> dict:
    """Generate a reply draft using the inbound email + retrieved tone examples."""
    print(f"  [draft_reply] Generating draft...")

    draft = generate_draft(
        email=state["email"],
        tone_examples=state.get("tone_examples") or [],
    )

    print(f"  [draft_reply] → Draft generated ({len(draft)} chars)")

    return {"draft": draft}


def skip(state: VolleyState) -> dict:
    """Terminal node for emails that are not leads — no action taken."""
    print(f"  [skip] Not a lead (intent={state.get('intent')}) — skipping.")
    return {}
