"""
Structured logging for Volley.
Every processed email gets a one-line JSON log entry so you can
review what happened without re-running the system.
"""

import json
import logging
import os
from datetime import datetime

from volley.config import CHROMA_DB_PATH

LOG_FILE = os.path.join(os.path.dirname(CHROMA_DB_PATH), "volley.log")

# ── Console logger (human-readable) ───────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("volley")


# ── Structured file logger (JSON, one entry per email) ────────────────────────

def log_email_processed(email: dict, state: dict):
    """Append a structured log entry after an email is fully processed."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "message_id": email.get("id"),
        "from": email.get("from"),
        "subject": email.get("subject"),
        "intent": state.get("intent"),
        "is_lead": state.get("is_lead"),
        "confidence": state.get("confidence"),
        "approval_status": state.get("approval_status"),
        "sent": state.get("approval_status") in ("approved", "edited"),
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_error(message_id: str, error: Exception):
    """Append an error entry for a failed email."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "message_id": message_id,
        "error": str(error),
        "type": type(error).__name__,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
