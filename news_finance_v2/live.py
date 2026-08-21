from __future__ import annotations

import json
import re
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .db import RadarRepository, make_cache_key
from .market import SIGNALS
from .sources import BASE_COMPANY_SOURCES, FULL_COMPANY_SOURCES, MEDIA_SOURCES, OFFICIAL_SOURCES
from .verification import verify_absolute, verify_relative


def _page_text(source: str) -> str:
    soup = BeautifulSoup(source or "", "html.parser")
    for tag in soup(["script", "style", "svg", "nav", "footer", "noscript"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return "\n".join(dict.fromkeys(line.strip() for line in root.get_text("\n").splitlines() if len(line.strip()) >= 3))[:12000]


def parse_ics_events(text: str, *, start: date | None = None, days: int = 14):
    start = start or date.today()
    end = start + timedelta(days=days)
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text or "", re.S | re.I):
        date_match = re.search(r"DTSTART[^:]*:(\d{8})", block, re.I)
        title_match = re.search(r"SUMMARY:(.+)", block, re.I)
        if not date_match or not title_match:
            continue
        event_date = datetime.strptime(date_match.group(1), "%Y%m%d").date()
        if start <= event_date < end:
            title = title_match.group(1).strip().replace("\\,", ",")
            events.append({"date": event_date.isoformat(), "title": title, "source": "BLS"})
    return sorted(events, key=lambda item: (item["date"], item["title"]))


def _default_market_loader(symbols):
    import yfinance as yf
    result = {}
    for symbol in symbols:
        data = yf.download(symbol, period="1mo", auto_adjust=True, progress=False, threads=False)
        if data is None or data.empty:
            continue
        close = data["Close"].dropna()
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        if len(close):
            result[symbol] = float(close.iloc[-1])
    return result


class HttpCollector:
    def __init__(self, settings: Settings, *, session=None, market_loader=None):
        self.settings = settings
        self.session = session or requests.Session()
        contact = settings.sec_user_agent or "independent-research contact@example.org"
        self.session.headers.update({
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) NEWS-FINANCE-V2/2.0 {contact}",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.market_loader = market_loader or _default_market_loader

    def collect(self, full=False):
        records = []
        evidence_kinds = {"market"}
        for name, url, core in OFFICIAL_SOURCES:
            records.append(self._fetch(name, url, "official", core))
        for name, url in MEDIA_SOURCES:
            records.append(self._fetch(name, url, "media", False))
        for name, url in BASE_COMPANY_SOURCES:
            records.append(self._fetch(name, url, "company", False))
        if full:
            for name, url in FULL_COMPANY_SOURCES:
                records.append(self._fetch(name, url, "company", False))
        market = self.market_loader(list(SIGNALS))
        if any(r["status"] == "SUCCESS" and r["kind"] == "official" for r in records):
            evidence_kinds.add("official")
        if any(r["status"] == "SUCCESS" and r["kind"] == "media" for r in records):
            evidence_kinds.add("media")
        if any(r["status"] == "SUCCESS" and r["kind"] == "company" for r in records):
            evidence_kinds.add("company")
        core_failures = [r["name"] for r in records if r["core"] and r["status"] != "SUCCESS"]
        events = next((r.get("events", []) for r in records if r["name"] == "BLS" and r["status"] == "SUCCESS"), [])
        return {
            "sources": records, "core_failures": core_failures,
            "evidence_kinds": evidence_kinds, "market": market,
            "market_coverage": len(market) / len(SIGNALS), "events": events,
        }

    def _fetch(self, name, url, kind, core):
        try:
            response = self.session.get(url, timeout=self.settings.timeout_seconds, allow_redirects=True)
            status = "SUCCESS" if response.status_code == 200 else f"HTTP_{response.status_code}"
            text = _page_text(response.text) if status == "SUCCESS" else ""
            if status == "SUCCESS" and len(text) < 40:
                status = "EMPTY"
            return {"name": name, "url": url, "final_url": str(response.url), "kind": kind,
                    "core": core, "status": status, "text": text,
                    "events": parse_ics_events(response.text, start=self.settings.report_date) if name == "BLS" and status == "SUCCESS" else [],
                    "message": ""}
        except requests.Timeout as exc:
            return {"name": name, "url": url, "kind": kind, "core": core, "status": "TIMEOUT", "text": "", "message": str(exc)}
        except requests.RequestException as exc:
            return {"name": name, "url": url, "kind": kind, "core": core, "status": "NETWORK_ERROR", "text": "", "message": str(exc)}


class OpenAIAnalyzer:
    def __init__(self, settings: Settings, *, client=None):
        self.settings = settings
        if client is None:
            from openai import OpenAI
            key = "OPENAI_API_KEY" if settings.ai_provider == "openai" else "DEEPSEEK_API_KEY"
            import os
            client = OpenAI(api_key=os.getenv(key), base_url="https://api.deepseek.com" if settings.ai_provider == "deepseek" else None)
        self.client = client
        self.repository = RadarRepository(settings.db_file)

    def analyze(self, collected):
        compact_sources = [{k: r.get(k) for k in ("name", "kind", "status", "text")} for r in collected.get("sources", [])]
        prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
        prompt += "\n来源证据：\n" + json.dumps(compact_sources, ensure_ascii=False)[:30000]
        prompt += """
\n请生成中文机构晨报所需的完整 JSON：
{
  "direction":{"title":"","brief":"","bias":"偏积极|偏谨慎|中性"},
  "horizons":[
    {"days":"3-5","direction":"","focus":[],"brief":"","risk":""},
    {"days":"5-10","direction":"","focus":[],"brief":"","risk":""},
    {"days":"10-15","direction":"","focus":[],"brief":"","risk":""}
  ],
  "actions":{"watch":[],"prepare":[],"avoid":[]},
  "flows":[{"from":"","to":"","brief":""}],
  "logic":[{"cause":"","middle":"","result":"","action":""}],
  "company_signals":[{"company":"","signal":"","brief":"","source":""}],
  "media_themes":[{"title":"","tone":"积极|谨慎|中性","brief":"","sources":[]}],
  "predictions":[{"horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,"thesis":"","invalidation":"","sensors":[],"evidence_ids":[]}]
}
约束：只输出 JSON；所有展示文案使用中文；horizons 必须正好三项；actions 每组最多三项；flows 最多三项；logic 最多四项；company_signals 最多四项且只使用 company 类一手来源；media_themes 最多四项并列出来源名；预测周期只能 3/5/10/15；概率 0.50-0.80；绝对方向 UP/DOWN/NEUTRAL，相对方向 OUTPERFORM/UNDERPERFORM/NEUTRAL；没有优势就写“等待确认”。
"""
        system_prompt = "你是克制的跨资产研究员。只依据输入证据，不承诺收益。严格输出JSON。"
        key = make_cache_key(
            provider=self.settings.ai_provider, model=self.settings.ai_model, purpose="master",
            system_prompt=system_prompt, user_prompt=prompt, prompt_version=self.settings.prompt_version,
        )
        now = datetime.now(timezone.utc)
        cached = self.repository.cache_get(key, now=now)
        if cached is not None:
            return cached
        response = self.client.responses.create(
            model=self.settings.ai_model,
            instructions=system_prompt,
            input=prompt,
        )
        raw = response.output_text.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.I).strip()
        parsed = json.loads(raw)
        self.repository.cache_set(key, parsed, expires_at=now + timedelta(hours=self.settings.cache_ttl_hours))
        return parsed


class SMTPMailer:
    def __init__(self, settings: Settings): self.settings = settings
    def send(self, report: str):
        if self.settings.public_report_url:
            link = (
                "<div style='padding:12px;background:#eaf4fb;border-left:5px solid #005ea8'>"
                f"公网最新版：<a href='{self.settings.public_report_url}'>{self.settings.public_report_url}</a></div>"
            )
            report = report.replace("<body>", "<body>" + link, 1)
        message = MIMEText(report, "html", "utf-8")
        message["Subject"] = f"NEWS FINANCE V2｜{self.settings.report_date.isoformat()}"
        message["From"] = self.settings.smtp_username
        message["To"] = self.settings.email_to
        with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, context=ssl.create_default_context()) as smtp:
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)


