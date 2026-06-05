from langgraph.types import interrupt

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


def human_approval(state: VolleyState) -> dict:
    """
    Pause the graph and wait for the user to approve, edit, or skip the draft.
    LangGraph persists the full state to the checkpointer at this point.
    The graph resumes only when Command(resume=...) is passed by the runner.
    """
    decision = interrupt({
        "draft": state["draft"],
        "sender": state["sender"],
        "subject": state["subject"],
        "body": state["body"],
    })

    status = decision.get("status", "skipped")          # "approved" | "edited" | "skipped"
    edited_text = decision.get("edited_text")

    final_reply = edited_text if status == "edited" else state["draft"]

    return {
        "approval_status": status,
        "final_reply": final_reply if status != "skipped" else None,
    }


def send_email_node(state: VolleyState) -> dict:
    """Send the approved/edited reply via the Gmail API, then index it into the corpus."""
    from volley.gmail.auth import get_gmail_service
    from volley.gmail.sender import send_reply
    from volley.rag.corpus import index_single_email

    print(f"  [send_email] Sending reply to {state['sender']}...")

    service = get_gmail_service()
    sent = send_reply(
        service=service,
        to=state["sender"],
        subject=state["subject"],
        body=state["final_reply"],
        thread_id=state["thread_id"],
    )

    print(f"  [send_email] → Sent.")

    # Auto-index the reply so future drafts can learn from it
    sent_email_record = {
        "id": sent.get("id", ""),
        "subject": f"Re: {state['subject']}",
        "body": state["final_reply"],
        "to": state["sender"],
        "date": "",
    }
    index_single_email(sent_email_record)
    print(f"  [send_email] → Indexed into tone corpus.")

    return {}


def skip(state: VolleyState) -> dict:
    """Terminal node for emails that are not leads — no action taken."""
    print(f"  [skip] Not a lead (intent={state.get('intent')}) — skipping.")
    return {}
