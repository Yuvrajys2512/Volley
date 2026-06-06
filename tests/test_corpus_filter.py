"""Corpus filtering — decides which sent emails become tone examples.

This filter is the gatekeeper for RAG quality: too aggressive and the corpus
starves, too loose and auto-generated noise pollutes the tone match.
"""

from volley.gmail.history import filter_for_corpus


def _email(body: str, to: str = "client@example.com") -> dict:
    return {"body": body, "to": to}


def test_keeps_substantial_human_email():
    long_body = " ".join(["word"] * 30)
    result = filter_for_corpus([_email(long_body)])
    assert len(result) == 1


def test_drops_email_below_min_words():
    short_body = " ".join(["word"] * 5)
    assert filter_for_corpus([_email(short_body)]) == []


def test_min_words_boundary_is_inclusive_of_threshold():
    # min_words=20 default: 19 words out, 20 words in.
    assert filter_for_corpus([_email(" ".join(["w"] * 19))]) == []
    assert len(filter_for_corpus([_email(" ".join(["w"] * 20))])) == 1


def test_drops_noreply_recipients():
    long_body = " ".join(["word"] * 30)
    for addr in ("noreply@x.com", "no-reply@x.com", "notifications@x.com", "MAILER-DAEMON@x.com"):
        assert filter_for_corpus([_email(long_body, to=addr)]) == [], addr


def test_respects_custom_min_words():
    body = " ".join(["word"] * 10)
    assert filter_for_corpus([_email(body)], min_words=5)  # passes
    assert filter_for_corpus([_email(body)], min_words=50) == []  # fails


def test_handles_missing_keys_gracefully():
    # Emails without 'body'/'to' should not raise, just be filtered out.
    assert filter_for_corpus([{}]) == []
