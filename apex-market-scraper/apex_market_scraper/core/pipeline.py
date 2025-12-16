from __future__ import annotations

import logging
from typing import Any

from apex_market_scraper.config.loader import RuntimeSettings, get_site_api_key
from apex_market_scraper.config.models import AppConfig, SiteConfig
from apex_market_scraper.sites.registry import get_scraper

logger = logging.getLogger(__name__)


def scrape_site(site: SiteConfig, settings: RuntimeSettings) -> list[dict[str, Any]]:
    scraper_cls = get_scraper(site.kind)
    api_key = get_site_api_key(site.api_key_env)
    scraper = scraper_cls(site=site, api_key=api_key, proxies=settings.resolved_proxies())

    logger.info("Scraping site=%s kind=%s", site.name, site.kind)
    records = scraper.scrape()
    for r in records:
        r.setdefault("site", site.name)

    logger.info("Scraped %s record(s) from site=%s", len(records), site.name)
    return records


def scrape_all_sites(cfg: AppConfig, settings: RuntimeSettings) -> list[dict[str, Any]]:
    all_records: list[dict[str, Any]] = []

    enabled_sites = [s for s in cfg.sites if s.enabled]
    if not enabled_sites:
        logger.warning("No enabled sites in config")
        return []

    for site in enabled_sites:
        try:
            all_records.extend(scrape_site(site, settings))
        except Exception:
            logger.exception("Failed scraping site=%s", site.name)

    return all_records
