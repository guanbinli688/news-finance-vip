from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .models import VerificationResult


def _brier(probability: float, correct: bool) -> float:
    return (probability - int(correct)) ** 2


def verify_absolute(
    prices: Mapping[date, float], base: float, direction: str,
    probability: float, neutral_band: float = 0.01,
) -> VerificationResult:
    if base <= 0 or not prices:
        raise ValueError("基准价格必须为正且价格路径不能为空")
    path = [float(prices[key]) / base - 1 for key in sorted(prices)]
    final = path[-1]
    if direction == "UP":
        correct, adverse = final > 0, min(path)
    elif direction == "DOWN":
        correct, adverse = final < 0, -max(path)
    elif direction == "NEUTRAL":
        correct, adverse = abs(final) < neutral_band, -max(abs(x) for x in path)
    else:
        raise ValueError("无效的绝对方向")
    return VerificationResult(correct, final, None, None, min(0.0, adverse), _brier(probability, correct))


def verify_relative(
    asset_prices: Mapping[date, float], benchmark_prices: Mapping[date, float],
    bases: tuple[float, float], direction: str, probability: float,
    neutral_band: float = 0.01,
) -> VerificationResult:
    base_asset, base_benchmark = bases
    if base_asset <= 0 or base_benchmark <= 0:
        raise ValueError("基准价格必须为正")
    dates = sorted(set(asset_prices) & set(benchmark_prices))
    if not dates:
        raise ValueError("资产与基准没有共同交易日")
    asset_path = [float(asset_prices[d]) / base_asset - 1 for d in dates]
    benchmark_path = [float(benchmark_prices[d]) / base_benchmark - 1 for d in dates]
    relative_path = [a - b for a, b in zip(asset_path, benchmark_path)]
    final = relative_path[-1]
    if direction == "OUTPERFORM":
        correct, adverse = final > 0, min(relative_path)
    elif direction == "UNDERPERFORM":
        correct, adverse = final < 0, -max(relative_path)
    elif direction == "NEUTRAL":
        correct, adverse = abs(final) < neutral_band, -max(abs(x) for x in relative_path)
    else:
        raise ValueError("无效的相对方向")
    return VerificationResult(
        correct, asset_path[-1], benchmark_path[-1], final,
        min(0.0, adverse), _brier(probability, correct),
    )
