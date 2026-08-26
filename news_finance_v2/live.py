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


# 一些新经济/事件股在旧版 sources.py 中可能只有 ticker，没有中文名。
# 这里做兜底，避免页面出现“重点公司（HOOD）”这种泛化标题。
_FALLBACK_COMPANY_NAMES = {
    "HOOD": "Robinhood",
    "COIN": "Coinbase",
    "TEM": "Tempus AI",
    "CRCL": "Circle",
    "RKLB": "Rocket Lab",
    "ASTS": "AST SpaceMobile",
    "LUNR": "Intuitive Machines",
    "RDW": "Redwire",
    "OKLO": "Oklo",
    "SMR": "NuScale Power",
    "LEU": "Centrus Energy",
    "IONQ": "IonQ",
    "RGTI": "Rigetti Computing",
    "QBTS": "D-Wave Quantum",
    "SMCI": "超微电脑",
    "VRT": "Vertiv",
    "APP": "AppLovin",
    "CRWV": "CoreWeave",
    "NBIS": "Nebius",
    "MSTR": "Strategy",
    "HCA": "HCA医疗",
    "FCX": "自由港麦克莫兰",
    "TGT": "塔吉特",
    "ROST": "罗斯百货",
}

_GENERIC_COMPANY_NAMES = {
    "",
    "重点公司",
    "重点标的",
    "公司",
    "个股",
    "候选公司",
}


def _company_display_name(symbol: str, fallback: str | None = None) -> str:
    symbol = str(symbol or "").upper()
    configured = str(COMPANY_NAMES.get(symbol, "") or "").strip()
    if configured and configured not in _GENERIC_COMPANY_NAMES:
        return configured

    fallback_name = str(fallback or "").strip()
    if fallback_name and fallback_name not in _GENERIC_COMPANY_NAMES:
        return fallback_name

    return _FALLBACK_COMPANY_NAMES.get(symbol, symbol)


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


# -------------------------------------------------------------------
# Market calendar: "有日程" != "值得交易".
# The raw BLS calendar is retained as evidence, but low-impact releases
# are removed from the displayed market calendar unless AI finds a
# stronger reason to keep them.
# -------------------------------------------------------------------

_MAJOR_CALENDAR_KEYWORDS = (
    # Inflation / growth / labor
    "consumer price index", "cpi",
    "producer price index", "ppi",
    "personal income and outlays", "pce",
    "gross domestic product", "gdp",
    "employment situation", "nonfarm", "payroll",
    "job openings and labor turnover", "jolts",
    "retail sales", "ism", "pmi",
    "employment cost index",
    "consumer sentiment", "inflation expectations",
    # Fed / rates
    "fomc", "federal reserve", "fed chair", "chair powell",
    "chair warsh", "jackson hole", "minutes",
    "treasury auction", "10-year", "30-year",
    # Energy / policy / geopolitical
    "opec", "sanction", "tariff", "white house",
    "treasury secretary", "ustr", "state department",
    # Earnings / corporate catalysts
    "earnings", "quarterly results", "financial results",
    "investor day", "guidance", "conference call",
)

_LOW_VALUE_BLS_KEYWORDS = (
    "summer youth labor force",
    "access to and use of leave",
    "employment projections and occupational outlook handbook",
    "worker displacement",
    "county employment and wages",
    "current employment statistics preliminary benchmark",
    "metropolitan area employment and unemployment",
    "occupational employment and wage statistics",
    "business employment dynamics",
)


def _is_market_relevant_raw_event(title: str) -> bool:
    normalized = " ".join(str(title or "").lower().split())
    if not normalized:
        return False
    if any(key in normalized for key in _LOW_VALUE_BLS_KEYWORDS):
        return False
    return any(key in normalized for key in _MAJOR_CALENDAR_KEYWORDS)


def _filter_raw_calendar_events(events, *, start: date, days: int = 14):
    """Fallback filter used when AI does not produce a reliable calendar."""
    end = start + timedelta(days=days)
    selected = []
    seen = set()

    for item in events or []:
        try:
            event_date = date.fromisoformat(str(item.get("date", ""))[:10])
        except ValueError:
            continue
        if not (start <= event_date < end):
            continue

        title = str(item.get("title") or "").strip()
        source = str(item.get("source") or "").strip() or "官方来源"
        if not _is_market_relevant_raw_event(title):
            continue

        key = (event_date.isoformat(), re.sub(r"\W+", "", title.lower()))
        if key in seen:
            continue
        seen.add(key)
        selected.append({
            "date": event_date.isoformat(),
            "title": title,
            "source": source,
        })

    return sorted(selected, key=lambda x: (x["date"], x["title"]))



_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_MONTH_ABBR_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _calendar_date_for_month_day(month: int, day: int, *, start: date) -> date | None:
    year = start.year
    # If a 14-day window crosses New Year, allow January to belong to next year.
    if start.month >= 11 and month <= 2:
        year += 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _calendar_local_importance(title: str) -> int:
    """Deterministic market-impact score used for ranking verified dated events."""
    value = " ".join(str(title or "").lower().split())

    if "personal income and outlays" in value or "pce" in value:
        return 100
    if ("chair" in value or "主席" in value) and ("jackson hole" in value or "fed" in value or "federal reserve" in value):
        return 99
    if "employment situation" in value or "nonfarm" in value or "非农" in value:
        return 98
    if "nvidia" in value and ("financial results" in value or "earnings" in value or "财报" in value):
        return 97
    if "consumer price index" in value or re.search(r"\bcpi\b", value):
        return 96
    if "gdp" in value and ("estimate" in value or "国内生产总值" in value):
        return 93
    if "manufacturing pmi" in value:
        return 91
    if "consumer sentiment" in value or "inflation expectation" in value or "密歇根" in value:
        return 90
    if "job openings and labor turnover" in value or "jolts" in value:
        return 89
    if "services pmi" in value:
        return 88
    if "producer price index" in value or re.search(r"\bppi\b", value):
        return 87
    if "treasury" in value and "auction" in value:
        return 82
    if "productivity and costs" in value:
        return 72
    if "international trade" in value or "trade in goods and services" in value:
        return 70
    if _is_market_relevant_raw_event(title):
        return 65
    return 0


def _event_title_key(title: str) -> str:
    value = str(title or "").lower()
    aliases = (
        ("personal income and outlays", "pce"),
        ("pce price index", "pce"),
        ("gdp (second estimate)", "gdp"),
        ("gdp second estimate", "gdp"),
        ("employment situation", "nonfarm"),
        ("job openings and labor turnover survey", "jolts"),
        ("nvidia 2nd quarter fy27 financial results", "nvidiaearnings"),
        ("nvidia second-quarter financial results", "nvidiaearnings"),
        ("chairman kevin warsh", "fedchair"),
        ("jackson hole", "fedchair"),
        ("consumer sentiment", "michigan"),
        ("manufacturing pmi", "ismmanufacturing"),
        ("services pmi", "ismservices"),
    )
    for needle, key in aliases:
        if needle in value:
            return key
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)


