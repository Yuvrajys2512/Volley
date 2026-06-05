from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from volley.config import DRAFT_MODEL, OPENAI_API_KEY
from volley.gmail.reader import truncate_body

# ── Prompt ─────────────────────────────────────────────────────────────────────

DRAFT_PROMPT = """\
You are drafting an email reply on behalf of the user. Your only job is to \
sound exactly like them — not like an AI assistant.

## How this user writes (examples from their actual sent emails)

{tone_examples}

---

## Rules

- Match their tone, sentence length, vocabulary, and sign-off precisely.
- Do NOT start with "I hope this email finds you well" or any generic opener.
- Do NOT explain what you're doing or add meta-commentary.
- Do NOT use bullet points unless the user's examples show they do.
- Keep the reply focused and appropriately concise — match the length style \
of the examples above.
- Write ONLY the reply body. No subject line. No "Draft:" prefix.

---

## Inbound email to reply to

From: {sender}
Subject: {subject}

{body}

---

Write the reply now:"""

# ── Drafter ────────────────────────────────────────────────────────────────────

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set in your .env file.")
        _llm = ChatOpenAI(
            model=DRAFT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0.4,  # slight creativity for natural-sounding replies
        )
    return _llm


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def generate_draft(email: dict, tone_examples: list[dict]) -> str:
    """
    Generate a reply draft for the given email using the retrieved tone examples.

    Args:
        email: dict with 'from', 'subject', 'body' keys (the inbound email)
        tone_examples: list of dicts with 'body' and 'metadata' from retrieve_similar()

    Returns:
        The draft reply as a plain string.
    """
    examples_text = _format_tone_examples(tone_examples)

    prompt = DRAFT_PROMPT.format(
        tone_examples=examples_text,
        sender=email.get("from", ""),
        subject=email.get("subject", ""),
        body=truncate_body(email.get("body", ""), max_chars=2000),
    )

    response = _get_llm().invoke(prompt)
    return response.content.strip()


def _format_tone_examples(examples: list[dict]) -> str:
    """Format retrieved tone examples into a readable block for the prompt."""
    if not examples:
        return "(No tone examples available — write in a professional but warm tone.)"

    parts = []
    for i, ex in enumerate(examples, 1):
        meta = ex.get("metadata", {})
        subject = meta.get("subject", "")
        header = f"[Example {i}]" + (f" Re: {subject}" if subject else "")
        parts.append(f"{header}\n{ex['body'][:600]}")

    return "\n\n---\n\n".join(parts)
