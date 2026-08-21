OFFICIAL_SOURCES = (
    ("BLS", "https://www.bls.gov/schedule/news_release/bls.ics", True),
    ("BEA", "https://www.bea.gov/news/schedule", True),
    ("Federal Reserve", "https://www.federalreserve.gov/newsevents/calendar.htm", True),
    ("Treasury Auctions", "https://www.treasurydirect.gov/auctions/upcoming/", True),
    ("White House", "https://www.whitehouse.gov/briefing-room/", False),
    ("US Census", "https://www.census.gov/economic-indicators/", False),
    ("EIA", "https://www.eia.gov/todayinenergy/", False),
    ("Treasury Press", "https://home.treasury.gov/news/press-releases", False),
    ("USTR", "https://ustr.gov/about-us/policy-offices/press-office/press-releases", False),
    ("State Department", "https://www.state.gov/press-releases/", False),
    ("Federal Register", "https://www.federalregister.gov/", False),
)

MEDIA_SOURCES = (
    ("AP Business", "https://apnews.com/hub/business"),
    ("CNBC Markets", "https://www.cnbc.com/markets/"),
    ("Financial Times", "https://www.ft.com/markets"),
    ("Reuters Markets", "https://www.reuters.com/markets/"),
    ("MarketWatch", "https://www.marketwatch.com/markets"),
    ("Yahoo Finance", "https://finance.yahoo.com/"),
)

BASE_COMPANY_SOURCES = (
    ("JPM IR", "https://www.jpmorganchase.com/ir"),
    ("Walmart IR", "https://stock.walmart.com/"),
    ("Microsoft IR", "https://www.microsoft.com/en-us/Investor"),
    ("Amazon IR", "https://ir.aboutamazon.com/"),
)

FULL_COMPANY_SOURCES = (
    ("NVIDIA IR", "https://investor.nvidia.com/"),
    ("Alphabet IR", "https://abc.xyz/investor/"),
    ("Apple IR", "https://investor.apple.com/"),
    ("Costco IR", "https://investor.costco.com/"),
    ("ExxonMobil IR", "https://investor.exxonmobil.com/"),
    ("TSMC IR", "https://investor.tsmc.com/english"),
    ("Alibaba IR", "https://www.alibabagroup.com/en-US/ir-home"),
    ("Tencent IR", "https://www.tencent.com/en-us/investors.html"),
    ("Broadcom IR", "https://investors.broadcom.com/"),
    ("Micron IR", "https://investors.micron.com/"),
    ("Tesla IR", "https://ir.tesla.com/"),
    ("Eli Lilly IR", "https://investor.lilly.com/"),
    ("UnitedHealth IR", "https://www.unitedhealthgroup.com/investors.html"),
    ("Caterpillar IR", "https://investors.caterpillar.com/"),
    ("Goldman Sachs IR", "https://www.goldmansachs.com/investor-relations/"),
    ("Visa IR", "https://investor.visa.com/"),
)

COMPANY_SYMBOLS = {
    "JPM IR": "JPM", "Walmart IR": "WMT", "Microsoft IR": "MSFT",
    "Amazon IR": "AMZN", "NVIDIA IR": "NVDA", "Alphabet IR": "GOOGL",
    "Apple IR": "AAPL", "Costco IR": "COST", "ExxonMobil IR": "XOM",
    "TSMC IR": "TSM", "Alibaba IR": "BABA", "Tencent IR": "TCEHY",
    "Broadcom IR": "AVGO", "Micron IR": "MU", "Tesla IR": "TSLA",
    "Eli Lilly IR": "LLY", "UnitedHealth IR": "UNH", "Caterpillar IR": "CAT",
    "Goldman Sachs IR": "GS", "Visa IR": "V",
}

