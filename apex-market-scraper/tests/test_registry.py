from __future__ import annotations

from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.sites.example import ExampleSiteScraper
from apex_market_scraper.sites.registry import create_scraper


def test_registry_create_scraper_from_config() -> None:
    site = SiteConfig(name="example_site", kind="example", enabled=True, api_key_env=None, params={})

    scraper = create_scraper(site=site, api_key=None, task_id="t1", proxies=[])

    assert isinstance(scraper, ExampleSiteScraper)
    assert scraper.site.name == "example_site"
    assert scraper.site.kind == "example"
    assert scraper.task_id == "t1"
