from __future__ import annotations

import html
import re
from datetime import date, timedelta

from .sources import COMPANY_NAMES


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
    return """<svg class="logo" viewBox="0 0 100 100" aria-label="NEWS FINANCE"><circle cx="50" cy="50" r="46" fill="#fff" stroke="#16345c" stroke-width="4"/><circle cx="50" cy="50" r="38" fill="none" stroke="#6e8eae" stroke-width="2"/><path d="M30 30 L50 22 L70 30 L67 68 L50 80 L33 68 Z" fill="#16345c"/><path d="M38 59 L47 49 L54 55 L65 39" fill="none" stroke="#fff" stroke-width="4"/><circle cx="39" cy="38" r="2.5" fill="#fff"/><circle cx="55" cy="33" r="2.5" fill="#fff"/><text x="50" y="70" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">NF</text></svg>"""


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
    end = start + timedelta(days=14)
    cells = []
    for current_text in sorted(by_date):
        try:
            current = date.fromisoformat(current_text)
        except ValueError:
            continue
        if not start <= current < end:
            continue
        body = []
        for index, event in enumerate(by_date[current_text], 1):
            title = translate_event_title(event.get("title"))
            source = SOURCE_LABELS.get(str(event.get("source", "")), "官方来源")
            body.append(f"<div class='event'><span>{index:02d}</span><strong>{esc(title)}</strong><small>{esc(source)}</small></div>")
        cells.append(f"<div class='day'><h3>{current.month}月{current.day}日</h3><div class='weekday'>周{weekdays[current.weekday()]}</div>{''.join(body)}</div>")
    return "".join(cells) or "<p class='muted'>未来14日暂无已确认的重要数据日程。</p>"


def _logic(context):
    flow_html = "".join(f"<div class='flow'><strong>{esc(x.get('from'))} → {esc(x.get('to'))}</strong><span>{esc(x.get('brief'))}</span></div>" for x in context.get("flows", [])[:3]) or "<p class='muted'>本轮没有形成明确资金迁移方向。</p>"
    chain_html = "".join(f"<div class='logic'><strong>{esc(x.get('cause'))}</strong><b>→</b><span>{esc(x.get('middle'))}</span><b>→</b><span>{esc(x.get('result'))}</span><em>{esc(x.get('action'))}</em></div>" for x in context.get("logic", [])[:4]) or "<p class='muted'>等待更多交叉资产证据。</p>"
    return flow_html + f"<div class='logic-grid'>{chain_html}</div>"


def _source_cards(context, kind):
    source_urls = {str(x.get("name")): x.get("url", "#") for x in context.get("sources", [])}
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
            source_names = [str(item.get("source", ""))]
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
        source_label = " · ".join(
            SOURCE_LABELS.get(x, f"{x[:-3]}动态新闻" if x.endswith(" 新闻") else x)
            for x in source_names
        ) or "公开来源"
        source_url = next((source_urls[x] for x in source_names if x in source_urls), "#")
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
            f"<p>{esc(brief)}</p>{details}<a href='{esc(source_url)}'>{esc(source_label)}</a></div>"
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
        rows.append(f"<tr><td>{esc(item.get('horizon_days'))}日</td><td><strong>{esc(item.get('target'))}</strong></td><td>{esc(direction)}</td><td>{probability}</td><td>{esc(item.get('thesis'))}</td><td>{esc(item.get('invalidation'))}</td></tr>")
    if not rows:
        return "<p class='muted'>当前证据不足，暂不形成方向性预测。</p>"
    return "<div class='table-wrap'><table><thead><tr><th>周期</th><th>对象</th><th>判断</th><th>概率</th><th>逻辑</th><th>失效条件</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"


