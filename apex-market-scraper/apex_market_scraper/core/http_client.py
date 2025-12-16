from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Final
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from apex_market_scraper.core.models import HttpResponse, RequestSpec

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENTS: Final[list[str]] = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
]


class RobotsTxtDisallowed(RuntimeError):
    pass


class MaxRetriesExceeded(RuntimeError):
    pass


class RetryableStatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"Retryable status_code={status_code}")
        self.status_code = status_code


@dataclass(slots=True, frozen=True)
class RetryConfig:
    max_attempts: int = 3
    backoff_initial_seconds: float = 0.5
    backoff_max_seconds: float = 8.0
    jitter_seconds: float = 0.25


def _sleep(seconds: float) -> None:
    if seconds <= 0:
        return
    time.sleep(seconds)


class ResilientHttpClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        user_agents: list[str] | None = None,
        proxies: list[str] | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._user_agents = user_agents or list(_DEFAULT_USER_AGENTS)
        self._proxies = proxies or []

        self._robots_by_origin: dict[str, RobotFileParser] = {}
        self._last_request_at: dict[str, float] = {}

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "ResilientHttpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _pick_user_agent(self) -> str:
        return random.choice(self._user_agents)

    def _pick_proxy(self) -> dict[str, str] | None:
        if not self._proxies:
            return None
        proxy = random.choice(self._proxies)
        return {"http": proxy, "https": proxy}

    def _throttle(self, *, site_key: str, min_interval_seconds: float) -> None:
        if min_interval_seconds <= 0:
            return

        now = time.monotonic()
        last = self._last_request_at.get(site_key)
        if last is None:
            self._last_request_at[site_key] = now
            return

        elapsed = now - last
        remaining = min_interval_seconds - elapsed
        if remaining > 0:
            _sleep(remaining)

        self._last_request_at[site_key] = time.monotonic()

    def _robots_allowed(self, *, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        rp = self._robots_by_origin.get(origin)
        if rp is None:
            robots_url = f"{origin}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = self._session.get(
                    robots_url,
                    headers={"User-Agent": user_agent},
                    timeout=10,
                    allow_redirects=True,
                )
                if resp.ok:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.parse([])
            except requests.RequestException:
                rp.parse([])

            self._robots_by_origin[origin] = rp

        return rp.can_fetch(user_agent, url)

    def request(
        self,
        spec: RequestSpec,
        *,
        site_key: str,
        dry_run: bool = False,
        respect_robots: bool = True,
        throttle_seconds: float = 0.0,
        retry: RetryConfig | None = None,
    ) -> HttpResponse:
        if dry_run:
            return HttpResponse(
                url=spec.url,
                status_code=0,
                headers={},
                text="",
                content=b"",
                is_dry_run=True,
            )

        retry_cfg = retry or RetryConfig()
        if retry_cfg.max_attempts < 1:
            raise ValueError("RetryConfig.max_attempts must be >= 1")

        user_agent = self._pick_user_agent()
        headers = {"User-Agent": user_agent, **spec.headers}

        if respect_robots and not self._robots_allowed(url=spec.url, user_agent=user_agent):
            raise RobotsTxtDisallowed(f"Blocked by robots.txt: {spec.url}")

        self._throttle(site_key=site_key, min_interval_seconds=throttle_seconds)

        proxies = self._pick_proxy()

        last_exc: BaseException | None = None

        for attempt in range(1, retry_cfg.max_attempts + 1):
            try:
                resp = self._session.request(
                    method=spec.method,
                    url=spec.url,
                    headers=headers,
                    params=spec.params,
                    data=spec.data,
                    json=spec.json,
                    timeout=spec.timeout_seconds,
                    allow_redirects=spec.allow_redirects,
                    proxies=proxies,
                )

                if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                    raise RetryableStatusError(resp.status_code)

                return HttpResponse(
                    url=str(resp.url),
                    status_code=int(resp.status_code),
                    headers={str(k): str(v) for k, v in resp.headers.items()},
                    text=str(resp.text),
                    content=bytes(resp.content),
                )
            except (requests.Timeout, requests.ConnectionError, RetryableStatusError) as exc:
                last_exc = exc
                if attempt >= retry_cfg.max_attempts:
                    break

                backoff = min(
                    retry_cfg.backoff_initial_seconds * (2 ** (attempt - 1)),
                    retry_cfg.backoff_max_seconds,
                )
                backoff += random.uniform(0.0, retry_cfg.jitter_seconds)

                logger.info(
                    "HTTP retry attempt=%s/%s url=%s reason=%s",
                    attempt,
                    retry_cfg.max_attempts,
                    spec.url,
                    exc,
                )

                _sleep(backoff)

        raise MaxRetriesExceeded(f"Failed after {retry_cfg.max_attempts} attempts: {spec.url}") from last_exc
