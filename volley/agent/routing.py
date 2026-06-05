from volley.agent.state import VolleyState
from volley.config import CONFIDENCE_THRESHOLD


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
    Decides what happens after human approval (used in Phase 7).
    - approved / edited → send_email
    - skipped → end
    """
    status = state.get("approval_status", "skipped")
    if status in ("approved", "edited"):
        return "send_email"
    return "__end__"
