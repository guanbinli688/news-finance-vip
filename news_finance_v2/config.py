from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    db_file: Path
    html_file: Path
    audit_file: Path
    ai_provider: str
    ai_model: str
    prompt_version: str
    timeout_seconds: int
    cache_ttl_hours: int
    market_coverage_threshold: float
    sec_user_agent: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_to: str
    report_timezone: str
    report_date_override: str
    public_report_url: str

    @classmethod
    def from_env(cls, base_dir: Path) -> "Settings":
        base_dir = Path(base_dir).resolve()
        load_dotenv(base_dir / ".env", override=False)
        return cls(
            base_dir=base_dir,
            db_file=base_dir / "data" / "news_finance_v2.db",
            html_file=base_dir / "html" / "news_finance_v2_preview.html",
            audit_file=base_dir / "data" / "news_finance_v2_audit.json",
            ai_provider=os.getenv("AI_PROVIDER", "openai").strip().lower(),
            ai_model=os.getenv("AI_MODEL", "").strip(),
            prompt_version=os.getenv("PROMPT_VERSION", "v2.0").strip(),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT", "25")),
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
            market_coverage_threshold=float(os.getenv("MARKET_COVERAGE_THRESHOLD", "0.80")),
            sec_user_agent=os.getenv("SEC_USER_AGENT", "").strip(),
            smtp_host=os.getenv("SMTP_HOST", "").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            email_to=os.getenv("EMAIL_TO", "").strip(),
            report_timezone=os.getenv("REPORT_TIMEZONE", "America/New_York").strip(),
            report_date_override=os.getenv("REPORT_DATE_OVERRIDE", "").strip(),
            public_report_url=os.getenv("PUBLIC_REPORT_URL", "").strip(),
        )

    @property
    def report_date(self) -> date:
        if self.report_date_override:
            try:
                return date.fromisoformat(self.report_date_override)
            except ValueError as exc:
                raise ValueError("REPORT_DATE_OVERRIDE 必须是 YYYY-MM-DD") from exc
        try:
            return datetime.now(ZoneInfo(self.report_timezone)).date()
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"无效 REPORT_TIMEZONE: {self.report_timezone}") from exc

    def validate_runtime(self, *, require_ai: bool, require_smtp: bool) -> list[str]:
        missing: list[str] = []
        if require_ai:
            if not self.ai_model:
                missing.append("AI_MODEL")
            key_name = "OPENAI_API_KEY" if self.ai_provider == "openai" else "DEEPSEEK_API_KEY"
            if not os.getenv(key_name, "").strip():
                missing.append(key_name)
        if require_smtp:
            for name, value in (
                ("SMTP_HOST", self.smtp_host),
                ("SMTP_USERNAME", self.smtp_username),
                ("SMTP_PASSWORD", self.smtp_password),
                ("EMAIL_TO", self.email_to),
            ):
                if not value:
                    missing.append(name)
        return missing

    @property
    def sec_enabled(self) -> bool:
        value = self.sec_user_agent.lower()
        return bool(value and "@" in value and "example.com" not in value)
