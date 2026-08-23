# ============================================================
# 官方宏观 / 政策 / 监管来源
# ============================================================

OFFICIAL_SOURCES = (
    # ----- 核心宏观来源：保留 required=True -----
    ("BLS", "https://www.bls.gov/schedule/news_release/bls.ics", True),
    ("BEA", "https://www.bea.gov/news/schedule", True),
    ("Federal Reserve", "https://www.federalreserve.gov/newsevents/calendar.htm", True),
    ("Treasury Auctions", "https://www.treasurydirect.gov/auctions/upcoming/", True),

    # ----- 美国政府 / 财政 / 贸易 -----
    ("White House", "https://www.whitehouse.gov/briefing-room/", False),
    ("US Census", "https://www.census.gov/economic-indicators/", False),
    ("EIA", "https://www.eia.gov/todayinenergy/", False),
    ("Treasury Press", "https://home.treasury.gov/news/press-releases", False),
    ("USTR", "https://ustr.gov/about-us/policy-offices/press-office/press-releases", False),
    ("State Department", "https://www.state.gov/press-releases/", False),
    ("Federal Register", "https://www.federalregister.gov/", False),

    # ----- 证券 / 金融监管 -----
    ("SEC Newsroom", "https://www.sec.gov/newsroom", False),
    ("CFTC Press", "https://www.cftc.gov/PressRoom/PressReleases", False),
    ("FDIC News", "https://www.fdic.gov/news/press-releases/", False),
    ("OCC News", "https://www.occ.gov/news-issuances/news-releases/index-news-releases.html", False),

    # ----- 反垄断 / 并购 -----
    ("FTC Press", "https://www.ftc.gov/news-events/news/press-releases", False),
    ("DOJ Antitrust", "https://www.justice.gov/atr/press-releases", False),

    # ----- 半导体 / 出口管制 / 科技政策 -----
    ("Commerce BIS", "https://www.bis.gov/press-release", False),

    # ----- 医药 -----
    ("FDA News", "https://www.fda.gov/news-events/fda-newsroom/press-announcements", False),

    # ----- 能源 / 电力 -----
    ("FERC News", "https://www.ferc.gov/news-events/news", False),
    ("DOE News", "https://www.energy.gov/articles", False),

    # ----- 农业 / 大宗商品 -----
    ("USDA Press", "https://www.usda.gov/about-usda/news/press-releases", False),

    # ----- 纽约联储 / 金融市场 -----
    ("New York Fed", "https://www.newyorkfed.org/newsevents", False),
)


# ============================================================
# 主流财经媒体
# 注意：
# 不宜无限增加媒体页。
# 真正扩股票范围主要依赖 COMPANY_UNIVERSE。
# ============================================================

MEDIA_SOURCES = (
    ("AP Business", "https://apnews.com/hub/business"),
    ("CNBC Markets", "https://www.cnbc.com/markets/"),
    ("Financial Times", "https://www.ft.com/markets"),
    ("Reuters Markets", "https://www.reuters.com/markets/"),
    ("MarketWatch", "https://www.marketwatch.com/markets"),
    ("Yahoo Finance", "https://finance.yahoo.com/"),

    # 扩展
    ("Bloomberg Markets", "https://www.bloomberg.com/markets"),
    ("WSJ Markets", "https://www.wsj.com/news/markets"),
    ("Barrons", "https://www.barrons.com/market-data"),
    ("Nasdaq News", "https://www.nasdaq.com/news-and-insights"),
)


# ============================================================
# Preview / 基础模式重点公司
# 不建议放太多，保证 preview 快速
# ============================================================

BASE_COMPANY_SOURCES = (
    ("JPM IR", "https://www.jpmorganchase.com/ir"),
    ("Walmart IR", "https://stock.walmart.com/"),
    ("Microsoft IR", "https://www.microsoft.com/en-us/Investor"),
    ("Amazon IR", "https://ir.aboutamazon.com/"),
)


# ============================================================
# Full 模式重点 IR
#
# 这里 deliberately 不放 200~300 家。
# 股票行情池可以很大，但 IR 官网应该保持高价值精简。
# ============================================================

