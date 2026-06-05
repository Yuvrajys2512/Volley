from typing import Optional
from typing_extensions import TypedDict


class VolleyState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────
    email: dict                         # raw email dict from Gmail reader

    # ── Extracted fields (populated at graph entry) ────────────────
    sender: str
    subject: str
    body: str
    thread_id: str

    # ── Classification (populated by classify node) ────────────────
    intent: Optional[str]               # e.g. "inbound_lead", "cold_outreach"
    is_lead: Optional[bool]
    confidence: Optional[float]
    classification_reasoning: Optional[str]

    # ── RAG (populated by retrieve_tone node) ──────────────────────
    tone_examples: Optional[list]       # list of {"body": ..., "metadata": ...}

    # ── Draft (populated by draft_reply node) ──────────────────────
    draft: Optional[str]

    # ── Approval (populated by human_approval node — Phase 7) ──────
    approval_status: Optional[str]      # "approved" | "edited" | "skipped"
    final_reply: Optional[str]          # the version actually sent
