from __future__ import annotations

import html
import re
from datetime import date, timedelta

from .sources import COMPANY_NAMES, COMPANY_SYMBOLS


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


BLS_EVENT_TRANSLATIONS = {
    "Summer Youth Labor Force": "暑期青年劳动力",
    "State Employment and Unemployment (Monthly)": "各州就业与失业（月度）",
    "Access to and Use of Leave": "休假获取与使用情况",
    "Employment Projections and Occupational Outlook Handbook": "就业预测与《职业展望手册》",
    "Worker Displacement": "工人失业与岗位流失",
    "County Employment and Wages": "县级就业与工资",
    "Current Employment Statistics Preliminary Benchmark (National)": "当前就业统计初步基准（全国）",
    "Current Employment Statistics Preliminary Benchmark (State and Area)": "当前就业统计初步基准（州和地区）",
    "Job Openings and Labor Turnover Survey": "职位空缺与劳动力流动调查",
    "The Employment Situation": "就业形势报告",
    "Consumer Price Index": "消费者价格指数",
    "Producer Price Index": "生产者价格指数",
    "U.S. Import and Export Price Indexes": "美国进出口价格指数",
    "Real Earnings": "实际收入",
    "Employment Cost Index": "就业成本指数",
    "Productivity and Costs": "生产率与成本",
    "Employer Costs for Employee Compensation": "雇主员工薪酬成本",
    "Metropolitan Area Employment and Unemployment": "大都会地区就业与失业",
    "Metropolitan Area Employment and Unemployment (Monthly)": "大都会地区就业与失业（月度）",
    "Occupational Employment and Wage Statistics": "职业就业与工资统计",
    "Business Employment Dynamics": "企业就业动态",
}

SOURCE_LABELS = {
    "BLS": "美国劳工统计局", "BEA": "美国经济分析局",
    "Federal Reserve": "美联储", "Treasury Auctions": "美国财政部",
    "White House": "美国白宫", "US Census": "美国人口普查局",
    "EIA": "美国能源信息署", "Treasury Press": "美国财政部新闻",
    "USTR": "美国贸易代表办公室", "State Department": "美国国务院",
    "Federal Register": "美国联邦公报",
    "AP Business": "美联社商业", "CNBC Markets": "CNBC市场",
    "Financial Times": "英国金融时报", "Reuters Markets": "路透市场",
    "MarketWatch": "市场观察", "Yahoo Finance": "雅虎财经",
    "JPM IR": "摩根大通公告",
    "Walmart IR": "沃尔玛公告", "Microsoft IR": "微软公告",
    "Amazon IR": "亚马逊公告", "NVIDIA IR": "英伟达公告",
    "Alphabet IR": "谷歌母公司公告", "Apple IR": "苹果公告",
    "Costco IR": "开市客公告", "ExxonMobil IR": "埃克森美孚公告",
    "TSMC IR": "台积电公告", "Broadcom IR": "博通公告",
    "Alibaba IR": "阿里巴巴公告", "Tencent IR": "腾讯公告",
    "Micron IR": "美光科技公告", "Tesla IR": "特斯拉公告",
    "Eli Lilly IR": "礼来公告", "UnitedHealth IR": "联合健康公告",
    "Caterpillar IR": "卡特彼勒公告", "Goldman Sachs IR": "高盛公告",
    "Visa IR": "维萨公告",
}

COMPANY_LABELS = {
    "JPM": "摩根大通", "JPMORGAN": "摩根大通", "WMT": "沃尔玛",
    "WALMART": "沃尔玛", "MSFT": "微软", "MICROSOFT": "微软",
    "AMZN": "亚马逊", "AMAZON": "亚马逊", "NVDA": "英伟达",
    "NVIDIA": "英伟达", "TSM": "台积电", "TSMC": "台积电",
    "AVGO": "博通", "BROADCOM": "博通", "MU": "美光科技", "MICRON": "美光科技",
    "GOOGL": "谷歌", "ALPHABET": "谷歌", "AAPL": "苹果", "APPLE": "苹果",
    "COST": "开市客", "COSTCO": "开市客", "XOM": "埃克森美孚",
    "EXXONMOBIL": "埃克森美孚", "BABA": "阿里巴巴", "ALIBABA": "阿里巴巴",
    "TCEHY": "腾讯", "TENCENT": "腾讯", "TSLA": "特斯拉", "TESLA": "特斯拉",
    "LLY": "礼来", "UNH": "联合健康", "CAT": "卡特彼勒",
    "GS": "高盛", "V": "维萨", "VISA": "维萨",
}

DIRECTION_LABELS = {
    "UP": "看涨", "DOWN": "看跌", "NEUTRAL": "中性",
    "OUTPERFORM": "有望跑赢", "UNDERPERFORM": "可能跑输",
}


