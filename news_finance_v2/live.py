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
from .market import SIGNALS, PREDICTION_TARGETS, PREDICTION_GROUPS, SIGNAL_NAMES
from . import sources as source_config
from .sources import (
    BASE_COMPANY_SOURCES, COMPANY_NAMES, COMPANY_SYMBOLS, COMPANY_UNIVERSE,
    FULL_COMPANY_SOURCES, MEDIA_SOURCES, OFFICIAL_SOURCES,
)

# 新版 sources.py 可提供这些增强配置；旧版没有时也能直接运行。
COMPANY_SECTORS = getattr(source_config, "COMPANY_SECTORS", {})
CORE_COMPANY_UNIVERSE = set(getattr(source_config, "CORE_COMPANY_UNIVERSE", ()))
SCREENING_CONFIG = {
    "market_prefilter_size": 50,
    "news_prefilter_size": 28,
    "ai_candidate_size": 16,
    "final_company_count": 8,
    "max_per_sector": 2,
}
SCREENING_CONFIG.update(getattr(source_config, "SCREENING_CONFIG", {}))
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
    """批量读取股票行情，并生成第一轮筛选需要的量价/趋势特征。"""
    import yfinance as yf

    symbols = tuple(dict.fromkeys(str(symbol).upper() for symbol in symbols if symbol))
    if not symbols:
        return {}

    frame = yf.download(
        list(symbols),
        period="3mo",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="ticker",
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

            volume = data["Volume"].dropna() if "Volume" in data else None
            returns = close.pct_change().dropna().tail(20)

            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2])
            close_5d = float(close.iloc[-6]) if len(close) >= 6 else previous
            close_20d = float(close.iloc[-21])

            recent20 = close.tail(20)
            recent60 = close.tail(60)

            ma20 = float(recent20.mean())
            ma50 = float(close.tail(50).mean()) if len(close) >= 50 else ma20

            low20 = float(recent20.min())
            high20 = float(recent20.max())
            low60 = float(recent60.min())
            high60 = float(recent60.max())

            position20 = 0.5 if high20 <= low20 else (latest - low20) / (high20 - low20)
            position60 = 0.5 if high60 <= low60 else (latest - low60) / (high60 - low60)

            volume_ratio = 1.0
            if volume is not None and len(volume) >= 2:
                latest_volume = float(volume.iloc[-1])
                base_volume = volume.iloc[-21:-1] if len(volume) >= 21 else volume.iloc[:-1]
                avg_volume = float(base_volume.mean()) if len(base_volume) else 0.0
                if avg_volume > 0:
                    volume_ratio = latest_volume / avg_volume

            volatility = max(float(returns.std()) * 100, 0.01)

            result[symbol] = {
                "price": round(latest, 4),
                "day_change_pct": round((latest / previous - 1) * 100, 3),
                "change_5d_pct": round((latest / close_5d - 1) * 100, 3),
                "month_change_pct": round((latest / close_20d - 1) * 100, 3),
                "volatility_20_pct": round(volatility, 3),
                "drawdown_20_pct": round((latest / high20 - 1) * 100, 3),
                "drawdown_60_pct": round((latest / high60 - 1) * 100, 3),
                "volume_ratio_20": round(volume_ratio, 3),
                "above_ma20": latest >= ma20,
                "above_ma50": latest >= ma50,
                "ma20_gap_pct": round((latest / ma20 - 1) * 100, 3) if ma20 else 0.0,
                "ma50_gap_pct": round((latest / ma50 - 1) * 100, 3) if ma50 else 0.0,
                "position_20d": round(max(0.0, min(position20, 1.0)), 3),
                "position_60d": round(max(0.0, min(position60, 1.0)), 3),
            }
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
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