def _history_loader(symbol, start, end):
    import yfinance as yf
    from datetime import timedelta
    data = yf.download(symbol, start=start.isoformat(), end=(end + timedelta(days=5)).isoformat(), auto_adjust=True, progress=False, threads=False)
    if data is None or data.empty:
        return {}
    close = data["Close"].dropna()
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return {idx.date(): float(value) for idx, value in close.items() if start < idx.date() <= end}


def verify_due_predictions(repository, *, loader=None, today=None) -> int:
    from datetime import date
    loader = loader or _history_loader
    today = today or date.today()
    saved = 0
    for prediction in repository.due_predictions(today):
        asset, _, benchmark = prediction.target.partition("/")
        asset_prices = loader(asset, prediction.base_session, prediction.target_session)
        if not asset_prices:
            continue
        if benchmark:
            benchmark_prices = loader(benchmark, prediction.base_session, prediction.target_session)
            if not benchmark_prices:
                continue
            result = verify_relative(
                asset_prices, benchmark_prices,
                (prediction.base_asset, prediction.base_benchmark),
                prediction.direction, prediction.probability,
            )
        else:
            result = verify_absolute(
                asset_prices, prediction.base_asset,
                prediction.direction, prediction.probability,
            )
        saved += int(repository.save_verification(prediction.id, result))
    return saved
