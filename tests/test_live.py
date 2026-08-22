import json
from datetime import date
from pathlib import Path

from news_finance_v2.config import Settings
from news_finance_v2.live import (
    HttpCollector, OpenAIAnalyzer, SMTPMailer, parse_ics_events, rank_news_symbols,
)
from news_finance_v2.market import SIGNALS
from news_finance_v2.sources import COMPANY_NAMES, COMPANY_UNIVERSE


class Response:
    def __init__(self, status_code=200, text="<main>Economic calendar and policy outlook with enough useful content for research.</main>"):
        self.status_code = status_code
        self.text = text
        self.url = "https://example.test/final"
        self.headers = {"Content-Type": "text/html"}


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
    def get(self, *args, **kwargs): return next(self.responses)


def test_http_collector_records_core_failure_and_market_coverage(tmp_path):
    settings = Settings.from_env(tmp_path)
    session = Session([Response(503)] + [Response() for _ in range(100)])
    collector = HttpCollector(
        settings, session=session,
        market_loader=lambda symbols: {symbol: 100.0 for symbol in symbols[:-1]},
    )

    result = collector.collect(full=False)

    assert "BLS" in result["core_failures"]
    assert result["market_coverage"] == (len(SIGNALS) - 1) / len(SIGNALS)
    assert result["sources"][0]["status"] == "HTTP_503"


def test_full_collection_adds_company_ir_sources(tmp_path):
    settings = Settings.from_env(tmp_path)
    session = Session([Response() for _ in range(100)])
    collector = HttpCollector(
        settings, session=session,
        market_loader=lambda symbols: {s: 1 for s in symbols},
        stock_loader=lambda symbols: {
            s: {"price": 1, "day_change_pct": -1, "volatility_20_pct": 1}
            for s in symbols
        },
    )
    regular = collector.collect(full=False)
    session.responses = iter([Response() for _ in range(100)])
    full = collector.collect(full=True)
    assert len(full["sources"]) > len(regular["sources"])
    assert any(item["kind"] == "company" for item in full["sources"])
    assert any(item["kind"] == "company_news" for item in full["sources"])
    assert len(full["stock_snapshot"]) == len(COMPANY_UNIVERSE)
    assert len(full["screened_symbols"]) == 50
    assert full["universe_size"] >= 100


def test_news_prefilter_uses_each_stocks_own_volatility():
    snapshot = {
        "A": {"day_change_pct": -1, "volatility_20_pct": 1},
        "B": {"day_change_pct": -2, "volatility_20_pct": 4},
        "C": {"day_change_pct": 1, "volatility_20_pct": 1},
    }

    assert rank_news_symbols(snapshot, limit=2) == ("A", "B")


def test_expanded_universe_has_one_canonical_chinese_name_per_symbol():
    assert set(COMPANY_NAMES) == set(COMPANY_UNIVERSE)
    assert COMPANY_NAMES["MRVL"] == "迈威尔科技"
    assert COMPANY_NAMES["MU"] == "美光科技"


def test_ics_events_are_limited_to_forward_window():
    text = "BEGIN:VEVENT\nDTSTART:20260820T123000Z\nSUMMARY:Initial Jobless Claims\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20260930T123000Z\nSUMMARY:Too Far\nEND:VEVENT"
    events = parse_ics_events(text, start=date(2026, 8, 19), days=14)
    assert events == [{"date": "2026-08-20", "title": "Initial Jobless Claims", "source": "BLS"}]


