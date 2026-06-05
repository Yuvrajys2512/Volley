import base64
from typing import Optional


def fetch_inbox_emails(service, max_results: int = 10, only_unread: bool = True) -> list[dict]:
    """Fetch emails from the inbox, newest first."""
    query = "is:unread" if only_unread else ""
    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        q=query,
        maxResults=max_results,
    ).execute()

    messages = result.get("messages", [])
    return [fetch_full_message(service, msg["id"]) for msg in messages]


def fetch_full_message(service, message_id: str) -> dict:
    """Fetch a single message by ID and return a clean dict."""
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    body = _extract_body(msg["payload"])

    return {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "body": body,
        "snippet": msg.get("snippet", ""),
    }


def _extract_body(payload: dict) -> str:
    """
    Walk the MIME tree and return the plain-text body.
    Prefers text/plain. Falls back to stripping text/html.
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return _decode(data)

    if mime_type == "text/html":
        # Only use HTML as a last resort — return raw so caller can strip tags
        data = payload.get("body", {}).get("data", "")
        return _decode(data)

    # Multipart: recurse into parts, prefer text/plain
    parts = payload.get("parts", [])
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    if plain:
        return _decode(plain.get("body", {}).get("data", ""))

    # No plain part — recurse deeper into first available part
    for part in parts:
        result = _extract_body(part)
        if result:
            return result

    return ""


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def truncate_body(body: str, max_chars: int = 3000) -> str:
    """Trim very long email bodies before sending to an LLM."""
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
