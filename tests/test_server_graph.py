"""The drafts-only server graph: no human_approval interrupt, no send_email
path — a lead always ends at create_draft, everything else ends at skip.
Gmail/LLM calls are faked so this runs without network or a checkpointer.
"""

from tests.test_sender import FakeService
from volley.agent import nodes
from volley.agent.classifier import EmailClassification
from volley.agent.graph import build_server_graph

LEAD_EMAIL = {
    "id": "msg-1",
    "from": "lead@example.com",
    "subject": "Rates for a 3-month engagement?",
    "body": "Hi, saw your work — what are your rates?",
    "thread_id": "thread-1",
}

NON_LEAD_EMAIL = {
    "id": "msg-2",
    "from": "newsletter@example.com",
    "subject": "Weekly digest",
    "body": "Here's what's new this week.",
    "thread_id": "thread-2",
}


class FakeRepo:
    def __init__(self):
        self.logged_drafts = []

    def retrieve_similar(self, query_embedding, n_results=5):
        return []

    def log_draft(self, message_id, gmail_draft_id, intent, confidence):
        self.logged_drafts.append(
            {"message_id": message_id, "gmail_draft_id": gmail_draft_id, "intent": intent}
        )


def _patch_llms(monkeypatch, *, is_lead: bool):
    monkeypatch.setattr(
        nodes,
        "classify_email",
        lambda email: EmailClassification(
            intent="inbound_lead" if is_lead else "unrelated",
            is_lead=is_lead,
            confidence=0.9,
            reasoning="test",
        ),
    )
    monkeypatch.setattr(nodes, "generate_draft", lambda email, tone_examples: "Sure, my rate is $X.")


def test_lead_reaches_create_draft_and_logs_it(monkeypatch):
    _patch_llms(monkeypatch, is_lead=True)

    service = FakeService()
    repo = FakeRepo()
    app = build_server_graph(gmail_service=service, repo=repo)

    result = app.invoke({"email": LEAD_EMAIL, "user_id": "u-1"})

    assert result["is_lead"] is True
    assert "drafts.create" in service.recorder
    assert len(repo.logged_drafts) == 1
    assert repo.logged_drafts[0]["message_id"] == "msg-1"


def test_non_lead_reaches_skip_without_touching_gmail(monkeypatch):
    _patch_llms(monkeypatch, is_lead=False)

    service = FakeService()
    repo = FakeRepo()
    app = build_server_graph(gmail_service=service, repo=repo)

    result = app.invoke({"email": NON_LEAD_EMAIL, "user_id": "u-1"})

    assert result["is_lead"] is False
    assert "drafts.create" not in service.recorder
    assert repo.logged_drafts == []


def test_graph_has_no_human_approval_or_send_email_nodes():
    app = build_server_graph()
    node_names = set(app.get_graph().nodes.keys())
    assert "human_approval" not in node_names
    assert "send_email" not in node_names
    assert "create_draft" in node_names
