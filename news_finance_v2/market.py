from __future__ import annotations

# ============================================================
# NEWS FINANCE V2 — Cross-Asset Market Universe
#
# 设计目标：
# 1. 扩大市场观察范围，但尽量使用 yfinance 稳定、流动性高的标的
# 2. 保持旧代码兼容：live.py 仍可直接 import SIGNALS
# 3. 为后续“先广泛扫描，再动态精选”提供分组、中文名和预测对象
# ============================================================


SIGNAL_GROUPS = {
    # 美国大盘 / 风格
    "us_broad": (
        "SPY",
        "QQQ",
        "DIA",
        "IWM",
        "RSP",
    ),

    # 美国 11 大行业
    "us_sectors": (
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLI",
        "XLY",
        "XLP",
        "XLU",
        "XLB",
        "XLRE",
        "XLC",
    ),

    # 波动率 / 利率 / 信用
    "rates_credit_risk": (
        "^VIX",
        "SHY",
        "IEF",
        "TLT",
        "HYG",
        "LQD",
    ),

    # 商品
    "commodities": (
        "GLD",
        "SLV",
        "USO",
        "UNG",
        "CPER",
    ),

    # 海外主要市场
    "international": (
        "EFA",
        "EEM",
        "VGK",
        "EWJ",
        "EWY",
        "FXI",
        "MCHI",
    ),

    # 美元
    "currency": (
        "UUP",
    ),
}


# 保持现有 live.py 兼容
SIGNALS = tuple(
    dict.fromkeys(
        symbol
        for symbols in SIGNAL_GROUPS.values()
        for symbol in symbols
    )
)


# 核心市场信号
CORE_SIGNALS = (
    "SPY",
    "QQQ",
    "IWM",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "^VIX",
    "HYG",
    "TLT",
    "GLD",
    "USO",
)


# 中文显示名称
SIGNAL_NAMES = {
    "SPY": "标普500",
    "QQQ": "纳斯达克100",
    "DIA": "道琼斯工业指数",
    "IWM": "罗素2000",
    "RSP": "标普500等权",

    "XLK": "科技",
    "XLF": "金融",
    "XLE": "能源",
    "XLV": "医疗保健",
    "XLI": "工业",
    "XLY": "可选消费",
    "XLP": "必需消费",
    "XLU": "公用事业",
    "XLB": "材料",
    "XLRE": "房地产",
    "XLC": "通信服务",

    "^VIX": "VIX恐慌指数",
    "SHY": "美国短期国债",
    "IEF": "美国7-10年期国债",
    "TLT": "美国长期国债",
    "HYG": "高收益债",
    "LQD": "投资级公司债",

    "GLD": "黄金",
    "SLV": "白银",
    "USO": "原油",
    "UNG": "天然气",
    "CPER": "铜",

    "EFA": "发达市场（美国以外）",
    "EEM": "新兴市场",
    "VGK": "欧洲股市",
    "EWJ": "日本股市",
    "EWY": "韩国股市",
    "FXI": "中国大型股",
    "MCHI": "中国股票",

    "UUP": "美元",
}


# 给 live.py 替换硬编码 allowed 用
PREDICTION_TARGETS = (
    # 美国大盘
    "SPY",
    "QQQ/SPY",
    "DIA/SPY",
    "IWM/SPY",
    "RSP/SPY",

    # 行业相对强弱
    "XLK/SPY",
    "XLF/SPY",
    "XLE/SPY",
    "XLV/SPY",
    "XLI/SPY",
    "XLY/SPY",
    "XLP/SPY",
    "XLU/SPY",
    "XLB/SPY",
    "XLRE/SPY",
    "XLC/SPY",

    # 利率 / 信用
    "SHY",
    "IEF",
    "TLT",
    "HYG",
    "LQD",

    # 商品
    "GLD",
    "SLV",
    "USO",
    "UNG",
    "CPER",

    # 海外相对强弱
    "EFA/SPY",
    "EEM/SPY",
    "VGK/SPY",
    "EWJ/SPY",
    "EWY/SPY",
    "FXI/SPY",
    "MCHI/SPY",

    # 美元 / 波动率
    "UUP",
    "^VIX",
)


PREDICTION_GROUPS = {
    "equity": (
        "SPY",
        "QQQ/SPY",
        "DIA/SPY",
        "IWM/SPY",
        "RSP/SPY",
    ),
    "sector": (
        "XLK/SPY",
        "XLF/SPY",
        "XLE/SPY",
        "XLV/SPY",
        "XLI/SPY",
        "XLY/SPY",
        "XLP/SPY",
        "XLU/SPY",
        "XLB/SPY",
        "XLRE/SPY",
        "XLC/SPY",
    ),
    "rates_credit": (
        "SHY",
        "IEF",
        "TLT",
        "HYG",
        "LQD",
    ),
    "commodity": (
        "GLD",
        "SLV",
        "USO",
        "UNG",
        "CPER",
    ),
    "international": (
        "EFA/SPY",
        "EEM/SPY",
        "VGK/SPY",
        "EWJ/SPY",
        "EWY/SPY",
        "FXI/SPY",
        "MCHI/SPY",
    ),
    "currency_volatility": (
        "UUP",
        "^VIX",
    ),
}


def coverage(snapshot):
    """完整市场信号覆盖率。"""
    if not SIGNALS:
        return 0.0
    return sum(symbol in snapshot for symbol in SIGNALS) / len(SIGNALS)


def core_coverage(snapshot):
    """核心市场信号覆盖率。"""
    if not CORE_SIGNALS:
        return 0.0
    return sum(symbol in snapshot for symbol in CORE_SIGNALS) / len(CORE_SIGNALS)


def group_coverage(snapshot):
    """按市场类别返回覆盖率。"""
    result = {}
    for group, symbols in SIGNAL_GROUPS.items():
        if not symbols:
            result[group] = 0.0
            continue
        result[group] = sum(symbol in snapshot for symbol in symbols) / len(symbols)
    return result


def missing_signals(snapshot):
    """返回当天没有成功获取行情的标的。"""
    return tuple(symbol for symbol in SIGNALS if symbol not in snapshot)
