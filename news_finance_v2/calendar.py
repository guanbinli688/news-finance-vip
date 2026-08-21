from __future__ import annotations

from datetime import date

try:
    import exchange_calendars as xcals
except ImportError as exc:  # pragma: no cover - exercised at installation boundary
    xcals = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


SUPPORTED_HORIZONS = frozenset({3, 5, 10, 15})


class TradingCalendar:
    def __init__(self):
        if xcals is None:
            raise RuntimeError(
                "exchange-calendars 未安装；请执行 pip install exchange-calendars"
            ) from _IMPORT_ERROR
        self._calendar = xcals.get_calendar("XNYS")

    def base_session(self, on_date: date) -> date:
        session = self._calendar.date_to_session(on_date, direction="previous")
        return session.date()

    def target_session(self, base: date, horizon: int) -> date:
        if horizon not in SUPPORTED_HORIZONS and horizon != 1:
            raise ValueError("预测周期只能是 3, 5, 10, 15 个交易日")
        base_session = self._calendar.date_to_session(base, direction="previous")
        return self._calendar.session_offset(base_session, horizon).date()
