"""Body truncation — guards the LLM context from oversized email bodies."""

from volley.gmail.reader import truncate_body


def test_short_body_unchanged():
    body = "hello there"
    assert truncate_body(body, max_chars=100) == body


def test_long_body_truncated_with_marker():
    body = "x" * 5000
    out = truncate_body(body, max_chars=100)
    assert out.startswith("x" * 100)
    assert "truncated" in out
    assert len(out) < len(body)


def test_boundary_exact_length_unchanged():
    body = "y" * 100
    assert truncate_body(body, max_chars=100) == body
