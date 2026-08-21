from datetime import date

import pytest

from news_finance_v2.calendar import TradingCalendar


def test_next_session_skips_weekend_and_labor_day():
    cal = TradingCalendar()
    assert cal.target_session(date(2026, 9, 4), 1) == date(2026, 9, 8)


def test_base_session_uses_previous_session_for_weekend():
    cal = TradingCalendar()
    assert cal.base_session(date(2026, 8, 23)) == date(2026, 8, 21)


def test_horizon_must_be_supported():
    with pytest.raises(ValueError, match="3, 5, 10, 15"):
        TradingCalendar().target_session(date(2026, 8, 19), 4)
