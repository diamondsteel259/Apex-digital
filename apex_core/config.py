"""Configuration management for Apex Core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

CONFIG_PATH = Path("config.json")


@dataclass(frozen=True)
class OperatingHours:
    start_hour_utc: int
    end_hour_utc: int


@dataclass(frozen=True)
class PaymentMethod:
    name: str
    instructions: str
    emoji: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class VipTier:
    name: str
    min_spend_cents: int
    discount_percent: float


@dataclass(frozen=True)
class LoggingChannels:
    audit: int
    payments: int
    tickets: int
    errors: int
    order_logs: int | None = None
    transcript_archive: int | None = None


@dataclass(frozen=True)
class RoleIDs:
    admin: int
    vip_tier1: int
    vip_tier2: int
    vip_tier3: int


@dataclass(frozen=True)
class TicketCategories:
    support: int
    billing: int
    sales: int


@dataclass(frozen=True)
class Config:
    token: str
    guild_ids: list[int]
    role_ids: RoleIDs
    ticket_categories: TicketCategories
    operating_hours: OperatingHours
    payment_methods: list[PaymentMethod]
    vip_thresholds: list[VipTier]
    logging_channels: LoggingChannels
    bot_prefix: str = "!"


def _coerce_hour(value: Any, *, field_name: str) -> int:
    hour = int(value)
    if not 0 <= hour <= 23:
        raise ValueError(f"{field_name} must be between 0 and 23 (got {value!r})")
    return hour


def _parse_operating_hours(payload: dict[str, Any]) -> OperatingHours:
    return OperatingHours(
        start_hour_utc=_coerce_hour(payload["start_hour_utc"], field_name="start_hour_utc"),
        end_hour_utc=_coerce_hour(payload["end_hour_utc"], field_name="end_hour_utc"),
    )


def _parse_payment_methods(payload: Iterable[dict[str, Any]]) -> list[PaymentMethod]:
    methods: list[PaymentMethod] = []
    for item in payload:
        methods.append(
            PaymentMethod(
                name=item["name"],
                instructions=item["instructions"],
                emoji=item.get("emoji"),
                metadata=item.get("metadata", {}),
            )
        )
    return methods


def _parse_vip_thresholds(payload: Iterable[dict[str, Any]]) -> list[VipTier]:
    tiers: list[VipTier] = []
    for item in payload:
        tiers.append(
            VipTier(
                name=item["name"],
                min_spend_cents=int(item["min_spend_cents"]),
                discount_percent=float(item["discount_percent"]),
            )
        )
    return tiers


def load_config(config_path: str | Path = CONFIG_PATH) -> Config:
    """Load and parse configuration from JSON file."""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            "Please copy config.example.json to config.json and fill in your values."
        )

    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)

    return Config(
        token=data["token"],
        guild_ids=[int(gid) for gid in data["guild_ids"]],
        role_ids=RoleIDs(**data["role_ids"]),
        ticket_categories=TicketCategories(**data["ticket_categories"]),
        operating_hours=_parse_operating_hours(data["operating_hours"]),
        payment_methods=_parse_payment_methods(data.get("payment_methods", [])),
        vip_thresholds=_parse_vip_thresholds(data.get("vip_thresholds", [])),
        logging_channels=LoggingChannels(**data["logging_channels"]),
        bot_prefix=data.get("bot_prefix", "!"),
    )
