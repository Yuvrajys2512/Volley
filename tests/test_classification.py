"""Classification schema + review gate.

We don't call the LLM here (that needs a key and network); we test the
Pydantic contract and the human-review threshold logic, which is where the
real decision rules live.
"""

import pytest
from pydantic import ValidationError

from volley.agent.classifier import EmailClassification, needs_human_review


def _classification(**overrides) -> EmailClassification:
    base = dict(intent="inbound_lead", is_lead=True, confidence=0.9, reasoning="x")
    base.update(overrides)
    return EmailClassification(**base)


class TestSchema:
    def test_valid_classification(self):
        c = _classification()
        assert c.is_lead is True
        assert c.confidence == 0.9

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            _classification(confidence=1.5)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            _classification(confidence=-0.1)


class TestNeedsHumanReview:
    def test_low_confidence_lead_flagged(self):
        assert needs_human_review(_classification(is_lead=True, confidence=0.5)) is True

    def test_high_confidence_lead_not_flagged(self):
        assert needs_human_review(_classification(is_lead=True, confidence=0.95)) is False

    def test_non_lead_never_flagged(self):
        # Not a lead → it's getting skipped anyway, no review needed.
        assert needs_human_review(_classification(is_lead=False, confidence=0.1)) is False