def _has_chinese(value) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def translate_event_title(title) -> str:
    normalized = " ".join(str(title or "").split())
    if normalized in BLS_EVENT_TRANSLATIONS:
        return BLS_EVENT_TRANSLATIONS[normalized]
    return normalized if _has_chinese(normalized) else "美国劳工统计局数据发布"


def _logo() -> str:
    return """<svg class="logo" viewBox="0 0 120 120" role="img" aria-label="NEWS FINANCE 美国鹰徽标">
<defs><filter id="eagle-shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity=".22"/></filter></defs>
<circle cx="60" cy="60" r="56" fill="#f8fafc" stroke="#d6c598" stroke-width="3" filter="url(#eagle-shadow)"/>
<circle cx="60" cy="60" r="49" fill="#0b2a4a" stroke="#b7a06a" stroke-width="1.5"/>
<g fill="#fff"><circle cx="30" cy="27" r="1.7"/><circle cx="40" cy="20" r="1.7"/><circle cx="51" cy="16" r="1.7"/><circle cx="69" cy="16" r="1.7"/><circle cx="80" cy="20" r="1.7"/><circle cx="90" cy="27" r="1.7"/></g>
<path d="M55 43C45 30 31 28 17 35c9 4 15 9 20 16-8-4-16-3-23 1 10 9 24 13 42 5z" fill="#eef2f6" stroke="#b7a06a" stroke-width="1.4"/>
<path d="M65 43c10-13 24-15 38-8-9 4-15 9-20 16 8-4 16-3 23 1-10 9-24 13-42 5z" fill="#eef2f6" stroke="#b7a06a" stroke-width="1.4"/>
<path d="M51 41c4-8 12-12 21-9-2 3-5 5-8 6 5 1 8 4 9 8-4 1-8 1-12-1l-5 5z" fill="#fff" stroke="#b7a06a" stroke-width="1.2"/>
<circle cx="65" cy="37" r="1.4" fill="#071a34"/><path d="M72 39l9 3-9 4z" fill="#d2a33d"/>
<path d="M48 45c5-4 19-4 24 0l-2 31H50z" fill="#9a5f36"/>
<path d="M41 56h38v19c0 10-8 17-19 22-11-5-19-12-19-22z" fill="#fff" stroke="#d6c598" stroke-width="1.5"/>
<path d="M41 56h38v10H41z" fill="#173f6b"/><g fill="#fff"><circle cx="48" cy="61" r="1.1"/><circle cx="55" cy="61" r="1.1"/><circle cx="62" cy="61" r="1.1"/><circle cx="69" cy="61" r="1.1"/><circle cx="76" cy="61" r="1.1"/></g>
<path d="M46 66v22M54 66v27M62 66v27M70 66v22" stroke="#b21f32" stroke-width="5"/>
<path d="M42 82c-8 0-14 4-19 11M78 82c8 0 14 4 19 11" fill="none" stroke="#d2a33d" stroke-width="2" stroke-linecap="round"/>
<path d="M24 88l-4 1m8-5-5-2m72 6 4 1m-8-5 5-2" stroke="#d2a33d" stroke-width="2" stroke-linecap="round"/>
</svg>"""


def _list(items, empty="等待确认"):
    values = [f"<li>{esc(x)}</li>" for x in (items or [])]
    return f"<ul>{''.join(values)}</ul>" if values else f"<p class='muted'>{esc(empty)}</p>"


def _horizons(context):
    items = context.get("horizons", [])[:3]
    defaults = ("3-5", "5-10", "10-15")
    cards = []
    for index, days in enumerate(defaults):
        item = items[index] if index < len(items) else {"days": days, "direction": "等待确认", "focus": [], "brief": "证据尚不足。", "risk": "等待新增数据"}
        focus = " · ".join(str(x) for x in item.get("focus", [])[:5])
        cards.append(f"""<div class="horizon"><div class="horizon-time">未来 {esc(item.get('days', days))} 日</div><div class="horizon-direction">{esc(item.get('direction', '等待确认'))}</div><div class="focus">{esc(focus)}</div><p>{esc(item.get('brief'))}</p><div class="risk">风险：{esc(item.get('risk', '等待确认'))}</div></div>""")
    return "".join(cards)


