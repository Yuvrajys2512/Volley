from volley.agent.state import VolleyState


def route_after_classify(state: VolleyState) -> str:
    """
    Decides what happens after classification:
    - Not a lead → skip
    - Lead with high confidence → retrieve_tone (proceed automatically)
    - Lead with low confidence → retrieve_tone (still proceed; human approval
      in Phase 7 will act as the safety gate for uncertain cases)
    """
    if not state.get("is_lead"):
        return "skip"
    return "retrieve_tone"


def route_after_approval(state: VolleyState) -> str:
    """
    Decides what happens after human approval.
    - approved / edited → send_email (sends immediately, in-thread)
    - drafted           → create_draft (saved to Gmail Drafts, not sent)
    - skipped / unknown → end (fail safe: never auto-send)
    """
    status = state.get("approval_status", "skipped")
    if status in ("approved", "edited"):
        return "send_email"
    if status == "drafted":
        return "create_draft"
    return "__end__"
