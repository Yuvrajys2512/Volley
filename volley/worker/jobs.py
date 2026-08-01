"""Job runner — currently just `index_corpus`, the one-time tone-corpus build
that runs right after a user connects their Gmail."""

from volley.db.engine import session_scope
from volley.db.repo import Repo, SchedulerRepo
from volley.gmail.auth import gmail_service_for_user
from volley.gmail.history import current_history_id
from volley.rag.corpus import build_corpus

INDEX_CORPUS_MAX_FETCH = 500


def run_queued_index_corpus_jobs(limit: int = 5) -> None:
    with session_scope() as session:
        jobs = SchedulerRepo(session).claim_next_jobs("index_corpus", limit=limit)
        job_ids = [(job.id, job.user_id, job.attempts) for job in jobs]

    for job_id, user_id, attempts in job_ids:
        try:
            _run_index_corpus_job(job_id, user_id)
        except Exception as e:
            print(f"  [worker] index_corpus job {job_id} (user {user_id}) failed: {e}")
            with session_scope() as session:
                SchedulerRepo(session).mark_job_failed(job_id, retry=attempts < 3)


def _run_index_corpus_job(job_id: int, user_id) -> None:
    service = gmail_service_for_user(user_id)
    with session_scope() as session:
        repo = Repo(session, user_id)
        build_corpus(service, max_fetch=INDEX_CORPUS_MAX_FETCH, user_id=user_id, repo=repo)
        # Anchor steady-state polling to start right after the corpus build
        # completes — mail arriving before this point was already seen during
        # the (one-time) corpus build, not treated as a lead.
        repo.set_last_history_id(current_history_id(service))
    with session_scope() as session:
        SchedulerRepo(session).mark_job_done(job_id)