def _calendar(context):
    by_date = {}
    for event in context.get("events", []):
        by_date.setdefault(str(event.get("date", ""))[:10], []).append(event)
    weekdays = "一二三四五六日"
    try:
        start = date.fromisoformat(str(context.get("report_date", ""))[:10])
    except ValueError:
        start = date.today()
    cells = []
    for offset in range(14):
        current = start + timedelta(days=offset)
        current_text = current.isoformat()
        body = []
        for index, event in enumerate(by_date.get(current_text, []), 1):
            title = translate_event_title(event.get("title"))
            source = SOURCE_LABELS.get(str(event.get("source", "")), "官方来源")
            body.append(f"<div class='event'><span>{index:02d}</span><strong>{esc(title)}</strong><small>{esc(source)}</small></div>")
        if not body:
            body.append("<div class='event-empty'>暂无已确认事件</div>")
        cells.append(
            f"<div class='day'><div class='day-head'><h3>{current.month}月{current.day}日</h3>"
            f"<div class='weekday'>周{weekdays[current.weekday()]}</div></div>{''.join(body)}</div>"
        )
    return "".join(cells)


def _logic(context):
    flow_html = "".join(
        f"<div class='flow'><span class='flow-index'>{index:02d}</span>"
        f"<strong>{esc(x.get('from'))}</strong><i>→</i><strong>{esc(x.get('to'))}</strong>"
        f"<p>{esc(x.get('brief'))}</p></div>"
        for index, x in enumerate(context.get("flows", [])[:3], 1)
    ) or "<p class='muted'>本轮没有形成明确资金迁移方向。</p>"
    chain_html = "".join(
        f"<div class='logic'><div class='logic-step'><small>起点</small><strong>{esc(x.get('cause'))}</strong></div>"
        f"<div class='logic-arrow'>→</div><div class='logic-step'><small>传导</small><span>{esc(x.get('middle'))}</span></div>"
        f"<div class='logic-arrow'>→</div><div class='logic-step'><small>结果</small><span>{esc(x.get('result'))}</span></div>"
        f"<div class='logic-action'><small>投资应对</small>{esc(x.get('action'))}</div></div>"
        for x in context.get("logic", [])[:4]
    ) or "<p class='muted'>等待更多交叉资产证据。</p>"
    return f"<div class='flow-strip'>{flow_html}</div><div class='logic-grid'>{chain_html}</div>"


def _source_cards(context, kind):
    source_records = context.get("sources", [])
    source_urls = {str(x.get("name")): x.get("url", "#") for x in source_records}
    curated = context.get("company_signals" if kind == "company" else "media_themes", [])
    curated_cards = []
    focus_count = 0
    limit = 8 if kind == "company" else 3
    for item in curated[:limit]:
        if kind == "company":
            brief = str(item.get("brief") or "").strip()
            if not _has_chinese(brief):
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            company = COMPANY_NAMES.get(ticker) or str(item.get("company") or "").strip()
            if not _has_chinese(company):
                company = COMPANY_LABELS.get(ticker) or COMPANY_LABELS.get(company.upper()) or "重点公司"
            title = f"{company}（{ticker}）" if ticker else company
            label = str(item.get("stance") or item.get("signal") or "等待").strip()
            if label not in {"关注", "等待", "回避"}:
                label = "等待"
            if label == "关注" and focus_count >= 4:
                label = "等待"
            if label == "关注":
                focus_count += 1
            trigger = str(item.get("trigger") or "").strip()
            risk = str(item.get("risk") or "").strip()
            source_names = []
            for record in source_records:
                record_name = str(record.get("name", ""))
                if record.get("symbol") == ticker or COMPANY_SYMBOLS.get(record_name) == ticker:
                    source_names.append(record_name)
            source_names = list(dict.fromkeys(source_names))[:2]
            if not source_names and ticker:
                market_source = f"{ticker} 行情"
                source_names = [market_source]
                source_urls[market_source] = f"https://finance.yahoo.com/quote/{ticker}/"
        else:
            title = item.get("title") or "市场主题"
            label = item.get("tone") or "中性"
            brief = str(item.get("brief") or "").strip()
            if not _has_chinese(brief):
                continue
            if not _has_chinese(title):
                title = "市场主题"
            impact = str(item.get("impact") or "").strip()
            source_names = [str(x) for x in item.get("sources", [])]
        source_names = [x for x in source_names if x]
        source_links = []
        for source_name in source_names:
            source_label = SOURCE_LABELS.get(
                source_name,
                f"{source_name[:-3]}动态新闻" if source_name.endswith(" 新闻")
                else (f"{source_name[:-3]}行情" if source_name.endswith(" 行情") else source_name),
            )
            source_url = source_urls.get(source_name)
            if source_url:
                source_links.append(
                    f"<a href='{esc(source_url)}' target='_blank' rel='noopener noreferrer'>"
                    f"{esc(source_label)}<span aria-hidden='true'>↗</span></a>"
                )
            else:
                source_links.append(f"<span>{esc(source_label)}</span>")
        links_html = "".join(source_links) or "<span>公开来源</span>"
        details = ""
        if kind == "company":
            snapshot = context.get("stock_snapshot", {}).get(ticker, {})
            if snapshot:
                price_text = f"{float(snapshot.get('price', 0)):.2f}"
                day_text = f"{float(snapshot.get('day_change_pct', 0)):+.2f}%"
                volatility_text = f"{float(snapshot.get('volatility_20_pct', 0)):.2f}%"
                details += (
                    "<div class='stock-meta'>"
                    f"现价 ${esc(price_text)}　当日 {esc(day_text)}　"
                    f"20日波动 {esc(volatility_text)}"
                    "</div>"
                )
            if _has_chinese(trigger):
                details += f"<div class='card-note'><strong>触发：</strong>{esc(trigger)}</div>"
            if _has_chinese(risk):
                details += f"<div class='card-risk'><strong>风险：</strong>{esc(risk)}</div>"
        elif _has_chinese(impact):
            details = f"<div class='card-note'><strong>投资含义：</strong>{esc(impact)}</div>"
        curated_cards.append(
            f"<div class='source-card'><div class='card-label'>{esc(label)}</div><h3>{esc(title)}</h3>"
            f"<p>{esc(brief)}</p>{details}<div class='source-links'>{links_html}</div></div>"
        )
    if curated_cards:
        return "".join(curated_cards)
    empty = "本轮未形成可执行的公司信号，原始材料不直接展示。" if kind == "company" else "本轮未形成值得交易的市场主题。"
    return f"<p class='muted'>{empty}</p>"