def test_collector_parses_calendar_from_untruncated_ics(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2026-08-19")
    settings = Settings.from_env(tmp_path)
    ics = "X" * 13000 + "\nBEGIN:VEVENT\nDTSTART:20260820T123000Z\nSUMMARY:Initial Jobless Claims\nEND:VEVENT"
    session = Session([Response(text=ics)] + [Response() for _ in range(100)])
    collector = HttpCollector(settings, session=session, market_loader=lambda symbols: {s: 1 for s in symbols})

    result = collector.collect(full=False)

    assert result["events"] == [{"date": "2026-08-20", "title": "Initial Jobless Claims", "source": "BLS"}]


class Output:
    output_text = json.dumps({
        "direction": {"title": "风险偏好改善", "brief": "信用和广度确认"},
        "predictions": [{
            "horizon_days": 5, "target": "SPY", "direction": "UP",
            "probability": .61, "thesis": "信用改善", "invalidation": "利差扩大",
            "sensors": ["credit"], "evidence_ids": ["MKT-SPY", "OFF-BLS"],
        }],
    }, ensure_ascii=False)


class Responses:
    def __init__(self): self.calls = 0
    def create(self, **kwargs):
        self.calls += 1
        assert kwargs["model"] == "test-model"
        assert "市场快照" in kwargs["input"]
        if "跨资产预测" not in kwargs["input"]:
            assert "horizons" in kwargs["input"]
            assert "actions" in kwargs["input"]
            assert "flows" in kwargs["input"]
            assert "logic" in kwargs["input"]
            assert "media_themes" in kwargs["input"]
        return Output()


class Client:
    def __init__(self): self.responses = Responses()


def test_openai_analyzer_parses_structured_prediction(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_MODEL", "test-model")
    client = Client()
    analyzer = OpenAIAnalyzer(Settings.from_env(tmp_path), client=client)
    result = analyzer.analyze({"market": {"SPY": 100}, "sources": [], "events": []})
    analyzer.analyze({"market": {"SPY": 100}, "sources": [], "events": []})
    assert result["predictions"][0]["target"] == "SPY"
    assert client.responses.calls == 2


def test_openai_analyzer_runs_dedicated_company_decision_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_MODEL", "test-model")

    class CompanyResponses:
        def __init__(self): self.calls = 0
        def create(self, **kwargs):
            self.calls += 1
            if "公司一手材料" in kwargs["input"]:
                assert "个股市场状态" in kwargs["input"]
                return type("Result", (), {"output_text": json.dumps({"company_signals": [{
                    "company": "英伟达", "ticker": "NVDA", "stance": "等待",
                    "brief": "新品需求仍强，但估值偏高，等待业绩确认后再行动。",
                    "trigger": "收入指引继续上调", "risk": "云厂商资本开支放缓", "source": "NVIDIA IR",
                }]}, ensure_ascii=False)})()
            return Output()

    client = type("CompanyClient", (), {"responses": CompanyResponses()})()
    analyzer = OpenAIAnalyzer(Settings.from_env(tmp_path), client=client)
    result = analyzer.analyze({
        "market": {"NVDA": 100},
        "stock_snapshot": {"NVDA": {"price": 100, "volatility_20_pct": 2}},
        "sources": [{"name": "NVIDIA IR", "kind": "company", "status": "SUCCESS", "text": "Q2 earnings and guidance"}],
    })

    assert client.responses.calls == 3
    assert result["company_signals"][0]["ticker"] == "NVDA"
    assert result["company_signals"][0]["stance"] == "等待"


def test_company_signal_guard_caps_focus_and_rejects_unknown_tickers():
    signals = [
        {"ticker": ticker, "stance": "关注", "brief": "中文结论"}
        for ticker in ("NVDA", "MSFT", "JPM", "XOM", "AAPL", "FAKE")
    ]
    snapshot = {
        ticker: {"price": 100, "day_change_pct": -2, "volatility_20_pct": 2}
        for ticker in ("NVDA", "MSFT", "JPM", "XOM", "AAPL")
    }

    selected = OpenAIAnalyzer._limit_company_signals(signals, snapshot)

    assert len(selected) == 5
    assert sum(item["stance"] == "关注" for item in selected) == 4
    assert selected[-1]["stance"] == "等待"


def test_company_signal_guard_requires_stock_specific_pullback():
    signals = [{"ticker": "MSFT", "stance": "关注", "brief": "中文结论"}]
    snapshot = {"MSFT": {"price": 100, "day_change_pct": -0.4, "volatility_20_pct": 2}}

    selected = OpenAIAnalyzer._limit_company_signals(signals, snapshot)

    assert selected[0]["stance"] == "等待"


def test_mailer_uses_dated_url_and_authenticated_sender(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2026-08-21")
    monkeypatch.setenv("PUBLIC_REPORT_URL", "https://example.test/reports/")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USERNAME", "original-sender@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("EMAIL_TO", "original-recipient@example.test")
    sent = []

    class SMTP:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def login(self, username, password):
            assert username == "original-sender@example.test"
            assert password == "secret"
        def send_message(self, message): sent.append(message)

    monkeypatch.setattr("news_finance_v2.live.smtplib.SMTP_SSL", lambda *args, **kwargs: SMTP())
    SMTPMailer(Settings.from_env(tmp_path)).send("<html><body>report</body></html>")

    message = sent[0]
    body = message.get_payload(decode=True).decode("utf-8")
    assert message["Subject"] == "NEWS FINANCE｜2026-08-21"
    assert message["From"] == "original-sender@example.test"
    assert message["To"] == "original-recipient@example.test"
    assert "https://example.test/reports/0821" in body
    assert ">8月21日最新版</a>" in body
    assert "公网最新版：" not in body
