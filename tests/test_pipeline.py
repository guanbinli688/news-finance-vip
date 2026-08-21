from dataclasses import dataclass

from news_finance_v2.app import Services, run_pipeline
from news_finance_v2.config import Settings


class Collector:
    def __init__(self, core_failures=()):
        self.core_failures = core_failures
    def collect(self, full=False):
        return {
            "sources": [{"name": "BLS", "status": "SUCCESS"}],
            "core_failures": list(self.core_failures), "evidence_kinds": {"official", "market"},
            "market_coverage": .9, "market": {"SPY": 100.0}, "events": [],
        }


class Analyzer:
    def analyze(self, collected):
        return {"direction": {"title": "等待确认", "brief": "离线测试"}, "predictions": []}


class PredictingAnalyzer:
    def analyze(self, collected):
        return {"direction": {"title": "偏积极", "brief": "多源确认"}, "predictions": [{
            "horizon_days": 5, "target": "SPY", "direction": "UP", "probability": .6,
            "thesis": "趋势改善", "invalidation": "跌破关键位", "sensors": ["breadth"],
            "evidence_ids": ["OFF-1", "MKT-SPY"],
        }]}


class Mailer:
    def __init__(self): self.calls = []
    def send(self, html): self.calls.append(html)


def services(core_failures=()):
    return Services(Collector(core_failures), Analyzer(), Mailer())


def test_preview_never_sends_email(tmp_path):
    svc = services()
    result = run_pipeline(Settings.from_env(tmp_path), svc, preview=True, full=False)
    assert svc.mailer.calls == []
    assert result.report_path.exists()


def test_failed_gate_renders_report_but_freezes_nothing(tmp_path):
    result = run_pipeline(Settings.from_env(tmp_path), services(["BLS"]), preview=True, full=False)
    assert result.predictions_frozen == 0
    assert "BLS" in result.report_html
    assert "不冻结预测" in result.report_html


def test_allowed_prediction_is_frozen_with_trading_day_target(tmp_path):
    svc = Services(Collector(), PredictingAnalyzer(), Mailer())
    result = run_pipeline(Settings.from_env(tmp_path), svc, preview=True, full=False)
    import sqlite3
    db = sqlite3.connect(tmp_path / "data" / "news_finance_v2.db")
    row = db.execute("SELECT target,target_session FROM predictions").fetchone()
    db.close()
    assert result.predictions_frozen == 1
    assert row[0] == "SPY"
    assert row[1] > "2026-08-19"
    assert "<strong>SPY</strong>" in result.report_html