def _stock_screen_score(symbol: str, snapshot: dict) -> tuple[float, list[str]]:
    """
    第一轮只看量价/趋势，不让 AI 在整个股票池里盲选。

    目标不是预测涨跌，而是找出“今天值得进一步搜新闻”的异常股票。
    同时关注上涨、下跌、放量、趋势和突破/超跌，避免旧版只偏向大跌股。
    """
    try:
        day_change = float(snapshot.get("day_change_pct", 0.0))
        change_5d = float(snapshot.get("change_5d_pct", 0.0))
        month_change = float(snapshot.get("month_change_pct", 0.0))
        volatility = max(float(snapshot.get("volatility_20_pct", 0.0)), 0.25)
        volume_ratio = max(float(snapshot.get("volume_ratio_20", 1.0)), 0.0)
        position20 = float(snapshot.get("position_20d", 0.5))
        ma20_gap = float(snapshot.get("ma20_gap_pct", 0.0))
    except (TypeError, ValueError):
        return 0.0, []

    score = 0.0
    reasons = []

    # 1) 当日异常波动：使用绝对值，因此上涨/下跌都能入选。
    standardized_move = abs(day_change) / volatility
    score += min(standardized_move, 3.0) * 15.0
    if standardized_move >= 0.75:
        reasons.append("当日波动显著")

    # 2) 放量通常意味着事件正在被市场交易。
    if volume_ratio > 1.0:
        score += min(volume_ratio - 1.0, 2.0) * 12.0
    if volume_ratio >= 1.5:
        reasons.append("成交量放大")

    # 3) 5日和20日趋势，避免只盯单日噪声。
    score += min(abs(change_5d) / max(volatility * 2.2, 1.0), 2.5) * 7.0
    score += min(abs(month_change) / max(volatility * 4.0, 2.0), 2.0) * 5.0
    if abs(change_5d) >= max(4.0, volatility * 2.0):
        reasons.append("5日趋势突出")

    # 4) 靠近20日极值时给少量加分，用于发现突破/超跌。
    if position20 >= 0.90:
        score += 7.0
        reasons.append("接近20日高位")
    elif position20 <= 0.10:
        score += 7.0
        reasons.append("接近20日低位")

    # 5) 均线偏离过大说明处于强趋势或风险释放期，但权重不能过高。
    score += min(abs(ma20_gap) / 8.0, 1.5) * 4.0

    # 核心公司只给非常轻的基础权重，避免大公司垄断候选名单。
    if symbol in CORE_COMPANY_UNIVERSE:
        score += 1.5

    return round(score, 3), reasons[:4]


def _sector_of(symbol: str) -> str:
    return str(COMPANY_SECTORS.get(symbol, "other"))


