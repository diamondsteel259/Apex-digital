from __future__ import annotations

from typing import Any

import pytest
import requests

import apex_market_scraper.core.http_client as http_client
from apex_market_scraper.core.http_client import ResilientHttpClient, RetryConfig
from apex_market_scraper.core.models import RequestSpec


def _make_response(*, url: str, status_code: int) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    resp.url = url
    resp._content = b"ok"
    return resp


def test_http_client_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http_client, "_sleep", lambda _seconds: None)

    session = requests.Session()
    calls = {"n": 0}

    def fake_request(method: str, url: str, **_kwargs: Any) -> requests.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.Timeout("boom")
        return _make_response(url=url, status_code=200)

    monkeypatch.setattr(session, "request", fake_request)

    client = ResilientHttpClient(session=session)
    resp = client.request(
        RequestSpec(url="https://example.invalid"),
        site_key="s1",
        respect_robots=False,
        throttle_seconds=0.0,
        retry=RetryConfig(max_attempts=2, backoff_initial_seconds=0.0, jitter_seconds=0.0),
    )

    assert resp.status_code == 200
    assert calls["n"] == 2


def test_http_client_retries_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http_client, "_sleep", lambda _seconds: None)

    session = requests.Session()
    calls = {"n": 0}

    def fake_request(method: str, url: str, **_kwargs: Any) -> requests.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _make_response(url=url, status_code=503)
        return _make_response(url=url, status_code=200)

    monkeypatch.setattr(session, "request", fake_request)

    client = ResilientHttpClient(session=session)
    resp = client.request(
        RequestSpec(url="https://example.invalid"),
        site_key="s1",
        respect_robots=False,
        throttle_seconds=0.0,
        retry=RetryConfig(max_attempts=2, backoff_initial_seconds=0.0, jitter_seconds=0.0),
    )

    assert resp.status_code == 200
    assert calls["n"] == 2
