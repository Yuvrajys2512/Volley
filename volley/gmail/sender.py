import base64
from email.mime.text import MIMEText
from googleapiclient.errors import HttpError


def send_reply(service, to: str, subject: str, body: str, thread_id: str) -> dict:
    """
    Send a reply email and keep it in the original thread.
    If the thread_id is invalid (e.g. test data), fall back to sending
    as a standalone email rather than failing.
    Returns the sent message resource from the Gmail API.
    """
    subject_line = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    mime_msg = MIMEText(body, "plain", "utf-8")
    mime_msg["to"] = to
    mime_msg["subject"] = subject_line

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    try:
        return service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
    except HttpError as e:
        if thread_id and "thread_id" in str(e).lower():
            # Invalid thread — send without threading
            print(f"  [send] Invalid thread_id, sending as standalone email instead.")
            return service.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()
        raise


def send_email(service, to: str, subject: str, body: str) -> dict:
    """
    Send a new (non-reply) email.
    Returns the sent message resource from the Gmail API.
    """
    mime_msg = MIMEText(body, "plain", "utf-8")
    mime_msg["to"] = to
    mime_msg["subject"] = subject

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    return sent
