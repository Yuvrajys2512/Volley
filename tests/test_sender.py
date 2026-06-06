"""Gmail sender — reply sending and Drafts-folder creation.

We drive the Gmail API with a fake client that records what it was called
with, so we test message construction and threading without any network.
"""

import base64
from email import message_from_bytes

from googleapiclient.errors import HttpError

from volley.gmail.sender import create_draft, send_reply


class _FakeExecutable:
    def __init__(self, recorder, key, raise_exc=None):
        self._recorder = recorder
        self._key = key
        self._raise = raise_exc

    def execute(self):
        if self._raise is not None:
            raise self._raise
        return {"id": "fake-id", "captured": self._recorder[self._key]}


class _FakeDrafts:
    def __init__(self, recorder, raise_on_thread=False):
        self._recorder = recorder
        self._raise_on_thread = raise_on_thread

    def create(self, userId, body):
        self._recorder["drafts.create"] = {"userId": userId, "body": body}
        has_thread = "threadId" in body.get("message", {})
        if self._raise_on_thread and has_thread:
            resp = type("R", (), {"status": 400, "reason": "Bad Request"})()
            content = b'{"error": {"message": "Invalid thread_id value."}}'
            err = HttpError(resp=resp, content=content)
            return _FakeExecutable(self._recorder, "drafts.create", raise_exc=err)
        return _FakeExecutable(self._recorder, "drafts.create")


class _FakeMessages:
    def __init__(self, recorder):
        self._recorder = recorder

    def send(self, userId, body):
        self._recorder["messages.send"] = {"userId": userId, "body": body}
        return _FakeExecutable(self._recorder, "messages.send")


class _FakeUsers:
    def __init__(self, recorder, raise_on_thread=False):
        self._drafts = _FakeDrafts(recorder, raise_on_thread)
        self._messages = _FakeMessages(recorder)

    def drafts(self):
        return self._drafts

    def messages(self):
        return self._messages


class FakeService:
    def __init__(self, raise_on_thread=False):
        self.recorder = {}
        self._users = _FakeUsers(self.recorder, raise_on_thread)

    def users(self):
        return self._users


def _parse(body: dict):
    """Decode the base64 raw MIME back into an email.Message (headers are
    case-insensitive; get_payload(decode=True) reverses base64 transfer-encoding)."""
    raw = body["message"]["raw"] if "message" in body else body["raw"]
    return message_from_bytes(base64.urlsafe_b64decode(raw))


class TestCreateDraft:
    def test_saves_draft_in_thread(self):
        svc = FakeService()
        create_draft(svc, to="lead@x.com", subject="Project", body="Hello", thread_id="t-123")

        call = svc.recorder["drafts.create"]
        assert call["userId"] == "me"
        assert call["body"]["message"]["threadId"] == "t-123"

        msg = _parse(call["body"])
        assert msg["to"] == "lead@x.com"
        assert msg.get_payload(decode=True).decode("utf-8") == "Hello"

    def test_adds_re_prefix_when_missing(self):
        svc = FakeService()
        create_draft(svc, to="a@x.com", subject="Project", body="b", thread_id="t")
        assert _parse(svc.recorder["drafts.create"]["body"])["subject"] == "Re: Project"

    def test_does_not_double_prefix_re(self):
        svc = FakeService()
        create_draft(svc, to="a@x.com", subject="Re: Project", body="b", thread_id="t")
        assert _parse(svc.recorder["drafts.create"]["body"])["subject"] == "Re: Project"

    def test_falls_back_to_standalone_on_bad_thread(self):
        # Invalid thread should not raise — it retries without threadId.
        svc = FakeService(raise_on_thread=True)
        create_draft(svc, to="a@x.com", subject="Project", body="b", thread_id="bad")
        # Final recorded call is the standalone retry (no threadId).
        assert "threadId" not in svc.recorder["drafts.create"]["body"]["message"]


class TestSendReply:
    def test_sends_in_thread(self):
        svc = FakeService()
        send_reply(svc, to="a@x.com", subject="Hi", body="body", thread_id="t-9")
        call = svc.recorder["messages.send"]
        assert call["body"]["threadId"] == "t-9"
        assert _parse(call["body"])["subject"] == "Re: Hi"
