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

    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        try:
            full = fetch_full_message(service, msg["id"])
            emails.append(full)
        except Exception as e:
            # Skip malformed messages without crashing the whole fetch
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

        # Skip very short replies (one-liners, confirmations)
        if len(body.split()) < min_words:
            continue

        # Skip auto-generated targets (calendar, notifications, receipts)
        skip_patterns = ["noreply", "no-reply", "donotreply", "notifications@", "mailer-daemon"]
        if any(p in to for p in skip_patterns):
            continue

        filtered.append(email)

    return filtered
