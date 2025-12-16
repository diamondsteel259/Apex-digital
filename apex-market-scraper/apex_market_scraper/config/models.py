from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExportFormat = Literal["csv", "xlsx"]


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    cadence_hours: int = Field(
        ..., description="How often to run a scrape+export cycle (12–24 hours inclusive)."
    )

    @field_validator("cadence_hours")
    @classmethod
    def _validate_cadence(cls, v: int) -> int:
        if not 12 <= v <= 24:
            raise ValueError("cadence_hours must be within 12..24")
        return v


class ExportConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    output_dir: Path = Field(Path("out"), description="Local output directory.")
    formats: list[ExportFormat] = Field(default_factory=lambda: ["csv"])
    apex_bot_drop_dir: Path | None = Field(
        default=None,
        description=(
            "Optional directory where the Apex bot can ingest exported files. "
            "If set, exports are also copied here."
        ),
    )
    dataset_name: str = Field("market_listings", description="Base filename for exports.")


class SiteConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    name: str
    kind: str
    enabled: bool = True
    api_key_env: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    scheduler: SchedulerConfig
    export: ExportConfig
    sites: list[SiteConfig] = Field(default_factory=list)
