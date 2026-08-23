from __future__ import annotations

import json
import re
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .db import RadarRepository, make_cache_key
from .market import SIGNALS
from .sources import (
    BASE_COMPANY_SOURCES, COMPANY_NAMES, COMPANY_SYMBOLS, COMPANY_UNIVERSE,
    FULL_COMPANY_SOURCES, MEDIA_SOURCES, OFFICIAL_SOURCES,
)
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


def _default_stock_loader(symbols):
    import yfinance as yf
    frame = yf.download(
        list(symbols), period="3mo", auto_adjust=True, progress=False,
        threads=True, group_by="ticker",
    )
    result = {}
    if frame is None or frame.empty:
        return result
    for symbol in symbols:
        try:
            data = frame[symbol] if hasattr(frame.columns, "levels") else frame
            close = data["Close"].dropna()
            if len(close) < 22:
                continue
            returns = close.pct_change().dropna().tail(20)
            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2])
            recent = close.tail(20)
            ma20 = float(recent.mean())
            ma50 = float(close.tail(50).mean())
            result[symbol] = {
                "price": round(latest, 4),
                "day_change_pct": round((latest / previous - 1) * 100, 3),
                "month_change_pct": round((latest / float(close.iloc[-21]) - 1) * 100, 3),
                "volatility_20_pct": round(float(returns.std()) * 100, 3),
                "drawdown_20_pct": round((latest / float(recent.max()) - 1) * 100, 3),
                "above_ma20": latest >= ma20,
                "above_ma50": latest >= ma50,
            }
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    return result


def _rss_text(source: str) -> str:
    try:
        root = ElementTree.fromstring(source or "")
    except ElementTree.ParseError:
        return ""
    titles = []
    for item in root.findall(".//item")[:8]:
        title = " ".join((item.findtext("title") or "").split())
        published = " ".join((item.findtext("pubDate") or "").split())
        if title:
            titles.append(f"{published}｜{title}" if published else title)
    return "\n".join(titles)[:8000]


def rank_news_symbols(stock_snapshot, limit=50):
    ranked = []
    for symbol, snapshot in stock_snapshot.items():
        try:
            change = float(snapshot["day_change_pct"])
            volatility = max(float(snapshot["volatility_20_pct"]), 0.1)
        except (KeyError, TypeError, ValueError):
            continue
        ranked.append((change / volatility, change, symbol))
    ranked.sort()
    return tuple(symbol for _, _, symbol in ranked[:limit])


