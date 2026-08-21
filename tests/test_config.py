from pathlib import Path

from news_finance_v2.config import Settings


def test_defaults_use_v2_paths(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("CACHE_TTL_HOURS", raising=False)
    settings = Settings.from_env(tmp_path)

    assert settings.db_file == tmp_path / "data" / "news_finance_v2.db"
    assert settings.html_file == tmp_path / "html" / "news_finance_v2_preview.html"
    assert settings.cache_ttl_hours == 24
    assert settings.report_timezone == "America/New_York"


def test_report_date_uses_override_for_reproducible_backfills(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2030-01-02")
    assert Settings.from_env(tmp_path).report_date.isoformat() == "2030-01-02"


def test_missing_ai_model_is_actionable(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AI_MODEL", raising=False)
    settings = Settings.from_env(tmp_path)

    assert "AI_MODEL" in settings.validate_runtime(require_ai=True, require_smtp=False)


def test_smtp_validation_reports_names_not_secret_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "never-print-this")
    for name in ("SMTP_HOST", "SMTP_USERNAME", "EMAIL_TO"):
        monkeypatch.delenv(name, raising=False)

    missing = Settings.from_env(tmp_path).validate_runtime(
        require_ai=False,
        require_smtp=True,
    )

    assert missing == ["SMTP_HOST", "SMTP_USERNAME", "EMAIL_TO"]
    assert "never-print-this" not in repr(missing)


def test_from_env_loads_project_dotenv_without_overriding_process_env(tmp_path: Path, monkeypatch):
    (tmp_path / ".env").write_text("AI_MODEL=file-model\n", encoding="utf-8")
    monkeypatch.setenv("AI_MODEL", "process-model")

    assert Settings.from_env(tmp_path).ai_model == "process-model"

    monkeypatch.delenv("AI_MODEL")
    assert Settings.from_env(tmp_path).ai_model == "file-model"