FULL_COMPANY_SOURCES = (
    # ---------------- 科技 / AI / 半导体 ----------------
    ("NVIDIA IR", "https://investor.nvidia.com/"),
    ("Alphabet IR", "https://abc.xyz/investor/"),
    ("Apple IR", "https://investor.apple.com/"),
    ("Meta IR", "https://investor.atmeta.com/"),
    ("AMD IR", "https://ir.amd.com/"),
    ("Broadcom IR", "https://investors.broadcom.com/"),
    ("Micron IR", "https://investors.micron.com/"),
    ("TSMC IR", "https://investor.tsmc.com/english"),
    ("Oracle IR", "https://investor.oracle.com/"),
    ("Salesforce IR", "https://investor.salesforce.com/"),
    ("Palantir IR", "https://investors.palantir.com/"),

    # ---------------- 消费 / 互联网 ----------------
    ("Tesla IR", "https://ir.tesla.com/"),
    ("Costco IR", "https://investor.costco.com/"),
    ("Netflix IR", "https://ir.netflix.net/"),
    ("Home Depot IR", "https://ir.homedepot.com/"),
    ("Uber IR", "https://investor.uber.com/"),

    # ---------------- 中国 / 亚洲 ----------------
    ("Alibaba IR", "https://www.alibabagroup.com/en-US/ir-home"),
    ("Tencent IR", "https://www.tencent.com/en-us/investors.html"),

    # ---------------- 金融 ----------------
    ("Goldman Sachs IR", "https://www.goldmansachs.com/investor-relations/"),
    ("Bank of America IR", "https://investor.bankofamerica.com/"),
    ("Morgan Stanley IR", "https://www.morganstanley.com/about-us-ir"),
    ("Visa IR", "https://investor.visa.com/"),
    ("Mastercard IR", "https://investor.mastercard.com/"),

    # ---------------- 医疗 ----------------
    ("Eli Lilly IR", "https://investor.lilly.com/"),
    ("UnitedHealth IR", "https://www.unitedhealthgroup.com/investors.html"),
    ("Johnson & Johnson IR", "https://www.investor.jnj.com/"),
    ("Merck IR", "https://www.merck.com/investor-relations/"),
    ("AbbVie IR", "https://investors.abbvie.com/"),

    # ---------------- 工业 / 国防 ----------------
    ("Caterpillar IR", "https://investors.caterpillar.com/"),
    ("GE Aerospace IR", "https://www.geaerospace.com/investor-relations"),
    ("RTX IR", "https://investors.rtx.com/"),
    ("Lockheed Martin IR", "https://investors.lockheedmartin.com/"),

    # ---------------- 能源 ----------------
    ("ExxonMobil IR", "https://investor.exxonmobil.com/"),
    ("Chevron IR", "https://www.chevron.com/investors"),
    ("ConocoPhillips IR", "https://www.conocophillips.com/investor-relations/"),

    # ---------------- 电力 / AI 数据中心能源 ----------------
    ("NextEra IR", "https://www.investor.nexteraenergy.com/"),
    ("Constellation Energy IR", "https://investor.constellationenergy.com/"),
    ("Vistra IR", "https://investor.vistracorp.com/"),

    # ---------------- 新经济 / Crypto ----------------
    ("Coinbase IR", "https://investor.coinbase.com/"),
)


# ============================================================
# IR source -> ticker
# ============================================================

COMPANY_SYMBOLS = {
    # BASE
    "JPM IR": "JPM",
    "Walmart IR": "WMT",
    "Microsoft IR": "MSFT",
    "Amazon IR": "AMZN",

    # Technology
    "NVIDIA IR": "NVDA",
    "Alphabet IR": "GOOGL",
    "Apple IR": "AAPL",
    "Meta IR": "META",
    "AMD IR": "AMD",
    "Broadcom IR": "AVGO",
    "Micron IR": "MU",
    "TSMC IR": "TSM",
    "Oracle IR": "ORCL",
    "Salesforce IR": "CRM",
    "Palantir IR": "PLTR",

    # Consumer / Internet
    "Tesla IR": "TSLA",
    "Costco IR": "COST",
    "Netflix IR": "NFLX",
    "Home Depot IR": "HD",
    "Uber IR": "UBER",

    # Asia
    "Alibaba IR": "BABA",
    "Tencent IR": "TCEHY",

    # Financials
    "Goldman Sachs IR": "GS",
    "Bank of America IR": "BAC",
    "Morgan Stanley IR": "MS",
    "Visa IR": "V",
    "Mastercard IR": "MA",

    # Healthcare
    "Eli Lilly IR": "LLY",
    "UnitedHealth IR": "UNH",
    "Johnson & Johnson IR": "JNJ",
    "Merck IR": "MRK",
    "AbbVie IR": "ABBV",

    # Industrials
    "Caterpillar IR": "CAT",
    "GE Aerospace IR": "GE",
    "RTX IR": "RTX",
    "Lockheed Martin IR": "LMT",

    # Energy
    "ExxonMobil IR": "XOM",
    "Chevron IR": "CVX",
    "ConocoPhillips IR": "COP",

    # Power
    "NextEra IR": "NEE",
    "Constellation Energy IR": "CEG",
    "Vistra IR": "VST",

    # Crypto
    "Coinbase IR": "COIN",
}


