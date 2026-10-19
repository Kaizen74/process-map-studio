"""The app answers only pages it served itself (deep review 2026-10-19). It listens on 127.0.0.1,
but a web page open in the same browser can still reach it: by DNS rebinding (an attacker's name
re-pointed at 127.0.0.1, so the browser sends the attacker's Host and treats the app as that
site) or by a cross-site form post. So a request must name the app's own host, and a request
that changes anything must not come from another site."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


@pytest.fixture()
def client(settings_config: AppConfig) -> Iterator[TestClient]:
    with TestClient(create_app(settings_config), base_url="http://127.0.0.1:8000") as c:
        yield c


ENGAGEMENT = {"name": "Load control", "trigger": "Flight scheduled", "end_point": "Sheet issued"}


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "127.0.0.1.evil.example"])
def test_a_request_naming_another_host_is_refused(client: TestClient, host: str) -> None:
    """DNS rebinding: the browser sends the attacker's name as Host."""
    for response in (
        client.get("/api/engagements", headers={"Host": host}),
        client.get("/api/settings", headers={"Host": host}),
        client.post("/api/engagements", json=ENGAGEMENT, headers={"Host": host}),
        client.get("/", headers={"Host": host}),
    ):
        assert response.status_code == 403, (host, response.status_code)
    assert client.get("/api/engagements").json() == []  # nothing was created


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "127.0.0.1", "localhost",
                                  "[::1]:8000"])  # fmt: skip
def test_the_app_s_own_names_are_answered(client: TestClient, host: str) -> None:
    assert client.get("/api/settings", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},  # a sandboxed page or a file
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "http://127.0.0.1:9999"},  # another local app on another port
    ],
)
def test_a_change_from_another_site_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    """Cross-site requests: a form post, or a fetch with no-cors, from a page on another site."""
    created = client.post("/api/engagements", json=ENGAGEMENT, headers=headers)
    assert created.status_code == 403
    assert created.json()["error"]["message"] == (
        "This request came from another website, so the app refused it."
    )
    assert client.get("/api/engagements").json() == []


def test_the_app_s_own_pages_may_change_things(client: TestClient) -> None:
    for headers in ({"Origin": "http://127.0.0.1:8000", "Sec-Fetch-Site": "same-origin"},
                    {"Origin": "http://localhost:8000"}, {}):  # fmt: skip
        assert client.post("/api/engagements", json=ENGAGEMENT, headers=headers).status_code == 201


def test_reading_is_allowed_from_anywhere_the_browser_lets_it(client: TestClient) -> None:
    """Without CORS headers the browser never lets another site read an answer; only changes
    need the origin check (a top-level link to a download must keep working)."""
    response = client.get("/api/settings", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_no_other_site_may_show_the_app_in_a_frame(client: TestClient) -> None:
    """Clickjacking: a page on another site could show the app in an invisible frame and trick a
    click on Publish or Delete; the frame's requests would come from the app's own origin."""
    for path in ("/", "/api/settings", "/engagements/x/review"):
        headers = client.get(path).headers
        assert headers["x-frame-options"] == "DENY", path
        assert "frame-ancestors 'none'" in headers["content-security-policy"], path
        assert headers["x-content-type-options"] == "nosniff", path
        assert headers["referrer-policy"] == "no-referrer", path
