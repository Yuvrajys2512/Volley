from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from volley.config import CLASSIFICATION_MODEL, CONFIDENCE_THRESHOLD, GROQ_API_KEY

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
You are their target, not the other way around. Key signal: they are pitching a product/service \
THEY own (CRM, SaaS tool, agency, recruiting). They want YOUR money or time, not the reverse.
- **support_request**: An existing client or user reporting a problem or asking for help.
- **unrelated**: Newsletter, automated notification, receipt, calendar invite, spam, \
or anything that does not require a personal reply.

## Classification Rules

- If the email could be an inbound_lead but you're unsure, classify it as inbound_lead \
with lower confidence rather than defaulting to unrelated.
- Generic "we should connect sometime" from unknown people with no specific ask = cold_outreach.
- If the email mentions "our product", "our platform", "our tool", "our software", "book a demo", \
"free trial" — it is almost certainly cold_outreach, NOT inbound_lead.
- An inbound_lead is someone who wants to HIRE or PAY you. A cold_outreach is someone who wants YOU to pay THEM.
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
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in your .env file.")
        llm = ChatGroq(
            model=CLASSIFICATION_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0,
        )
        _llm = llm.with_structured_output(EmailClassification)
    return _llm


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
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
    return result.is_lead and result.confidence < CONFIDENCE_THRESHOLD