# ============================================================
# 股票扫描池
#
# 目标不是把全部股票交给 AI。
#
# 正确流程：
# 260+ -> 行情筛 50~60 -> 新闻筛 20~30
# -> AI 深度分析 12~16 -> 最终 8
# ============================================================

SECTOR_UNIVERSES = {

    # ========================================================
    # 1. 超大型科技 / 平台
    # ========================================================
    "mega_cap_platform": (
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
        "META", "TSLA", "AVGO", "ORCL", "IBM", "CSCO",
    ),

    # ========================================================
    # 2. 半导体 / 芯片设备
    # ========================================================
    "semiconductors": (
        "AMD", "INTC", "QCOM", "TXN", "MU",
        "AMAT", "LRCX", "KLAC", "MRVL",
        "ARM", "ASML", "TSM",
        "ADI", "MCHP", "NXPI", "ON",
        "MPWR", "WDC", "STX",
    ),

    # ========================================================
    # 3. AI / 软件 / 云 / 网络安全
    # ========================================================
    "software_cyber_ai": (
        "CRM", "ADBE", "NOW", "PLTR",
        "PANW", "CRWD", "SNOW", "DDOG",
        "NET", "MDB", "TEAM",
        "INTU", "ADSK", "CDNS", "SNPS",
        "ANET", "DELL", "HPE",
    ),

    # ========================================================
    # 4. 互联网 / 金融科技 / 高成长
    # ========================================================
    "internet_consumer_growth": (
        "UBER", "ABNB", "BKNG", "DASH",
        "SHOP", "MELI", "SE", "SPOT",
        "RBLX", "HOOD", "COIN", "XYZ",
        "PYPL", "EBAY", "ETSY",
    ),

    # ========================================================
    # 5. 可选消费 / 汽车 / 旅游
    # ========================================================
    "consumer_discretionary": (
        "HD", "LOW", "TGT", "NKE",
        "SBUX", "MCD", "CMG", "YUM", "DRI",
        "ROST", "TJX",
        "MAR", "HLT",
        "RCL", "CCL", "NCLH",
        "GM", "F", "RIVN", "LCID",
    ),

    # ========================================================
    # 6. 必需消费
    # ========================================================
    "consumer_staples": (
        "WMT", "COST",
        "PG", "KO", "PEP",
        "PM", "MO", "CL",
        "MDLZ", "KHC", "GIS",
        "KMB", "EL", "HSY", "SYY",
    ),

    # ========================================================
    # 7. 金融
    # ========================================================
    "financials": (
        "JPM", "BAC", "C", "WFC",
        "GS", "MS", "BLK", "SCHW",
        "AXP", "COF",
        "V", "MA",
        "ICE", "CME",
        "SPGI", "MCO",
        "BK", "STT",
        "AON", "MMC",
        "CB", "PGR", "TRV",
        "BRK-B",
    ),

    # ========================================================
    # 8. 医疗 / 制药 / 医疗器械
    # ========================================================
    "healthcare": (
        "LLY", "UNH", "JNJ", "PFE",
        "MRK", "ABBV", "AMGN", "GILD",
        "TMO", "DHR",
        "ISRG", "CVS", "NVO",
        "BMY", "MDT", "SYK", "BSX",
        "ZTS", "REGN", "VRTX", "BIIB",
        "MCK", "CI", "ELV",
        "HCA", "HUM", "DXCM",
        "AZN", "GSK",
    ),

    # ========================================================
    # 9. 工业 / 航空航天 / 国防 / 运输
    # ========================================================
    "industrials_aerospace": (
        "CAT", "GE", "RTX", "LMT",
        "BA", "DE", "HON",
        "UPS", "FDX", "UNP",
        "NOC", "GD",
        "ETN", "PH", "EMR",
        "MMM", "ITW",
        "CARR", "OTIS", "URI",
        "PCAR", "CMI",
        "PWR",
        "DAL", "UAL", "LUV",
    ),

    # ========================================================
    # 10. 石油 / 天然气 / 材料 / 黄金 / 铜
    # ========================================================
    "energy_materials": (
        "XOM", "CVX", "COP",
        "SLB", "OXY", "EOG",
        "MPC", "VLO", "PSX",
        "KMI", "WMB", "LNG",
        "HAL", "BKR", "FANG", "DVN",

        "FCX", "NEM",
        "NUE", "STLD",
        "APD", "LIN", "SHW", "ECL",

        "SHEL", "BP",
    ),

    # ========================================================
    # 11. 电力 / 公用事业
    # 特别适合跟踪 AI 数据中心用电主题
    # ========================================================
    "utilities_power": (
        "NEE", "DUK", "SO", "AEP",
        "EXC", "SRE", "XEL", "ED", "PEG",
        "CEG", "VST",
    ),

    # ========================================================
    # 12. 通信 / 媒体 / 娱乐
    # ========================================================
    "communications_media": (
        "TMUS", "VZ", "T", "CMCSA",
        "DIS", "NFLX",
        "WBD", "PSKY", "FOXA",
    ),

    # ========================================================
    # 13. REIT / 数据中心 / 地产
    # ========================================================
    "real_estate": (
        "AMT", "PLD", "EQIX",
        "O", "SPG",
        "DLR", "WELL",
        "PSA", "CCI",
    ),

    # ========================================================
    # 14. 中国 / 亚洲 / 国际 ADR
    # ========================================================
    "china_asia_adr": (
        "BABA", "TCEHY",
        "PDD", "JD", "BIDU",
        "NIO", "LI", "XPEV",
        "SONY", "SAP",
    ),

    # ========================================================
    # 15. 新经济 / AI 基建 / 太空 / 核能 / 量子
    #
    # 这一组很重要：
    # 用来发现不属于传统 Mega Cap 的事件驱动机会。
    # ========================================================
    "new_economy_event": (
        # Space
        "RKLB", "ASTS", "LUNR", "RDW", "PL",

        # Nuclear / power
        "OKLO", "SMR", "LEU",

        # Quantum
        "IONQ", "RGTI", "QBTS",

        # AI infrastructure
        "SMCI", "VRT", "APP",
        "TEM", "CRWV", "NBIS",

        # Fintech / new listings
        "CRCL", "FIG",

        # Bitcoin proxy
        "MSTR",
    ),
}


