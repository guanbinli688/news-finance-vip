from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings


def stage_public_site(settings: Settings) -> Path:
    if not settings.html_file.exists():
        raise FileNotFoundError(f"报告不存在: {settings.html_file}")
    docs_dir = settings.base_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_slug = settings.report_date.strftime("%m%d")
    index_file = docs_dir / "index.html"
    archive_file = docs_dir / f"{report_slug}.html"
    archive_index = docs_dir / report_slug / "index.html"
    archive_index.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings.html_file, index_file)
    shutil.copy2(settings.html_file, archive_file)
    shutil.copy2(settings.html_file, archive_index)
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")

    audit: dict[str, object] = {}
    if settings.audit_file.exists():
        loaded = json.loads(settings.audit_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            audit = loaded
    audit["published_at"] = datetime.now(timezone.utc).isoformat()
    audit["public_file"] = archive_file.name
    audit["public_path"] = f"{report_slug}/"
    (docs_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return index_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage NEWS FINANCE V2 for GitHub Pages")
    parser.add_argument("--base-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    output = stage_public_site(Settings.from_env(args.base_dir))
    print(f"GitHub Pages 文件已准备: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
