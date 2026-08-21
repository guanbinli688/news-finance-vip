from dataclasses import replace
from datetime import date, datetime, timezone

from news_finance_v2.db import RadarRepository
from news_finance_v2.models import Prediction


def make_prediction():
    return Prediction(
        id="p1", run_id="r1", created_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        base_session=date(2026, 8, 19), target_session=date(2026, 8, 26),
        horizon_days=5, target="SPY", direction="UP", probability=.6,
        thesis="original", invalidation="credit spreads", evidence_ids=("MKT-1",),
        base_asset=100.0, model="test", prompt_version="v2",
    )


def test_frozen_prediction_cannot_be_overwritten(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.start_run("r1", "test", "v2")
    prediction = make_prediction()
    assert repo.freeze_prediction(prediction)
    assert not repo.freeze_prediction(replace(prediction, thesis="changed"))
    assert repo.get_prediction("p1").thesis == "original"


def test_run_audit_is_persisted(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.start_run("r1", "test", "v2")
    repo.finish_run("r1", "SUCCESS", {"coverage": .9})
    assert repo.get_run("r1")["status"] == "SUCCESS"


def test_due_predictions_excludes_future_and_verified(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.start_run("r1", "test", "v2")
    prediction = make_prediction()
    assert repo.freeze_prediction(prediction)
    assert repo.due_predictions(date(2026, 8, 25)) == []
    assert [p.id for p in repo.due_predictions(date(2026, 8, 26))] == ["p1"]
    from news_finance_v2.models import VerificationResult
    repo.save_verification("p1", VerificationResult(True, .02, None, None, 0.0, .16))
    assert repo.due_predictions(date(2026, 8, 26)) == []
