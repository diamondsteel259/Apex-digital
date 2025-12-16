from __future__ import annotations

from collections.abc import Callable

from apex_market_scraper.sites.base import BaseSiteScraper

ScraperFactory = Callable[..., BaseSiteScraper]

_SCRAPERS: dict[str, type[BaseSiteScraper]] = {}


def register(kind: str) -> Callable[[type[BaseSiteScraper]], type[BaseSiteScraper]]:
    def decorator(cls: type[BaseSiteScraper]) -> type[BaseSiteScraper]:
        _SCRAPERS[kind] = cls
        return cls

    return decorator


def get_scraper(kind: str) -> type[BaseSiteScraper]:
    if kind not in _SCRAPERS:
        raise KeyError(f"No scraper registered for kind={kind!r}. Registered: {sorted(_SCRAPERS)}")
    return _SCRAPERS[kind]