class HttpCollector:
    def __init__(self, settings: Settings, *, session=None, market_loader=None, stock_loader=None):
        self.settings = settings
        self._external_session = session is not None
        self.session = session or requests.Session()
        contact = settings.sec_user_agent or "independent-research contact@example.org"
        self.session.headers.update({
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) NEWS-FINANCE-V2/2.0 {contact}",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.market_loader = market_loader or _default_market_loader
        self.stock_loader = stock_loader or _default_stock_loader

    def collect(self, full=False):
        evidence_kinds = {"market"}
        specs = [(name, url, "official", core) for name, url, core in OFFICIAL_SOURCES]
        specs += [(name, url, "media", False) for name, url in MEDIA_SOURCES]
        specs += [(name, url, "company", False) for name, url in BASE_COMPANY_SOURCES]
        if full:
            specs += [(name, url, "company", False) for name, url in FULL_COMPANY_SOURCES]
        if self._external_session:
            records = [self._fetch(*spec) for spec in specs]
        else:
            with ThreadPoolExecutor(max_workers=10) as executor:
                records = list(executor.map(lambda spec: self._fetch(*spec), specs))
        market = self.market_loader(list(SIGNALS))
        stock_snapshot = self.stock_loader(COMPANY_UNIVERSE) if full else {}
        news_symbols = rank_news_symbols(stock_snapshot) if full else ()
        if full:
            news_specs = [
                (f"{symbol} 新闻", f"https://finance.yahoo.com/rss/2.0/headline?s={symbol}", symbol)
                for symbol in news_symbols
            ]
            if self._external_session:
                records += [self._fetch_company_news(*spec) for spec in news_specs]
            else:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    records += list(executor.map(lambda spec: self._fetch_company_news(*spec), news_specs))
        if any(r["status"] == "SUCCESS" and r["kind"] == "official" for r in records):
            evidence_kinds.add("official")
        if any(r["status"] == "SUCCESS" and r["kind"] == "media" for r in records):
            evidence_kinds.add("media")
        if any(r["status"] == "SUCCESS" and r["kind"] in {"company", "company_news"} for r in records):
            evidence_kinds.add("company")
        core_failures = [r["name"] for r in records if r["core"] and r["status"] != "SUCCESS"]
        events = next((r.get("events", []) for r in records if r["name"] == "BLS" and r["status"] == "SUCCESS"), [])
        return {
            "sources": records, "core_failures": core_failures,
            "evidence_kinds": evidence_kinds, "market": market,
            "market_coverage": len(market) / len(SIGNALS), "events": events,
            "stock_snapshot": stock_snapshot,
            "universe_size": len(COMPANY_UNIVERSE),
            "screened_symbols": list(news_symbols),
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

    def _fetch_company_news(self, name, url, symbol):
        try:
            response = self.session.get(url, timeout=self.settings.timeout_seconds, allow_redirects=True)
            status = "SUCCESS" if response.status_code == 200 else f"HTTP_{response.status_code}"
            text = _rss_text(response.text) if status == "SUCCESS" else ""
            if status == "SUCCESS" and not text:
                status = "EMPTY"
            return {
                "name": name, "url": url, "final_url": str(response.url),
                "kind": "company_news", "symbol": symbol, "core": False,
                "status": status, "text": text, "message": "",
            }
        except requests.Timeout as exc:
            return {"name": name, "url": url, "kind": "company_news", "symbol": symbol, "core": False, "status": "TIMEOUT", "text": "", "message": str(exc)}
        except requests.RequestException as exc:
            return {"name": name, "url": url, "kind": "company_news", "symbol": symbol, "core": False, "status": "NETWORK_ERROR", "text": "", "message": str(exc)}


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

    def _complete_json(self, purpose: str, system_prompt: str, prompt: str):
        key = make_cache_key(
            provider=self.settings.ai_provider, model=self.settings.ai_model, purpose=purpose,
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
        if not isinstance(parsed, dict):
            raise ValueError(f"AI {purpose} 输出必须是JSON对象")
        self.repository.cache_set(key, parsed, expires_at=now + timedelta(hours=self.settings.cache_ttl_hours))
        return parsed

    def analyze(self, collected):
        compact_sources = []
        for record in collected.get("sources", []):
            text = " ".join(str(record.get("text", "")).split())
            kind = record.get("kind")
            limit = 1200 if kind == "company" else (700 if kind == "company_news" else 900)
            compact_sources.append({
                "name": record.get("name"), "kind": kind,
                "symbol": record.get("symbol") or COMPANY_SYMBOLS.get(record.get("name")),
                "status": record.get("status"), "text": text[:limit],
            })
        macro_sources = [
            item for item in compact_sources
            if item.get("kind") in {"official", "media"}
        ]
        prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
        prompt += "\n宏观、政策与财经证据：\n" + json.dumps(macro_sources, ensure_ascii=False)
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
  "media_themes":[{"title":"","tone":"积极|谨慎|中性","brief":"","impact":"","sources":[]}],
  "predictions":[{"horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,"thesis":"","invalidation":"","sensors":[],"evidence_ids":[]}]
}
约束：只输出 JSON；除股票代码和来源名外，展示文案全部使用简体中文；表达应细腻、克制、专业，结论明确但不过度武断；禁止复制网页导航、菜单、公司介绍或英文原文；direction.brief 不超过70字；horizons 必须正好三项，每项 brief 不超过45字、focus 最多3个标的；actions 每组最多3项，每项必须写“标的＋动作＋触发条件”，不写空泛口号；flows 最多3项；logic 最多4项；media_themes 最多3项，每项必须说明投资含义；预测周期只能 3/5/10/15；概率 0.50-0.80；绝对方向 UP/DOWN/NEUTRAL，相对方向 OUTPERFORM/UNDERPERFORM/NEUTRAL；没有优势就写“等待确认”。
"""
        system_prompt = "你是成熟、克制且措辞温和的中文跨资产投资研究员。只依据输入证据，先给动作再解释原因，不承诺收益。严格输出JSON。"
        parsed = self._complete_json("master", system_prompt, prompt)

        prediction_prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
        prediction_prompt += "\n宏观、政策与财经证据：\n" + json.dumps(macro_sources, ensure_ascii=False)
        prediction_prompt += """
\n请单独生成跨资产预测，只输出以下JSON：
{"predictions":[{"horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,"thesis":"","invalidation":"","sensors":[],"evidence_ids":[]}]}
必须正好4项且target互不重复：至少1项股票或行业相对强弱（SPY、QQQ/SPY、IWM/SPY、XLK/SPY、XLF/SPY、XLE/SPY），至少1项利率或信用（TLT、HYG），至少1项避险或商品（GLD、USO），第4项可从上述对象或^VIX选择；不能4项都写同一方向；周期只能3/5/10/15；概率0.50-0.80；每项必须有简洁中文逻辑、可观察失效条件和证据编号；绝对方向使用UP/DOWN/NEUTRAL，相对方向使用OUTPERFORM/UNDERPERFORM/NEUTRAL。
"""
        prediction_system = "你是跨资产预测负责人。以分散、可验证和可复盘为首要原则，严格输出JSON。"
        prediction_result = self._complete_json(
            "cross_asset_predictions", prediction_system, prediction_prompt
        )
        cross_asset_predictions = prediction_result.get("predictions", [])
        if isinstance(cross_asset_predictions, list) and cross_asset_predictions:
            parsed["predictions"] = self._limit_predictions(cross_asset_predictions)

        company_sources = [
            item for item in compact_sources
            if item.get("kind") in {"company", "company_news"}
            and item.get("status") == "SUCCESS" and item.get("text")
        ]
        if company_sources:
            company_prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
            company_prompt += "\n个股市场状态：\n" + json.dumps(collected.get("stock_snapshot", {}), ensure_ascii=False)
            company_prompt += "\n股票代码与标准中文名：\n" + json.dumps(COMPANY_NAMES, ensure_ascii=False)
            company_prompt += "\n公司一手材料与逐股新闻：\n" + json.dumps(company_sources, ensure_ascii=False)
            company_prompt += """
\n从上述候选中筛选最多8个真正可交易的增量信号，输出：
{"company_signals":[{"company":"中文公司名","ticker":"股票代码","stance":"关注|等待|回避","brief":"事实→股票影响→动作","trigger":"何种可观察条件出现才行动","risk":"最大风险或失效条件","source":"输入中的来源名"}]}
硬约束：只输出JSON；除ticker和source外全部使用简体中文；当前为模拟盘弹性执行，最多4只标记“关注”，其余只能“等待/回避”；“关注”应同时具备可验证的正向逻辑、当日下跌达到该股20日波动率的0.25倍、且没有明显利空导致逻辑失效；若样本中有合格对象，应优先给出2-4只行业分散的“关注”，不要因轻微信息不完美全部写成等待；跌幅达到自身波动率但由明确重大利空驱动的应“回避”；触发条件优先写止跌确认，不写追涨；不能只凭网站介绍或单条媒体标题；不为凑数量而牺牲基本逻辑；不能用统一百分比判断所有股票；不要翻译或复述整段网页；不要使用导航词、公司自我介绍和宣传语；每家公司结论必须不同；brief不超过55字，trigger和risk各不超过35字；不能编造买卖价格。
"""
            company_system = "你是中文美股研究负责人。把公司公告压缩为可执行的股票观察结论，只输出JSON。"
            company_result = self._complete_json("company", company_system, company_prompt)
            signals = company_result.get("company_signals", [])
            parsed["company_signals"] = self._limit_company_signals(
                signals, collected.get("stock_snapshot", {})
            )
        else:
            parsed["company_signals"] = []
        return parsed

    @staticmethod
    def _limit_predictions(predictions):
        allowed = {
            "SPY", "QQQ/SPY", "IWM/SPY", "XLK/SPY", "XLF/SPY", "XLE/SPY",
            "HYG", "TLT", "GLD", "USO", "^VIX",
        }
        selected = []
        seen = set()
        for raw in predictions:
            if not isinstance(raw, dict):
                continue
            target = str(raw.get("target", "")).strip().upper()
            if target not in allowed or target in seen:
                continue
            item = dict(raw)
            item["target"] = target
            selected.append(item)
            seen.add(target)
            if len(selected) == 5:
                break
        return selected

    @staticmethod
    def _limit_company_signals(signals, stock_snapshot):
        if not isinstance(signals, list):
            return []
        allowed = set(COMPANY_UNIVERSE)
        selected = []
        seen = set()
        focus_count = 0
        for raw in signals:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            ticker = str(item.get("ticker", "")).strip().upper()
            if ticker not in allowed or ticker in seen:
                continue
            seen.add(ticker)
            stance = str(item.get("stance", "等待")).strip()
            if stance not in {"关注", "等待", "回避"}:
                stance = "等待"
            snapshot = stock_snapshot.get(ticker, {})
            if stance == "关注":
                try:
                    day_change = float(snapshot["day_change_pct"])
                    volatility = max(float(snapshot["volatility_20_pct"]), 0.1)
                    controlled_pullback = day_change <= -0.25 * volatility
                except (KeyError, TypeError, ValueError):
                    controlled_pullback = False
                if focus_count >= 4 or not controlled_pullback:
                    stance = "等待"
            if stance == "关注":
                focus_count += 1
            item["ticker"] = ticker
            item["stance"] = stance
            selected.append(item)
            if len(selected) == 8:
                break
        return selected


class SMTPMailer:
    def __init__(self, settings: Settings): self.settings = settings
    def send(self, report: str):
        if self.settings.public_report_url:
            dated_url = (
                f"{self.settings.public_report_url.rstrip('/')}"
                f"/{self.settings.report_date.strftime('%m%d')}"
            )
            dated_label = (
                f"{self.settings.report_date.month}月"
                f"{self.settings.report_date.day}日最新版"
            )
            link = (
                "<div style='padding:12px;background:#eaf4fb;border-left:5px solid #005ea8'>"
                f"<a href='{dated_url}'>{dated_label}</a></div>"
            )
            report = report.replace(
    "<body",
    "<body" + ">" + link,
    1
)
        message = MIMEText(report, "html", "utf-8")
        message["Subject"] = f"NEWS FINANCE｜{self.settings.report_date.isoformat()}"
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
