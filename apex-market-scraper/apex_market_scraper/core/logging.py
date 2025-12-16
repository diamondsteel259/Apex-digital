from __future__ import annotations

import logging
import os
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)s | %(name)s | site=%(site)s task=%(task_id)s | %(message)s"
)


class _DefaultContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if not hasattr(record, "site"):
            record.site = "-"  # type: ignore[attr-defined]
        if not hasattr(record, "task_id"):
            record.task_id = "-"  # type: ignore[attr-defined]
        return True


def get_logger(name: str, *, site: str, task_id: str) -> logging.LoggerAdapter[logging.Logger]:
    return logging.LoggerAdapter(logging.getLogger(name), {"site": site, "task_id": task_id})


def setup_logging(level: str | None = None) -> None:
    resolved_level = (level or os.getenv("AMSCRAPER_LOG_LEVEL") or "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format=DEFAULT_LOG_FORMAT,
    )

    logging.getLogger().addFilter(_DefaultContextFilter())

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
