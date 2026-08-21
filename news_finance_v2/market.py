SIGNALS = ("SPY", "QQQ", "IWM", "^VIX", "HYG", "TLT", "GLD", "USO")

def coverage(snapshot):
    return sum(symbol in snapshot for symbol in SIGNALS) / len(SIGNALS)
