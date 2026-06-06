"""Routing logic — the conditional edges that steer the LangGraph agent.

These are pure functions over the state dict, so they need no LLM or network.
"""

from volley.agent.routing import route_after_approval, route_after_classify


class TestRouteAfterClassify:
    def test_non_lead_is_skipped(self):
        assert route_after_classify({"is_lead": False}) == "skip"

    def test_missing_is_lead_is_skipped(self):
        # Defensive: a malformed state with no is_lead must not fall through to drafting.
        assert route_after_classify({}) == "skip"

    def test_lead_proceeds_to_tone_retrieval(self):
        assert route_after_classify({"is_lead": True}) == "retrieve_tone"


class TestRouteAfterApproval:
    def test_approved_sends(self):
        assert route_after_approval({"approval_status": "approved"}) == "send_email"

    def test_edited_sends(self):
        assert route_after_approval({"approval_status": "edited"}) == "send_email"

    def test_skipped_ends(self):
        assert route_after_approval({"approval_status": "skipped"}) == "__end__"

    def test_missing_status_defaults_to_end(self):
        # Fail safe: an unknown/absent decision must never auto-send.
        assert route_after_approval({}) == "__end__"
