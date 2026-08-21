from datetime import datetime, timedelta, timezone

from news_finance_v2.db import RadarRepository, make_cache_key


NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def test_expired_cache_is_not_returned(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.cache_set("k", {"x": 1}, expires_at=NOW - timedelta(seconds=1))
    assert repo.cache_get("k", now=NOW) is None


def test_live_cache_round_trips_json(tmp_path):
    repo = RadarRepository(tmp_path / "v2.db")
    repo.cache_set("k", {"x": 1}, expires_at=NOW + timedelta(hours=1))
    assert repo.cache_get("k", now=NOW) == {"x": 1}


def test_system_prompt_and_version_change_cache_key():
    base = dict(provider="openai", model="m", purpose="p", user_prompt="u")
    assert make_cache_key(**base, system_prompt="a", prompt_version="1") != make_cache_key(**base, system_prompt="b", prompt_version="1")
    assert make_cache_key(**base, system_prompt="a", prompt_version="1") != make_cache_key(**base, system_prompt="a", prompt_version="2")
