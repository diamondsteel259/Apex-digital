from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apex_market_scraper.sites.base import BaseSiteScraper
from apex_market_scraper.sites.registry import register


@register("example")
class ExampleSiteScraper(BaseSiteScraper):
    def scrape(self) -> list[dict[str, Any]]:
        now = datetime.now(tz=UTC).isoformat()
        base_url = str(self.site.params.get("base_url", "https://example.invalid"))

        return [
            {
                "site": self.site.name,
                "listing_id": "example-1",
                "title": "Example Listing",
                "price": 9.99,
                "currency": "USD",
                "url": f"{base_url}/listing/example-1",
                "scraped_at": now,
            }
        ]