# ============================================================
# 给现有代码保持兼容：
# EXPANDED_COMPANY_UNIVERSE 仍然存在
# ============================================================

EXPANDED_COMPANY_UNIVERSE = tuple(
    dict.fromkeys(
        symbol
        for symbols in SECTOR_UNIVERSES.values()
        for symbol in symbols
    )
)


# ============================================================
# 核心公司池
#
# 后面 live.py 可以给 CORE 更高基础权重，
# 但绝对不能只从 CORE 里面选。
# ============================================================

CORE_COMPANY_UNIVERSE = (
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "AVGO", "AMD", "TSM",
    "ASML", "ORCL", "CRM", "PLTR",

    # Financial
    "JPM", "BAC", "GS", "MS", "V", "MA",

    # Consumer
    "WMT", "COST", "HD", "MCD",
    "NFLX", "UBER", "BKNG",

    # Healthcare
    "LLY", "UNH", "JNJ", "MRK", "ABBV",

    # Industrial
    "CAT", "GE", "RTX", "LMT", "BA",

    # Energy
    "XOM", "CVX", "COP",

    # Power
    "NEE", "CEG", "VST",

    # China / Asia
    "BABA", "PDD", "JD", "BIDU",

    # High-beta / event
    "COIN", "HOOD", "RKLB", "CRWV",
)


# ============================================================
# 最终完整股票池
#
# dict.fromkeys 保持顺序并自动去重
# ============================================================

COMPANY_UNIVERSE = tuple(
    dict.fromkeys(
        (
            *COMPANY_SYMBOLS.values(),
            *CORE_COMPANY_UNIVERSE,
            *EXPANDED_COMPANY_UNIVERSE,
        )
    )
)


