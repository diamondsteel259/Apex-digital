from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.core.http_client import ResilientHttpClient
from apex_market_scraper.sites.base import BaseSiteScraper

ScraperFactory = Callable[..., BaseSiteScraper]

_SCRAPERS: dict[str, type[BaseSiteScraper]] = {}
_BUILTINS_LOADED = False


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    import_module("apex_market_scraper.sites")
    _BUILTINS_LOADED = True


def register(kind: str) -> Callable[[type[BaseSiteScraper]], type[BaseSiteScraper]]:
    def decorator(cls: type[BaseSiteScraper]) -> type[BaseSiteScraper]:
        _SCRAPERS[kind] = cls
        return cls

    return decorator


def get_scraper(kind: str) -> type[BaseSiteScraper]:
    _ensure_builtins_loaded()

    if kind not in _SCRAPERS:
        raise KeyError(f"No scraper registered for kind={kind!r}. Registered: {sorted(_SCRAPERS)}")
    return _SCRAPERS[kind]


def create_scraper(
    *,
    site: SiteConfig,
    api_key: str | None,
    task_id: str,
    proxies: list[str] | None = None,
    http_client: ResilientHttpClient | None = None,
) -> BaseSiteScraper:
    scraper_cls = get_scraper(site.kind)
    return scraper_cls(
        site=site,
        api_key=api_key,
        task_id=task_id,
        proxies=proxies,
        http_client=http_client,
    )
