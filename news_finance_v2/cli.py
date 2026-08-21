from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from .app import Services, run_pipeline
from .calendar import TradingCalendar
from .config import Settings
from .validation import evaluate_gate, validate_prediction


class OfflineCollector:
    def collect(self, full=False):
        return {
            "sources": [{"name": "OFFLINE_FIXTURE", "status": "SUCCESS"}],
            "core_failures": [], "evidence_kinds": {"official", "market"},
            "market_coverage": 1.0,
            "market": {"SPY": 100.0, "QQQ": 101.0, "HYG": 78.0, "TLT": 89.0},
            "events": [{"date": date.today().isoformat(), "title": "离线演示事件"}],
        }


class OfflineAnalyzer:
    def analyze(self, collected):
        return {"direction": {"title": "等待确认", "brief": "这是确定性离线演示，不代表实时市场判断。"}, "predictions": []}


class DisabledMailer:
    def send(self, html):
        raise RuntimeError("离线模式禁止发送邮件")


def _self_test() -> None:
    assert evaluate_gate([], 1.0, {"official", "market"}, .8).allowed
    assert validate_prediction({
        "horizon_days": 5, "target": "SPY", "direction": "UP", "probability": .6,
        "evidence_ids": ["MKT-1"], "thesis": "x", "invalidation": "y",
    }).accepted
    assert TradingCalendar().target_session(TradingCalendar().base_session(__import__("datetime").date.today()), 3)


def build_parser():
    parser = argparse.ArgumentParser(description="NEWS FINANCE V2")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--base-dir", type=Path, default=Path(__file__).resolve().parents[1])
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        _self_test()
        print("NEWS FINANCE V2 self-test passed")
        return 0
    settings = Settings.from_env(args.base_dir)
    if args.verify:
        from .db import RadarRepository
        from .live import verify_due_predictions
        count = verify_due_predictions(RadarRepository(settings.db_file))
        print(f"完成到期验证: {count}")
        return 0
    offline = os.getenv("NEWS_FINANCE_OFFLINE", "").strip() == "1"
    if not offline:
        missing = settings.validate_runtime(require_ai=True, require_smtp=not args.preview)
        if missing:
            print("缺少运行配置: " + ", ".join(missing), file=sys.stderr)
            return 2
        from .live import HttpCollector, OpenAIAnalyzer, SMTPMailer
        services = Services(HttpCollector(settings), OpenAIAnalyzer(settings), SMTPMailer(settings))
        result = run_pipeline(settings, services, preview=args.preview, full=args.full)
        print(f"生成: {result.report_path}")
        if args.preview:
            print("PREVIEW 模式：未发送邮件。")
        else:
            print("报告邮件发送完成。")
        return 0
    result = run_pipeline(settings, Services(OfflineCollector(), OfflineAnalyzer(), DisabledMailer()), preview=True, full=args.full)
    print(f"生成: {result.report_path}")
    print("OFFLINE 模式：未访问网络、AI 或 SMTP。")
    return 0
