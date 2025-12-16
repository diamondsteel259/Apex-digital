from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from apex_market_scraper.config.loader import RuntimeSettings, load_app_config
from apex_market_scraper.core.logging import setup_logging
from apex_market_scraper.core.pipeline import run_scrape, scrape_all_sites
from apex_market_scraper.export.writers import export_records
from apex_market_scraper.scheduler.runner import run_scheduler

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apex-market-scraper",
        description="Independent market ingestion scraper for Apex-digital",
    )
    parser.add_argument(
        "--config",
        help="Path to YAML/JSON config (or set AMSCRAPER_CONFIG_PATH)",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        help="Override log level (or set AMSCRAPER_LOG_LEVEL)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command")

    scrape_p = subparsers.add_parser("scrape", help="Scrape configured site(s) and print summary")
    scrape_p.add_argument(
        "--sites",
        help="Comma-separated site names, or 'all' (default)",
        default="all",
    )
    scrape_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute wiring/normalization without issuing network requests",
    )
    scrape_p.add_argument(
        "--raw-json",
        help="Optional path to write normalized JSON records",
        default=None,
    )

    export_p = subparsers.add_parser("export", help="Export scraped data to CSV/Excel")
    export_p.add_argument(
        "--input",
        help="Path to JSON file produced by --raw-json (list[dict])",
        default=None,
    )
    export_p.add_argument(
        "--sample",
        action="store_true",
        help="Export a small sample dataset (no scraping)",
    )

    schedule_p = subparsers.add_parser("schedule", help="Run scrape+export on a cadence")
    schedule_p.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one cycle (useful for cron/K8s jobs)",
    )

    return parser


def _read_json_records(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON input must be a list of objects")
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("JSON input must be a list of objects")
        records.append(item)
    return records


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        return

    args = parser.parse_args(argv)

    settings = RuntimeSettings(log_level=args.log_level)
    setup_logging(settings.log_level)

    config_path = Path(args.config) if args.config else (settings.config_path or Path("configs/example.json"))
    cfg = load_app_config(config_path, settings=settings)

    if args.command == "scrape":
        result = run_scrape(cfg, settings, sites=str(args.sites), dry_run=bool(args.dry_run))
        records = [r.to_dict() for r in result.records]

        logger.info(
            "Scrape complete: sites_attempted=%s sites_succeeded=%s records_total=%s records_deduped=%s",
            result.metrics.sites_attempted,
            result.metrics.sites_succeeded,
            result.metrics.records_total,
            result.metrics.records_deduped,
        )

        if args.raw_json:
            out_path = Path(args.raw_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Wrote normalized JSON: %s", out_path)
        return

    if args.command == "export":
        if args.sample:
            records = [
                {
                    "site": "sample",
                    "listing_id": "sample-1",
                    "title": "Sample Listing",
                    "price": 1.23,
                    "currency": "USD",
                    "url": "https://example.invalid/listing/sample-1",
                }
            ]
        elif args.input:
            records = _read_json_records(Path(args.input))
        else:
            records = scrape_all_sites(cfg, settings)

        written = export_records(records, cfg.export)
        for p in written:
            logger.info("Wrote export: %s", p)
        return

    if args.command == "schedule":
        run_scheduler(cfg, settings, once=bool(args.once))
        return
    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
