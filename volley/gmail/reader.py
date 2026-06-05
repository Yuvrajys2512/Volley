import base64
import re


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
    emails = []
    for msg in messages:
        try:
            emails.append(fetch_full_message(service, msg["id"]))
        except Exception as e:
            print(f"  Warning: could not fetch message {msg['id']}: {e}")
    return emails


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
    Walk the MIME tree and return clean plain text.

    Priority order:
      1. text/plain part (used directly)
      2. text/html part (HTML tags stripped)
      3. Nested multipart (recurse)
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _decode(payload.get("body", {}).get("data", ""))

    if mime_type == "text/html":
        raw = _decode(payload.get("body", {}).get("data", ""))
        return _strip_html(raw)

    # Multipart: prefer text/plain, fall back to text/html, then recurse
    parts = payload.get("parts", [])

    plain_part = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    if plain_part:
        return _decode(plain_part.get("body", {}).get("data", ""))

    html_part = next((p for p in parts if p.get("mimeType") == "text/html"), None)
    if html_part:
        raw = _decode(html_part.get("body", {}).get("data", ""))
        return _strip_html(raw)

    # Nested multipart (e.g. multipart/related inside multipart/alternative)
    for part in parts:
        result = _extract_body(part)
        if result:
            return result

    return ""


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities to get readable plain text."""
    # Remove <style> and <script> blocks entirely
    html = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newlines
    html = re.sub(r"<(br|/p|/div|/li|/tr)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common HTML entities
    replacements = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&quot;": '"'}
    for entity, char in replacements.items():
        html = html.replace(entity, char)
    # Collapse whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def truncate_body(body: str, max_chars: int = 3000) -> str:
    """Trim very long email bodies before sending to an LLM."""
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