CSS = """
:root{--navy:#17365d;--blue:#005ea8;--red:#d83933;--ink:#111820;--muted:#586675;--line:#cbd2d9}*{box-sizing:border-box}body{margin:0;background:#eee;font:16px/1.55 Arial,"Microsoft YaHei",sans-serif;color:var(--ink)}.wrap,main{max-width:1380px;margin:auto}.top-strip{background:#f7f7f7;border-bottom:1px solid #d9d9d9;font-size:12px;color:#38495a;padding:8px 36px}header{background:#fff;padding:18px 36px}.brand{display:flex;align-items:center;gap:22px}.logo{width:90px;height:90px}.eyebrow,.kicker{font-size:12px;letter-spacing:2px;font-weight:700;color:#637587}h1{font-size:34px;line-height:1.1;color:#082d59;margin:7px 0 3px}.subtitle{color:#43576b}.navbar{background:var(--navy);border-bottom:5px solid var(--red);color:#fff;font-weight:700;padding:13px 36px}main{background:#fff;border:1px solid #d4d8dc;margin-top:28px;margin-bottom:28px;padding:8px 44px 48px}section{padding:32px 0;border-top:3px solid var(--navy)}section:first-child{border-top:0}h2{font-size:25px;color:#082d59;margin:5px 0 18px}h3{color:#082d59}.hero{background:#eaf4fb;border-left:7px solid var(--blue);padding:20px 24px;margin-bottom:16px}.hero-title{font-size:25px;font-weight:800;color:#082d59}.hero-text{margin-top:8px}.horizon-grid,.action-grid,.source-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.horizon{border:1px solid var(--line);border-top:5px solid var(--blue);padding:16px;min-height:165px}.horizon-time{color:#004b87;font-weight:700}.horizon-direction{font-size:21px;font-weight:800;color:#082d59;margin:7px 0}.focus{color:#596b7c}.risk,.card-risk{color:#b42318;font-size:14px}.action-box{border:1px solid var(--line);padding:16px;min-height:135px}.action-box h3{margin-top:0}.calendar-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.day{border:1px solid var(--line);border-top:5px solid var(--blue);padding:14px;min-height:150px}.day h3{margin:0;font-size:19px}.weekday{color:#667788;border-bottom:1px solid var(--line);padding:2px 0 10px}.event{margin-top:10px}.event span{background:var(--blue);color:white;border-radius:3px;padding:3px 6px;margin-right:6px}.event strong{font-size:13px}.event small{display:block;color:#52677b;margin-top:5px}.logic-root{background:var(--navy);color:#fff;font-size:21px;font-weight:800;text-align:center;padding:16px}.flow{display:flex;gap:20px;border-left:4px solid var(--blue);background:#f3f6f8;padding:12px 15px;margin-top:8px}.logic-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:14px}.logic{border:1px solid var(--line);padding:15px;display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:8px;align-items:center}.logic em{grid-column:1/-1;color:#8a2b20;font-style:normal;font-weight:700}.source-grid{grid-template-columns:repeat(2,1fr)}.source-card{border:1px solid var(--line);border-left:4px solid var(--blue);padding:15px}.card-label{display:inline-block;background:#eaf4fb;color:#004b87;font-size:12px;font-weight:800;padding:3px 8px;margin-bottom:8px}.source-card h3{margin:0 0 7px}.source-card p{color:#243b53;margin:7px 0}.stock-meta{background:#f3f6f8;color:#40566b;font-size:13px;padding:6px 8px;margin:6px 0}.card-note,.card-risk{border-top:1px solid #e1e6eb;padding-top:7px;margin-top:7px}.source-card a{display:inline-block;color:#005ea8;font-size:13px;margin-top:9px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th{background:var(--navy);color:#fff;text-align:left}th,td{border:1px solid var(--line);padding:11px;vertical-align:top}.audit-ok,.audit-warn{padding:15px;border-left:6px solid}.audit-ok{background:#e9f6ec;border-color:#168821}.audit-warn{background:#fff1f0;border-color:var(--red)}.metrics{display:flex;gap:28px;margin-top:14px}.muted{color:#6c7883}footer{background:var(--navy);color:#fff;padding:26px 36px;font-size:13px}@media(max-width:900px){.horizon-grid,.action-grid,.source-grid,.logic-grid{grid-template-columns:1fr}.calendar-grid{grid-template-columns:repeat(2,1fr)}main{margin:0;padding:20px}.logo{width:65px}.navbar{font-size:12px}}
"""


