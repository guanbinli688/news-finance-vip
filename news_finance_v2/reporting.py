from __future__ import annotations

import html
from datetime import date, timedelta


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


def translate_event_title(title) -> str:
    normalized = " ".join(str(title or "").split())
    return BLS_EVENT_TRANSLATIONS.get(normalized, normalized)


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
    cells = []
    try:
        start = date.fromisoformat(str(context.get("report_date", ""))[:10])
    except ValueError:
        start = date.today()
    for offset in range(14):
        current = start + timedelta(days=offset)
        body = []
        for index, event in enumerate(by_date.get(current.isoformat(), []), 1):
            title = translate_event_title(event.get("title"))
            body.append(f"<div class='event'><span>{index:02d}</span><strong>{esc(title)}</strong><small>{esc(event.get('source', '官方来源'))}</small></div>")
        if not body:
            body.append("<p class='muted'>暂无重点日程</p>")
        cells.append(f"<div class='day'><h3>{current.month}月{current.day}日</h3><div class='weekday'>周{weekdays[current.weekday()]}</div>{''.join(body)}</div>")
    return "".join(cells)


def _logic(context):
    flow_html = "".join(f"<div class='flow'><strong>{esc(x.get('from'))} → {esc(x.get('to'))}</strong><span>{esc(x.get('brief'))}</span></div>" for x in context.get("flows", [])[:3]) or "<p class='muted'>本轮没有形成明确资金迁移方向。</p>"
    chain_html = "".join(f"<div class='logic'><strong>{esc(x.get('cause'))}</strong><b>→</b><span>{esc(x.get('middle'))}</span><b>→</b><span>{esc(x.get('result'))}</span><em>{esc(x.get('action'))}</em></div>" for x in context.get("logic", [])[:4]) or "<p class='muted'>等待更多交叉资产证据。</p>"
    return flow_html + f"<div class='logic-grid'>{chain_html}</div>"


def _source_cards(context, kind):
    source_urls = {str(x.get("name")): x.get("url", "#") for x in context.get("sources", [])}
    curated = context.get("company_signals" if kind == "company" else "media_themes", [])
    curated_cards = []
    for item in curated[:4]:
        if kind == "company":
            title = item.get("company") or item.get("source") or "公司信号"
            label = item.get("signal") or "等待确认"
            brief = item.get("brief") or "证据尚不足。"
            source_names = [str(item.get("source", ""))]
        else:
            title = item.get("title") or "市场主题"
            label = item.get("tone") or "中性"
            brief = item.get("brief") or "证据尚不足。"
            source_names = [str(x) for x in item.get("sources", [])]
        source_names = [x for x in source_names if x]
        source_label = " · ".join(source_names) or "公开来源"
        source_url = next((source_urls[x] for x in source_names if x in source_urls), "#")
        curated_cards.append(
            f"<div class='source-card'><div class='card-label'>{esc(label)}</div><h3>{esc(title)}</h3>"
            f"<p>{esc(brief)}</p><a href='{esc(source_url)}'>{esc(source_label)}</a></div>"
        )
    if curated_cards:
        return "".join(curated_cards)
    sources = [x for x in context.get("sources", []) if x.get("kind") == kind and x.get("status") == "SUCCESS"]
    cards = []
    for source in sources[:8]:
        text = " ".join(str(source.get("text", "")).split())[:220]
        cards.append(f"<div class='source-card'><h3>{esc(source.get('name'))}</h3><p>{esc(text or '已读取，等待提炼。')}</p><a href='{esc(source.get('url'))}'>官方来源</a></div>")
    return "".join(cards) or "<p class='muted'>本轮暂无可展示的一手信号。</p>"


def _predictions(context):
    rows = []
    for item in context.get("display_predictions", context.get("predictions", [])):
        try:
            probability = f"{float(item.get('probability', 0)):.0%}"
        except (TypeError, ValueError):
            probability = "—"
        rows.append(f"<tr><td>{esc(item.get('horizon_days'))}日</td><td><strong>{esc(item.get('target'))}</strong></td><td>{esc(item.get('direction'))}</td><td>{probability}</td><td>{esc(item.get('thesis'))}</td><td>{esc(item.get('invalidation'))}</td></tr>")
    if not rows:
        return "<p class='muted'>当前证据不足，暂不形成方向性预测。</p>"
    return "<div class='table-wrap'><table><thead><tr><th>周期</th><th>对象</th><th>判断</th><th>概率</th><th>逻辑</th><th>失效条件</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"