def _predictions(context):
    rows = []
    for item in context.get("display_predictions", context.get("predictions", [])):
        try:
            probability = f"{float(item.get('probability', 0)):.0%}"
        except (TypeError, ValueError):
            probability = "—"
        direction = DIRECTION_LABELS.get(str(item.get("direction", "")).upper(), item.get("direction"))
        rows.append(f"<tr><td><strong>{esc(item.get('horizon_days'))}日</strong></td><td><strong>{esc(item.get('target'))}</strong></td><td><span class='direction-pill'>{esc(direction)}</span></td><td>{probability}</td><td>{esc(item.get('thesis'))}</td><td>{esc(item.get('invalidation'))}</td></tr>")
    if not rows:
        return "<p class='muted'>当前证据不足，暂不形成方向性预测。</p>"
    return "<div class='table-wrap'><table><thead><tr><th>周期</th><th>对象</th><th>判断</th><th>概率</th><th>逻辑</th><th>失效条件</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"


LEGACY_CSS = """
:root{--navy:#17365d;--blue:#005ea8;--red:#d83933;--ink:#111820;--muted:#586675;--line:#cbd2d9}*{box-sizing:border-box}body{margin:0;background:#eee;font:16px/1.55 Arial,"Microsoft YaHei",sans-serif;color:var(--ink)}.wrap,main{max-width:1380px;margin:auto}.top-strip{background:#f7f7f7;border-bottom:1px solid #d9d9d9;font-size:12px;color:#38495a;padding:8px 36px}header{background:#fff;padding:18px 36px}.brand{display:flex;align-items:center;gap:22px}.logo{width:90px;height:90px}.eyebrow,.kicker{font-size:12px;letter-spacing:2px;font-weight:700;color:#637587}h1{font-size:34px;line-height:1.1;color:#082d59;margin:7px 0 3px}.subtitle{color:#43576b}.navbar{background:var(--navy);border-bottom:5px solid var(--red);color:#fff;font-weight:700;padding:13px 36px}main{background:#fff;border:1px solid #d4d8dc;margin-top:28px;margin-bottom:28px;padding:8px 44px 48px}section{padding:32px 0;border-top:3px solid var(--navy)}section:first-child{border-top:0}h2{font-size:25px;color:#082d59;margin:5px 0 18px}h3{color:#082d59}.hero{background:#eaf4fb;border-left:7px solid var(--blue);padding:20px 24px;margin-bottom:16px}.hero-title{font-size:25px;font-weight:800;color:#082d59}.hero-text{margin-top:8px}.horizon-grid,.action-grid,.source-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.horizon{border:1px solid var(--line);border-top:5px solid var(--blue);padding:16px;min-height:165px}.horizon-time{color:#004b87;font-weight:700}.horizon-direction{font-size:21px;font-weight:800;color:#082d59;margin:7px 0}.focus{color:#596b7c}.risk,.card-risk{color:#b42318;font-size:14px}.action-box{border:1px solid var(--line);padding:16px;min-height:135px}.action-box h3{margin-top:0}.calendar-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.day{border:1px solid var(--line);border-top:5px solid var(--blue);padding:14px;min-height:150px}.day h3{margin:0;font-size:19px}.weekday{color:#667788;border-bottom:1px solid var(--line);padding:2px 0 10px}.event{margin-top:10px}.event span{background:var(--blue);color:white;border-radius:3px;padding:3px 6px;margin-right:6px}.event strong{font-size:13px}.event small{display:block;color:#52677b;margin-top:5px}.logic-root{background:var(--navy);color:#fff;font-size:21px;font-weight:800;text-align:center;padding:16px}.flow{display:flex;gap:20px;border-left:4px solid var(--blue);background:#f3f6f8;padding:12px 15px;margin-top:8px}.logic-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:14px}.logic{border:1px solid var(--line);padding:15px;display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:8px;align-items:center}.logic em{grid-column:1/-1;color:#8a2b20;font-style:normal;font-weight:700}.source-grid{grid-template-columns:repeat(2,1fr)}.source-card{border:1px solid var(--line);border-left:4px solid var(--blue);padding:15px}.card-label{display:inline-block;background:#eaf4fb;color:#004b87;font-size:12px;font-weight:800;padding:3px 8px;margin-bottom:8px}.source-card h3{margin:0 0 7px}.source-card p{color:#243b53;margin:7px 0}.stock-meta{background:#f3f6f8;color:#40566b;font-size:13px;padding:6px 8px;margin:6px 0}.card-note,.card-risk{border-top:1px solid #e1e6eb;padding-top:7px;margin-top:7px}.source-card a{display:inline-block;color:#005ea8;font-size:13px;margin-top:9px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th{background:var(--navy);color:#fff;text-align:left}th,td{border:1px solid var(--line);padding:11px;vertical-align:top}.audit-ok,.audit-warn{padding:15px;border-left:6px solid}.audit-ok{background:#e9f6ec;border-color:#168821}.audit-warn{background:#fff1f0;border-color:var(--red)}.metrics{display:flex;gap:28px;margin-top:14px}.muted{color:#6c7883}footer{background:var(--navy);color:#fff;padding:26px 36px;font-size:13px}@media(max-width:900px){.horizon-grid,.action-grid,.source-grid,.logic-grid{grid-template-columns:1fr}.calendar-grid{grid-template-columns:repeat(2,1fr)}main{margin:0;padding:20px}.logo{width:65px}.navbar{font-size:12px}}
"""

