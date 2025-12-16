from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from apex_market_scraper.config.loader import RuntimeSettings, get_site_api_key
from apex_market_scraper.config.models import AppConfig, SiteConfig
from apex_market_scraper.core.logging import get_logger
from apex_market_scraper.core.models import (
    ProductRecord,
    ScrapeEvent,
    ScrapeMetrics,
    ScrapeResult,
    SiteMetadata,
)
from apex_market_scraper.sites.registry import create_scraper


def _select_sites(enabled_sites: list[SiteConfig], sites: str | Iterable[str]) -> list[SiteConfig]:
    if isinstance(sites, str):
        if sites.lower() == "all":
            return enabled_sites
        wanted = {s.strip() for s in sites.split(",") if s.strip()}
    else:
        wanted = {s.strip() for s in sites if s.strip()}

    return [s for s in enabled_sites if s.name in wanted]


def run_scrape(
    cfg: AppConfig,
    settings: RuntimeSettings,
    *,
    sites: str | Iterable[str] = "all",
    dry_run: bool = False,
) -> ScrapeResult:
    enabled_sites = [s for s in cfg.sites if s.enabled]
    selected_sites = _select_sites(enabled_sites, sites)

    pipeline_task_id = uuid4().hex
    plog = get_logger(__name__, site="*", task_id=pipeline_task_id)

    events: list[ScrapeEvent] = []

    if not selected_sites:
        plog.warning("pipeline.no_sites enabled=%s", len(enabled_sites))
        events.append(
            ScrapeEvent(
                ts=datetime.now(tz=timezone.utc),
                event="pipeline.no_sites",
                message="No enabled/selected sites to scrape",
                task_id=pipeline_task_id,
                data={"enabled_sites": len(enabled_sites)},
            )
        )
        return ScrapeResult(
            records=[],
            site_metadata={},
            metrics=ScrapeMetrics(
                sites_attempted=0,
                sites_succeeded=0,
                records_total=0,
                records_deduped=0,
            ),
            events=events,
        )

    plog.info("pipeline.start sites=%s dry_run=%s", [s.name for s in selected_sites], dry_run)
    events.append(
        ScrapeEvent(
            ts=datetime.now(tz=timezone.utc),
            event="pipeline.start",
            message="Pipeline started",
            task_id=pipeline_task_id,
            data={"sites": [s.name for s in selected_sites], "dry_run": dry_run},
        )
    )

    all_records: list[ProductRecord] = []
    site_metadata: dict[str, SiteMetadata] = {}

    sites_attempted = 0
    sites_succeeded = 0

    for site in selected_sites:
        sites_attempted += 1
        site_task_id = f"{pipeline_task_id}:{site.name}"
        slog = get_logger(__name__, site=site.name, task_id=site_task_id)
        slog.info("site.start kind=%s", site.kind)

        api_key = get_site_api_key(site.api_key_env)

        try:
            scraper = create_scraper(
                site=site,
                api_key=api_key,
                task_id=site_task_id,
                proxies=settings.resolved_proxies(),
            )
            records, meta = scraper.scrape_with_metadata(dry_run=dry_run)
        except Exception as e:
            now = datetime.now(tz=timezone.utc)
            records = []
            meta = SiteMetadata(
                site_name=site.name,
                site_kind=site.kind,
                task_id=site_task_id,
                started_at=now,
                finished_at=now,
                dry_run=dry_run,
                errors=[str(e)],
            )
            events.append(
                ScrapeEvent(
                    ts=now,
                    event="site.failed",
                    message="Site scrape failed",
                    site_name=site.name,
                    task_id=site_task_id,
                    data={"error": str(e), "kind": site.kind},
                )
            )
            slog.exception("site.failed")

        site_metadata[site.name] = meta
        all_records.extend(records)

        if not meta.errors:
            sites_succeeded += 1
        slog.info("site.complete records=%s errors=%s", len(records), len(meta.errors))

    deduped_by_url: dict[str, ProductRecord] = {}
    for rec in all_records:
        key = rec.dedupe_key()
        if key in deduped_by_url:
            continue
        deduped_by_url[key] = rec

    deduped_records = list(deduped_by_url.values())
    duplicate_count = len(all_records) - len(deduped_records)
    if duplicate_count:
        events.append(
            ScrapeEvent(
                ts=datetime.now(tz=timezone.utc),
                event="records.deduplicated",
                message="Deduplicated records by product_url",
                task_id=pipeline_task_id,
                data={"duplicates": duplicate_count},
            )
        )

    metrics = ScrapeMetrics(
        sites_attempted=sites_attempted,
        sites_succeeded=sites_succeeded,
        records_total=len(all_records),
        records_deduped=len(deduped_records),
    )

    plog.info(
        "pipeline.complete sites_attempted=%s sites_succeeded=%s records_total=%s records_deduped=%s",
        metrics.sites_attempted,
        metrics.sites_succeeded,
        metrics.records_total,
        metrics.records_deduped,
    )

    events.append(
        ScrapeEvent(
            ts=datetime.now(tz=timezone.utc),
            event="pipeline.complete",
            message="Pipeline completed",
            task_id=pipeline_task_id,
            data={
                "sites_attempted": metrics.sites_attempted,
                "sites_succeeded": metrics.sites_succeeded,
                "records_total": metrics.records_total,
                "records_deduped": metrics.records_deduped,
            },
        )
    )

    return ScrapeResult(
        records=deduped_records,
        site_metadata=site_metadata,
        metrics=metrics,
        events=events,
    )


def scrape_site(site: SiteConfig, settings: RuntimeSettings, *, dry_run: bool = False) -> list[dict[str, Any]]:
    # Backwards-compatible helper for exporter/scheduler; prefer run_scrape().
    task_id = uuid4().hex
    api_key = get_site_api_key(site.api_key_env)
    scraper = create_scraper(
        site=site,
        api_key=api_key,
        task_id=task_id,
        proxies=settings.resolved_proxies(),
    )
    records = scraper.scrape(dry_run=dry_run)
    return [r.to_dict() for r in records]


def scrape_all_sites(cfg: AppConfig, settings: RuntimeSettings, *, dry_run: bool = False) -> list[dict[str, Any]]:
    # Backwards-compatible API for existing callers.
    result = run_scrape(cfg, settings, sites="all", dry_run=dry_run)
    return [r.to_dict() for r in result.records]