def _select_diverse_symbols(ranked, limit: int, *, max_per_sector: int | None = None):
    """按分数取前列，同时限制单一行业过度占位。"""
    if limit <= 0:
        return []

    max_per_sector = max_per_sector or max(4, limit // 6)
    selected = []
    selected_set = set()
    sector_counts = {}

    # 第一轮应用行业上限。
    for score, symbol in ranked:
        sector = _sector_of(symbol)
        if sector != "other" and sector_counts.get(sector, 0) >= max_per_sector:
            continue
        selected.append((score, symbol))
        selected_set.add(symbol)
        if sector != "other":
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= limit:
            return selected

    # 如果行业上限导致数量不足，再按总分补齐。
    for score, symbol in ranked:
        if symbol in selected_set:
            continue
        selected.append((score, symbol))
        selected_set.add(symbol)
        if len(selected) >= limit:
            break

    return selected


def rank_news_symbols(stock_snapshot, limit=50):
    """
    从完整股票池筛出需要抓逐股新闻的候选。

    生产环境的新行情快照包含 change_5d_pct / volume_ratio_20 /
    position_20d 等增强字段，此时使用新版综合评分。

    为保持原有测试和旧调用兼容：如果传入的是旧版最小快照
    （只有 day_change_pct / volatility_20_pct 等字段），则沿用旧版
    change / volatility 从小到大的排序规则。
    """
    if not isinstance(stock_snapshot, dict):
        return ()

    snapshots = [
        snapshot for snapshot in stock_snapshot.values()
        if isinstance(snapshot, dict)
    ]
    enhanced_keys = {
        "change_5d_pct",
        "volume_ratio_20",
        "position_20d",
        "ma20_gap_pct",
    }
    enhanced_mode = any(
        any(key in snapshot for key in enhanced_keys)
        for snapshot in snapshots
    )

    # 旧测试 / 旧调用兼容路径。
    if not enhanced_mode:
        ranked = []
        for symbol, snapshot in stock_snapshot.items():
            if not isinstance(snapshot, dict):
                continue
            try:
                change = float(snapshot["day_change_pct"])
                volatility = max(float(snapshot["volatility_20_pct"]), 0.1)
            except (KeyError, TypeError, ValueError):
                continue
            ranked.append((change / volatility, change, symbol))
        ranked.sort()
        return tuple(symbol for _, _, symbol in ranked[:limit])

    # 新生产路径：异常程度 + 放量 + 多周期趋势 + 行业分散。
    ranked = []
    for symbol, snapshot in stock_snapshot.items():
        if not isinstance(snapshot, dict):
            continue
        score, reasons = _stock_screen_score(symbol, snapshot)
        snapshot["screen_score"] = score
        snapshot["screen_reasons"] = reasons
        ranked.append((score, symbol))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    diversified = _select_diverse_symbols(ranked, int(limit))
    return tuple(symbol for _, symbol in diversified)


_EVENT_KEYWORDS = (
    # 财报 / 指引
    "earnings", "revenue", "eps", "guidance", "forecast", "outlook",
    "quarter", "results", "profit", "margin",
    # 资本动作
    "buyback", "repurchase", "dividend", "offering", "debt", "acquisition",
    "acquire", "merger", "spin-off", "spinoff",
    # 监管 / 诉讼 / 医药
    "sec", "fda", "doj", "ftc", "lawsuit", "settlement", "approval",
    "trial", "investigation", "antitrust",
    # 公司经营与重大事件
    "contract", "partnership", "launch", "orders", "layoffs", "ceo", "cfo",
    "recall", "cyber", "breach", "tariff", "export", "sanction",
    # 市场评价
    "upgrade", "downgrade", "price target", "initiates", "rating",
)


def _news_event_score(text: str) -> float:
    """用标题中的重大事件词给第二轮新闻筛选加权，不替代 AI 语义判断。"""
    lowered = (text or "").lower()
    if not lowered:
        return 0.0

    hits = 0
    for keyword in _EVENT_KEYWORDS:
        # 单词使用边界匹配，避免 "sec" 命中 "second" 之类的误判。
        if re.fullmatch(r"[a-z0-9]+", keyword):
            matched = re.search(rf"\\b{re.escape(keyword)}\\b", lowered) is not None
        else:
            matched = keyword in lowered
        hits += int(matched)

    headline_count = min(len([line for line in text.splitlines() if line.strip()]), 10)
    return min(hits * 2.5 + headline_count * 0.6, 24.0)


def _choose_ai_company_candidates(compact_sources, collected):
    """
    第二轮：在已抓新闻的股票中，根据市场异常 + 新闻事件密度再次缩小范围。

    返回：
      news_prefilter_symbols: 新闻二筛后的约28只
      ai_symbols: 真正送给 AI 深度比较的约16只
    """
    stock_snapshot = collected.get("stock_snapshot", {})

    screened = [
        str(symbol).upper()
        for symbol in collected.get("screened_symbols", [])
        if str(symbol).upper() in stock_snapshot
    ]

    # 兼容旧测试夹具和旧调用：旧版 collected 里可能没有 screened_symbols。
    # 优先从逐股新闻/公司来源恢复候选；仍为空时再退回 stock_snapshot。
    if not screened:
        source_symbols = []
        for item in compact_sources:
            if item.get("kind") not in {"company", "company_news"}:
                continue
            symbol = str(item.get("symbol") or "").upper()
            if symbol and symbol in stock_snapshot and symbol not in source_symbols:
                source_symbols.append(symbol)
        screened = source_symbols or [
            str(symbol).upper()
            for symbol in stock_snapshot
            if str(symbol).upper() in COMPANY_UNIVERSE
        ]

    if not screened:
        return [], []

    news_by_symbol = {}
    ir_by_symbol = {}
    for item in compact_sources:
        if item.get("status") != "SUCCESS" or not item.get("text"):
            continue
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue
        if item.get("kind") == "company_news":
            news_by_symbol.setdefault(symbol, []).append(item)
        elif item.get("kind") == "company":
            ir_by_symbol.setdefault(symbol, []).append(item)

    ranked = []
    for symbol in screened:
        snapshot = stock_snapshot.get(symbol, {})
        market_score = float(snapshot.get("screen_score", 0.0) or 0.0)
        news_text = "\n".join(item.get("text", "") for item in news_by_symbol.get(symbol, []))
        ir_text = "\n".join(item.get("text", "") for item in ir_by_symbol.get(symbol, []))

        event_score = _news_event_score(news_text)
        # IR只给很小加成，避免固定IR公司长期霸榜。
        ir_bonus = min(_news_event_score(ir_text) * 0.20, 3.0)
        source_bonus = 2.0 if news_by_symbol.get(symbol) else 0.0

        total = market_score + event_score + ir_bonus + source_bonus
        ranked.append((round(total, 3), symbol))

        snapshot["news_event_score"] = round(event_score, 3)
        snapshot["candidate_score"] = round(total, 3)

    ranked.sort(key=lambda item: (-item[0], item[1]))

    news_limit = min(int(SCREENING_CONFIG.get("news_prefilter_size", 28)), len(ranked))
    # 新闻二筛允许每行业多一些，避免过早丢掉真正的行业主线。
    news_ranked = _select_diverse_symbols(
        ranked,
        news_limit,
        max_per_sector=max(4, news_limit // 5),
    )

    ai_limit = min(int(SCREENING_CONFIG.get("ai_candidate_size", 16)), len(news_ranked))
    ai_ranked = _select_diverse_symbols(
        news_ranked,
        ai_limit,
        max_per_sector=max(3, ai_limit // 5),
    )

    return [symbol for _, symbol in news_ranked], [symbol for _, symbol in ai_ranked]


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
        news_limit = min(
            int(SCREENING_CONFIG.get("market_prefilter_size", 60)),
            len(stock_snapshot),
        )
        news_symbols = rank_news_symbols(stock_snapshot, limit=news_limit) if full else ()
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
            "screening_summary": {
                "universe": len(COMPANY_UNIVERSE),
                "market_data": len(stock_snapshot),
                "market_prefilter": len(news_symbols),
                "news_prefilter_target": int(SCREENING_CONFIG.get("news_prefilter_size", 28)),
                "ai_candidate_target": int(SCREENING_CONFIG.get("ai_candidate_size", 16)),
                "final_target": int(SCREENING_CONFIG.get("final_company_count", 8)),
            },
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
        except StopIteration as exc:
            return {
                "name": name, "url": url, "kind": kind, "core": core,
                "status": "MOCK_EXHAUSTED", "text": "", "message": str(exc),
            }
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
        except StopIteration as exc:
            return {
                "name": name, "url": url, "kind": "company_news", "symbol": symbol,
                "core": False, "status": "MOCK_EXHAUSTED", "text": "", "message": str(exc),
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
        prompt += "\n市场标的中文说明：\n" + json.dumps(SIGNAL_NAMES, ensure_ascii=False)
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
        prediction_prompt += "\n市场标的中文说明：\n" + json.dumps(SIGNAL_NAMES, ensure_ascii=False)
        prediction_prompt += "\n宏观、政策与财经证据：\n" + json.dumps(macro_sources, ensure_ascii=False)
        prediction_prompt += "\n允许预测的完整对象：\n" + json.dumps(PREDICTION_TARGETS, ensure_ascii=False)
        prediction_prompt += "\n预测对象分组：\n" + json.dumps(PREDICTION_GROUPS, ensure_ascii=False)
        prediction_prompt += """
\n请单独生成跨资产预测，只输出以下JSON：
{"predictions":[{"horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,"thesis":"","invalidation":"","sensors":[],"evidence_ids":[]}]}

必须正好4项且target互不重复。
选择原则：
1. 至少1项来自美国大盘/风格；
2. 至少1项来自美国行业相对强弱；
3. 至少1项来自利率或信用；
4. 第4项从商品、美元、波动率或海外市场中选择当天增量信号最强者。
5. 不要机械重复 SPY、QQQ/SPY、XLF/SPY、XLE/SPY、TLT；如果其他行业、海外市场、商品或信用出现更强证据，应主动替换。
6. 只能从“允许预测的完整对象”中选择；不能凭记忆添加其他标的。
7. 不得4项全部表达同一方向或同一风险因子；优先保持跨资产分散。
8. 必须结合输入证据选择有增量信息的对象，不因标的知名度高而优先。
9. 周期只能3/5/10/15；概率0.50-0.80；每项必须有简洁中文逻辑、可观察失效条件和证据编号。
10. 绝对方向使用UP/DOWN/NEUTRAL；相对方向使用OUTPERFORM/UNDERPERFORM/NEUTRAL。
"""
        prediction_system = "你是跨资产预测负责人。以分散、可验证和可复盘为首要原则，严格输出JSON。"
        prediction_result = self._complete_json(
            "cross_asset_predictions", prediction_system, prediction_prompt
        )
        cross_asset_predictions = prediction_result.get("predictions", [])
        if isinstance(cross_asset_predictions, list) and cross_asset_predictions:
            parsed["predictions"] = self._limit_predictions(cross_asset_predictions)

        # 公司部分采用三层漏斗：
        # 完整股票池 -> 行情预筛 -> 新闻二筛 -> AI候选 -> 最终8只。
        news_prefilter_symbols, ai_symbols = _choose_ai_company_candidates(
            compact_sources, collected
        )
        ai_symbol_set = set(ai_symbols)

        company_sources = [
            item for item in compact_sources
            if item.get("kind") in {"company", "company_news"}
            and item.get("status") == "SUCCESS"
            and item.get("text")
            and str(item.get("symbol") or "").upper() in ai_symbol_set
        ]

        stock_snapshot = collected.get("stock_snapshot", {})
        candidate_snapshot = {
            symbol: stock_snapshot.get(symbol, {})
            for symbol in ai_symbols
            if symbol in stock_snapshot
        }
        candidate_names = {
            symbol: COMPANY_NAMES.get(symbol, symbol)
            for symbol in ai_symbols
        }

        # 便于HTML或审计模块以后展示“池子有多大、最后怎么筛出来的”。
        collected["news_prefilter_symbols"] = news_prefilter_symbols
        collected["ai_candidate_symbols"] = ai_symbols

        if company_sources and ai_symbols:
            company_prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
            company_prompt += "\n今日二次筛选后的候选代码（只能从这里选）：\n" + json.dumps(ai_symbols, ensure_ascii=False)
            company_prompt += "\n候选个股市场状态与筛选分数：\n" + json.dumps(candidate_snapshot, ensure_ascii=False)
            company_prompt += "\n候选股票代码与标准中文名：\n" + json.dumps(candidate_names, ensure_ascii=False)
            company_prompt += "\n候选公司的官方材料与逐股新闻：\n" + json.dumps(company_sources, ensure_ascii=False)
            company_prompt += """
\n从上述候选中按“增量信息强度 + 价格反应 + 风险收益比 + 行业分散”排序，
输出最多12个候选，系统随后会再压缩到最终8个。JSON格式：
{"company_signals":[{"company":"中文公司名","ticker":"股票代码","stance":"关注|等待|回避","brief":"事实→股票影响→动作","trigger":"何种可观察条件出现才行动","risk":"最大风险或失效条件","source":"输入中的来源名"}]}

硬约束：
1. 只输出JSON；ticker只能来自“今日二次筛选后的候选代码”，禁止从记忆补充其他股票。
2. 除ticker和source外全部使用简体中文。
3. 按优先级排序；不要因为公司知名度高而优先，优先真正有当日增量信息的股票。
4. 同一行业尽量不超过2只；如果同一行业确有明显主线，可给到3只，但必须各有不同催化剂。
5. “关注”最多4只，必须具备可验证的正向逻辑，并满足以下至少一种：
   A. 上升趋势中的可控回撤/止跌；
   B. 放量突破或趋势重新转强，但触发条件必须防止追高。
6. 明确重大利空导致下跌、且核心逻辑受损的，应优先“回避”，不能机械当作抄底机会。
7. “等待”用于方向尚可但价格、成交量或事件确认不足的股票。
8. 不能只凭网站介绍或单条媒体标题；公司官网页面若只有宣传性内容，不得作为主要论据。
9. 每家公司结论必须不同，brief不超过55字，trigger和risk各不超过35字。
10. 不编造买卖价格，不承诺收益，不为了凑数量牺牲证据质量。
"""
            company_system = (
                "你是中文美股研究负责人。你面对的是已经通过量价和新闻初筛的候选池。"
                "你的任务是做最后一轮精挑细选，而不是偏爱熟悉的大公司。"
                "只依据输入证据，严格输出JSON。"
            )
            company_result = self._complete_json("company", company_system, company_prompt)
            signals = company_result.get("company_signals", [])
            parsed["company_signals"] = self._limit_company_signals(
                signals,
                stock_snapshot,
            )
        else:
            parsed["company_signals"] = []
        return parsed

    @staticmethod
    def _limit_predictions(predictions):
        """
        最终跨资产预测守门：
        - 只允许 market.py 定义的 PREDICTION_TARGETS；
        - 去重；
        - 最多4项；
        - 尽量避免同一类别占满全部名额。

        AI prompt 已负责要求跨资产分散；这里再做一次轻量防守，
        但不会为了形式强行制造缺乏证据的预测。
        """
        if not isinstance(predictions, list):
            return []

        allowed = set(PREDICTION_TARGETS)
        target_group = {}
        for group, targets in PREDICTION_GROUPS.items():
            for target in targets:
                target_group[str(target).upper()] = group

        normalized = []
        seen = set()
        for raw in predictions:
            if not isinstance(raw, dict):
                continue
            target = str(raw.get("target", "")).strip().upper()
            if target not in allowed or target in seen:
                continue
            item = dict(raw)
            item["target"] = target
            normalized.append(item)
            seen.add(target)

        selected = []
        selected_targets = set()
        group_counts = {}

        # 第一轮：单组最多2项，避免4项全挤在同一类。
        for item in normalized:
            target = item["target"]
            group = target_group.get(target, "other")
            if group_counts.get(group, 0) >= 2:
                continue
            selected.append(item)
            selected_targets.add(target)
            group_counts[group] = group_counts.get(group, 0) + 1
            if len(selected) >= 4:
                return selected

        # 第二轮：若AI有效输出不足4项，再按原始排序补齐。
        for item in normalized:
            if item["target"] in selected_targets:
                continue
            selected.append(item)
            selected_targets.add(item["target"])
            if len(selected) >= 4:
                break

        return selected

    @staticmethod
    def _limit_company_signals(signals, stock_snapshot, allowed_tickers=None):
        if not isinstance(signals, list):
            return []

        allowed = set(COMPANY_UNIVERSE)
        if allowed_tickers is not None:
            allowed &= {str(symbol).upper() for symbol in allowed_tickers}

        final_limit = int(SCREENING_CONFIG.get("final_company_count", 8))
        max_per_sector = int(SCREENING_CONFIG.get("max_per_sector", 2))

        normalized = []
        seen = set()
        focus_count = 0

        # 第一步只做合法性、去重和 stance 守门，不因为行业直接丢股票。
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
                    day_change = float(snapshot.get("day_change_pct", 0.0))
                    volatility = max(float(snapshot.get("volatility_20_pct", 0.0)), 0.1)

                    # 兼容旧版快照：没有增强字段时，维持原来的“可控回撤”判断。
                    has_enhanced_fields = any(
                        key in snapshot
                        for key in (
                            "volume_ratio_20",
                            "above_ma20",
                            "above_ma50",
                            "ma20_gap_pct",
                        )
                    )

                    if not has_enhanced_fields:
                        actionable = day_change <= -0.25 * volatility
                    else:
                        volume_ratio = float(snapshot.get("volume_ratio_20", 1.0))
                        above_ma20 = bool(snapshot.get("above_ma20", False))
                        above_ma50 = bool(snapshot.get("above_ma50", False))
                        ma20_gap = float(snapshot.get("ma20_gap_pct", 0.0))

                        controlled_pullback = (
                            day_change <= -0.25 * volatility
                            and day_change >= -2.25 * volatility
                            and (above_ma20 or above_ma50)
                        )
                        confirmed_breakout = (
                            day_change >= 0.35 * volatility
                            and volume_ratio >= 1.30
                            and above_ma20
                            and above_ma50
                            and ma20_gap <= 10.0
                        )
                        actionable = controlled_pullback or confirmed_breakout
                except (TypeError, ValueError):
                    actionable = False

                # 保持原测试/原产品契约：最多4只“关注”。
                if focus_count >= 4 or not actionable:
                    stance = "等待"

            if stance == "关注":
                focus_count += 1

            item["ticker"] = ticker
            item["company"] = COMPANY_NAMES.get(
                ticker, item.get("company") or ticker
            )
            item["stance"] = stance
            item["_sector"] = _sector_of(ticker)
            normalized.append(item)

        # 第二步做“软行业分散”：
        # 先按每行业上限取，剩余名额再用被延后的高优先级股票补齐。
        selected = []
        deferred = []
        sector_counts = {}

        for item in normalized:
            sector = item.pop("_sector", "other")
            if (
                sector != "other"
                and sector_counts.get(sector, 0) >= max_per_sector
            ):
                item["_deferred_sector"] = sector
                deferred.append(item)
                continue

            selected.append(item)
            if sector != "other":
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
            if len(selected) >= final_limit:
                return selected

        # 不因行业上限导致结果数量缩水；测试中的5个合法ticker仍应保留5个。
        for item in deferred:
            item.pop("_deferred_sector", None)
            selected.append(item)
            if len(selected) >= final_limit:
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
            report = re.sub(
    r"<body([^>]*)>",
    r"<body\1>" + link,
    report,
    count=1,
    flags=re.I
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