def _parse_dedicated_calendar_events(name: str, html_text: str, *, start: date, days: int = 14):
    """
    Deterministically extract dated events from dedicated official/IR schedule pages.
    The AI may rank events, but it no longer has to invent dates from prose.
    """
    end = start + timedelta(days=days)
    soup = BeautifulSoup(html_text or "", "html.parser")
    plain = _page_text(html_text or "")
    events = []

    def add(event_date: date | None, title: str, source: str):
        if event_date is None or not (start <= event_date < end):
            return
        title = " ".join(str(title or "").split()).strip()
        if not title:
            return
        events.append({
            "date": event_date.isoformat(),
            "title": title,
            "source": source,
        })

    # BEA release schedule: table rows contain month/day/time + release title.
    if name == "BEA":
        for row in soup.find_all("tr"):
            row_text = " ".join(row.stripped_strings)
            match = re.search(
                r"\b(" + "|".join(m.title() for m in _MONTH_NUM) + r")\s+(\d{1,2})\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b",
                row_text,
                re.I,
            )
            if not match:
                continue
            month = _MONTH_NUM[match.group(1).lower()]
            event_date = _calendar_date_for_month_day(month, int(match.group(2)), start=start)
            title = row_text[match.end():].strip()
            title = re.sub(r"^(?:News|Data|Article)\s+", "", title, flags=re.I)
            title = re.sub(r"\s+View$", "", title, flags=re.I)
            if title:
                add(event_date, title, "BEA")

    # Federal Reserve calendar: for chair speeches, the date number often follows
    # the speech details in the page's accessible text.
    if name.startswith("Federal Reserve"):
        month_year = re.search(
            r"\b(" + "|".join(m.title() for m in _MONTH_NUM) + r")\s+(\d{4})\b",
            plain,
            re.I,
        )
        if month_year:
            month = _MONTH_NUM[month_year.group(1).lower()]
            year = int(month_year.group(2))
            lines = plain.splitlines()
            for i, line in enumerate(lines):
                low = line.lower()
                if "speech - chairman" not in low and not ("chairman" in low and "speech" in low):
                    continue
                nearby = lines[i:i + 12]
                day_num = None
                for candidate in nearby[1:]:
                    if re.fullmatch(r"\d{1,2}", candidate.strip()):
                        day_num = int(candidate.strip())
                        break
                if not day_num:
                    continue
                try:
                    event_date = date(year, month, day_num)
                except ValueError:
                    continue
                detail = " ".join(nearby).lower()
                title = "Fed主席Jackson Hole讲话" if "jackson hole" in detail else "Fed主席讲话"
                add(event_date, title, "Federal Reserve")

    # Michigan: "Next data release: Friday, August 28, 2026 ... Final August data".
    if name == "Michigan Surveys of Consumers":
        match = re.search(
            r"Next data release:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
            r"(" + "|".join(m.title() for m in _MONTH_NUM) + r")\s+(\d{1,2}),\s+(\d{4})",
            plain,
            re.I,
        )
        if match:
            month = _MONTH_NUM[match.group(1).lower()]
            add(
                date(int(match.group(3)), month, int(match.group(2))),
                "密歇根消费者信心终值",
                "Michigan Surveys of Consumers",
            )

    # NVIDIA home/events page.
    if name == "NVIDIA IR":
        lines = plain.splitlines()
        for i, line in enumerate(lines):
            if "NVIDIA 2nd Quarter FY27 Financial Results" not in line:
                continue
            window = lines[max(0, i - 4):i + 3]
            date_match = None
            for candidate in window:
                date_match = re.search(
                    r"\b(" + "|".join(_MONTH_ABBR_NUM) + r")\s+(\d{1,2}),\s+(\d{4})\b",
                    candidate,
                    re.I,
                )
                if date_match:
                    break
            if date_match:
                month = _MONTH_ABBR_NUM[date_match.group(1).lower()]
                add(
                    date(int(date_match.group(3)), month, int(date_match.group(2))),
                    "NVIDIA FY2027 Q2财报",
                    "NVIDIA IR",
                )

    # ISM official 2026 release-date table.
    if name == "ISM PMI Calendar":
        for row in soup.find_all("tr"):
            cells = [" ".join(cell.stripped_strings) for cell in row.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            month_match = re.search(
                r"\b(" + "|".join(m.title() for m in _MONTH_NUM) + r")\s+(\d{4})\b",
                cells[0],
                re.I,
            )
            if not month_match:
                continue
            month = _MONTH_NUM[month_match.group(1).lower()]
            year = int(month_match.group(2))
            nums = []
            for cell in cells[1:3]:
                m = re.search(r"\b(\d{1,2})\b", cell)
                nums.append(int(m.group(1)) if m else None)
            if nums[0]:
                add(date(year, month, nums[0]), "ISM制造业PMI", "ISM")
            if nums[1]:
                add(date(year, month, nums[1]), "ISM服务业PMI", "ISM")

    # Deduplicate source parser output.
    deduped = []
    seen = set()
    for item in events:
        key = (item["date"], _event_title_key(item["title"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_market_calendar_events(ai_events, raw_events, *, start: date, days: int = 14, target_count: int = 8):
    """
    Build the displayed calendar from verified dated candidates first.

    Rules:
    - If at least 8 verified/high-confidence events exist, display exactly 8.
    - If fewer than 8 exist, display fewer; never fabricate.
    - Raw official/IR parsed dates outrank AI-only dates.
    - AI-only events are fallback candidates and cannot overwrite a verified
      event with a conflicting date.
    """
    end = start + timedelta(days=days)
    candidates = []
    title_keys_from_verified = set()

    # 1) Verified structured candidates from BLS ICS and dedicated schedule parsers.
    for item in raw_events or []:
        if not isinstance(item, dict):
            continue
        try:
            event_date = date.fromisoformat(str(item.get("date", ""))[:10])
        except ValueError:
            continue
        if not (start <= event_date < end):
            continue
        title = " ".join(str(item.get("title") or "").split()).strip()
        source = " ".join(str(item.get("source") or "").split()).strip() or "官方来源"
        if not title:
            continue

        score = _calendar_local_importance(title)
        if score < 58:
            continue

        title_key = _event_title_key(title)
        title_keys_from_verified.add(title_key)
        candidates.append({
            "date": event_date.isoformat(),
            "title": title,
            "source": source,
            "_importance": score,
            "_verified": True,
            "_title_key": title_key,
        })

    # 2) AI may discover explicit policy/geopolitical/company dates from other evidence.
    #    It can add events, but cannot replace a verified event's date.
    if not isinstance(ai_events, list):
        ai_events = []

    for item in ai_events:
        if not isinstance(item, dict):
            continue
        try:
            event_date = date.fromisoformat(str(item.get("date", ""))[:10])
        except ValueError:
            continue
        if not (start <= event_date < end):
            continue

        title = " ".join(str(item.get("title") or "").split()).strip()
        source = " ".join(str(item.get("source") or "").split()).strip()
        if not title or not source:
            continue

        title_key = _event_title_key(title)
        if title_key in title_keys_from_verified:
            # This is the safeguard that prevents, for example, an AI-parsed
            # Jackson Hole speech from moving from the verified Aug 28 date to Aug 27.
            continue

        try:
            ai_score = int(float(item.get("importance", 0)))
        except (TypeError, ValueError):
            ai_score = 0
        local_score = _calendar_local_importance(title)
        score = max(local_score, min(ai_score, 92))
        if score < 58:
            continue

        candidates.append({
            "date": event_date.isoformat(),
            "title": title,
            "source": source,
            "_importance": score,
            "_verified": False,
            "_title_key": title_key,
        })

    # 3) Deduplicate by conceptual title. Prefer verified, then higher impact.
    best_by_title = {}
    for item in candidates:
        key = item["_title_key"]
        current = best_by_title.get(key)
        if current is None:
            best_by_title[key] = item
            continue
        current_rank = (1 if current["_verified"] else 0, current["_importance"])
        item_rank = (1 if item["_verified"] else 0, item["_importance"])
        if item_rank > current_rank:
            best_by_title[key] = item

    ranked = list(best_by_title.values())
    ranked.sort(
        key=lambda x: (
            -x["_importance"],
            0 if x["_verified"] else 1,
            x["date"],
            x["title"],
        )
    )

    # 4) Keep at most 3 per day, and exactly target_count when enough exist.
    selected = []
    per_day = {}
    for item in ranked:
        if per_day.get(item["date"], 0) >= 3:
            continue
        selected.append(item)
        per_day[item["date"]] = per_day.get(item["date"], 0) + 1
        if len(selected) >= target_count:
            break

    selected.sort(key=lambda x: (x["date"], -x["_importance"], x["title"]))
    return [
        {"date": x["date"], "title": x["title"], "source": x["source"]}
        for x in selected
    ]



def _dedicated_calendar_specs(report_date: date):
    """
    High-value schedule pages used only to improve event discovery.
    They do not change the calendar UI.

    These pages are selected because they publish explicit forward dates:
    - BEA: PCE/GDP/trade release schedule
    - Federal Reserve: monthly official calendar, including speeches/FOMC
    - Michigan: next Consumer Sentiment release
    - NVIDIA IR: major index-moving earnings/events
    """
    month_slug = report_date.strftime("%B").lower()
    next_month_date = (report_date.replace(day=28) + timedelta(days=7)).replace(day=1)
    next_month_slug = next_month_date.strftime("%B").lower()

    specs = [
        ("BEA", "https://www.bea.gov/news/schedule", "calendar", False),
        (
            "Federal Reserve",
            f"https://www.federalreserve.gov/newsevents/{report_date.year}-{month_slug}.htm",
            "calendar",
            False,
        ),
        (
            "Federal Reserve Next Month",
            f"https://www.federalreserve.gov/newsevents/{next_month_date.year}-{next_month_slug}.htm",
            "calendar",
            False,
        ),
        (
            "Michigan Surveys of Consumers",
            "https://www.sca.isr.umich.edu/",
            "calendar",
            False,
        ),
        (
            "NVIDIA IR",
            "https://investor.nvidia.com/home/default.aspx",
            "calendar",
            False,
        ),
        (
            "ISM PMI Calendar",
            "https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/",
            "calendar",
            False,
        ),
    ]
    return specs


_DISPLAY_META_LEAK_MARKERS = (
    "absent",
    "schedule evidence",
    "calendar text",
    "later dates include",
    "input confirms",
    "input only confirms",
    "source text",
    "page text",
    "not found in",
    "no date found",
    "未找到",
    "输入仅确认",
    "日程文本",
    "来源页面",
    "抓取",
)


def _has_display_meta_leak(text: str) -> bool:
    """
    Detect source-debug / prompt-debug language that should never appear
    in reader-facing Chinese prose.
    """
    value = " ".join(str(text or "").split())
    if not value:
        return False

    lowered = value.lower()
    if any(marker in lowered for marker in _DISPLAY_META_LEAK_MARKERS):
        return True

    # Reader-facing Simplified Chinese may legitimately contain tickers/acronyms
    # such as CPI/PCE/SPY. What we reject is a natural-language English clause.
    for match in re.finditer(
        r"\b[A-Za-z][A-Za-z0-9'?-]*(?:\s+[A-Za-z][A-Za-z0-9'?-]*){2,}\b",
        value,
    ):
        words = match.group(0).split()
        # All-uppercase finance acronyms/tickers are acceptable.
        if all(word.upper() == word and len(word) <= 8 for word in words):
            continue
        return True

    return False


def _sanitize_media_themes(themes, source_records, limit: int = 5):
    """
    Keep MARKET FOCUS about the market, not about our data-collection process.

    - Drop any theme whose Chinese title/brief/impact contains prompt/source-debug leakage.
    - Keep only real source names from collected evidence.
    - Never let tickers or market symbols masquerade as source names.
    """
    valid_source_names = {
        str(record.get("name") or "").strip()
        for record in source_records or []
        if record.get("status") == "SUCCESS" and str(record.get("name") or "").strip()
    }

    cleaned = []
    for item in themes or []:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        brief = str(item.get("brief") or "").strip()
        impact = str(item.get("impact") or "").strip()

        if not title or not brief:
            continue

        if (
            _has_display_meta_leak(title)
            or _has_display_meta_leak(brief)
            or _has_display_meta_leak(impact)
        ):
            continue

        sources = []
        for source in item.get("sources", []) or []:
            source_name = str(source or "").strip()
            if source_name in valid_source_names:
                sources.append(source_name)

        item = dict(item)
        item["sources"] = list(dict.fromkeys(sources))[:3]
        cleaned.append(item)

        if len(cleaned) >= limit:
            break

    return cleaned


def _calendar_company_evidence(compact_sources, limit: int = 24):
    """
    Feed the master pass only company material likely to contain a scheduled,
    market-moving catalyst. This lets earnings / investor days compete with
    macro events without dumping the whole stock universe into the prompt.
    """
    event_words = (
        "earnings", "financial results", "quarterly results", "conference call",
        "webcast", "investor day", "guidance", "reports results",
        "财报", "业绩", "电话会议", "投资者日", "指引",
    )

    selected = []
    for item in compact_sources or []:
        if item.get("kind") not in {"company", "company_news"}:
            continue
        if item.get("status") != "SUCCESS":
            continue
        body = str(item.get("text") or "")
        if not body:
            continue
        lowered = body.lower()
        if not any(word in lowered for word in event_words):
            continue
        selected.append({
            "name": item.get("name"),
            "kind": item.get("kind"),
            "symbol": item.get("symbol"),
            "status": item.get("status"),
            "text": body[:1800],
        })
        if len(selected) >= limit:
            break
    return selected


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


def _default_market_context_loader(symbols):
    """
    批量读取跨资产 1日/5日/20日变化和趋势。

    注意：原有 collected["market"] 仍保持 {ticker: 最新价格}，
    不破坏数据库、验证和旧测试；新增的数据放在 market_context。
    """
    import yfinance as yf

    symbols = tuple(dict.fromkeys(str(symbol) for symbol in symbols if symbol))
    if not symbols:
        return {}

    try:
        frame = yf.download(
            list(symbols),
            period="3mo",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
    except Exception:
        return {}

    if frame is None or frame.empty:
        return {}

    result = {}
    for symbol in symbols:
        try:
            data = frame[symbol] if hasattr(frame.columns, "levels") else frame
            close = data["Close"].dropna()
            if len(close) < 22:
                continue

            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2])
            close_5d = float(close.iloc[-6]) if len(close) >= 6 else previous
            close_20d = float(close.iloc[-21])

            returns = close.pct_change().dropna().tail(20)
            volatility = max(float(returns.std()) * 100, 0.01)
            ma20 = float(close.tail(20).mean())

            result[symbol] = {
                "price": round(latest, 4),
                "day_change_pct": round((latest / previous - 1) * 100, 3),
                "change_5d_pct": round((latest / close_5d - 1) * 100, 3),
                "month_change_pct": round((latest / close_20d - 1) * 100, 3),
                "volatility_20_pct": round(volatility, 3),
                "above_ma20": latest >= ma20,
                "ma20_gap_pct": round((latest / ma20 - 1) * 100, 3) if ma20 else 0.0,
            }
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            continue

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


def _classify_stock_setup(snapshot: dict) -> tuple[str, float, list[str]]:
    """
    给第二轮选股增加“可执行性”维度。

    第一轮 screen_score 负责找异常；
    这里负责判断异常是否值得进入最终研究池：
    - constructive_pullback: 上升结构中的可控回撤
    - clean_breakout: 放量突破但不过热
    - steady_strength: 稳健强势
    - risk_breakdown: 破位/风险释放，适合进入“回避”候选
    - overextended: 大涨过热，只保留重大事件，不鼓励追涨
    - neutral: 暂无清晰技术形态
    """
    try:
        day_change = float(snapshot.get("day_change_pct", 0.0))
        change_5d = float(snapshot.get("change_5d_pct", 0.0))
        volatility = max(float(snapshot.get("volatility_20_pct", 0.0)), 0.25)
        volume_ratio = max(float(snapshot.get("volume_ratio_20", 1.0)), 0.0)
        above_ma20 = bool(snapshot.get("above_ma20", False))
        above_ma50 = bool(snapshot.get("above_ma50", False))
        ma20_gap = float(snapshot.get("ma20_gap_pct", 0.0))
        ma50_gap = float(snapshot.get("ma50_gap_pct", 0.0))
        position20 = float(snapshot.get("position_20d", 0.5))
    except (TypeError, ValueError):
        return "neutral", 0.0, []

    tags = []

    # 过热：这类股票可以进入新闻池，但不应霸占最终8只。
    if (
        day_change >= max(7.0, 1.8 * volatility)
        or ma20_gap >= 12.0
        or (position20 >= 0.97 and ma20_gap >= 8.0)
    ):
        tags.append("短线过热")
        return "overextended", -12.0, tags

    # 趋势中的回撤：更符合“等确认后参与”的可执行风格。
    if (
        day_change <= -0.20 * volatility
        and day_change >= -1.60 * volatility
        and above_ma50
        and ma50_gap >= -4.0
        and ma20_gap >= -7.0
    ):
        tags.append("上升结构中的可控回撤")
        return "constructive_pullback", 18.0, tags

    # 不过热的放量突破。
    if (
        day_change >= 0.30 * volatility
        and day_change <= 1.60 * volatility
        and volume_ratio >= 1.25
        and above_ma20
        and above_ma50
        and ma20_gap <= 8.0
    ):
        tags.append("放量转强")
        return "clean_breakout", 16.0, tags

    # 稳健强势：不是单日暴冲，而是5日结构较好。
    if (
        above_ma20
        and above_ma50
        and 0.0 <= day_change <= max(4.0, 1.0 * volatility)
        and change_5d >= max(2.0, 0.8 * volatility)
        and ma20_gap <= 7.0
    ):
        tags.append("趋势稳健")
        return "steady_strength", 10.0, tags

    # 明显破位也值得进入最终研究池，因为“回避”也是有价值的动作。
    if (
        day_change <= -0.80 * volatility
        and not above_ma20
        and (not above_ma50 or ma20_gap <= -5.0)
    ):
        tags.append("风险破位")
        return "risk_breakdown", 13.0, tags

    return "neutral", 0.0, tags


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
        setup_type, setup_score, setup_tags = _classify_stock_setup(snapshot)

        # IR只给很小加成，避免固定IR公司长期霸榜。
        ir_bonus = min(_news_event_score(ir_text) * 0.20, 3.0)
        source_bonus = 2.0 if news_by_symbol.get(symbol) else 0.0

        # 第二轮不再简单延续“谁涨跌最大谁优先”。
        # 让事件、可执行形态和风险形态获得更高权重，
        # 对短线过热股票降权，避免最终8只全是当日大涨股。
        total = (
            market_score * 0.45
            + event_score * 1.25
            + setup_score
            + ir_bonus
            + source_bonus
        )

        if setup_type == "overextended":
            # 若没有足够事件支撑，进一步降低“纯情绪暴冲股”的优先级。
            if event_score < 8.0:
                total -= 8.0

        ranked.append((round(total, 3), symbol))

        snapshot["news_event_score"] = round(event_score, 3)
        snapshot["setup_type"] = setup_type
        snapshot["setup_score"] = round(setup_score, 3)
        snapshot["setup_tags"] = setup_tags
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
    ai_ranked = _select_balanced_ai_symbols(
        news_ranked,
        stock_snapshot,
        ai_limit,
    )

    return [symbol for _, symbol in news_ranked], [symbol for _, symbol in ai_ranked]


def _select_balanced_ai_symbols(ranked, stock_snapshot, limit: int):
    """
    AI最终候选池做“软平衡”。

    目标不是强行凑类型，而是避免16只候选全部来自同一种
    单日暴涨形态。优先保证：
    - 过热股最多约25%
    - 同行业不过度集中
    - 可控回撤 / 突破 / 风险破位都有机会进入
    """
    if limit <= 0:
        return []

    max_overextended = max(2, limit // 4)
    max_per_sector = max(3, limit // 5)

    selected = []
    deferred = []
    sector_counts = {}
    overextended_count = 0

    # 第一轮：控制行业和过热股占比。
    for score, symbol in ranked:
        snapshot = stock_snapshot.get(symbol, {})
        setup_type = str(snapshot.get("setup_type", "neutral"))
        sector = _sector_of(symbol)

        if (
            setup_type == "overextended"
            and overextended_count >= max_overextended
        ):
            deferred.append((score, symbol))
            continue

        if (
            sector != "other"
            and sector_counts.get(sector, 0) >= max_per_sector
        ):
            deferred.append((score, symbol))
            continue

        selected.append((score, symbol))
        if setup_type == "overextended":
            overextended_count += 1
        if sector != "other":
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        if len(selected) >= limit:
            return selected

    # 第二轮：如果数量不足，再按分数补齐，不为了形式丢掉高质量候选。
    selected_symbols = {symbol for _, symbol in selected}
    for score, symbol in deferred:
        if symbol in selected_symbols:
            continue
        selected.append((score, symbol))
        selected_symbols.add(symbol)
        if len(selected) >= limit:
            break

    return selected


class HttpCollector:
    def __init__(
        self,
        settings: Settings,
        *,
        session=None,
        market_loader=None,
        stock_loader=None,
        market_context_loader=None,
    ):
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

        # 只有生产环境默认路径才自动额外抓跨资产趋势；
        # 测试/自定义session不会因为这项增强而触发真实网络请求。
        if market_context_loader is not None:
            self.market_context_loader = market_context_loader
        elif session is None and market_loader is None:
            self.market_context_loader = _default_market_context_loader
        else:
            self.market_context_loader = None

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

            # Dedicated forward-looking schedule pages.
            # Skipped for externally mocked sessions so existing finite-session tests
            # do not need extra mocked HTTP responses.
            calendar_specs = _dedicated_calendar_specs(self.settings.report_date)
            with ThreadPoolExecutor(max_workers=6) as executor:
                records += list(executor.map(lambda spec: self._fetch(*spec), calendar_specs))

        market = self.market_loader(list(SIGNALS))
        market_context = {}
        if full and self.market_context_loader is not None:
            try:
                market_context = self.market_context_loader(list(SIGNALS))
            except Exception:
                market_context = {}

        stock_snapshot = self.stock_loader(COMPANY_UNIVERSE) if full else {}
        news_limit = min(
            int(SCREENING_CONFIG.get("market_prefilter_size", 50)),
            50,
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
        events = []
        for record in records:
            if record.get("status") != "SUCCESS":
                continue
            events.extend(record.get("events", []) or [])

        return {
            "sources": records, "core_failures": core_failures,
            "evidence_kinds": evidence_kinds, "market": market,
            "market_context": market_context,
            "market_coverage": len(market) / len(SIGNALS), "events": events,
            "stock_snapshot": stock_snapshot,
            "universe_size": len(COMPANY_UNIVERSE),
            "screened_symbols": list(news_symbols),
            "screening_summary": {
                "universe": len(COMPANY_UNIVERSE),
                "market_data": len(stock_snapshot),
                "market_prefilter": len(news_symbols),
                "market_prefilter_cap": 50,
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
            parsed_events = []
            if status == "SUCCESS":
                if name == "BLS":
                    parsed_events = parse_ics_events(
                        response.text,
                        start=self.settings.report_date,
                    )
                elif kind == "calendar":
                    parsed_events = _parse_dedicated_calendar_events(
                        name,
                        response.text,
                        start=self.settings.report_date,
                        days=14,
                    )

            return {"name": name, "url": url, "final_url": str(response.url), "kind": kind,
                    "core": core, "status": status, "text": text,
                    "events": parsed_events,
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


# Multilingual display fields:
# base = Simplified Chinese; suffixes = zh_tw/en/bg/ru/ja/ko/fr/de/es/th.
# Analysis call count is unchanged; translations are returned in the same three AI calls.
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
        """
        JSON-safe OpenAI call for large multilingual payloads.

        - OpenAI: request JSON mode explicitly.
        - Allow a larger output budget for 11-language responses.
        - Retry once if parsing still fails.
        - Fall back to the old call signature for lightweight mocked test clients.
        """
        key = make_cache_key(
            provider=self.settings.ai_provider,
            model=self.settings.ai_model,
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=prompt,
            prompt_version=self.settings.prompt_version,
        )
        now = datetime.now(timezone.utc)
        cached = self.repository.cache_get(key, now=now)
        if cached is not None:
            return cached

        def create_response(extra_instructions: str = ""):
            instructions = system_prompt
            if extra_instructions:
                instructions += "\n\n" + extra_instructions

            kwargs = {
                "model": self.settings.ai_model,
                "instructions": instructions,
                "input": prompt,
            }

            if self.settings.ai_provider == "openai":
                # JSON mode guarantees syntactically valid JSON.
                kwargs["text"] = {"format": {"type": "json_object"}}
                # 11-language output is much larger than the old bilingual payload.
                kwargs["max_output_tokens"] = 30000

            try:
                return self.client.responses.create(**kwargs)
            except TypeError:
                # Preserve compatibility with simple mocked clients in pytest.
                kwargs.pop("text", None)
                kwargs.pop("max_output_tokens", None)
                return self.client.responses.create(**kwargs)

        last_error = None

        for attempt in range(2):
            retry_instruction = ""
            if attempt:
                retry_instruction = (
                    "上一次输出无法被 json.loads 解析。请重新输出完整合法的 JSON 对象；"
                    "不要Markdown代码块，不要解释，不要省略任何结尾括号或逗号，"
                    "JSON之外不要输出任何文字。"
                )

            response = create_response(retry_instruction)

            status = str(getattr(response, "status", "") or "").lower()
            if status == "incomplete":
                details = getattr(response, "incomplete_details", None)
                last_error = ValueError(
                    f"AI {purpose} 输出不完整: {details or 'unknown reason'}"
                )
                continue

            raw = str(getattr(response, "output_text", "") or "").strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                last_error = ValueError(
                    f"AI {purpose} JSON解析失败: "
                    f"line={exc.lineno}, column={exc.colno}, char={exc.pos}"
                )
                continue

            if not isinstance(parsed, dict):
                last_error = ValueError(f"AI {purpose} 输出必须是JSON对象")
                continue

            self.repository.cache_set(
                key,
                parsed,
                expires_at=now + timedelta(hours=self.settings.cache_ttl_hours),
            )
            return parsed

        raise last_error or ValueError(f"AI {purpose} JSON输出失败")

    def analyze(self, collected):
        compact_sources = []
        for record in collected.get("sources", []):
            text = " ".join(str(record.get("text", "")).split())
            kind = record.get("kind")
            # 高密度版：增加证据输入，输出仍要求惜字如金。
            if kind == "company":
                limit = 1800
            elif kind == "company_news":
                limit = 1000
            elif kind == "calendar":
                limit = 5000
            elif kind == "official":
                limit = 1800
            else:
                limit = 1400
            compact_sources.append({
                "name": record.get("name"), "kind": kind,
                "symbol": record.get("symbol") or COMPANY_SYMBOLS.get(record.get("name")),
                "status": record.get("status"), "text": text[:limit],
            })
        macro_sources = [
            item for item in compact_sources
            if item.get("kind") in {"official", "media", "calendar"}
        ]
        calendar_company_sources = _calendar_company_evidence(compact_sources)

        prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
        prompt += "\n跨资产1日/5日/20日量化状态：\n" + json.dumps(collected.get("market_context", {}), ensure_ascii=False)
        prompt += "\n市场标的中文说明：\n" + json.dumps(SIGNAL_NAMES, ensure_ascii=False)
        prompt += "\n宏观、政策与财经证据：\n" + json.dumps(
            [x for x in macro_sources if x.get("kind") != "calendar"],
            ensure_ascii=False,
        )
        prompt += (
            "\n高优先级未来日程页面【仅用于 events 字段提取日期；"
            "不得用于 direction/horizons/actions/flows/logic/media_themes 的正文论据】：\n"
            + json.dumps(
                [x for x in macro_sources if x.get("kind") == "calendar"],
                ensure_ascii=False,
            )
        )
        prompt += "\n原始未来14日结构化日程候选（只作候选，禁止照单全收）：\n" + json.dumps(
            collected.get("events", []), ensure_ascii=False
        )
        prompt += "\n可能包含财报/投资者日等明确日期的公司证据：\n" + json.dumps(
            calendar_company_sources, ensure_ascii=False
        )
        prompt += """
\n请生成中文机构晨报所需的完整 JSON：
{
  "direction":{
    "title":"","title_en":"",
    "brief":"","brief_en":"",
    "bias":"偏积极|偏谨慎|中性","bias_en":"Constructive|Cautious|Neutral"
  },
  "horizons":[
    {"days":"3-5","direction":"","direction_en":"","focus":[],"brief":"","brief_en":"","risk":"","risk_en":""},
    {"days":"5-10","direction":"","direction_en":"","focus":[],"brief":"","brief_en":"","risk":"","risk_en":""},
    {"days":"10-15","direction":"","direction_en":"","focus":[],"brief":"","brief_en":"","risk":"","risk_en":""}
  ],
  "actions":{"watch":[],"prepare":[],"avoid":[]},
  "actions_en":{"watch":[],"prepare":[],"avoid":[]},
  "flows":[{"from":"","to":"","brief":"","brief_en":""}],
  "logic":[{
    "cause":"","cause_en":"",
    "middle":"","middle_en":"",
    "result":"","result_en":"",
    "action":"","action_en":""
  }],
  "media_themes":[{
    "title":"","title_en":"",
    "tone":"积极|谨慎|中性","tone_en":"Positive|Cautious|Neutral",
    "brief":"","brief_en":"",
    "impact":"","impact_en":"",
    "sources":[]
  }],
  "events":[
    {"date":"YYYY-MM-DD","title":"高影响事件短标题","source":"输入中的真实来源名","importance":90,"category":"宏观|Fed|财报|政策|地缘|跨资产"}
  ],
  "predictions":[{
    "horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,
    "thesis":"","thesis_en":"",
    "invalidation":"","invalidation_en":"",
    "sensors":[],"evidence_ids":[]
  }]
}

总原则：高信息密度，惜字如金。不是“写长”，而是“每句话都有用”。

写作纪律：
1. 只输出JSON。中文字段保持原字段名；对应英文统一使用 `_en` 后缀。
2. 中文是主判断，英文只能忠实表达同一判断，禁止重新分析、改变方向、增删事实或增加中文没有的信息。
3. ticker、资产代码、数字、日期、概率、source、evidence_ids保持一致，不翻译、不改写。
4. 英文使用简洁的 institutional market research 风格；同样惜字如金，不逐字翻译中文套话。
5. `actions_en` 必须与 `actions` 三组逐项一一对应、顺序一致。
6. 只依据输入证据；禁止补造数字、时间、人物、预期或新闻。
7. 未经官方确认的信息，中文写“据报道/尚待确认/市场传闻”，英文对应写 `reported / unconfirmed / market reports` 等同等限定语，不得写成既定事实。
8. 每句话至少承担一项功能：事实、数字、预期差、因果、资产影响、触发条件；没有功能就删。
9. 优先结构：“事件/数据 → 预期差 → 传导 → 资产”；能用40字说清，不写80字；英文保持同等密度。
10. 同一事实只出现一次；不同模块不得反复复述同一结论。
11. 中文禁止套话：值得关注、密切留意、市场正在关注、可能产生一定影响、从某种程度上、整体来看、需要注意的是；英文也禁止对应空话。
12. 结论先行；少形容词、少铺垫、少重复。
13. 读者正文禁止出现任何“分析过程/数据抓取/页面诊断”语言，例如：
    absent、schedule evidence、calendar text、later dates include、input confirms、
    “输入仅确认”“页面未找到”“日程文本显示”“来源抓取失败”等。
14. 中文简体字段必须是自然中文；允许 CPI/PCE/GDP/FOMC/SPY/QQQ/NVDA 等标准缩写和ticker，
    但禁止出现连续英文解释句、英文网页片段或把原始证据直接粘贴进中文正文。


多语言输出（必须执行）：
- 默认无后缀字段仍为中文简体，是唯一主判断。
- 所有面向读者的文本字段，除现有 `_en` 外，还必须同步输出：
  `_zh_tw` 中文繁体、`_bg` 保加利亚语、`_ru` 俄语、`_ja` 日语、
  `_ko` 韩语、`_fr` 法语、`_de` 德语、`_es` 西班牙语、`_th` 泰语。
- 翻译顺序/语言代码固定：
  zh（中文简体，无后缀）→ zh_tw → en → bg → ru → ja → ko → fr → de → es → th。
- 这些字段只是同一投资判断的本地化表达，不是重新分析：
  数字、方向、概率、资产代码、日期、触发条件、失效条件必须完全一致。
- 各语言都保持“高信息密度、惜字如金”；使用当地自然的金融研究表达，不做生硬逐字翻译。
- ticker、target、focus、source、sources、sensors、evidence_ids 不翻译。
- 对数组 actions，除 `actions` / `actions_en` 外，还必须输出：
  `actions_zh_tw`、`actions_bg`、`actions_ru`、`actions_ja`、`actions_ko`、
  `actions_fr`、`actions_de`、`actions_es`、`actions_th`；
  每个语言版本的 watch / prepare / avoid 数量、顺序、标的一一对应。
- 若某专有名词在目标语言中没有稳定译名，保留常用英文名，不臆造。

direction：
- title 12-24字，直写核心矛盾；title_en为同义精炼英文标题。
- brief 70-100字：串联2-4个关键变量，必须含“主线 + 关键验证点”；brief_en表达完全相同的信息。
- bias 只给最终倾向；bias_en严格对应，不得改变倾向。

horizons：
- 正好三项：3-5、5-10、10-15。
- direction / brief / risk 为中文；direction_en / brief_en / risk_en为完全对应英文。
- brief 50-75字：判断→核心依据→确认条件；英文保持同等信息密度。
- risk 30-50字：只写最关键失效条件。
- focus 最多4个，只留真正相关标的；focus中资产代码不翻译。

actions：
- actions 与 actions_en 的 watch / prepare / avoid 每组最多4项，数量、顺序、标的一一对应。
- 中文每项35-55字，尽量用“标的：动作；原因；触发/停止条件”；英文用同样结构压缩表达。
- 禁止空泛“等待观察”；必须说明等什么。

flows：
- 最多4项；brief 35-55字，brief_en为等义英文。
- from/to资产代码保持不变。
- 仅表示相对配置倾向/潜在轮动；没有直接资金流证据，不得声称真实资金已经迁移。
- 必须解释A为何弱/强、B为何受益/承压。

logic：
- 最多6项；宁缺毋滥。
- cause / middle / result / action 为中文；对应 `_en` 字段必须逐项同义。
- 各字段只写一个信息点，形成“事实/催化 → 中间变量 → 资产结果 → 动作”。
- 优先覆盖真正有证据的利率、美元、通胀/商品、风险偏好、市场宽度、行业轮动、海外市场。

media_themes：
- 最多5项；这里只写“市场正在交易的主题”，不是日程检查器、数据抓取日志或来源诊断。
- 优先“已经发生/正在发酵且正在影响定价的主题”；未来纯日程若尚未产生交易影响，应留在 events，不要重复塞进 media_themes。
- 高优先级未来日程页面只允许帮助 events 提取日期，禁止把“某日期缺失/某页面只确认某项/后续还有CPI”等页面诊断写进 media_themes。
- title / brief / impact 为自然中文；title_en / brief_en / impact_en为同义英文；tone_en与tone严格对应。
- 中文正文只允许标准金融缩写/ticker夹在中文句子中；禁止连续英文自然语言短语或原始网页片段。
- title 12-28字，直接写市场主题。
- brief 50-80字：事实 + 关键数字/状态 + 预期差；禁止背景科普、禁止说明“输入有没有找到什么”。
- impact 35-60字：传导链 + 受影响资产 + 下一验证点。
- sources 必须逐字使用“宏观、政策与财经证据”中的真实 source name；不得填 SPY/QQQ/VIX/GLD 等资产代码。
- 一个主题只讲一件事；没有可靠增量主题时宁可少于3项。

events（这是“未来14日日历”的最终展示事件，必须严筛）：
- 日历形式不变，但禁止“为了填格子而填格子”；没有高影响事件的日期可以留空。
- 只选输入证据中明确给出未来日期、且可能显著影响美股/美债/美元/黄金/原油/主要行业的事件。
- 固定目标8项；如果输入中存在至少8个经明确日期证据确认的高影响事件，必须输出8项；只有经核实候选不足8个时才允许少于8项。
- 单日最多3项；按市场重要性排序并给 importance 0-100。importance < 58 不得输出；禁止为了凑8项加入与美股定价弱相关的统计发布。
- 优先级：
  A级：FOMC、Fed主席/杰克逊霍尔、CPI、核心PCE、非农、GDP、重大关税/制裁/政策节点；
  B级：PPI、零售销售、ISM/JOLTS/消费者通胀预期、10Y/30Y国债拍卖、OPEC+、大型权重股/行业龙头财报；
  C级：只有在当前市场主线高度相关时才保留其他官方数据。
- 大型公司财报只有在输入中存在明确日期证据时才能进入；公司IR Events/Press Release属于有效日期证据，禁止凭记忆补财报日期。
- Fed月度Calendar、BEA Release Schedule、Michigan官方下一发布日期、ISM官方PMI发布日历属于有效日程证据，应主动提取而不是忽略。
- 政策/地缘事件只有在输入中存在明确日程、截止日期或已宣布发布会时才能进入；单纯评论或已发生新闻不进入未来日历。
- BLS的普通统计发布不是天然重要。明确排除：暑期青年劳动力、休假获取与使用、职业展望手册、县级就业工资、初步基准等低交易价值项目。
- 同一事件多来源重复时只保留一项；优先 source：官方机构 > 公司IR > Reuters/FT/AP/CNBC等主流媒体。
- title 只写“事件本身”，建议10-24字；不要在日历标题里写影响分析。
- source 必须逐字使用输入里真实存在的来源名，不得虚构来源。
- date 必须是 YYYY-MM-DD 且位于报告日开始的未来14日内；没有明确日期就不输出。
- 宁可某天显示“暂无已确认事件”，也不要塞入低价值日程。

predictions：
- 周期仅3/5/10/15，概率0.50-0.80。
- target / direction / probability / sensors / evidence_ids为中英文共用结构。
- thesis / invalidation 为中文；thesis_en / invalidation_en为完全对应英文。
- 绝对方向UP/DOWN/NEUTRAL；相对方向OUTPERFORM/UNDERPERFORM/NEUTRAL。
- thesis 必须是“证据→方向”的短因果链；invalidation 必须可观察。
- 没有优势写“等待确认”，英文对应 `Wait for confirmation`，不硬凑方向。

最终自检：
删掉任何不影响结论的句子；删掉重复观点；删掉没有事实、数字、因果或动作的句子。
JSON结构必须完整闭合；禁止Markdown代码块、注释或JSON之外的任何文字。
"""

        system_prompt = (
            "你是多语种跨资产首席研究员兼信息编辑。"
            "先用中文简体形成唯一投资判断，再将同一判断本地化为中文繁体、英语、保加利亚语、俄语、"
            "日语、韩语、法语、德语、西班牙语和泰语；任何语言都不是第二次分析。"
            "事实优先、数字优先、因果优先、动作优先；惜字如金，删除铺垫、套话、重复和无效形容词。"
            "所有语言的事实、方向、动作、触发和失效条件必须一致。"
            "只依据输入证据，不承诺收益，严格输出JSON。"
        )
        parsed = self._complete_json("master", system_prompt, prompt)

        # Reader-facing MARKET FOCUS must never expose source/debug fragments.
        parsed["media_themes"] = _sanitize_media_themes(
            parsed.get("media_themes", []),
            collected.get("sources", []),
            limit=5,
        )

        # Calendar stays exactly the same visually. Only replace its event list
        # with a high-impact, evidence-backed selection.
        curated_events = _normalize_market_calendar_events(
            parsed.get("events", []),
            collected.get("events", []),
            start=self.settings.report_date,
            days=14,
            target_count=8,
        )
        parsed["events"] = curated_events
        collected["events"] = curated_events

        prediction_prompt = "市场快照：\n" + json.dumps(collected.get("market", {}), ensure_ascii=False)
        prediction_prompt += "\n跨资产1日/5日/20日量化状态：\n" + json.dumps(collected.get("market_context", {}), ensure_ascii=False)
        prediction_prompt += "\n市场标的中文说明：\n" + json.dumps(SIGNAL_NAMES, ensure_ascii=False)
        prediction_prompt += "\n宏观、政策与财经证据：\n" + json.dumps(
            [x for x in macro_sources if x.get("kind") != "calendar"],
            ensure_ascii=False,
        )
        prediction_prompt += "\n允许预测的完整对象：\n" + json.dumps(PREDICTION_TARGETS, ensure_ascii=False)
        prediction_prompt += "\n预测对象分组：\n" + json.dumps(PREDICTION_GROUPS, ensure_ascii=False)
        prediction_prompt += """
\n请单独生成跨资产预测，只输出以下JSON：
{"predictions":[{"horizon_days":5,"target":"SPY","direction":"UP","probability":0.60,"thesis":"","thesis_en":"","invalidation":"","invalidation_en":"","sensors":[],"evidence_ids":[]}]}

必须正好4项且target互不重复。
选择原则：
1. 至少1项来自美国大盘/风格；
2. 至少1项来自美国行业相对强弱；
3. 至少1项来自利率或信用；
4. 第4项从商品、美元、波动率或海外市场中选择当天增量信号最强者。
5. 不要机械重复 SPY、QQQ/SPY、XLF/SPY、XLE/SPY、TLT；如果其他行业、海外市场、商品或信用出现更强证据，应主动替换。
6. 只能从“允许预测的完整对象”中选择；不能凭记忆添加其他标的。
7. 不得4项全部表达同一方向或同一风险因子；优先保持跨资产分散。
8. 必须优先参考1日/5日/20日变化、20日波动率、MA20位置，再结合新闻/政策；不因知名度高而优先。
9. thesis 45-70字：只写“量化状态 + 催化/宏观变量 → 方向”；thesis_en为同义精炼英文，不得增加新事实。
10. invalidation 25-45字：必须可观察；invalidation_en严格对应；sensors优先2-3个真正能验证判断的变量。
11. 每项至少包含一个输入中的量化状态或具体事件，不写纯主观判断。
12. 中英文必须共享同一 target、direction、probability、sensors、evidence_ids；不得出现方向不一致。
13. 周期仅3/5/10/15；概率0.50-0.80。
14. 绝对方向UP/DOWN/NEUTRAL；相对方向OUTPERFORM/UNDERPERFORM/NEUTRAL。

15. 对 `thesis` 与 `invalidation`，除 `_en` 外，同时输出 `_zh_tw/_bg/_ru/_ja/_ko/_fr/_de/_es/_th`。
16. 所有语言共享同一 horizon_days、target、direction、probability、sensors、evidence_ids；仅翻译展示文本。
17. 各语言保持高信息密度，不增加中文没有的事实。
18. JSON结构必须完整闭合；禁止Markdown代码块、注释或JSON之外的任何文字。
"""
        prediction_system = (
            "你是多语种跨资产预测负责人。先形成唯一中文预测，再把同一预测翻译为所要求的十种其他语言。"
            "结论必须短、硬、可验证：量化状态→催化→方向→失效条件。"
            "任何语言都不得改变方向、数字或增加事实；拒绝套话和重复，严格输出JSON。"
        )
        prediction_result = self._complete_json(
            "cross_asset_predictions", prediction_system, prediction_prompt
        )
        cross_asset_predictions = prediction_result.get("predictions", [])
        if isinstance(cross_asset_predictions, list) and cross_asset_predictions:
            parsed["predictions"] = self._limit_predictions(cross_asset_predictions)

        # 公司部分采用三层漏斗：
        # 完整股票池 -> 行情预筛50只 -> 新闻二筛 -> AI候选 -> 最终8只。
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
            symbol: _company_display_name(symbol)
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
            # 保留旧版提示词标记，兼容现有测试中的模拟 OpenAI 客户端。
            # 实际内容仍然只是经过今日候选池筛选后的公司材料。
            company_prompt += "\n公司一手材料与逐股新闻：\n" + json.dumps(company_sources, ensure_ascii=False)
            company_prompt += """
\n从上述候选中按“增量信息强度 + 价格反应 + 风险收益比 + 行业分散”排序，
输出最多12个候选，系统随后会再压缩到最终8个。JSON格式：
{"company_signals":[{
  "company":"中文公司名","company_en":"English company name",
  "ticker":"股票代码",
  "stance":"关注|等待|回避","stance_en":"WATCH|WAIT|AVOID",
  "brief":"事实→股票影响→动作","brief_en":"same thesis in concise English",
  "trigger":"何种可观察条件出现才行动","trigger_en":"same trigger in concise English",
  "risk":"最大风险或失效条件","risk_en":"same risk in concise English",
  "source":"输入中的来源名"
}]}

硬约束：
1. 只输出JSON；ticker只能来自“今日二次筛选后的候选代码”，禁止从记忆补充其他股票。
2. 中文字段保持原字段名；英文使用 `_en` 后缀。ticker和source中英文共用。
3. 英文必须忠实表达中文同一结论，不得重新分析、改变stance、增删事实或补充中文没有的数字。
4. stance_en严格映射：关注=WATCH，等待=WAIT，回避=AVOID。
5. company_en优先使用输入中明确出现的官方/常用英文公司名；无法可靠确定时使用ticker，不猜名称。
6. 按优先级排序；不要因为公司知名度高而优先，优先真正有当日增量信息且“下一步动作清晰”的股票。
7. 必须综合 candidate_score、news_event_score、setup_type、setup_score；不能把最终名单简单变成“当日涨幅榜”。
8. 同一行业尽量不超过2只；如果同一行业确有明显主线，可给到3只，但必须各有不同催化剂。
9. “关注”最多4只，必须具备可验证的正向逻辑，并满足以下至少一种：
   A. 上升趋势中的可控回撤/止跌；
   B. 放量突破或趋势重新转强，但触发条件必须防止追高。
10. setup_type=overextended 的股票原则上不得标“关注”，除非事件极强且触发条件明确要求回踩/整理后再参与。
11. setup_type=risk_breakdown 且存在基本面或事件利空时，应优先考虑“回避”，不能机械抄底。
12. “等待”用于方向尚可但价格、成交量或事件确认不足的股票；不要因为措辞保守而把所有股票都写成“等待”。
13. 若候选中确有满足条件的机会，优先给出2-4只行业分散的“关注”；若存在明确破位/重大利空，也应给出1-2只“回避”。没有合格对象时可以不凑数量。
14. 不能只凭网站介绍或单条媒体标题；公司官网若只有宣传性内容，不得作为主要论据。
15. brief 65-85字，固定顺序：“核心事实/催化 → 价格或基本面含义 → 当前动作”；brief_en表达同样三层信息，保持同等密度，不逐字翻译。
16. trigger 30-45字，只写升级/执行所需的可观察条件；trigger_en严格对应；禁止空泛“等待进一步确认”。
17. risk 30-45字，只写最可能使当前逻辑失效的风险；risk_en严格对应；不同公司不得复制同一句风险。
18. source必须是真实输入来源；只有媒体消息时，中文brief与英文brief_en都保留同等“据报道/尚待确认”限定。
19. 中英文都能用短句不用长句；删除公司背景、行业科普、重复评价。
20. 不编造买卖价格，不承诺收益，不为凑数量牺牲证据质量。

21. company / stance / brief / trigger / risk 除 `_en` 外，同时输出 `_zh_tw/_bg/_ru/_ja/_ko/_fr/_de/_es/_th`。
22. company 的各语言版本可使用该市场最常见的公司名称；无法可靠本地化时保留英文公司名或ticker。
23. 所有语言的 stance 必须与中文完全一致；只翻译表达，不重新判断。
24. JSON结构必须完整闭合；禁止Markdown代码块、注释或JSON之外的任何文字。
"""
            company_system = (
                "你是多语种美股研究负责人。候选已通过量价和新闻初筛。"
                "先形成唯一中文股票判断，再将同一判断本地化为中文繁体、英语、保加利亚语、俄语、"
                "日语、韩语、法语、德语、西班牙语和泰语；翻译不是第二次分析。"
                "每只股票按“事实/催化→市场含义→动作→触发→失效”压缩表达。"
                "所有语言的事实、stance、trigger、risk必须一致；惜字如金，不写公司介绍，不把涨幅榜当精选榜。"
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

                        setup_type = str(snapshot.get("setup_type", "neutral"))

                        controlled_pullback = (
                            day_change <= -0.20 * volatility
                            and day_change >= -1.60 * volatility
                            and above_ma50
                            and ma20_gap >= -7.0
                        )
                        confirmed_breakout = (
                            day_change >= 0.30 * volatility
                            and day_change <= 1.60 * volatility
                            and volume_ratio >= 1.25
                            and above_ma20
                            and above_ma50
                            and ma20_gap <= 8.0
                        )
                        steady_strength = (
                            setup_type == "steady_strength"
                            and above_ma20
                            and above_ma50
                            and ma20_gap <= 7.0
                        )

                        actionable = (
                            controlled_pullback
                            or confirmed_breakout
                            or steady_strength
                        )

                        # 明确过热的股票即使AI给“关注”，也先降级为等待，
                        # 避免报告在+8%、+13%之后再提示追涨。
                        if setup_type == "overextended":
                            actionable = False
                except (TypeError, ValueError):
                    actionable = False

                # 保持原测试/原产品契约：最多4只“关注”。
                if focus_count >= 4 or not actionable:
                    stance = "等待"

            if stance == "关注":
                focus_count += 1

            item["ticker"] = ticker
            item["company"] = _company_display_name(
                ticker,
                item.get("company"),
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
