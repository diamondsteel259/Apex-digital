from __future__ import annotations

from pathlib import Path

import pytest

from apex_market_scraper.config.loader import RuntimeSettings, load_app_config


def test_load_example_config() -> None:
    cfg = load_app_config(Path("configs/example.json"), settings=RuntimeSettings())

    assert cfg.scheduler.cadence_hours == 12
    assert cfg.export.dataset_name == "market_listings"
    assert cfg.sites


def test_cadence_env_override_is_validated() -> None:
    settings = RuntimeSettings(cadence_hours=24)
    cfg = load_app_config(Path("configs/example.json"), settings=settings)
    assert cfg.scheduler.cadence_hours == 24

    with pytest.raises(ValueError):
        settings = RuntimeSettings(cadence_hours=1)
        load_app_config(Path("configs/example.json"), settings=settings)
