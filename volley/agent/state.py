
from typing_extensions import TypedDict


class VolleyState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────
    email: dict                         # raw email dict from Gmail reader
    user_id: str | None                 # set by the server graph; None for the CLI

    # ── Extracted fields (populated at graph entry) ────────────────
    sender: str
    subject: str
    body: str
    thread_id: str

    # ── Classification (populated by classify node) ────────────────
    intent: str | None               # e.g. "inbound_lead", "cold_outreach"
    is_lead: bool | None
    confidence: float | None
    classification_reasoning: str | None

    # ── RAG (populated by retrieve_tone node) ──────────────────────
    tone_examples: list | None       # list of {"body": ..., "metadata": ...}

    # ── Draft (populated by draft_reply node) ──────────────────────
    draft: str | None

    # ── Approval (populated by human_approval node — Phase 7) ──────
    approval_status: str | None      # "approved" | "edited" | "drafted" | "skipped"
    final_reply: str | None          # the version sent or saved to Drafts
