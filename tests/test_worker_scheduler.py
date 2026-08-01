"""Worker scheduler: dedup, watermark advance, and auth-revoked handling.
Gmail/graph calls are mocked; Postgres rows are real (dedup/watermark state
must actually persist) — requires the local dev database."""

from tests.conftest import requires_db
from volley.db.engine import session_scope
from volley.db.models import User
from volley.db.repo import Repo
from volley.gmail.history import HistoryIdExpired
from volley.worker import scheduler


def _make_connected_user(email: str, last_history_id: int | None = 100):
    with session_scope() as session:
        user = User(email=email)
        session.add(user)
        session.flush()
        repo = Repo(session, user.id)
        repo.upsert_gmail_account(refresh_token_enc=b"enc", granted_scopes=["gmail.readonly"])
        if last_history_id is not None:
            repo.set_last_history_id(last_history_id)
        return user.id


def _cleanup(user_id):
    with session_scope() as session:
        Repo(session, user_id).delete_all_user_data()


FAKE_EMAIL = {
    "id": "msg-1",
    "thread_id": "t-1",
    "from": "lead@example.com",
    "subject": "Rates?",
    "body": "Hi, what are your rates?",
    "date": "",
}


class _RecordingApp:
    def __init__(self, fail_times=0):
        self.calls = []
        self._fail_times = fail_times

    def invoke(self, payload):
        self.calls.append(payload)
        if len(self.calls) <= self._fail_times:
            raise RuntimeError("simulated transient failure")
        return {"is_lead": True}


@requires_db
def test_new_message_is_processed_and_marked(monkeypatch):
    user_id = _make_connected_user("worker-a@example.com")
    try:
        monkeypatch.setattr(scheduler, "gmail_service_for_user", lambda uid: object())
        monkeypatch.setattr(
            scheduler, "fetch_new_message_ids_since", lambda service, since: (["msg-1"], 200)
        )
        monkeypatch.setattr(scheduler.reader, "fetch_full_message", lambda service, mid: FAKE_EMAIL)

        app = _RecordingApp()
        monkeypatch.setattr(scheduler, "build_server_graph", lambda **kw: app)

        scheduler.process_account(user_id, last_history_id=100)

        assert len(app.calls) == 1
        assert app.calls[0]["email"]["id"] == "msg-1"

        with session_scope() as session:
            repo = Repo(session, user_id)
            assert repo.is_processed("msg-1") is True
            assert repo.get_gmail_account().last_history_id == 200
    finally:
        _cleanup(user_id)


@requires_db
def test_already_processed_message_is_skipped(monkeypatch):
    user_id = _make_connected_user("worker-b@example.com")
    try:
        with session_scope() as session:
            Repo(session, user_id).mark_processed("msg-1")

        monkeypatch.setattr(scheduler, "gmail_service_for_user", lambda uid: object())
        monkeypatch.setattr(
            scheduler, "fetch_new_message_ids_since", lambda service, since: (["msg-1"], 200)
        )
        app = _RecordingApp()
        monkeypatch.setattr(scheduler, "build_server_graph", lambda **kw: app)

        scheduler.process_account(user_id, last_history_id=100)

        assert app.calls == []
    finally:
        _cleanup(user_id)


@requires_db
def test_history_id_expired_reanchors_watermark(monkeypatch):
    user_id = _make_connected_user("worker-c@example.com")
    try:
        monkeypatch.setattr(scheduler, "gmail_service_for_user", lambda uid: object())

        def _raise_expired(service, since):
            raise HistoryIdExpired("too old")

        monkeypatch.setattr(scheduler, "fetch_new_message_ids_since", _raise_expired)
        monkeypatch.setattr(scheduler, "current_history_id", lambda service: 999)

        scheduler.process_account(user_id, last_history_id=1)

        with session_scope() as session:
            assert Repo(session, user_id).get_gmail_account().last_history_id == 999
    finally:
        _cleanup(user_id)


@requires_db
def test_invalid_grant_marks_account_auth_revoked(monkeypatch):
    user_id = _make_connected_user("worker-d@example.com")
    try:
        def _raise_invalid_grant(uid):
            raise RuntimeError("invalid_grant: Bad Request")

        monkeypatch.setattr(scheduler, "gmail_service_for_user", _raise_invalid_grant)

        with session_scope() as session:
            accounts = scheduler.SchedulerRepo(session).list_active_accounts()
            assert any(a.user_id == user_id for a in accounts)

        try:
            scheduler.process_account(user_id, last_history_id=100)
        except scheduler.AuthRevokedError:
            with session_scope() as session:
                Repo(session, user_id).set_watch_status("auth_revoked")

        with session_scope() as session:
            assert Repo(session, user_id).get_gmail_account().watch_status == "auth_revoked"
    finally:
        _cleanup(user_id)


@requires_db
def test_poll_all_accounts_isolates_one_account_failure(monkeypatch):
    good_id = _make_connected_user("worker-e@example.com")
    bad_id = _make_connected_user("worker-f@example.com")
    try:
        calls = []

        def fake_process_account(user_id, last_history_id):
            calls.append(user_id)
            if user_id == bad_id:
                raise RuntimeError("boom")

        monkeypatch.setattr(scheduler, "process_account", fake_process_account)

        scheduler.poll_all_accounts()

        # Both accounts were attempted; the bad one's failure didn't stop the sweep.
        assert good_id in calls
        assert bad_id in calls
    finally:
        _cleanup(good_id)
        _cleanup(bad_id)


def test_process_one_message_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(scheduler.time, "sleep", lambda *_: None)
    monkeypatch.setattr(scheduler.reader, "fetch_full_message", lambda service, mid: FAKE_EMAIL)

    app = _RecordingApp(fail_times=2)
    monkeypatch.setattr(scheduler, "build_server_graph", lambda **kw: app)

    scheduler._process_one_message(service=object(), repo=object(), user_id="u-x", message_id="msg-1")

    assert len(app.calls) == 3  # failed twice, succeeded on the 3rd


def test_process_one_message_gives_up_after_max_attempts_without_raising(monkeypatch):
    monkeypatch.setattr(scheduler.time, "sleep", lambda *_: None)
    monkeypatch.setattr(scheduler.reader, "fetch_full_message", lambda service, mid: FAKE_EMAIL)

    app = _RecordingApp(fail_times=99)  # always fails
    monkeypatch.setattr(scheduler, "build_server_graph", lambda **kw: app)

    # A permanently-failing message must not raise out of _process_one_message —
    # process_account still needs to mark it processed so it isn't retried forever.
    scheduler._process_one_message(service=object(), repo=object(), user_id="u-x", message_id="msg-1")

    assert len(app.calls) == scheduler.MAX_INVOKE_ATTEMPTS
