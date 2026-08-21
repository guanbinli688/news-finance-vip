import json

from news_finance_v2.config import Settings
from news_finance_v2.publishing import stage_public_site


def test_stage_public_site_copies_report_and_safe_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2030-01-02")
    settings = Settings.from_env(tmp_path)
    settings.html_file.parent.mkdir(parents=True)
    settings.html_file.write_text("<html><body>report</body></html>", encoding="utf-8")
    settings.audit_file.parent.mkdir(parents=True)
    settings.audit_file.write_text(json.dumps({"report_date": "2030-01-02"}), encoding="utf-8")

    output = stage_public_site(settings)

    assert output == tmp_path / "docs" / "index.html"
    assert output.read_text(encoding="utf-8") == "<html><body>report</body></html>"
    assert (tmp_path / "docs" / "0102.html").read_text(encoding="utf-8") == output.read_text(encoding="utf-8")
    assert (tmp_path / "docs" / "0102" / "index.html").read_text(encoding="utf-8") == output.read_text(encoding="utf-8")
    audit = json.loads((tmp_path / "docs" / "audit.json").read_text(encoding="utf-8"))
    assert audit["report_date"] == "2030-01-02"
    assert audit["public_file"] == "0102.html"
    assert audit["public_path"] == "0102/"
    assert (tmp_path / "docs" / ".nojekyll").exists()
