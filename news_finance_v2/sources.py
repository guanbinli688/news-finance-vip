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

COMPANY_UNIVERSE = tuple(COMPANY_SYMBOLS.values())
