import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from volley.db.models import CorpusEntry, DraftLog, GmailAccount, Job, ProcessedMessage, User


def _now() -> datetime:
    return datetime.now(UTC)


def get_or_create_user_by_email(session: Session, email: str) -> User:
    """The one legitimately unscoped user lookup: OAuth callback bootstrap,
    before a user_id even exists to construct a Repo with."""
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email)
        session.add(user)
        session.flush()
    return user


class Repo:
    """All data access is scoped to a single user_id, set at construction.

    No method accepts a foreign user_id — that is the tenant-isolation
    invariant this class exists to enforce. Cross-tenant needs (listing all
    accounts, claiming jobs) belong in SchedulerRepo instead.
    """

    def __init__(self, session: Session, user_id: uuid.UUID | str):
        self.session = session
        self.user_id = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    # -- users / gmail_accounts -------------------------------------------------

    def get_user(self) -> User | None:
        return self.session.get(User, self.user_id)

    def set_user_status(self, status: str) -> None:
        user = self.get_user()
        if user is not None:
            user.status = status

    def get_gmail_account(self) -> GmailAccount | None:
        return self.session.get(GmailAccount, self.user_id)

    def upsert_gmail_account(self, refresh_token_enc: bytes, granted_scopes: list[str]) -> GmailAccount:
        account = self.get_gmail_account()
        if account is None:
            account = GmailAccount(
                user_id=self.user_id,
                refresh_token_enc=refresh_token_enc,
                granted_scopes=granted_scopes,
            )
            self.session.add(account)
        else:
            account.refresh_token_enc = refresh_token_enc
            account.granted_scopes = granted_scopes
            account.watch_status = "ok"
        return account

    def set_last_history_id(self, history_id: int) -> None:
        account = self.get_gmail_account()
        if account is not None:
            account.last_history_id = history_id

    def set_watch_status(self, status: str) -> None:
        account = self.get_gmail_account()
        if account is not None:
            account.watch_status = status

    # -- dedup --------------------------------------------------------------

    def is_processed(self, message_id: str) -> bool:
        stmt = select(ProcessedMessage).where(
            ProcessedMessage.user_id == self.user_id,
            ProcessedMessage.message_id == message_id,
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def mark_processed(self, message_id: str) -> None:
        stmt = (
            insert(ProcessedMessage)
            .values(user_id=self.user_id, message_id=message_id, processed_at=_now())
            .on_conflict_do_nothing(index_elements=["user_id", "message_id"])
        )
        self.session.execute(stmt)

    # -- corpus (pgvector) ----------------------------------------------------

    def upsert_corpus_entry(
        self,
        message_id: str,
        body: str,
        subject: str,
        sent_to: str,
        sent_at: datetime | None,
        embedding: list[float],
    ) -> None:
        stmt = insert(CorpusEntry).values(
            user_id=self.user_id,
            message_id=message_id,
            body=body,
            subject=subject,
            sent_to=sent_to,
            sent_at=sent_at,
            embedding=embedding,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "message_id"],
            set_={
                "body": stmt.excluded.body,
                "subject": stmt.excluded.subject,
                "sent_to": stmt.excluded.sent_to,
                "sent_at": stmt.excluded.sent_at,
                "embedding": stmt.excluded.embedding,
            },
        )
        self.session.execute(stmt)

    def upsert_corpus_entries_batch(self, entries: list[dict]) -> int:
        count = 0
        for entry in entries:
            self.upsert_corpus_entry(
                message_id=entry["message_id"],
                body=entry["body"],
                subject=entry.get("subject", ""),
                sent_to=entry.get("sent_to", ""),
                sent_at=entry.get("sent_at"),
                embedding=entry["embedding"],
            )
            count += 1
        return count

    def retrieve_similar(self, query_embedding: list[float], n_results: int = 5) -> list[dict]:
        stmt = (
            select(CorpusEntry)
            .where(CorpusEntry.user_id == self.user_id)
            .order_by(CorpusEntry.embedding.cosine_distance(query_embedding))
            .limit(n_results)
        )
        rows = self.session.execute(stmt).scalars().all()
        return [
            {
                "message_id": r.message_id,
                "body": r.body,
                "subject": r.subject,
                "sent_to": r.sent_to,
                "sent_at": r.sent_at,
            }
            for r in rows
        ]

    def corpus_size(self) -> int:
        stmt = select(CorpusEntry).where(CorpusEntry.user_id == self.user_id)
        return len(self.session.execute(stmt).scalars().all())

    # -- draft log ------------------------------------------------------------

    def log_draft(self, message_id: str, gmail_draft_id: str, intent: str, confidence: float | None) -> None:
        self.session.add(
            DraftLog(
                user_id=self.user_id,
                message_id=message_id,
                gmail_draft_id=gmail_draft_id,
                intent=intent,
                confidence=confidence,
            )
        )

    def draft_count(self) -> int:
        stmt = select(DraftLog).where(DraftLog.user_id == self.user_id)
        return len(self.session.execute(stmt).scalars().all())

    # -- jobs -------------------------------------------------------------------

    def enqueue_job(self, kind: str, payload: dict, run_after: datetime | None = None) -> Job:
        job = Job(
            user_id=self.user_id,
            kind=kind,
            payload=payload,
            run_after=run_after or _now(),
        )
        self.session.add(job)
        return job

    # -- disconnect / hard delete ------------------------------------------------

    def delete_all_user_data(self) -> None:
        uid = self.user_id
        self.session.execute(delete(DraftLog).where(DraftLog.user_id == uid))
        self.session.execute(delete(CorpusEntry).where(CorpusEntry.user_id == uid))
        self.session.execute(delete(ProcessedMessage).where(ProcessedMessage.user_id == uid))
        self.session.execute(delete(Job).where(Job.user_id == uid))
        self.session.execute(delete(GmailAccount).where(GmailAccount.user_id == uid))
        self.session.execute(delete(User).where(User.id == uid))


class SchedulerRepo:
    """Deliberately unscoped: the worker legitimately needs cross-tenant reads.

    Kept separate from Repo (and named to stand out) so "every other query is
    user-scoped" stays an honest invariant instead of an escape hatch.
    """

    def __init__(self, session: Session):
        self.session = session

    def list_active_accounts(self) -> list[GmailAccount]:
        stmt = (
            select(GmailAccount)
            .join(User, User.id == GmailAccount.user_id)
            .where(User.status == "active", GmailAccount.watch_status == "ok")
        )
        return list(self.session.execute(stmt).scalars().all())

    def claim_next_jobs(self, kind: str, limit: int = 10) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.kind == kind, Job.status == "queued", Job.run_after <= _now())
            .order_by(Job.created_at)
            .limit(limit)
        )
        jobs = list(self.session.execute(stmt).scalars().all())
        for job in jobs:
            job.status = "running"
            job.attempts += 1
        return jobs

    def mark_job_done(self, job_id: int) -> None:
        job = self.session.get(Job, job_id)
        if job is not None:
            job.status = "done"

    def mark_job_failed(self, job_id: int, retry: bool) -> None:
        job = self.session.get(Job, job_id)
        if job is not None:
            job.status = "queued" if retry else "failed"