# ============================================================
# ticker -> sector
#
# 后面 live.py 可以直接：
#
# sector = COMPANY_SECTORS.get(symbol, "other")
#
# 用于限制最终结果每个行业最多 2~3 家。
# ============================================================

COMPANY_SECTORS = {
    symbol: sector
    for sector, symbols in SECTOR_UNIVERSES.items()
    for symbol in symbols
}


# ============================================================
# 推荐的筛选配置
#
# sources.py 加上没有副作用。
# 后面 live.py 直接 import 使用。
# ============================================================

SCREENING_CONFIG = {
    # 整个 COMPANY_UNIVERSE 都扫描行情
    "market_scan_limit": len(COMPANY_UNIVERSE),

    # 第一轮行情留下多少
    "market_prefilter_size": 60,

    # 第二轮新闻 / 事件留下多少
    "news_prefilter_size": 28,

    # 最终送给 OpenAI 深度比较多少
    "ai_candidate_size": 16,

    # Equity 页面最终展示
    "final_company_count": 8,

    # 普通情况下每行业最大数量
    "max_per_sector": 2,

    # 最近多少个交易日检查重复
    "repeat_lookback_days": 5,

    # 重复出现扣分
    "repeat_penalty": 12,

    # 如果重大事件评分超过该值，可取消重复惩罚
    "major_event_override_score": 85,
}


# ============================================================
# 中文公司名称
# 已有的全部保留，并增加主要新增公司。
#
# 最下面 setdefault 保证：
# 即使新 ticker 暂时没有中文名，也不会 KeyError。
# ============================================================