def render_report(context: dict) -> str:
    direction = context.get("direction", {})
    actions = context.get("actions", {})
    gate = context["gate"]
    failures = context.get("core_failures", [])
    audit_class = "audit-ok" if gate.allowed else "audit-warn"
    audit_title = "核心官方来源本轮读取正常" if gate.allowed else "数据存在缺口，本轮不冻结预测"
    report_date = str(context.get("report_date") or date.today().isoformat())[:10]
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>投资方向研究简报</title><style>{CSS}</style></head><body>
<div class="top-strip"><div class="wrap">独立市场研究　·　公开信息整合　·　非政府网站</div></div><header><div class="wrap brand">{_logo()}<div><div class="eyebrow">NEWS FINANCE · 投资情报</div><h1>投资方向研究简报</h1><div class="subtitle">宏观判断 · 资金流向 · 行业机会 · 个股动作　|　{esc(report_date)}</div></div></div></header><div class="navbar"><div class="wrap">宏观判断　/　资金流向　/　行业机会　/　个股动作</div></div><main>
<section><div class="kicker">今日结论</div><h2>一｜今日投资方向</h2><div class="hero"><div class="hero-title">{esc(direction.get('title','等待确认'))}</div><div class="hero-text">{esc(direction.get('brief'))}</div></div><div class="horizon-grid">{_horizons(context)}</div></section>
<section><div class="kicker">执行清单</div><h2>二｜具体动作</h2><div class="action-grid"><div class="action-box"><h3>观察</h3>{_list(actions.get('watch'))}</div><div class="action-box"><h3>准备</h3>{_list(actions.get('prepare'))}</div><div class="action-box"><h3>回避 / 降低风险</h3>{_list(actions.get('avoid'))}</div></div></section>
<section><div class="kicker">关键日程</div><h2>三｜未来14日重要日程</h2><div class="calendar-grid">{_calendar(context)}</div></section>
<section><div class="kicker">影响链</div><h2>四｜资金流向与投资逻辑</h2><div class="logic-root">{esc(direction.get('title','等待确认'))}</div>{_logic(context)}</section>
<section><div class="kicker">个股信号</div><h2>五｜重点公司前瞻</h2><div class="source-grid">{_source_cards(context,'company')}</div></section>
<section><div class="kicker">市场焦点</div><h2>六｜市场正在交易什么</h2><div class="source-grid">{_source_cards(context,'media')}</div></section>
<section><div class="kicker">跟踪验证</div><h2>七｜预测与验证</h2><p class="muted">预测生成后即冻结，后续只用真实市场结果验证，不做事后修改。</p>{_predictions(context)}</section>
<section><div class="kicker">数据检查</div><h2>数据完整性</h2><div class="{audit_class}"><strong>{audit_title}</strong><br>核心失败：{esc(' · '.join(failures) or '无')}　门槛原因：{esc(', '.join(gate.reasons) or '无')}</div><div class="metrics"><span>市场覆盖率：<strong>{context.get('market_coverage',0):.0%}</strong></span><span>本轮冻结：<strong>{context.get('predictions_frozen',0)}</strong></span><span>来源数量：<strong>{len(context.get('sources',[]))}</strong></span></div></section>
</main><footer><div class="wrap">NEWS FINANCE · 独立投资研究<br>官方数据 · 公司公告 · 跨资产验证 · 事后复盘<br><br>本报告仅用于研究与学习，不构成投资建议、收益保证或证券买卖承诺。</div></footer></body></html>"""
