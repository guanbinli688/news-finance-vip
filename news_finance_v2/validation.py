from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .models import EvidenceGate, ValidationResult


ALLOWED_TARGETS = frozenset({
    "SPY", "QQQ/SPY", "IWM/SPY", "XLK/SPY", "XLF/SPY", "XLE/SPY",
    "HYG", "TLT", "GLD", "USO", "^VIX",
})
ABSOLUTE_DIRECTIONS = frozenset({"UP", "DOWN", "NEUTRAL"})
RELATIVE_DIRECTIONS = frozenset({"OUTPERFORM", "UNDERPERFORM", "NEUTRAL"})
HORIZONS = frozenset({3, 5, 10, 15})


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _strings(value: object, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(_clip(item, 80) for item in value[:limit] if _clip(item, 80))


def validate_prediction(raw: Mapping[str, Any]) -> ValidationResult:
    reasons: list[str] = []
    target = str(raw.get("target", "")).strip().upper()
    direction = str(raw.get("direction", "")).strip().upper()

    try:
        horizon = int(raw.get("horizon_days"))
    except (TypeError, ValueError):
        horizon = -1
    if horizon not in HORIZONS:
        reasons.append("horizon_days")

    if target not in ALLOWED_TARGETS:
        reasons.append("target")

    valid_directions = RELATIVE_DIRECTIONS if "/" in target else ABSOLUTE_DIRECTIONS
    if direction not in valid_directions:
        reasons.append("direction")

    try:
        probability = float(raw.get("probability"))
    except (TypeError, ValueError):
        probability = math.nan
    if not math.isfinite(probability) or not 0.50 <= probability <= 0.80:
        reasons.append("probability")

    evidence_ids = _strings(raw.get("evidence_ids"), 12)
    if not evidence_ids:
        reasons.append("evidence_ids")

    if reasons:
        return ValidationResult(False, None, tuple(dict.fromkeys(reasons)))

    normalized = {
        "horizon_days": horizon,
        "target": target,
        "direction": direction,
        "probability": probability,
        "thesis": _clip(raw.get("thesis"), 120),
        "invalidation": _clip(raw.get("invalidation"), 100),
        "sensors": _strings(raw.get("sensors"), 6),
        "evidence_ids": evidence_ids,
    }
    return ValidationResult(True, normalized)


def evaluate_gate(
    core_failures: list[str] | tuple[str, ...],
    market_coverage: float,
    evidence_kinds: set[str],
    threshold: float,
) -> EvidenceGate:
    reasons: list[str] = []
    if core_failures:
        reasons.append("core_sources")
    if not math.isfinite(market_coverage) or market_coverage < threshold:
        reasons.append("market_coverage")
    if len(evidence_kinds) < 2:
        reasons.append("evidence_kinds")
    return EvidenceGate(not reasons, tuple(reasons))
