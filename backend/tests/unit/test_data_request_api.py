"""GET /api/templates/data-request (R1, criterion 82): three formats, no engagement needed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


def test_each_format_downloads_with_its_name_and_type(settings_config: AppConfig) -> None:
    with TestClient(create_app(settings_config)) as client:
        for fmt, media, name in (
            ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "data-request-template.docx"),
            ("md", "text/markdown; charset=utf-8", "data-request-template.md"),
            ("csv", "text/csv; charset=utf-8", "data-request-header.csv"),
        ):  # fmt: skip
            found = client.get("/api/templates/data-request", params={"format": fmt})
            assert found.status_code == 200, found.text
            assert found.headers["content-type"] == media
            assert found.headers["content-disposition"] == f'attachment; filename="{name}"'
        assert found.content.startswith(b"case_id,activity,timestamp")
        word = client.get("/api/templates/data-request", params={"format": "docx"}).content
        assert word[:2] == b"PK"  # a real .docx (a zip package)
        refused = client.get("/api/templates/data-request", params={"format": "pdf"})
        assert refused.status_code == 422
        assert "Choose docx, md or csv." in refused.text
