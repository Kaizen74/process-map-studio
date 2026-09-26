"""Test helper: upload a source and wait for its background reading job (API_CONTRACT → Sources)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.paths import BACKEND_ROOT

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "engagement_load_control"


def wait_for_jobs(client: TestClient) -> None:
    assert client.app.state.worker.drain(30), "background jobs did not finish"  # type: ignore[attr-defined]


class Uploaded:
    """The upload response, plus the source as stored once its reading job has finished."""

    def __init__(self, client: TestClient, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.upload_body = body
        self._client = client

    def json(self) -> Any:
        if self.status_code != 201:
            return self.upload_body
        wait_for_jobs(self._client)
        return self._client.get(f"/api/sources/{self.upload_body['id']}").json()


def upload(
    client: TestClient, engagement: str, name: str, content: bytes | None = None, **form: Any
) -> Uploaded:
    data = content if content is not None else (FIXTURES / name).read_bytes()
    response = client.post(
        f"/api/engagements/{engagement}/sources",
        files={"file": (name, data, "application/octet-stream")},
        data={k: str(v).lower() if isinstance(v, bool) else v for k, v in form.items()},
    )
    return Uploaded(client, response.status_code, response.json())