CSS = """
:root{--navy:#071a34;--navy-2:#12385b;--navy-3:#1d466f;--blue:#1769aa;--red:#b21f32;--gold:#b7a06a;--ink:#172336;--muted:#5f6c7b;--line:#d7dde4;--paper:#f5f4ef;--white:#fff}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.72 "Noto Sans SC","Source Han Sans SC","Microsoft YaHei UI","Microsoft YaHei",Arial,sans-serif;-webkit-font-smoothing:antialiased}.wrap{width:100%;max-width:1580px;margin:0 auto;padding-left:52px;padding-right:52px}.gov-banner{background:#fff;border-bottom:1px solid #d8dde3;color:#3b4857;font-size:13px;letter-spacing:.03em}.gov-banner .wrap{min-height:38px;display:flex;align-items:center;gap:11px}.flag-mark{display:inline-grid;grid-template-columns:repeat(3,4px);gap:2px;width:18px}.flag-mark i{display:block;width:4px;height:4px;background:var(--red)}.flag-mark i:nth-child(2n){background:var(--navy-2)}.masthead{background:linear-gradient(112deg,#071a34 0%,#0c2c4d 63%,#153d62 100%);color:#fff;border-bottom:1px solid rgba(255,255,255,.18)}.brand{min-height:170px;display:flex;align-items:center;gap:28px}.logo{width:96px;height:96px;flex:0 0 96px}.mast-copy{min-width:0}.overline{font:700 12px/1.2 Arial,sans-serif;letter-spacing:.28em;color:#d6c598;margin-bottom:14px}.masthead h1{margin:0;font:500 clamp(38px,4vw,58px)/1 Georgia,"Noto Serif SC","Songti SC",serif;letter-spacing:.035em}.mast-subtitle{margin-top:15px;color:#d9e2eb;font-size:17px;letter-spacing:.09em}.report-stamp{margin-left:auto;border-left:1px solid rgba(255,255,255,.28);padding-left:32px;text-align:right}.report-stamp span{display:block;color:#d6c598;font:700 11px/1.2 Arial,sans-serif;letter-spacing:.22em}.report-stamp strong{display:block;margin-top:8px;font:500 22px/1.2 Georgia,serif;letter-spacing:.04em}.navbar{background:#fff;border-bottom:4px solid var(--red);box-shadow:0 2px 10px rgba(7,26,52,.08)}.nav-inner{min-height:58px;display:flex;align-items:center;gap:42px;color:var(--navy);font:700 13px/1 Arial,sans-serif;letter-spacing:.12em}.nav-inner span+span:before{content:"";display:inline-block;width:1px;height:14px;background:#cbd2d9;margin-right:42px;vertical-align:middle}main{width:100%;max-width:1580px;margin:0 auto;background:#fff;box-shadow:0 0 0 1px rgba(7,26,52,.05)}section{padding:54px 52px;border-top:1px solid var(--line)}section:first-child{border-top:0}.section-heading{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-bottom:24px}.section-heading h2,section>h2{margin:0;color:var(--navy);font:650 clamp(27px,2.3vw,36px)/1.25 Georgia,"Noto Serif SC","Songti SC",serif;letter-spacing:.01em}.section-heading small{color:#7a8491;font:700 11px/1 Arial,sans-serif;letter-spacing:.22em;white-space:nowrap}.hero{background:linear-gradient(105deg,#edf3f8 0%,#f8fafb 100%);border-left:8px solid var(--red);padding:28px 32px;margin-bottom:20px}.hero-title{color:var(--navy);font:650 clamp(25px,2.2vw,34px)/1.25 Georgia,"Noto Serif SC","Songti SC",serif}.hero-text{max-width:1100px;margin-top:10px;color:#33485f;font-size:18px}.horizon-grid,.action-grid,.source-grid{display:grid;gap:0;border:1px solid var(--line)}.horizon-grid,.action-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.horizon,.action-box{padding:24px 26px;min-height:176px;background:#fff;border-right:1px solid var(--line)}.horizon:last-child,.action-box:last-child{border-right:0}.horizon-time{color:var(--red);font:700 11px/1.2 Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase}.horizon-direction{color:var(--navy);font:650 23px/1.25 Georgia,"Noto Serif SC","Songti SC",serif;margin:13px 0 7px}.focus{color:var(--blue);font-size:14px;font-weight:700;letter-spacing:.03em}.horizon p{margin:10px 0}.risk,.card-risk{color:#9c2633;font-size:14px}.action-box h3{margin:0 0 15px;color:var(--navy);font:650 22px/1.2 Georgia,"Noto Serif SC","Songti SC",serif}.action-box ul{margin:0;padding-left:19px}.action-box li+li{margin-top:8px}.calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border:1px solid var(--line);background:#fff}.day{min-height:176px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:0}.day:nth-child(7n){border-right:0}.day:nth-last-child(-n+7){border-bottom:0}.day-head{background:#f1f4f7;border-bottom:1px solid var(--line);padding:14px 15px 11px}.day h3{margin:0;color:var(--navy);font:650 17px/1.2 Georgia,"Noto Serif SC","Songti SC",serif}.weekday{margin-top:4px;color:#788493;font-size:12px}.event{padding:13px 14px}.event+.event{border-top:1px solid #edf0f3}.event span{display:inline-block;margin-right:6px;color:var(--red);font:700 10px/1 Arial,sans-serif}.event strong{display:block;margin-top:5px;color:#24384e;font-size:13px;line-height:1.45}.event small{display:block;margin-top:5px;color:#73808d;font-size:11px}.event-empty{padding:14px;color:#9ba4ad;font-size:12px}.logic-root{background:var(--navy);color:#fff;text-align:center;padding:20px 28px;font:650 23px/1.3 Georgia,"Noto Serif SC","Songti SC",serif;border-bottom:4px solid var(--red)}.flow-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--line);border-top:0}.flow{position:relative;min-height:122px;padding:22px 22px 18px;border-right:1px solid var(--line)}.flow:last-child{border-right:0}.flow-index{display:block;color:var(--red);font:700 10px/1 Arial,sans-serif;letter-spacing:.15em;margin-bottom:12px}.flow strong{color:var(--navy);font-size:15px}.flow i{margin:0 9px;color:var(--red);font-style:normal}.flow p{margin:8px 0 0;color:var(--muted);font-size:14px}.logic-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:18px}.logic{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:9px;align-items:center;border:1px solid var(--line);border-top:4px solid var(--navy-2);padding:20px;min-height:180px;background:#fbfcfd}.logic-step small,.logic-action small{display:block;color:#89939e;font:700 9px/1 Arial,sans-serif;letter-spacing:.15em;margin-bottom:7px}.logic-step strong,.logic-step span{color:#24384e;font-size:14px;line-height:1.45}.logic-arrow{color:var(--red);font-size:19px}.logic-action{grid-column:1/-1;border-top:1px solid var(--line);padding-top:12px;color:var(--navy);font-weight:700}.company-grid{grid-template-columns:repeat(4,minmax(0,1fr));border:0;gap:15px}.media-grid{grid-template-columns:repeat(3,minmax(0,1fr));border:0;gap:15px}.source-card{display:flex;flex-direction:column;min-width:0;border:1px solid var(--line);border-top:5px solid var(--navy-2);padding:22px;background:#fff;box-shadow:0 8px 20px rgba(7,26,52,.045)}.card-label{align-self:flex-start;background:#e9f1f8;color:#074f84;font:800 11px/1 Arial,sans-serif;letter-spacing:.08em;padding:7px 10px;margin-bottom:15px}.source-card h3{margin:0;color:var(--navy);font:650 22px/1.25 Georgia,"Noto Serif SC","Songti SC",serif}.source-card>p{margin:13px 0;color:#35495d}.stock-meta{background:#f2f5f7;border:1px solid #e4e8ec;color:#4c6074;font-size:12px;padding:8px 10px;margin:5px 0 3px}.card-note,.card-risk{border-top:1px solid #e2e6ea;padding-top:9px;margin-top:9px;font-size:13px}.card-note{color:#344d65}.source-links{display:flex;flex-wrap:wrap;gap:8px 12px;margin-top:auto;padding-top:18px}.source-links a,.source-links span{display:inline-flex;align-items:center;gap:4px;color:#075ea1;font-size:12px;text-decoration:none;border-bottom:1px solid #8eb7d5}.source-links a:hover{color:var(--red);border-color:var(--red)}.source-links a span{border:0}.prediction-note{margin:-11px 0 20px;color:#6a7684;font-size:14px}.table-wrap{overflow:auto;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;background:#fff}th{background:var(--navy);color:#fff;text-align:left;font:700 11px/1.2 Arial,sans-serif;letter-spacing:.11em;text-transform:uppercase}th,td{padding:15px 16px;border-bottom:1px solid var(--line);vertical-align:top}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f7f9fa}.direction-pill{display:inline-block;background:#eaf1f7;color:#0a568d;font-size:12px;font-weight:800;padding:4px 8px}.integrity{display:flex;align-items:center;gap:20px;margin:0 52px 38px;padding:13px 17px;background:#f3f4f5;border:1px solid #e1e4e7;color:#66717c;font-size:12px}.integrity-title{color:#344657;font-weight:800;white-space:nowrap}.audit-ok,.audit-warn{flex:1}.audit-ok strong{color:#2d6442}.audit-warn strong{color:#9c2633}.metrics{display:flex;gap:18px;white-space:nowrap}.metrics strong{color:#33485f}.muted{color:var(--muted)}footer{background:var(--navy);color:#d7e0e9;border-top:7px solid var(--red)}.footer-main{display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:70px;padding-top:58px;padding-bottom:58px}.footer-brand{color:#fff;font:500 34px/1 Georgia,serif;letter-spacing:.04em}.footer-tagline{margin-top:16px;color:#aebccb;max-width:450px}.footer-col h3{margin:0 0 17px;color:#fff;font:700 11px/1 Arial,sans-serif;letter-spacing:.2em}.footer-col p{margin:0;color:#aebccb;font-size:13px}.footer-bottom{border-top:1px solid rgba(255,255,255,.17);padding-top:22px;padding-bottom:25px;display:flex;justify-content:space-between;gap:20px;color:#91a3b5;font-size:11px;letter-spacing:.04em}@media(max-width:1200px){.company-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.calendar-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.day:nth-child(7n),.day:nth-last-child(-n+7){border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.day:nth-child(4n){border-right:0}.day:nth-last-child(-n+2){border-bottom:0}.report-stamp{display:none}}@media(max-width:820px){.wrap{padding-left:22px;padding-right:22px}.brand{min-height:138px}.logo{width:72px;height:72px;flex-basis:72px}.mast-subtitle{font-size:14px}.nav-inner{gap:18px;overflow:auto}.nav-inner span+span:before{margin-right:18px}.horizon-grid,.action-grid,.flow-strip,.logic-grid,.media-grid,.company-grid{grid-template-columns:1fr}.horizon,.action-box,.flow{border-right:0;border-bottom:1px solid var(--line)}.calendar-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.day:nth-child(4n){border-right:1px solid var(--line)}.day:nth-child(2n){border-right:0}.day:nth-last-child(-n+2){border-bottom:0}section{padding:38px 22px}.section-heading{align-items:flex-start;flex-direction:column}.section-heading small{white-space:normal}.logic{grid-template-columns:1fr}.logic-arrow{transform:rotate(90deg);text-align:center}.integrity{margin:0 22px 26px;align-items:flex-start;flex-direction:column}.metrics{white-space:normal;flex-wrap:wrap}.footer-main{grid-template-columns:1fr;gap:30px;padding-top:40px;padding-bottom:40px}.footer-bottom{flex-direction:column}.gov-banner{font-size:11px}}
"""
CSS += ".logic:last-child:nth-child(odd){grid-column:1/-1}"


