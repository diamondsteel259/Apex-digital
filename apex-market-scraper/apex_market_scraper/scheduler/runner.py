from __future__ import annotations

import logging
import time

from apex_market_scraper.config.loader import RuntimeSettings
from apex_market_scraper.config.models import AppConfig
from apex_market_scraper.core.pipeline import scrape_all_sites
from apex_market_scraper.export.writers import export_records

logger = logging.getLogger(__name__)


def run_cycle(cfg: AppConfig, settings: RuntimeSettings) -> None:
    records = scrape_all_sites(cfg, settings)
    if not records:
        logger.warning("No records scraped; skipping export")
        return

    written = export_records(records, cfg.export)
    logger.info("Exported %s file(s): %s", len(written), ", ".join(p.name for p in written))


def run_scheduler(cfg: AppConfig, settings: RuntimeSettings, *, once: bool = False) -> None:
    cadence_seconds = int(cfg.scheduler.cadence_hours * 3600)

    while True:
        run_cycle(cfg, settings)

        if once:
            return

        logger.info("Sleeping for %s hour(s)", cfg.scheduler.cadence_hours)
        try:
            time.sleep(cadence_seconds)
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted")
            return
