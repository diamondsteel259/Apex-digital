from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from apex_market_scraper.config.models import AppConfig


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AMSCRAPER_", env_file=".env", extra="ignore")

    config_path: Path | None = None
    log_level: str | None = None
    output_dir: Path | None = None
    cadence_hours: int | None = None

    proxies: str | None = None
    proxies_file: Path | None = None

    def resolved_proxies(self) -> list[str]:
        if self.proxies:
            return [p.strip() for p in self.proxies.split(",") if p.strip()]
        if self.proxies_file and self.proxies_file.exists():
            return [
                line.strip()
                for line in self.proxies_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        return []


def _load_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as e:  # pragma: no cover
            raise RuntimeError("PyYAML is required to load .yaml/.yml configs") from e

        return yaml.safe_load(text) or {}
    if suffix == ".json":
        return json.loads(text)

    raise ValueError(f"Unsupported config format: {suffix}. Use .yaml/.yml or .json")


def load_app_config(config_path: Path, settings: RuntimeSettings | None = None) -> AppConfig:
    raw = _load_raw_config(config_path)

    try:
        app_config = AppConfig.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid config: {config_path}\n{e}") from e

    if settings:
        if settings.output_dir is not None:
            app_config.export.output_dir = settings.output_dir
        if settings.cadence_hours is not None:
            app_config.scheduler.cadence_hours = settings.cadence_hours

    return app_config


def resolve_config_path(cli_path: str | None) -> Path:
    settings = RuntimeSettings()

    if cli_path:
        return Path(cli_path)

    if settings.config_path is not None:
        return settings.config_path

    return Path("configs/example.json")


def get_site_api_key(env_var_name: str | None) -> str | None:
    if not env_var_name:
        return None
    return os.getenv(env_var_name)
