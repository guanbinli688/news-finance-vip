SIGNALS = (
    "SPY", "QQQ", "IWM", "XLK", "XLF", "XLE",
    "^VIX", "HYG", "TLT", "GLD", "USO",
)

def coverage(snapshot):
    return sum(symbol in snapshot for symbol in SIGNALS) / len(SIGNALS)