def render_report(context: dict) -> str:
    direction = context.get("direction", {})
    actions = context.get("actions", {})
    gate = context["gate"]
    failures = context.get("core_failures", [])
    audit_class = "audit-ok" if gate.allowed else "audit-warn"
    audit_title = "核心官方来源本轮读取正常" if gate.allowed else "数据存在缺口，本轮不冻结预测"
    report_date = str(context.get("report_date") or date.today().isoformat())[:10]
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEWS FINANCE | Global Market Intelligence</title><style>{CSS}</style></head><body>
<div class="gov-banner"><div class="wrap"><span class="flag-mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></span>Independent Investment Research · Public Data · Non-Government Website</div></div>
<header class="masthead"><div class="wrap brand">{_logo()}<div class="mast-copy"><div class="overline">GLOBAL MARKET INTELLIGENCE</div><h1>NEWS FINANCE</h1><div class="mast-subtitle">全球宏观事件驱动投资分析 · Daily Investment Briefing</div></div><div class="report-stamp"><span>REPORT DATE</span><strong>{esc(report_date)}</strong></div></div></header>
<nav class="navbar"><div class="wrap nav-inner"><span>MACRO OUTLOOK</span><span>CAPITAL FLOW</span><span>SECTOR VIEW</span><span>EQUITY ACTION</span></div></nav><main>
<section><div class="section-heading"><h2>一｜今日投资方向</h2><small>MARKET DIRECTION</small></div><div class="hero"><div class="hero-title">{esc(direction.get('title','等待确认'))}</div><div class="hero-text">{esc(direction.get('brief'))}</div></div><div class="horizon-grid">{_horizons(context)}</div></section>
<section><div class="section-heading"><h2>二｜具体动作</h2><small>ACTION AGENDA</small></div><div class="action-grid"><div class="action-box"><h3>观察</h3>{_list(actions.get('watch'))}</div><div class="action-box"><h3>准备</h3>{_list(actions.get('prepare'))}</div><div class="action-box"><h3>回避 / 降低风险</h3>{_list(actions.get('avoid'))}</div></div></section>
<section><div class="section-heading"><h2>三｜未来14日重要日程</h2><small>ECONOMIC CALENDAR</small></div><div class="calendar-grid">{_calendar(context)}</div></section>
<section><div class="section-heading"><h2>四｜资金流向与投资逻辑</h2><small>CAPITAL FLOW &amp; TRANSMISSION</small></div><div class="logic-root">{esc(direction.get('title','等待确认'))}</div>{_logic(context)}</section>
<section><div class="section-heading"><h2>五｜重点公司前瞻</h2><small>EQUITY WATCHLIST</small></div><div class="source-grid company-grid">{_source_cards(context,'company')}</div></section>
<section><div class="section-heading"><h2>六｜市场正在交易什么</h2><small>MARKET FOCUS</small></div><div class="source-grid media-grid">{_source_cards(context,'media')}</div></section>
<section><div class="section-heading"><h2>七｜预测与验证</h2><small>FORECAST &amp; REVIEW</small></div><p class="prediction-note">判断生成后即冻结，后续仅以真实市场结果检验；不因结果倒推或修改原始结论。</p>{_predictions(context)}</section>
<aside class="integrity"><span class="integrity-title">数据完整性</span><div class="{audit_class}"><strong>{audit_title}</strong>　核心失败：{esc(' · '.join(failures) or '无')}　门槛原因：{esc(', '.join(gate.reasons) or '无')}</div><div class="metrics"><span>覆盖率 <strong>{context.get('market_coverage',0):.0%}</strong></span><span>冻结 <strong>{context.get('predictions_frozen',0)}</strong></span><span>来源 <strong>{len(context.get('sources',[]))}</strong></span></div></aside>
</main><footer><div class="wrap footer-main"><div><div class="footer-brand">NEWS FINANCE</div><div class="footer-tagline">Independent research for a clearer view of macro events, capital flows and equity decisions.</div></div><div class="footer-col"><h3>RESEARCH FRAMEWORK</h3><p>官方数据 · 公司公告 · 跨资产验证<br>事件推演 · 历史参照 · 事后复盘</p></div><div class="footer-col"><h3>DISCLOSURE</h3><p>本报告仅用于研究与学习，不构成投资建议、收益保证或证券买卖承诺。</p></div></div><div class="wrap footer-bottom"><span>NEWS FINANCE · INDEPENDENT MARKET RESEARCH</span><span>PUBLIC INFORMATION · NON-GOVERNMENT WEBSITE · {esc(report_date)}</span></div></footer></body></html>"""
