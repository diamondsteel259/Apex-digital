from __future__ import annotations

from typing import Mapping

from apex_market_scraper.core.models import HttpResponse, ProductRecord, RequestSpec
from apex_market_scraper.sites.base import BaseSiteScraper
from apex_market_scraper.sites.registry import register


@register("example")
class ExampleSiteScraper(BaseSiteScraper):
    def build_requests(self) -> list[RequestSpec]:
        base_url = str(self.site.params.get("base_url", "https://example.invalid"))
        return [RequestSpec(url=f"{base_url}/listings")]

    def parse_listing(self, response: HttpResponse, request: RequestSpec) -> list[Mapping[str, Any]]:
        if response.is_dry_run:
            return [
                {
                    "name": "Example Listing",
                    "category": str(self.site.params.get("category", "all")),
                    "price": 9.99,
                    "currency": "USD",
                    "url": f"{request.url}#example-1",
                    "description": "Example record produced during dry-run.",
                }
            ]

        # Real scrapers would parse HTML/JSON from response.text here.
        return []

    def normalize_record(self, raw: Mapping[str, Any]) -> ProductRecord:
        price = raw.get("price")
        currency = raw.get("currency")

        return ProductRecord(
            site_name=self.site.name,
            site_kind=self.site.kind,
            product_name=str(raw.get("name") or ""),
            category=str(raw.get("category")) if raw.get("category") is not None else None,
            price=float(price) if price is not None else None,
            currency=str(currency) if currency is not None else None,
            description=str(raw.get("description")) if raw.get("description") is not None else None,
            min_quantity=None,
            max_quantity=None,
            seller_rating=None,
            sold_amount=None,
            stock=None,
            delivery_eta=None,
            refill_available=None,
            warranty=None,
            product_url=str(raw.get("url") or ""),
            hidden_link_metadata=dict(raw.get("hidden_link_metadata") or {}),
        )
