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
