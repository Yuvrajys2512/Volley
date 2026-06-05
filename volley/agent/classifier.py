from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from volley.config import CLASSIFICATION_MODEL, OPENAI_API_KEY, CONFIDENCE_THRESHOLD

# ── Output schema ──────────────────────────────────────────────────────────────

class EmailClassification(BaseModel):
    intent: str = Field(
        description=(
            "One of: inbound_lead, follow_up, referral, partnership, "
            "cold_outreach, support_request, unrelated"
        )
    )
    is_lead: bool = Field(
        description="True if this email represents an opportunity worth drafting a reply for."
    )
    confidence: float = Field(
        description="Confidence in the classification, from 0.0 (uncertain) to 1.0 (certain).",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description="One sentence explaining why this classification was chosen."
    )

# ── Prompt ─────────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """\
You are classifying inbound emails for a professional consultant or founder.

## Intent Categories

- **inbound_lead**: A potential new client actively inquiring about hiring you, your \
rates, or your availability. Clear intent to engage you commercially.
- **follow_up**: A lead or client who has already been in contact, checking in on a \
prior conversation, proposal, or project.
- **referral**: Someone sent by a mutual contact, reaching out on a warm introduction \
to work with you.
- **partnership**: Another company proposing a collaboration, integration, guest post, \
co-marketing, or similar mutual arrangement.
- **cold_outreach**: Someone selling TO you — software, ads, services, recruiting. \
You are their target, not the other way around.
- **support_request**: An existing client or user reporting a problem or asking for help.
- **unrelated**: Newsletter, automated notification, receipt, calendar invite, spam, \
or anything that does not require a personal reply.

## Classification Rules

- If the email could be an inbound_lead but you're unsure, classify it as inbound_lead \
with lower confidence rather than defaulting to unrelated.
- Generic "we should connect sometime" from unknown people with no specific ask = cold_outreach.
- If the sender mentions a mutual contact or "was referred by" = referral.
- Only mark is_lead=true for: inbound_lead, follow_up, referral, partnership.

## Email to Classify

From: {sender}
Subject: {subject}

{body}

Classify this email now."""

# ── Classifier ─────────────────────────────────────────────────────────────────

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set in your .env file.")
        llm = ChatOpenAI(
            model=CLASSIFICATION_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,  # deterministic output for classification
        )
        _llm = llm.with_structured_output(EmailClassification)
    return _llm


def classify_email(email: dict) -> EmailClassification:
    """
    Classify a single email dict (must have 'from', 'subject', 'body' keys).
    Returns an EmailClassification with intent, is_lead, confidence, reasoning.
    """
    from volley.gmail.reader import truncate_body

    prompt = CLASSIFICATION_PROMPT.format(
        sender=email.get("from", "Unknown"),
        subject=email.get("subject", "(no subject)"),
        body=truncate_body(email.get("body", ""), max_chars=2000),
    )

    return _get_llm().invoke(prompt)


def needs_human_review(result: EmailClassification) -> bool:
    """
    Returns True if confidence is below the threshold — meaning a human
    should confirm the classification before the agent proceeds.
    """
    return result.is_lead and result.confidence < CONFIDENCE_THRESHOLD
