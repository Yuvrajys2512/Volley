import base64
from email.mime.text import MIMEText


def send_reply(service, to: str, subject: str, body: str, thread_id: str) -> dict:
    """
    Send a reply email and keep it in the original thread.
    Returns the sent message resource from the Gmail API.
    """
    subject_line = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    mime_msg = MIMEText(body, "plain", "utf-8")
    mime_msg["to"] = to
    mime_msg["subject"] = subject_line

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()

    return sent


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
