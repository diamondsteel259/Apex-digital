from __future__ import annotations

import abc
from dataclasses import replace
from datetime import datetime, timezone
from typing import Mapping

from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.core.http_client import ResilientHttpClient, RetryConfig
from apex_market_scraper.core.logging import get_logger
from apex_market_scraper.core.models import HttpResponse, ProductRecord, RequestSpec, SiteMetadata


class BaseSiteScraper(abc.ABC):
    def __init__(
        self,
        *,
        site: SiteConfig,
        api_key: str | None,
        task_id: str,
        proxies: list[str] | None = None,
        http_client: ResilientHttpClient | None = None,
    ) -> None:
        self.site = site
        self.api_key = api_key
        self.task_id = task_id
        self.proxies = proxies or []
        self.http = http_client or ResilientHttpClient(proxies=self.proxies)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}",
            site=self.site.name,
            task_id=self.task_id,
        )

    @abc.abstractmethod
    def build_requests(self) -> list[RequestSpec]:
        raise NotImplementedError

    @abc.abstractmethod
    def parse_listing(self, response: HttpResponse, request: RequestSpec) -> list[Mapping[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    def normalize_record(self, raw: Mapping[str, Any]) -> ProductRecord:
        raise NotImplementedError

    def to_dataframe(self, records: list[ProductRecord]) -> Any:
        try:
            import pandas as pd  # type: ignore[import-not-found]
        except ModuleNotFoundError as e:  # pragma: no cover
            raise RuntimeError("pandas is not installed") from e

        return pd.DataFrame([r.to_dict() for r in records])

    def _retry_config(self) -> RetryConfig:
        params = self.site.params
        return RetryConfig(
            max_attempts=int(params.get("max_attempts", 3)),
            backoff_initial_seconds=float(params.get("backoff_initial_seconds", 0.5)),
            backoff_max_seconds=float(params.get("backoff_max_seconds", 8.0)),
            jitter_seconds=float(params.get("jitter_seconds", 0.25)),
        )

    def _respect_robots(self) -> bool:
        return bool(self.site.params.get("respect_robots", True))

    def _throttle_seconds(self) -> float:
        return float(self.site.params.get("throttle_seconds", 0.0))

    def scrape_with_metadata(self, *, dry_run: bool = False) -> tuple[list[ProductRecord], SiteMetadata]:
        started_at = datetime.now(tz=timezone.utc)
        meta = SiteMetadata(
            site_name=self.site.name,
            site_kind=self.site.kind,
            task_id=self.task_id,
            started_at=started_at,
            dry_run=dry_run,
        )

        requests_to_make = self.build_requests()
        meta.requests_built = len(requests_to_make)

        records: list[ProductRecord] = []

        self.logger.info("scrape.start kind=%s dry_run=%s", self.site.kind, dry_run)
        try:
            for req in requests_to_make:
                response = self.http.request(
                    req,
                    site_key=self.site.name,
                    dry_run=dry_run,
                    respect_robots=self._respect_robots(),
                    throttle_seconds=self._throttle_seconds(),
                    retry=self._retry_config(),
                )
                if not response.is_dry_run:
                    meta.requests_executed += 1

                raw_items = self.parse_listing(response, req)
                meta.raw_records_parsed += len(raw_items)

                for raw in raw_items:
                    normalized = self.normalize_record(raw)
                    if normalized.site_name != self.site.name or normalized.site_kind != self.site.kind:
                        normalized = replace(
                            normalized,
                            site_name=self.site.name,
                            site_kind=self.site.kind,
                        )
                    records.append(normalized)

                meta.records_normalized = len(records)

            meta.finished_at = datetime.now(tz=timezone.utc)
            self.logger.info("scrape.success records=%s", len(records))
            return records, meta
        except Exception as e:
            meta.finished_at = datetime.now(tz=timezone.utc)
            meta.errors.append(str(e))
            self.logger.exception("scrape.failed")
            return records, meta

    def scrape(self, *, dry_run: bool = False) -> list[ProductRecord]:
        records, _meta = self.scrape_with_metadata(dry_run=dry_run)
        return records
