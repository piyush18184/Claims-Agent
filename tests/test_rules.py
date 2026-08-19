from src.sample_data import SAMPLE_CONFLICT, SAMPLE_HIGH_VALUE, SAMPLE_STANDARD
from src.workflow import assess_risk, extract_entities, parse_document, validate_claim


def run_until_risk(text):
    state = {"raw_text": text, "document_id": "TEST"}
    state.update(parse_document(state))
    state.update(extract_entities(state))
    state.update(validate_claim(state))
    state.update(assess_risk(state))
    return state


def test_standard_claim_does_not_require_hitl(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    state = run_until_risk(SAMPLE_STANDARD)
    assert state["recommended_decision"] == "APPROVE"
    assert state["requires_hitl"] is False


def test_high_value_claim_requires_hitl(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    state = run_until_risk(SAMPLE_HIGH_VALUE)
    assert state["requires_hitl"] is True
    assert any("threshold" in reason.lower() for reason in state["risk_reasons"])


def test_conflicting_policy_numbers_require_hitl(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    state = run_until_risk(SAMPLE_CONFLICT)
    assert state["requires_hitl"] is True
    assert state["conflicts"]
