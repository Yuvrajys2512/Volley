"""Multi-account worker loop: runs queued index_corpus jobs, then sweeps every
active connected account for new inbox mail via Gmail's history.list
watermark, running the drafts-only server graph on each new message.

This is the hosted equivalent of volley/gmail/watcher.py's single-user
polling loop — same dedup principle (mark-then-process so a crash mid-run
doesn't reprocess), but iterating accounts from Postgres instead of one
service/app pair, and using history.list instead of is:unread polling.
"""

import random
import time

from volley.agent.graph import build_server_graph
from volley.config import WORKER_POLL_INTERVAL_SECONDS
from volley.db.engine import session_scope
from volley.db.repo import Repo, SchedulerRepo
from volley.gmail import reader
from volley.gmail.auth import gmail_service_for_user
from volley.gmail.history import HistoryIdExpired, current_history_id, fetch_new_message_ids_since
from volley.worker.jobs import run_queued_index_corpus_jobs

MAX_INVOKE_ATTEMPTS = 3


class AuthRevokedError(Exception):
    pass


def main_loop():
    print(f"Volley worker started. Polling every ~{WORKER_POLL_INTERVAL_SECONDS}s.")
    while True:
        try:
            run_queued_index_corpus_jobs()
        except Exception as e:
            print(f"  [worker] index_corpus sweep error: {e}")

        try:
            poll_all_accounts()
        except Exception as e:
            print(f"  [worker] account poll sweep error: {e}")

        jitter = random.uniform(-15, 15)
        time.sleep(max(10, WORKER_POLL_INTERVAL_SECONDS + jitter))


def poll_all_accounts():
    with session_scope() as session:
        accounts = SchedulerRepo(session).list_active_accounts()
        account_infos = [(a.user_id, a.last_history_id) for a in accounts]

    for user_id, last_history_id in account_infos:
        try:
            process_account(user_id, last_history_id)
        except AuthRevokedError:
            with session_scope() as session:
                Repo(session, user_id).set_watch_status("auth_revoked")
            print(f"  [worker] user {user_id}: auth revoked, will not poll until reconnect.")
        except Exception as e:
            # One account's failure must never stop the sweep for everyone else.
            print(f"  [worker] user {user_id}: unexpected error, skipping this cycle: {e}")


def process_account(user_id, last_history_id: int | None):
    try:
        service = gmail_service_for_user(user_id)
    except Exception as e:
        if _looks_like_revoked_auth(e):
            raise AuthRevokedError(str(e)) from e
        raise

    if last_history_id is None:
        # No watermark yet (index_corpus job hasn't finished) — nothing to do.
        return

    try:
        message_ids, new_history_id = fetch_new_message_ids_since(service, last_history_id)
    except HistoryIdExpired:
        # Gmail only retains history ~7 days. If we fell behind that far,
        # re-anchor to "now" and accept the gap rather than erroring forever.
        new_history_id = current_history_id(service)
        with session_scope() as session:
            Repo(session, user_id).set_last_history_id(new_history_id)
        print(f"  [worker] user {user_id}: historyId expired, re-anchored to {new_history_id}.")
        return

    with session_scope() as session:
        repo = Repo(session, user_id)
        for message_id in message_ids:
            if repo.is_processed(message_id):
                continue
            _process_one_message(service, repo, user_id, message_id)
            # Marked regardless of success/failure below — a permanently
            # failing message must not retry forever, every cycle.
            repo.mark_processed(message_id)
        repo.set_last_history_id(new_history_id)


def _process_one_message(service, repo, user_id, message_id: str) -> None:
    try:
        email = reader.fetch_full_message(service, message_id)
    except Exception as e:
        print(f"  [worker] user {user_id}: could not fetch message {message_id}: {e}")
        return

    app = build_server_graph(gmail_service=service, repo=repo)

    last_error = None
    for attempt in range(1, MAX_INVOKE_ATTEMPTS + 1):
        try:
            app.invoke({"email": email, "user_id": str(user_id)})
            return
        except Exception as e:
            last_error = e
            if attempt < MAX_INVOKE_ATTEMPTS:
                time.sleep(2**attempt)

    print(
        f"  [worker] user {user_id}: message {message_id} failed after "
        f"{MAX_INVOKE_ATTEMPTS} attempts: {last_error}"
    )


def _looks_like_revoked_auth(error: Exception) -> bool:
    return "invalid_grant" in str(error).lower()
