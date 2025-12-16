from __future__ import annotations

import abc
from typing import Any

from apex_market_scraper.config.models import SiteConfig


class BaseSiteScraper(abc.ABC):
    def __init__(self, site: SiteConfig, api_key: str | None, proxies: list[str] | None = None):
        self.site = site
        self.api_key = api_key
        self.proxies = proxies or []

    @abc.abstractmethod
    def scrape(self) -> list[dict[str, Any]]:
        """Return a list of normalized listing dicts."""
