"""Tenant isolation is the load-bearing safety guarantee of the phase-1
multi-tenant server: Repo(user_id) must never let one user's data leak into
another user's queries, mutations, or deletes.
"""

from datetime import UTC, datetime

from tests.conftest import requires_db
from volley.db.models import User
from volley.db.repo import Repo

EMBEDDING = [0.1] * 384


def _make_user(session, email: str) -> User:
    user = User(email=email)
    session.add(user)
    session.flush()
    return user


@requires_db
def test_corpus_entries_are_isolated(db_session):
    user_a = _make_user(db_session, "a@example.com")
    user_b = _make_user(db_session, "b@example.com")
    repo_a = Repo(db_session, user_a.id)
    repo_b = Repo(db_session, user_b.id)

    repo_a.upsert_corpus_entry(
        "msg-a", body="hello from A", subject="s", sent_to="x@y.com",
        sent_at=datetime.now(UTC), embedding=EMBEDDING,
    )
    repo_b.upsert_corpus_entry(
        "msg-b", body="hello from B", subject="s", sent_to="x@y.com",
        sent_at=datetime.now(UTC), embedding=EMBEDDING,
    )
    db_session.flush()

    assert repo_a.corpus_size() == 1
    assert repo_b.corpus_size() == 1

    results_a = repo_a.retrieve_similar(EMBEDDING, n_results=10)
    assert [r["message_id"] for r in results_a] == ["msg-a"]

    results_b = repo_b.retrieve_similar(EMBEDDING, n_results=10)
    assert [r["message_id"] for r in results_b] == ["msg-b"]


@requires_db
def test_processed_messages_are_isolated(db_session):
    user_a = _make_user(db_session, "a2@example.com")
    user_b = _make_user(db_session, "b2@example.com")
    repo_a = Repo(db_session, user_a.id)
    repo_b = Repo(db_session, user_b.id)

    repo_a.mark_processed("shared-message-id")
    db_session.flush()

    assert repo_a.is_processed("shared-message-id") is True
    assert repo_b.is_processed("shared-message-id") is False


@requires_db
def test_draft_log_is_isolated(db_session):
    user_a = _make_user(db_session, "a3@example.com")
    user_b = _make_user(db_session, "b3@example.com")
    repo_a = Repo(db_session, user_a.id)
    repo_b = Repo(db_session, user_b.id)

    repo_a.log_draft("msg-1", "draft-1", intent="lead", confidence=0.9)
    db_session.flush()

    assert repo_a.draft_count() == 1
    assert repo_b.draft_count() == 0


@requires_db
def test_delete_all_user_data_does_not_affect_other_users(db_session):
    user_a = _make_user(db_session, "a4@example.com")
    user_b = _make_user(db_session, "b4@example.com")
    repo_a = Repo(db_session, user_a.id)
    repo_b = Repo(db_session, user_b.id)

    repo_a.upsert_corpus_entry(
        "msg-a", body="A", subject="", sent_to="", sent_at=None, embedding=EMBEDDING
    )
    repo_a.mark_processed("msg-a")
    repo_a.log_draft("msg-a", "draft-a", intent="lead", confidence=0.9)

    repo_b.upsert_corpus_entry(
        "msg-b", body="B", subject="", sent_to="", sent_at=None, embedding=EMBEDDING
    )
    repo_b.mark_processed("msg-b")
    repo_b.log_draft("msg-b", "draft-b", intent="lead", confidence=0.9)
    db_session.flush()

    repo_a.delete_all_user_data()
    db_session.flush()

    assert repo_a.get_user() is None
    assert repo_b.get_user() is not None
    assert repo_b.corpus_size() == 1
    assert repo_b.is_processed("msg-b") is True
    assert repo_b.draft_count() == 1


@requires_db
def test_gmail_account_is_isolated(db_session):
    user_a = _make_user(db_session, "a5@example.com")
    user_b = _make_user(db_session, "b5@example.com")
    repo_a = Repo(db_session, user_a.id)
    repo_b = Repo(db_session, user_b.id)

    repo_a.upsert_gmail_account(b"encrypted-token-a", ["gmail.readonly", "gmail.compose"])
    db_session.flush()

    assert repo_a.get_gmail_account() is not None
    assert repo_b.get_gmail_account() is None