EXPANDED_COMPANY_UNIVERSE = (
    # 科技、半导体、软件
    "AMD", "INTC", "ORCL", "CRM", "ADBE", "QCOM", "TXN", "AMAT",
    "LRCX", "KLAC", "MRVL", "PLTR", "NOW", "IBM", "CSCO", "PANW",
    "CRWD", "SNOW", "ARM", "ASML", "META",
    # 消费、互联网、媒体
    "HD", "LOW", "TGT", "NKE", "SBUX", "MCD", "BKNG", "DIS",
    "NFLX", "ABNB", "ROST", "TJX", "PDD", "JD", "BIDU", "SONY",
    # 金融
    "BAC", "C", "WFC", "MS", "BLK", "SCHW", "AXP", "COF", "PYPL",
    # 医疗
    "JNJ", "PFE", "MRK", "ABBV", "AMGN", "GILD", "TMO", "DHR",
    "ISRG", "CVS", "NVO",
    # 工业、国防、运输
    "BA", "GE", "RTX", "LMT", "DE", "UPS", "FDX", "HON", "UNP",
    # 能源、材料、黄金
    "CVX", "COP", "SLB", "OXY", "EOG", "FCX", "NEM",
    # 通信、防御消费、公用事业、REIT
    "TMUS", "VZ", "T", "CMCSA", "PG", "KO", "PEP", "PM", "MO",
    "CL", "MDLZ", "NEE", "DUK", "SO", "AMT",
)

COMPANY_UNIVERSE = tuple(dict.fromkeys((*COMPANY_SYMBOLS.values(), *EXPANDED_COMPANY_UNIVERSE)))

COMPANY_NAMES = {
    "JPM": "摩根大通", "WMT": "沃尔玛", "MSFT": "微软", "AMZN": "亚马逊",
    "NVDA": "英伟达", "GOOGL": "谷歌", "AAPL": "苹果", "COST": "开市客",
    "XOM": "埃克森美孚", "TSM": "台积电", "BABA": "阿里巴巴",
    "TCEHY": "腾讯控股", "AVGO": "博通", "MU": "美光科技", "TSLA": "特斯拉",
    "LLY": "礼来", "UNH": "联合健康", "CAT": "卡特彼勒", "GS": "高盛", "V": "维萨",
    "AMD": "超威半导体", "INTC": "英特尔", "ORCL": "甲骨文", "CRM": "赛富时",
    "ADBE": "奥多比", "QCOM": "高通", "TXN": "德州仪器", "AMAT": "应用材料",
    "LRCX": "泛林集团", "KLAC": "科磊", "MRVL": "迈威尔科技", "PLTR": "帕兰提尔",
    "NOW": "赛维斯诺", "IBM": "国际商业机器", "CSCO": "思科", "PANW": "派拓网络",
    "CRWD": "克劳德斯特莱克", "SNOW": "雪花公司", "ARM": "安谋", "ASML": "阿斯麦",
    "META": "Meta平台", "HD": "家得宝", "LOW": "劳氏", "TGT": "塔吉特",
    "NKE": "耐克", "SBUX": "星巴克", "MCD": "麦当劳", "BKNG": "Booking控股",
    "DIS": "迪士尼", "NFLX": "奈飞", "ABNB": "爱彼迎", "ROST": "罗斯百货",
    "TJX": "TJX公司", "PDD": "拼多多", "JD": "京东", "BIDU": "百度", "SONY": "索尼",
    "BAC": "美国银行", "C": "花旗集团", "WFC": "富国银行", "MS": "摩根士丹利",
    "BLK": "贝莱德", "SCHW": "嘉信理财", "AXP": "美国运通", "COF": "第一资本",
    "PYPL": "贝宝", "JNJ": "强生", "PFE": "辉瑞", "MRK": "默沙东",
    "ABBV": "艾伯维", "AMGN": "安进", "GILD": "吉利德科学", "TMO": "赛默飞世尔",
    "DHR": "丹纳赫", "ISRG": "直觉外科", "CVS": "CVS健康", "NVO": "诺和诺德",
    "BA": "波音", "GE": "GE航空航天", "RTX": "雷神技术", "LMT": "洛克希德·马丁",
    "DE": "迪尔", "UPS": "联合包裹", "FDX": "联邦快递", "HON": "霍尼韦尔",
    "UNP": "联合太平洋", "CVX": "雪佛龙", "COP": "康菲石油", "SLB": "斯伦贝谢",
    "OXY": "西方石油", "EOG": "EOG资源", "FCX": "自由港麦克莫兰", "NEM": "纽蒙特",
    "TMUS": "美国T-Mobile", "VZ": "威瑞森", "T": "美国电话电报",
    "CMCSA": "康卡斯特", "PG": "宝洁", "KO": "可口可乐", "PEP": "百事",
    "PM": "菲利普莫里斯国际", "MO": "奥驰亚", "CL": "高露洁", "MDLZ": "亿滋国际",
    "NEE": "新纪元能源", "DUK": "杜克能源", "SO": "南方电力", "AMT": "美国电塔",
}
