from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Prediction:
    id: str
    run_id: str
    created_at: datetime
    base_session: date
    target_session: date
    horizon_days: int
    target: str
    direction: str
    probability: float
    thesis: str
    invalidation: str
    sensors: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    base_asset: float | None = None
    base_benchmark: float | None = None
    model: str = ""
    prompt_version: str = ""
    frozen_hash: str = ""


@dataclass(frozen=True)
class EvidenceGate:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    prediction: dict[str, Any] | None
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VerificationResult:
    correct: bool
    asset_return: float
    benchmark_return: float | None
    excess_return: float | None
    max_adverse: float
    brier: float
