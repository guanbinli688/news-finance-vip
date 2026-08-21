from news_finance_v2.models import EvidenceGate
from news_finance_v2.reporting import render_report


def rich_context():
    return {
        "report_date": "2026-08-20",
        "direction": {"title": "防御占优", "brief": "资金转向黄金和长债"},
        "horizons": [{"days": "3-5", "direction": "防御", "focus": ["GLD", "TLT"], "brief": "波动上升", "risk": "VIX回落"}],
        "actions": {"watch": ["CPI"], "prepare": ["GLD/TLT"], "avoid": ["追高"]},
        "flows": [{"from": "QQQ", "to": "GLD", "brief": "风险偏好降温"}],
        "logic": [{"cause": "通胀粘性", "middle": "利率高位", "result": "估值承压", "action": "降低久期风险"}],
        "events": [{"date": "2026-08-20", "title": "初请失业金", "source": "BLS"}],
        "sources": [
            {"name": "NVIDIA IR", "kind": "company", "status": "SUCCESS", "text": "AI demand remains strong", "url": "https://example.test/ir"},
            {"name": "CNBC Markets", "kind": "media", "status": "SUCCESS", "text": "Market narrative", "url": "https://example.test/media"},
        ],
        "company_signals": [{
            "company": "英伟达", "ticker": "NVDA", "stance": "关注",
            "brief": "需求仍有韧性，但应等待订单与产能继续确认。",
            "trigger": "收入指引继续上调", "risk": "云厂商资本开支放缓", "source": "NVIDIA IR",
        }],
        "media_themes": [{"title": "市场等待政策确认", "tone": "谨慎", "brief": "主流讨论聚焦利率路径与盈利兑现。", "sources": ["CNBC Markets"]}],
        "display_predictions": [{"horizon_days": 5, "target": "SPY", "direction": "UP", "probability": .6, "thesis": "趋势改善", "invalidation": "跌破关键位"}],
        "gate": EvidenceGate(True, ()), "core_failures": [], "market_coverage": 1.0,
        "predictions_frozen": 1,
    }


def test_report_keeps_v2_layout_with_chinese_labels_and_seven_sections():
    report = render_report(rich_context())
    for text in (
        "NEWS FINANCE · 投资情报", "投资方向研究简报",
        "一｜今日投资方向", "二｜具体动作", "三｜未来14日重要日程",
        "四｜资金流向与投资逻辑", "五｜重点公司前瞻",
        "六｜市场正在交易什么", "七｜预测与验证", "数据完整性",
    ):
        assert text in report
    assert 'class="horizon-grid"' in report
    assert "SPY" in report and "60%" in report
    assert "需求仍有韧性" in report
    assert "市场等待政策确认" in report


def test_report_escapes_untrusted_source_text():
    context = rich_context()
    context["direction"]["title"] = "<script>alert(1)</script>"
    report = render_report(context)
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in report


def test_report_translates_known_bls_calendar_events_to_chinese():
    context = rich_context()
    context["events"] = [
        {"date": "2026-08-20", "title": "Summer Youth Labor Force", "source": "BLS"},
        {"date": "2026-08-21", "title": "State Employment and Unemployment (Monthly)", "source": "BLS"},
        {"date": "2026-08-21", "title": "Metropolitan Area Employment and Unemployment (Monthly)", "source": "BLS"},
    ]

    report = render_report(context)

    assert "暑期青年劳动力" in report
    assert "各州就业与失业（月度）" in report
    assert "大都会地区就业与失业（月度）" in report
    assert "Summer Youth Labor Force" not in report


def test_report_hides_untranslated_english_calendar_event_title():
    context = rich_context()
    context["events"] = [{"date": "2026-08-20", "title": "New Unmapped Release", "source": "BLS"}]

    report = render_report(context)

    assert "美国劳工统计局数据发布" in report
    assert "New Unmapped Release" not in report


def test_report_never_falls_back_to_raw_english_company_pages():
    context = rich_context()
    context["company_signals"] = []
    context["sources"][0]["text"] = "Skip to main content Latest News Investor Relations " * 20

    report = render_report(context)

    assert "本轮未形成可执行的公司信号" in report
    assert "Skip to main content" not in report
