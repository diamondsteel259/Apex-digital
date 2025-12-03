"""Configuration management for Apex Core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

CONFIG_PATH = Path("config.json")
PAYMENTS_CONFIG_PATH = Path("config/payments.json")


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
class PaymentSettings:
    payment_methods: list[PaymentMethod]
    order_confirmation_template: str
    refund_policy: str


@dataclass(frozen=True)
class RefundSettings:
    enabled: bool
    max_days: int
    handling_fee_percent: float


@dataclass(frozen=True)
class RateLimitRule:
    cooldown: int
    max_uses: int
    per: str


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
class Role:
    name: str
    role_id: int
    assignment_mode: str
    unlock_condition: int | str
    discount_percent: float
    benefits: list[str] = field(default_factory=list)
    tier_priority: int = 0


@dataclass(frozen=True)
class RoleIDs:
    admin: int


@dataclass(frozen=True)
class TicketCategories:
    support: int
    billing: int
    sales: int


@dataclass(frozen=True)
class CacheSettings:
    enabled: bool
    max_size_mb: int
    ttl_config: int
    ttl_reference: int
    ttl_user: int
    ttl_query: int
    cleanup_interval: int


@dataclass(frozen=True)
class Config:
    token: str
    guild_ids: list[int]
    role_ids: RoleIDs
    ticket_categories: TicketCategories
    operating_hours: OperatingHours
    payment_methods: list[PaymentMethod]
    logging_channels: LoggingChannels
    payment_settings: PaymentSettings | None = None
    refund_settings: RefundSettings | None = None
    rate_limits: dict[str, RateLimitRule] = field(default_factory=dict)
    financial_cooldowns: dict[str, int] = field(default_factory=dict)
    roles: list[Role] = field(default_factory=list)
    vip_thresholds: list[VipTier] = field(default_factory=list)
    bot_prefix: str = "!"
    cache_settings: CacheSettings | None = None


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
        metadata = dict(item.get("metadata", {}))
        if "is_enabled" not in metadata and "is_enabled" in item:
            metadata["is_enabled"] = item["is_enabled"]
        
        methods.append(
            PaymentMethod(
                name=item["name"],
                instructions=item["instructions"],
                emoji=item.get("emoji"),
                metadata=metadata,
            )
        )
    return methods


def _parse_roles(payload: Iterable[dict[str, Any]]) -> list[Role]:
    roles: list[Role] = []
    for item in payload:
        roles.append(
            Role(
                name=item["name"],
                role_id=int(item["role_id"]),
                assignment_mode=item["assignment_mode"],
                unlock_condition=item["unlock_condition"] if isinstance(item["unlock_condition"], str) else int(item["unlock_condition"]),
                discount_percent=float(item["discount_percent"]),
                benefits=item.get("benefits", []),
                tier_priority=int(item.get("tier_priority", 0)),
            )
        )
    return roles


def _parse_refund_settings(payload: dict[str, Any] | None) -> RefundSettings | None:
    """Parse refund settings from config payload."""
    if not payload:
        return None
    
    return RefundSettings(
        enabled=bool(payload.get("enabled", True)),
        max_days=int(payload.get("max_days", 3)),
        handling_fee_percent=float(payload.get("handling_fee_percent", 10.0)),
    )


def _parse_rate_limits(payload: dict[str, Any] | None) -> dict[str, RateLimitRule]:
    """Parse rate limit definitions from configuration."""
    if not payload:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("rate_limits must be an object mapping command keys to settings")

    limits: dict[str, RateLimitRule] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            raise ValueError(f"rate_limits entry for '{key}' must be an object")
        try:
            cooldown = int(value["cooldown"])
            max_uses = int(value["max_uses"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"rate_limits entry for '{key}' must include integer cooldown and max_uses") from exc
        per = str(value.get("per", "user")).lower()
        limits[key] = RateLimitRule(cooldown=cooldown, max_uses=max_uses, per=per)
    return limits


def _parse_financial_cooldowns(payload: dict[str, Any] | None) -> dict[str, int]:
    """Parse financial cooldown definitions from configuration."""
    if not payload:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("financial_cooldowns must be an object mapping command keys to cooldown seconds")

    cooldowns: dict[str, int] = {}
    for key, value in payload.items():
        try:
            cooldown_seconds = int(value)
            if cooldown_seconds < 0:
                raise ValueError(f"financial_cooldowns entry for '{key}' must be non-negative")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"financial_cooldowns entry for '{key}' must be an integer number of seconds") from exc
        cooldowns[key] = cooldown_seconds
    return cooldowns


def _parse_cache_settings(payload: dict[str, Any] | None) -> CacheSettings | None:
    """Parse cache settings from config payload."""
    if not payload:
        return None
    
    return CacheSettings(
        enabled=bool(payload.get("enabled", True)),
        max_size_mb=int(payload.get("max_size_mb", 100)),
        ttl_config=int(payload.get("ttl_config", 86400)),  # 24 hours
        ttl_reference=int(payload.get("ttl_reference", 43200)),  # 12 hours
        ttl_user=int(payload.get("ttl_user", 3600)),  # 1 hour
        ttl_query=int(payload.get("ttl_query", 1800)),  # 30 minutes
        cleanup_interval=int(payload.get("cleanup_interval", 3600)),  # 1 hour
    )


def _validate_order_confirmation_template(template: str) -> None:
    """Validate that the order confirmation template contains required placeholders."""
    required_placeholders = {"{order_id}", "{service_name}", "{variant_name}", "{price}", "{eta}"}
    
    # Check if each required placeholder is present in the template
    missing_placeholders = []
    for placeholder in required_placeholders:
        if placeholder not in template:
            missing_placeholders.append(placeholder)
    
    if missing_placeholders:
        raise ValueError(
            f"Order confirmation template missing required placeholders: {', '.join(sorted(missing_placeholders))}"
        )


def load_payment_settings(config_path: str | Path = PAYMENTS_CONFIG_PATH) -> PaymentSettings:
    """Load and parse payment settings from JSON file."""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(
            f"Payments configuration file not found: {path}\n"
            "Please ensure config/payments.json exists with the required structure."
        )
    
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    
    # Validate required fields
    if "payment_methods" not in data:
        raise ValueError("payment_methods field is required in payments configuration")
    if "order_confirmation_template" not in data:
        raise ValueError("order_confirmation_template field is required in payments configuration")
    if "refund_policy" not in data:
        raise ValueError("refund_policy field is required in payments configuration")
    
    # Validate template placeholders
    _validate_order_confirmation_template(data["order_confirmation_template"])
    
    return PaymentSettings(
        payment_methods=_parse_payment_methods(data["payment_methods"]),
        order_confirmation_template=data["order_confirmation_template"],
        refund_policy=data["refund_policy"],
    )


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

    # Try to load payment settings, fall back to None if file doesn't exist
    payment_settings = None
    try:
        payment_settings = load_payment_settings()
    except FileNotFoundError:
        # Payments config is optional, fall back to legacy inline payment methods
        pass
    except Exception as e:
        # Log error but don't fail startup - payments config should be validated separately
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Failed to load payments configuration: %s", e)

    return Config(
        token=data["token"],
        guild_ids=[int(gid) for gid in data["guild_ids"]],
        role_ids=RoleIDs(**data["role_ids"]),
        ticket_categories=TicketCategories(**data["ticket_categories"]),
        operating_hours=_parse_operating_hours(data["operating_hours"]),
        payment_methods=_parse_payment_methods(data.get("payment_methods", [])),
        payment_settings=payment_settings,
        refund_settings=_parse_refund_settings(data.get("refund_settings")),
        rate_limits=_parse_rate_limits(data.get("rate_limits")),
        financial_cooldowns=_parse_financial_cooldowns(data.get("financial_cooldowns")),
        roles=_parse_roles(data.get("roles", [])),
        logging_channels=LoggingChannels(**data["logging_channels"]),
        bot_prefix=data.get("bot_prefix", "!"),
        cache_settings=_parse_cache_settings(data.get("cache")),
    )
