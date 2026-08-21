from datetime import date, datetime, timezone

from news_finance_v2.db import RadarRepository
from news_finance_v2.live import verify_due_predictions
from news_finance_v2.models import Prediction


def test_due_prediction_is_mechanically_verified(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.start_run("r1", "m", "v2")
    repo.freeze_prediction(Prediction(
        id="p", run_id="r1", created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        base_session=date(2026, 8, 3), target_session=date(2026, 8, 10),
        horizon_days=5, target="SPY", direction="UP", probability=.6,
        thesis="x", invalidation="y", base_asset=100, model="m", prompt_version="v2",
    ))
    loader = lambda symbol, start, end: {date(2026, 8, 10): 102.0}

    assert verify_due_predictions(repo, loader=loader, today=date(2026, 8, 10)) == 1
    assert repo.due_predictions(date(2026, 8, 10)) == []


def test_missing_prices_leave_prediction_pending(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.start_run("r1", "m", "v2")
    repo.freeze_prediction(Prediction(
        id="p", run_id="r1", created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        base_session=date(2026, 8, 3), target_session=date(2026, 8, 10),
        horizon_days=5, target="SPY", direction="UP", probability=.6,
        thesis="x", invalidation="y", base_asset=100, model="m", prompt_version="v2",
    ))
    assert verify_due_predictions(repo, loader=lambda *args: {}, today=date(2026, 8, 10)) == 0
    assert len(repo.due_predictions(date(2026, 8, 10))) == 1
