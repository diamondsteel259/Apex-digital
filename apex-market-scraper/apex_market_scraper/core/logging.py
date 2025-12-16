from __future__ import annotations

import logging
import os
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: str | None = None) -> None:
    resolved_level = (level or os.getenv("AMSCRAPER_LOG_LEVEL") or "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format=DEFAULT_LOG_FORMAT,
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