CSS = """
:root{--navy:#17365d;--blue:#005ea8;--red:#d83933;--ink:#111820;--muted:#586675;--line:#cbd2d9}*{box-sizing:border-box}body{margin:0;background:#eee;font:16px/1.55 Arial,"Microsoft YaHei",sans-serif;color:var(--ink)}.wrap,main{max-width:1380px;margin:auto}.top-strip{background:#f7f7f7;border-bottom:1px solid #d9d9d9;font-size:12px;color:#38495a;padding:8px 36px}header{background:#fff;padding:18px 36px}.brand{display:flex;align-items:center;gap:22px}.logo{width:90px;height:90px}.eyebrow,.kicker{font-size:12px;letter-spacing:2px;font-weight:700;color:#637587;text-transform:uppercase}h1{font-size:34px;line-height:1.1;color:#082d59;margin:7px 0 3px}.subtitle{color:#43576b}.navbar{background:var(--navy);border-bottom:5px solid var(--red);color:#fff;font-weight:700;padding:13px 36px}main{background:#fff;border:1px solid #d4d8dc;margin-top:28px;margin-bottom:28px;padding:8px 44px 48px}section{padding:38px 0;border-top:3px solid var(--navy)}section:first-child{border-top:0}h2{font-size:25px;color:#082d59;margin:5px 0 20px}h3{color:#082d59}.hero{background:#eaf4fb;border-left:7px solid var(--blue);padding:22px 26px;margin-bottom:16px}.hero-title{font-size:25px;font-weight:800;color:#082d59}.hero-text{margin-top:8px}.horizon-grid,.action-grid,.source-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.horizon{border:1px solid var(--line);border-top:5px solid var(--blue);padding:18px;min-height:180px}.horizon-time{color:#004b87;font-weight:700}.horizon-direction{font-size:21px;font-weight:800;color:#082d59;margin:7px 0}.focus{color:#596b7c}.risk{color:#c82020;font-size:14px}.action-box{border:1px solid var(--line);padding:18px;min-height:150px}.action-box h3{margin-top:0}.calendar-grid{display:grid;grid-template-columns:repeat(7,1fr)}.day{border:1px solid var(--line);border-top:5px solid var(--blue);padding:14px;min-height:230px}.day h3{margin:0;font-size:19px}.weekday{color:#667788;border-bottom:1px solid var(--line);padding:2px 0 12px}.event{margin-top:12px}.event span{background:var(--blue);color:white;border-radius:3px;padding:3px 6px;margin-right:6px}.event strong{font-size:13px}.event small{display:block;color:#52677b;margin-top:5px}.logic-root{background:var(--navy);color:#fff;font-size:21px;font-weight:800;text-align:center;padding:18px}.flow{display:flex;gap:20px;border-left:4px solid var(--blue);background:#f3f6f8;padding:13px 16px;margin-top:8px}.logic-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:14px}.logic{border:1px solid var(--line);padding:16px;display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:8px;align-items:center}.logic em{grid-column:1/-1;color:#8a2b20;font-style:normal;font-weight:700}.source-grid{grid-template-columns:repeat(2,1fr)}.source-card{border:1px solid var(--line);border-left:4px solid var(--blue);padding:16px}.card-label{display:inline-block;background:#eaf4fb;color:#004b87;font-size:12px;font-weight:800;padding:3px 8px;margin-bottom:8px}.source-card h3{margin:0 0 8px}.source-card p{color:#34495e}.source-card a{color:#005ea8;font-size:13px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th{background:var(--navy);color:#fff;text-align:left}th,td{border:1px solid var(--line);padding:12px;vertical-align:top}.audit-ok,.audit-warn{padding:16px;border-left:6px solid}.audit-ok{background:#e9f6ec;border-color:#168821}.audit-warn{background:#fff1f0;border-color:var(--red)}.metrics{display:flex;gap:28px;margin-top:14px}.muted{color:#7a8792}footer{background:var(--navy);color:#fff;padding:30px 36px;font-size:13px}@media(max-width:900px){.horizon-grid,.action-grid,.source-grid,.logic-grid{grid-template-columns:1fr}.calendar-grid{grid-template-columns:repeat(2,1fr)}main{margin:0;padding:20px}.logo{width:65px}.navbar{font-size:12px}}
"""