COMPANY_NAMES = {
    # --------------------------------------------------------
    # Mega Tech
    # --------------------------------------------------------
    "AAPL": "苹果",
    "MSFT": "微软",
    "NVDA": "英伟达",
    "GOOGL": "谷歌",
    "AMZN": "亚马逊",
    "META": "Meta平台",
    "TSLA": "特斯拉",
    "AVGO": "博通",
    "ORCL": "甲骨文",
    "IBM": "IBM",
    "CSCO": "思科",

    # --------------------------------------------------------
    # Semiconductor
    # --------------------------------------------------------
    "AMD": "超威半导体",
    "INTC": "英特尔",
    "QCOM": "高通",
    "TXN": "德州仪器",
    "MU": "美光科技",
    "AMAT": "应用材料",
    "LRCX": "泛林集团",
    "KLAC": "科磊",
    "MRVL": "迈威尔科技",
    "ARM": "安谋",
    "ASML": "阿斯麦",
    "TSM": "台积电",
    "ADI": "亚德诺半导体",
    "MCHP": "微芯科技",
    "NXPI": "恩智浦",
    "ON": "安森美",
    "MPWR": "芯源系统",
    "WDC": "西部数据",
    "STX": "希捷科技",

    # --------------------------------------------------------
    # Software / AI / Cyber
    # --------------------------------------------------------
    "CRM": "赛富时",
    "ADBE": "奥多比",
    "NOW": "ServiceNow",
    "PLTR": "帕兰提尔",
    "PANW": "派拓网络",
    "CRWD": "CrowdStrike",
    "SNOW": "雪花公司",
    "DDOG": "Datadog",
    "NET": "Cloudflare",
    "MDB": "MongoDB",
    "TEAM": "Atlassian",
    "INTU": "Intuit",
    "ADSK": "欧特克",
    "CDNS": "铿腾电子",
    "SNPS": "新思科技",
    "ANET": "Arista Networks",
    "DELL": "戴尔科技",
    "HPE": "慧与科技",

    # --------------------------------------------------------
    # Internet / Fintech / Growth
    # --------------------------------------------------------
    "UBER": "优步",
    "ABNB": "爱彼迎",
    "BKNG": "Booking控股",
    "DASH": "DoorDash",
    "SHOP": "Shopify",
    "MELI": "MercadoLibre",
    "SE": "Sea Limited",
    "SPOT": "Spotify",
    "RBLX": "Roblox",
    "HOOD": "Robinhood",
    "COIN": "Coinbase",
    "XYZ": "Block",
    "PYPL": "贝宝",
    "EBAY": "eBay",
    "ETSY": "Etsy",

    # --------------------------------------------------------
    # Consumer
    # --------------------------------------------------------
    "WMT": "沃尔玛",
    "COST": "开市客",
    "HD": "家得宝",
    "LOW": "劳氏",
    "TGT": "塔吉特",
    "NKE": "耐克",
    "SBUX": "星巴克",
    "MCD": "麦当劳",
    "CMG": "Chipotle",
    "YUM": "百胜餐饮",
    "DRI": "达登饭店",
    "ROST": "罗斯百货",
    "TJX": "TJX公司",
    "MAR": "万豪国际",
    "HLT": "希尔顿",
    "RCL": "皇家加勒比",
    "CCL": "嘉年华邮轮",
    "NCLH": "挪威邮轮",
    "GM": "通用汽车",
    "F": "福特汽车",
    "RIVN": "Rivian",
    "LCID": "Lucid",

    "PG": "宝洁",
    "KO": "可口可乐",
    "PEP": "百事",
    "PM": "菲利普莫里斯国际",
    "MO": "奥驰亚",
    "CL": "高露洁",
    "MDLZ": "亿滋国际",
    "KHC": "卡夫亨氏",
    "GIS": "通用磨坊",
    "KMB": "金佰利",
    "EL": "雅诗兰黛",
    "HSY": "好时",
    "SYY": "西斯科食品",

    # --------------------------------------------------------
    # Financials
    # --------------------------------------------------------
    "JPM": "摩根大通",
    "BAC": "美国银行",
    "C": "花旗集团",
    "WFC": "富国银行",
    "GS": "高盛",
    "MS": "摩根士丹利",
    "BLK": "贝莱德",
    "SCHW": "嘉信理财",
    "AXP": "美国运通",
    "COF": "第一资本",
    "V": "维萨",
    "MA": "万事达",
    "ICE": "洲际交易所",
    "CME": "芝商所集团",
    "SPGI": "标普全球",
    "MCO": "穆迪",
    "BK": "纽约梅隆银行",
    "STT": "道富银行",
    "AON": "怡安",
    "MMC": "威达信",
    "CB": "安达保险",
    "PGR": "Progressive",
    "TRV": "旅行者保险",
    "BRK-B": "伯克希尔·哈撒韦",

    # --------------------------------------------------------
    # Healthcare
    # --------------------------------------------------------
    "LLY": "礼来",
    "UNH": "联合健康",
    "JNJ": "强生",
    "PFE": "辉瑞",
    "MRK": "默沙东",
    "ABBV": "艾伯维",
    "AMGN": "安进",
    "GILD": "吉利德科学",
    "TMO": "赛默飞世尔",
    "DHR": "丹纳赫",
    "ISRG": "直觉外科",
    "CVS": "CVS健康",
    "NVO": "诺和诺德",
    "BMY": "百时美施贵宝",
    "MDT": "美敦力",
    "SYK": "史赛克",
    "BSX": "波士顿科学",
    "ZTS": "硕腾",
    "REGN": "再生元",
    "VRTX": "福泰制药",
    "BIIB": "百健",
    "MCK": "麦克森",
    "CI": "信诺",
    "ELV": "Elevance Health",
    "HCA": "HCA医疗",
    "HUM": "哈门那",
    "DXCM": "德康医疗",
    "AZN": "阿斯利康",
    "GSK": "葛兰素史克",

    # --------------------------------------------------------
    # Industrials
    # --------------------------------------------------------
    "CAT": "卡特彼勒",
    "GE": "GE航空航天",
    "RTX": "RTX",
    "LMT": "洛克希德·马丁",
    "BA": "波音",
    "DE": "迪尔",
    "HON": "霍尼韦尔",
    "UPS": "联合包裹",
    "FDX": "联邦快递",
    "UNP": "联合太平洋",
    "NOC": "诺斯罗普·格鲁曼",
    "GD": "通用动力",
    "ETN": "伊顿",
    "PH": "派克汉尼汾",
    "EMR": "艾默生电气",
    "MMM": "3M",
    "ITW": "伊利诺伊工具",
    "CARR": "开利全球",
    "OTIS": "奥的斯",
    "URI": "联合租赁",
    "PCAR": "帕卡",
    "CMI": "康明斯",
    "PWR": "Quanta Services",
    "DAL": "达美航空",
    "UAL": "联合航空",
    "LUV": "西南航空",

    # --------------------------------------------------------
    # Energy / Materials
    # --------------------------------------------------------
    "XOM": "埃克森美孚",
    "CVX": "雪佛龙",
    "COP": "康菲石油",
    "SLB": "斯伦贝谢",
    "OXY": "西方石油",
    "EOG": "EOG资源",
    "MPC": "马拉松原油",
    "VLO": "瓦莱罗能源",
    "PSX": "Phillips 66",
    "KMI": "金德摩根",
    "WMB": "威廉姆斯公司",
    "LNG": "Cheniere Energy",
    "HAL": "哈里伯顿",
    "BKR": "贝克休斯",
    "FANG": "Diamondback Energy",
    "DVN": "戴文能源",
    "FCX": "自由港麦克莫兰",
    "NEM": "纽蒙特",
    "NUE": "纽柯",
    "STLD": "Steel Dynamics",
    "APD": "空气化工",
    "LIN": "林德",
    "SHW": "宣伟",
    "ECL": "艺康",
    "SHEL": "壳牌",
    "BP": "英国石油",

    # --------------------------------------------------------
    # Utilities / Power
    # --------------------------------------------------------
    "NEE": "新纪元能源",
    "DUK": "杜克能源",
    "SO": "南方电力",
    "AEP": "美国电力",
    "EXC": "爱克斯龙",
    "SRE": "桑普拉能源",
    "XEL": "Xcel Energy",
    "ED": "联合爱迪生",
    "PEG": "公共服务企业集团",
    "CEG": "星座能源",
    "VST": "Vistra",

    # --------------------------------------------------------
    # Communications / Media
    # --------------------------------------------------------
    "TMUS": "美国T-Mobile",
    "VZ": "威瑞森",
    "T": "美国电话电报",
    "CMCSA": "康卡斯特",
    "DIS": "迪士尼",
    "NFLX": "奈飞",
    "WBD": "华纳兄弟探索",
    "PSKY": "派拉蒙Skydance",
    "FOXA": "福克斯",

    # --------------------------------------------------------
    # REIT
    # --------------------------------------------------------
    "AMT": "美国电塔",
    "PLD": "普洛斯",
    "EQIX": "Equinix",
    "O": "Realty Income",
    "SPG": "西蒙地产",
    "DLR": "Digital Realty",
    "WELL": "Welltower",
    "PSA": "Public Storage",
    "CCI": "Crown Castle",

    # --------------------------------------------------------
    # China / Asia
    # --------------------------------------------------------
    "BABA": "阿里巴巴",
    "TCEHY": "腾讯控股",
    "PDD": "拼多多",
    "JD": "京东",
    "BIDU": "百度",
    "NIO": "蔚来",
    "LI": "理想汽车",
    "XPEV": "小鹏汽车",
    "SONY": "索尼",
    "SAP": "SAP",

    # --------------------------------------------------------
    # New Economy / Event
    # --------------------------------------------------------
    "RKLB": "Rocket Lab",
    "ASTS": "AST SpaceMobile",
    "LUNR": "Intuitive Machines",
    "RDW": "Redwire",
    "PL": "Planet Labs",

    "OKLO": "Oklo",
    "SMR": "NuScale Power",
    "LEU": "Centrus Energy",

    "IONQ": "IonQ",
    "RGTI": "Rigetti Computing",
    "QBTS": "D-Wave Quantum",

    "SMCI": "超微电脑",
    "VRT": "Vertiv",
    "APP": "AppLovin",
    "TEM": "Tempus AI",
    "CRWV": "CoreWeave",
    "NBIS": "Nebius",

    "CRCL": "Circle",
    "FIG": "Figma",

    "MSTR": "Strategy",
}


# ============================================================
# 防止未来增加 ticker 时 COMPANY_NAMES 出现 KeyError
# 没有中文名时先直接显示 ticker
# ============================================================

for _symbol in COMPANY_UNIVERSE:
    COMPANY_NAMES.setdefault(_symbol, _symbol)


# ============================================================
# symbol -> official IR URL
# 后续 live.py 找公司官方来源时非常方便
# ============================================================

COMPANY_IR_BY_SYMBOL = {
    COMPANY_SYMBOLS[name]: url
    for name, url in (*BASE_COMPANY_SOURCES, *FULL_COMPANY_SOURCES)
    if name in COMPANY_SYMBOLS
}
