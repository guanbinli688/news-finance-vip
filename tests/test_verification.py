from datetime import date

import pytest

from news_finance_v2.verification import verify_absolute, verify_relative


D1 = date(2026, 8, 20)
D2 = date(2026, 8, 21)


def test_relative_max_adverse_uses_relative_path():
    result = verify_relative(
        {D1: 80.0, D2: 110.0}, {D1: 90.0, D2: 100.0},
        (100.0, 100.0), "OUTPERFORM", 0.6,
    )
    assert result.excess_return == pytest.approx(0.10)
    assert result.max_adverse == pytest.approx(-0.10)
    assert result.correct


def test_relative_series_aligns_common_dates():
    result = verify_relative(
        {D1: 101.0, D2: 102.0}, {D2: 100.0},
        (100.0, 100.0), "OUTPERFORM", 0.6,
    )
    assert result.excess_return == pytest.approx(0.02)


def test_absolute_down_and_brier():
    result = verify_absolute({D1: 98.0}, 100.0, "DOWN", 0.7)
    assert result.correct
    assert result.max_adverse == pytest.approx(0.0)
    assert result.brier == pytest.approx(0.09)


def test_empty_common_dates_are_rejected():
    with pytest.raises(ValueError, match="共同交易日"):
        verify_relative({D1: 101.0}, {D2: 99.0}, (100.0, 100.0), "OUTPERFORM", 0.6)
