from googleapiclient.errors import HttpError

from volley.gmail.reader import fetch_full_message


def fetch_sent_emails(service, max_results: int = 500) -> list[dict]:
    """
    Fetch emails from the Sent folder.
    Used to build the tone corpus for RAG.
    """
    result = service.users().messages().list(
        userId="me",
        labelIds=["SENT"],
        maxResults=max_results,
    ).execute()

    return _fetch_messages(service, result.get("messages", []))


def fetch_sent_emails_since(service, after_date: str, max_results: int = 100) -> list[dict]:
    """
    Fetch sent emails after a given date string (Gmail 'after:' query format).

    Args:
        after_date: Gmail date string, e.g. "2024/01/15"
    """
    result = service.users().messages().list(
        userId="me",
        labelIds=["SENT"],
        q=f"after:{after_date}",
        maxResults=max_results,
    ).execute()

    return _fetch_messages(service, result.get("messages", []))


def _fetch_messages(service, message_stubs: list) -> list[dict]:
    """Fetch full message content for a list of message stubs ({id})."""
    emails = []
    for msg in message_stubs:
        try:
            full = fetch_full_message(service, msg["id"])
            emails.append(full)
        except Exception as e:
            print(f"  Warning: could not fetch message {msg['id']}: {e}")
    return emails


class HistoryIdExpired(Exception):
    """Raised when Gmail's history.list rejects a startHistoryId as too old
    (Gmail retains history for ~7 days). Caller should re-anchor via
    current_history_id() and accept that some messages in the gap are missed."""


def current_history_id(service) -> int:
    """The mailbox's current historyId — used as the initial watermark right
    after connecting (so only mail arriving after that point is processed)
    and as the re-anchor point after a HistoryIdExpired."""
    profile = service.users().getProfile(userId="me").execute()
    return int(profile["historyId"])


def fetch_new_message_ids_since(service, start_history_id: int) -> tuple[list[str], int]:
    """
    Return (new_inbox_message_ids, new_history_id) for messages added to the
    inbox since start_history_id, using Gmail's history.list watermark
    (cheaper and more precise than re-polling is:unread every cycle).

    Raises HistoryIdExpired if start_history_id is too old for Gmail to
    resolve — the caller should re-anchor via current_history_id().
    """
    message_ids: list[str] = []
    page_token = None
    latest_history_id = start_history_id

    while True:
        try:
            result = service.users().history().list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                labelId="INBOX",
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise HistoryIdExpired(str(e)) from e
            raise

        for record in result.get("history", []):
            for added in record.get("messagesAdded", []):
                message_ids.append(added["message"]["id"])

        if "historyId" in result:
            latest_history_id = max(latest_history_id, int(result["historyId"]))

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    # De-dupe while preserving order (a message can appear in multiple history records).
    seen = set()
    unique_ids = [m for m in message_ids if not (m in seen or seen.add(m))]
    return unique_ids, latest_history_id


def filter_for_corpus(emails: list[dict], min_words: int = 20) -> list[dict]:
    """
    Remove emails that are too short or auto-generated to be useful
    tone examples. Returns only emails worth indexing.
    """
    filtered = []
    for email in emails:
        body = email.get("body", "")
        to = email.get("to", "").lower()

        if len(body.split()) < min_words:
            continue

        skip_patterns = ["noreply", "no-reply", "donotreply", "notifications@", "mailer-daemon"]
        if any(p in to for p in skip_patterns):
            continue

        filtered.append(email)

    return filtered