def render_report(context: dict) -> str:
    direction = context.get("direction", {})
    actions = context.get("actions", {})
    gate = context["gate"]
    failures = context.get("core_failures", [])
    audit_class = "audit-ok" if gate.allowed else "audit-warn"
    audit_title = "核心官方来源本轮读取正常" if gate.allowed else "数据存在缺口，本轮不冻结预测"
    report_date = str(context.get("report_date") or date.today().isoformat())[:10]
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEWS FINANCE V2</title><style>{CSS}</style></head><body>
<div class="top-strip"><div class="wrap">Independent Market Research　·　独立公开信息研究　·　非美国政府网站</div></div><header><div class="wrap brand">{_logo()}<div><div class="eyebrow">NEWS FINANCE · MARKET INTELLIGENCE</div><h1>投资方向研究简报</h1><div class="subtitle">宏观 · 资金流向 · 公司前瞻 · 预测验证　|　{esc(report_date)}</div></div></div></header><div class="navbar"><div class="wrap">ECONOMIC OUTLOOK　/　CAPITAL FLOW　/　FORWARD RESEARCH</div></div><main>
<section><div class="kicker">INVESTMENT DIRECTION</div><h2>一｜今日投资方向</h2><div class="hero"><div class="hero-title">{esc(direction.get('title','等待确认'))}</div><div class="hero-text">{esc(direction.get('brief'))}</div></div><div class="horizon-grid">{_horizons(context)}</div></section>
<section><div class="kicker">ACTION</div><h2>二｜动作</h2><div class="action-grid"><div class="action-box"><h3>观察</h3>{_list(actions.get('watch'))}</div><div class="action-box"><h3>准备</h3>{_list(actions.get('prepare'))}</div><div class="action-box"><h3>回避 / 降低风险</h3>{_list(actions.get('avoid'))}</div></div></section>
<section><div class="kicker">FORWARD CALENDAR</div><h2>三｜未来14日重要日程</h2><div class="calendar-grid">{_calendar(context)}</div></section>
<section><div class="kicker">CAPITAL FLOW</div><h2>四｜资金流向与投资逻辑</h2><div class="logic-root">{esc(direction.get('title','等待确认'))}</div>{_logic(context)}</section>
<section><div class="kicker">CORPORATE SIGNALS</div><h2>五｜重点公司前瞻</h2><div class="source-grid">{_source_cards(context,'company')}</div></section>
<section><div class="kicker">MARKET NARRATIVE</div><h2>六｜市场正在讨论什么</h2><div class="source-grid">{_source_cards(context,'media')}</div></section>
<section><div class="kicker">FORWARD TEST</div><h2>七｜预测与验证</h2><p class="muted">预测生成后写入数据库冻结，后续由真实市场结果机械验证，不允许事后修改。</p>{_predictions(context)}</section>
<section><div class="kicker">DATA INTEGRITY</div><h2>数据完整性</h2><div class="{audit_class}"><strong>{audit_title}</strong><br>核心失败：{esc(' · '.join(failures) or '无')}　门槛原因：{esc(', '.join(gate.reasons) or '无')}</div><div class="metrics"><span>市场覆盖率：<strong>{context.get('market_coverage',0):.0%}</strong></span><span>本轮冻结：<strong>{context.get('predictions_frozen',0)}</strong></span><span>来源数量：<strong>{len(context.get('sources',[]))}</strong></span></div></section>
</main><footer><div class="wrap">NEWS FINANCE · Independent Research Monitor<br>Official Sources · Corporate Intelligence · Cross-Asset Confirmation · Forward Verification<br><br>本报告仅用于研究与学习，不构成投资建议或收益保证，也不构成任何证券买卖建议。</div></footer></body></html>"""
