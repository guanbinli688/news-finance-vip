from __future__ import annotations

import json
import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .config import Settings
from .db import RadarRepository
from .calendar import TradingCalendar
from .models import Prediction
from .reporting import render_report
from .validation import evaluate_gate, validate_prediction


@dataclass
class Services:
    collector: Any
    analyzer: Any
    mailer: Any


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    predictions_frozen: int
    report_html: str
    report_path: Any


def run_pipeline(settings: Settings, services: Services, *, preview: bool, full: bool) -> RunSummary:
    run_id = uuid.uuid4().hex
    report_date = settings.report_date
    repo = RadarRepository(settings.db_file)
    repo.start_run(run_id, settings.ai_model or "offline", settings.prompt_version)
    collected = services.collector.collect(full=full)
    gate = evaluate_gate(
        collected.get("core_failures", []), float(collected.get("market_coverage", 0)),
        set(collected.get("evidence_kinds", set())), settings.market_coverage_threshold,
    )
    analysis = services.analyzer.analyze(collected)
    frozen = 0
    display_predictions = []
    if gate.allowed:
        calendar = TradingCalendar()
        base_session = calendar.base_session(report_date)
        market = collected.get("market", {})
        for raw in analysis.get("predictions", []):
            checked = validate_prediction(raw)
            if not checked.accepted:
                continue
            item = checked.prediction
            display_predictions.append(item)
            asset, _, benchmark = item["target"].partition("/")
            base_asset = market.get(asset)
            base_benchmark = market.get(benchmark) if benchmark else None
            if base_asset is None or (benchmark and base_benchmark is None):
                continue
            identity = f'{run_id}|{item["horizon_days"]}|{item["target"]}'
            pid = hashlib.sha256(identity.encode()).hexdigest()[:28]
            canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, default=list)
            prediction = Prediction(
                id=pid, run_id=run_id, created_at=datetime.now(timezone.utc),
                base_session=base_session,
                target_session=calendar.target_session(base_session, item["horizon_days"]),
                horizon_days=item["horizon_days"], target=item["target"], direction=item["direction"],
                probability=item["probability"], thesis=item["thesis"], invalidation=item["invalidation"],
                sensors=item["sensors"], evidence_ids=item["evidence_ids"], base_asset=float(base_asset),
                base_benchmark=float(base_benchmark) if base_benchmark is not None else None,
                model=settings.ai_model or "offline", prompt_version=settings.prompt_version,
                frozen_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            )
            frozen += int(repo.freeze_prediction(prediction))
    context = {
        **collected, **analysis, "gate": gate, "predictions_frozen": frozen,
        "display_predictions": display_predictions, "report_date": report_date.isoformat(),
    }
    report = render_report(context)
    settings.html_file.parent.mkdir(parents=True, exist_ok=True)
    settings.html_file.write_text(report, encoding="utf-8")
    settings.audit_file.parent.mkdir(parents=True, exist_ok=True)
    settings.audit_file.write_text(json.dumps({
        "run_id": run_id, "report_date": report_date.isoformat(), "gate": gate.reasons,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    repo.finish_run(run_id, "SUCCESS", {"market_coverage": collected.get("market_coverage", 0), "frozen": frozen})
    if not preview:
        services.mailer.send(report)
    return RunSummary(run_id, frozen, report, settings.html_file)
