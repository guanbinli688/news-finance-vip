import pytest

from news_finance_v2.validation import evaluate_gate, validate_prediction


def valid_raw(**overrides):
    value = {
        "horizon_days": 5,
        "target": "SPY",
        "direction": "UP",
        "probability": 0.62,
        "thesis": "增长与流动性共同改善",
        "invalidation": "信用利差快速扩大",
        "sensors": ["credit", "breadth"],
        "evidence_ids": ["OFF-1", "MKT-1"],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize("direction", ["BULLISH", "上涨", "outperform"])
def test_absolute_target_rejects_invalid_direction(direction):
    assert not validate_prediction(valid_raw(direction=direction)).accepted


def test_relative_target_accepts_only_relative_directions():
    assert validate_prediction(valid_raw(target="QQQ/SPY", direction="OUTPERFORM")).accepted
    assert not validate_prediction(valid_raw(target="QQQ/SPY", direction="UP")).accepted


def test_direction_is_case_normalized_when_semantically_valid():
    result = validate_prediction(valid_raw(direction="up"))
    assert result.accepted
    assert result.prediction["direction"] == "UP"


def test_nan_probability_is_rejected():
    assert not validate_prediction(valid_raw(probability=float("nan"))).accepted


def test_unknown_target_and_missing_evidence_are_rejected():
    result = validate_prediction(valid_raw(target="FAKE", evidence_ids=[]))
    assert set(result.reasons) == {"target", "evidence_ids"}


def test_gate_requires_two_evidence_kinds():
    gate = evaluate_gate([], 0.9, {"market"}, 0.8)
    assert not gate.allowed
    assert "evidence_kinds" in gate.reasons


def test_gate_reports_each_failed_condition():
    gate = evaluate_gate(["BLS"], 0.5, {"market"}, 0.8)
    assert set(gate.reasons) == {"core_sources", "market_coverage", "evidence_kinds"}
