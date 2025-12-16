from __future__ import annotations

from typing import Any, Mapping

from apex_market_scraper.config.loader import RuntimeSettings
from apex_market_scraper.config.models import AppConfig
from apex_market_scraper.core.models import HttpResponse, ProductRecord, RequestSpec
from apex_market_scraper.core.pipeline import run_scrape
from apex_market_scraper.sites.base import BaseSiteScraper
from apex_market_scraper.sites.registry import register


@register("dupe_test")
class _DupeTestScraper(BaseSiteScraper):
    def build_requests(self) -> list[RequestSpec]:
        return [RequestSpec(url="https://example.invalid/listings")]

    def parse_listing(self, response: HttpResponse, request: RequestSpec) -> list[Mapping[str, Any]]:
        assert response.is_dry_run
        return [
            {"name": "A", "url": "https://example.invalid/p/1", "price": 1.0},
            {"name": "B", "url": "https://example.invalid/p/1", "price": 2.0},
        ]

    def normalize_record(self, raw: Mapping[str, Any]) -> ProductRecord:
        return ProductRecord(
            site_name=self.site.name,
            site_kind=self.site.kind,
            product_name=str(raw.get("name") or ""),
            category=None,
            price=float(raw["price"]),
            currency=None,
            description=None,
            min_quantity=None,
            max_quantity=None,
            seller_rating=None,
            sold_amount=None,
            stock=None,
            delivery_eta=None,
            refill_available=None,
            warranty=None,
            product_url=str(raw.get("url") or ""),
            hidden_link_metadata={},
        )


def test_pipeline_deduplicates_by_product_url() -> None:
    cfg = AppConfig(
        scheduler={"cadence_hours": 12},
        export={},
        sites=[
            {
                "name": "dupe_site",
                "kind": "dupe_test",
                "enabled": True,
                "params": {},
            }
        ],
    )

    result = run_scrape(cfg, RuntimeSettings(), sites="all", dry_run=True)

    assert result.metrics.records_total == 2
    assert result.metrics.records_deduped == 1
    assert len(result.records) == 1

    rec = result.records[0]
    assert rec.product_url == "https://example.invalid/p/1"
    assert rec.site_name == "dupe_site"
    assert rec.site_kind == "dupe_test"
