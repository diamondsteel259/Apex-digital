"""Configuration management for Apex Core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

CONFIG_PATH = Path("config.json")
PAYMENTS_CONFIG_PATH = Path("config/payments.json")

VALID_ASSIGNMENT_MODES = {
    "automatic_spend",
    "automatic_first_purchase",
    "automatic_all_ranks",
    "manual",
}


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
class ReferralSettings:
    cashback_percent: float


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
    wallet: int | None = None
    tips: int | None = None
    airdrops: int | None = None
    ai_support: int | None = None


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
    apex_staff: int | None = None
    apex_client: int | None = None
    apex_insider: int | None = None
    client: int | None = None
    apex_vip: int | None = None
    apex_elite: int | None = None
    apex_legend: int | None = None
    apex_sovereign: int | None = None
    apex_donor: int | None = None
    legendary_donor: int | None = None
    apex_zenith: int | None = None
    ai_free: int | None = None
    ai_premium: int | None = None
    ai_ultra: int | None = None
    data: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TicketCategories:
    support: int
    billing: int
    sales: int


@dataclass(frozen=True)
class CategoryIDs:
    """Mapping of category names to Discord category IDs."""
    data: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelIDs:
    """Mapping of channel names to Discord channel IDs."""
    data: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SetupSettings:
    """Settings for the setup wizard."""
    session_timeout_minutes: int = 30
    default_mode: str = "modern"  # "modern" (slash) or "legacy" (modal)


@dataclass
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
    referral_settings: ReferralSettings | None = None
    rate_limits: dict[str, RateLimitRule] = field(default_factory=dict)
    financial_cooldowns: dict[str, int] = field(default_factory=dict)
    roles: list[Role] = field(default_factory=list)
    vip_thresholds: list[VipTier] = field(default_factory=list)
    bot_prefix: str = "!"
    category_ids: CategoryIDs = field(default_factory=CategoryIDs)
    channel_ids: ChannelIDs = field(default_factory=ChannelIDs)
    setup_settings: SetupSettings = field(default_factory=SetupSettings)


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
        name = str(item.get("name", "Unknown Role"))
        
        # Validate assignment_mode
        assignment_mode = item.get("assignment_mode")
        if assignment_mode not in VALID_ASSIGNMENT_MODES:
            raise ValueError(
                f"Role '{name}': assignment_mode must be one of {sorted(VALID_ASSIGNMENT_MODES)} "
                f"(got {assignment_mode!r})"
            )

        # Validate role_id
        try:
            role_id = int(item["role_id"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Role '{name}': role_id must be an integer (got {item.get('role_id')!r})") from exc
        
        if role_id <= 0:
            raise ValueError(f"Role '{name}': role_id must be a positive integer (got {role_id})")

        # Validate discount_percent
        try:
            discount_percent = float(item["discount_percent"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Role '{name}': discount_percent must be a number (got {item.get('discount_percent')!r})") from exc
            
        if not 0 <= discount_percent <= 100:
            raise ValueError(f"Role '{name}': discount_percent must be between 0 and 100 (got {discount_percent})")

        # Validate tier_priority
        try:
            tier_priority = int(item.get("tier_priority", 0))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Role '{name}': tier_priority must be an integer (got {item.get('tier_priority')!r})") from exc
            
        if tier_priority < 0:
            raise ValueError(f"Role '{name}': tier_priority must be non-negative (got {tier_priority})")

        roles.append(
            Role(
                name=item["name"],
                role_id=role_id,
                assignment_mode=assignment_mode,
                unlock_condition=item["unlock_condition"] if isinstance(item["unlock_condition"], str) else int(item["unlock_condition"]),
                discount_percent=discount_percent,
                benefits=item.get("benefits", []),
                tier_priority=tier_priority,
            )
        )
    return roles


def _parse_refund_settings(payload: dict[str, Any] | None) -> RefundSettings | None:
    """Parse refund settings from config payload."""
    if not payload:
        return None

    # Validate enabled flag
    enabled = bool(payload.get("enabled", True))

    # Validate max_days
    raw_max_days = payload.get("max_days", 3)
    try:
        max_days = int(raw_max_days)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"refund_settings.max_days must be an integer (got {raw_max_days!r})") from exc

    if not 0 <= max_days <= 365:
        raise ValueError(f"refund_settings.max_days must be between 0 and 365 (got {max_days})")

    # Validate handling_fee_percent
    raw_fee = payload.get("handling_fee_percent", 10.0)
    try:
        handling_fee_percent = float(raw_fee)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"refund_settings.handling_fee_percent must be a number (got {raw_fee!r})") from exc

    if not 0 <= handling_fee_percent <= 100:
        raise ValueError(f"refund_settings.handling_fee_percent must be between 0 and 100 (got {handling_fee_percent})")

    return RefundSettings(
        enabled=enabled,
        max_days=max_days,
        handling_fee_percent=handling_fee_percent,
    )


def _parse_referral_settings(payload: dict[str, Any] | None) -> ReferralSettings | None:
    """Parse referral settings from config payload."""
    if not payload:
        return None

    # Validate cashback_percent
    raw_cashback = payload.get("cashback_percent", 0.5)
    try:
        cashback_percent = float(raw_cashback)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"referral_settings.cashback_percent must be a number (got {raw_cashback!r})") from exc

    if not 0 <= cashback_percent <= 100:
        raise ValueError(f"referral_settings.cashback_percent must be between 0 and 100 (got {cashback_percent})")

    return ReferralSettings(cashback_percent=cashback_percent)


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


def _parse_category_ids(payload: dict[str, Any] | None) -> CategoryIDs:
    """Parse category IDs mapping from configuration."""
    if not payload:
        return CategoryIDs(data={})
    if not isinstance(payload, dict):
        raise ValueError("category_ids must be an object mapping category names to IDs")
    
    data: dict[str, int] = {}
    for key, value in payload.items():
        try:
            data[key] = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"category_ids entry for '{key}' must be an integer ID") from exc
    
    return CategoryIDs(data=data)


def _parse_channel_ids(payload: dict[str, Any] | None) -> ChannelIDs:
    """Parse channel IDs mapping from configuration."""
    if not payload:
        return ChannelIDs(data={})
    if not isinstance(payload, dict):
        raise ValueError("channel_ids must be an object mapping channel names to IDs")
    
    data: dict[str, int] = {}
    for key, value in payload.items():
        try:
            data[key] = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"channel_ids entry for '{key}' must be an integer ID") from exc
    
    return ChannelIDs(data=data)


def _parse_setup_settings(payload: dict[str, Any] | None) -> SetupSettings:
    """Parse setup settings from configuration."""
    if not payload:
        return SetupSettings()
    
    if not isinstance(payload, dict):
        raise ValueError("setup_settings must be an object")
    
    session_timeout_minutes = payload.get("session_timeout_minutes", 30)
    try:
        session_timeout_minutes = int(session_timeout_minutes)
        if session_timeout_minutes <= 0:
            raise ValueError("session_timeout_minutes must be positive")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"setup_settings.session_timeout_minutes must be a positive integer") from exc
    
    default_mode = payload.get("default_mode", "modern")
    if default_mode not in ("modern", "legacy"):
        raise ValueError(f"setup_settings.default_mode must be 'modern' or 'legacy' (got {default_mode!r})")
    
    return SetupSettings(
        session_timeout_minutes=session_timeout_minutes,
        default_mode=default_mode
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
        referral_settings=_parse_referral_settings(data.get("referral_settings")),
        rate_limits=_parse_rate_limits(data.get("rate_limits")),
        financial_cooldowns=_parse_financial_cooldowns(data.get("financial_cooldowns")),
        roles=_parse_roles(data.get("roles", [])),
        logging_channels=LoggingChannels(**data["logging_channels"]),
        bot_prefix=data.get("bot_prefix", "!"),
        category_ids=_parse_category_ids(data.get("category_ids")),
        channel_ids=_parse_channel_ids(data.get("channel_ids")),
        setup_settings=_parse_setup_settings(data.get("setup_settings")),
    )
