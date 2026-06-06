"""De-duplication store — ensures the watcher never reprocesses an email,
even across restarts. Backed by SQLite, so we point it at a temp DB.
"""

from volley.gmail import watcher


def test_unseen_then_seen(tmp_path, monkeypatch):
    db = tmp_path / "seen.db"
    monkeypatch.setattr(watcher, "SEEN_DB", str(db))

    watcher._init_seen_db()

    assert watcher._is_seen("msg-1") is False
    watcher._mark_seen("msg-1")
    assert watcher._is_seen("msg-1") is True


def test_mark_seen_is_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "seen.db"
    monkeypatch.setattr(watcher, "SEEN_DB", str(db))
    watcher._init_seen_db()

    watcher._mark_seen("msg-1")
    watcher._mark_seen("msg-1")  # INSERT OR IGNORE — must not raise on the PK clash
    assert watcher._is_seen("msg-1") is True


def test_persists_across_reconnect(tmp_path, monkeypatch):
    # Simulate a restart: same DB file, fresh connections each call.
    db = tmp_path / "seen.db"
    monkeypatch.setattr(watcher, "SEEN_DB", str(db))
    watcher._init_seen_db()
    watcher._mark_seen("survivor")

    # _is_seen opens its own connection, so this models a process restart.
    assert watcher._is_seen("survivor") is True
    assert watcher._is_seen("never-seen") is False
