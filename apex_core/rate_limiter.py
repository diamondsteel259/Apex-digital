"""Rate limiting utilities for protecting sensitive commands."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Literal, Optional, TypeVar

import discord
from discord.ext import commands

from apex_core.config import RateLimitRule
from apex_core.constants import (
    RATE_LIMIT_ALERT_COOLDOWN_SECONDS,
    RATE_LIMIT_ALERT_THRESHOLD,
    RATE_LIMIT_ALERT_WINDOW_SECONDS,
)
from apex_core.logger import get_logger
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()

F = TypeVar("F", bound=Callable[..., Any])
RateLimitScope = Literal["user", "channel", "guild"]


@dataclass(frozen=True)
class RateLimitSettings:
    """Normalized settings applied to a rate limited command."""

    key: str
    cooldown: int
    max_uses: int
    scope: RateLimitScope


class RateLimitBucket:
    """Tracks command usage for a specific entity (user/channel/guild)."""

    __slots__ = ("cooldown", "max_uses", "timestamps", "lock")

    def __init__(self, cooldown: int, max_uses: int) -> None:
        self.cooldown = cooldown
        self.max_uses = max_uses
        self.timestamps: deque[float] = deque()
        self.lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        cooldown = self.cooldown
        timestamps = self.timestamps
        while timestamps and (now - timestamps[0]) >= cooldown:
            timestamps.popleft()

    async def acquire(self) -> tuple[bool, int, int]:
        """
        Attempt to consume a rate limit token.

        Returns:
            allowed: Whether execution may continue
            retry_after: Seconds before the next available token (0 if allowed)
            remaining_uses: Remaining uses within the current window
        """
        async with self.lock:
            now = time.monotonic()
            self._prune(now)

            if len(self.timestamps) >= self.max_uses:
                oldest = self.timestamps[0]
                retry_after = math.ceil(self.cooldown - (now - oldest))
                return False, max(retry_after, 1), 0

            self.timestamps.append(now)
            remaining = max(0, self.max_uses - len(self.timestamps))
            return True, 0, remaining


class RateLimiter:
    """Global, in-memory rate limiter shared across commands."""

    def __init__(self) -> None:
        self._buckets: dict[str, RateLimitBucket] = {}
        self._violation_history: dict[tuple[int, str], deque[float]] = {}
        self._violation_lock = asyncio.Lock()
        self.alert_threshold = RATE_LIMIT_ALERT_THRESHOLD
        self.alert_window = RATE_LIMIT_ALERT_WINDOW_SECONDS
        self.alert_cooldown = RATE_LIMIT_ALERT_COOLDOWN_SECONDS
        self._last_alert: dict[tuple[int, str], float] = {}

    def _bucket_key(self, command_key: str, scope: RateLimitScope, identifier: int) -> str:
        return f"{command_key}:{scope}:{identifier}"

    def _get_bucket(self, key: str, cooldown: int, max_uses: int) -> RateLimitBucket:
        bucket = self._buckets.get(key)
        if bucket is None or bucket.cooldown != cooldown or bucket.max_uses != max_uses:
            bucket = RateLimitBucket(cooldown, max_uses)
            self._buckets[key] = bucket
        return bucket

    async def try_acquire(
        self,
        command_key: str,
        scope: RateLimitScope,
        identifier: int,
        cooldown: int,
        max_uses: int,
    ) -> tuple[bool, int, int]:
        """Attempt to use a rate limited operation."""
        bucket_key = self._bucket_key(command_key, scope, identifier)
        bucket = self._get_bucket(bucket_key, cooldown, max_uses)
        return await bucket.acquire()

    async def record_violation(self, user_id: int, command_key: str) -> tuple[int, bool]:
        """
        Record a violation and determine if it should trigger an alert.

        Returns:
            (violation_count, alert_staff)
        """
        key = (user_id, command_key)
        now = time.monotonic()
        async with self._violation_lock:
            history = self._violation_history.setdefault(key, deque())
            history.append(now)
            while history and (now - history[0]) > self.alert_window:
                history.popleft()

            alert = (
                len(history) >= self.alert_threshold
                and (key not in self._last_alert or (now - self._last_alert[key]) > self.alert_cooldown)
            )
            if alert:
                self._last_alert[key] = now
            return len(history), alert


_RATE_LIMITER = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Expose the singleton rate limiter."""
    return _RATE_LIMITER


def _normalize_scope(scope: str | RateLimitScope) -> RateLimitScope:
    value = str(scope).lower()
    if value not in {"user", "channel", "guild"}:
        return "user"
    return value  # type: ignore[return-value]


def _resolve_settings(
    bot: commands.Bot | None,
    fallback_key: str,
    default_cooldown: int,
    default_max_uses: int,
    default_scope: RateLimitScope,
    config_key: str | None,
) -> RateLimitSettings:
    key = config_key or fallback_key
    if bot and getattr(bot, "config", None):
        config = bot.config
        config_limits = getattr(config, "rate_limits", None)
        if config_limits and key in config_limits:
            rule: RateLimitRule = config_limits[key]
            return RateLimitSettings(
                key=key,
                cooldown=int(rule.cooldown),
                max_uses=int(rule.max_uses),
                scope=_normalize_scope(rule.per),
            )
    return RateLimitSettings(
        key=key,
        cooldown=int(default_cooldown),
        max_uses=int(default_max_uses),
        scope=default_scope,
    )


def _build_violation_message(remaining_seconds: int, remaining_uses: int, settings: RateLimitSettings) -> str:
    if remaining_seconds >= 3600:
        time_str = f"{remaining_seconds // 3600}h {(remaining_seconds % 3600) // 60}m"
    elif remaining_seconds >= 60:
        time_str = f"{remaining_seconds // 60}m {remaining_seconds % 60}s"
    else:
        time_str = f"{remaining_seconds}s"

    attempts_text = max(0, remaining_uses)

    return (
        "⏱️ Please wait {time} before using this command again.\n"
        "You can use this command {attempts} more times in the current window."
    ).format(time=time_str, attempts=attempts_text)


def _get_scope_identifier(
    scope: RateLimitScope,
    user: discord.abc.User,
    channel: discord.abc.GuildChannel | discord.Thread | discord.DMChannel | None,
    guild: discord.Guild | None,
) -> int:
    if scope == "user":
        return user.id
    if scope == "channel" and channel is not None:
        return channel.id  # type: ignore[attr-defined]
    if scope == "guild" and guild is not None:
        return guild.id
    # Fallback to user scope if channel/guild isn't available
    return user.id


async def _send_audit_log(
    *,
    bot: commands.Bot | None,
    guild: Optional[discord.Guild],
    title: str,
    description: str,
    color: discord.Color,
) -> None:
    if not bot or not guild or not getattr(bot, "config", None):
        return

    audit_channel_id = getattr(bot.config.logging_channels, "audit", None)
    if not audit_channel_id:
        return

    channel = guild.get_channel(audit_channel_id)
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("Failed to send audit log: %s", exc)


def rate_limit(
    *,
    cooldown: int,
    max_uses: int,
    per: RateLimitScope = "user",
    config_key: str | None = None,
    admin_bypass: bool = True,
) -> Callable[[F], F]:
    """Decorator applied to Discord commands to enforce rate limits."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not args:
                return await func(*args, **kwargs)

            self_obj = args[0]
            bot = getattr(self_obj, "bot", None)

            interaction: Optional[discord.Interaction] = None
            ctx: Optional[commands.Context] = None

            if len(args) > 1:
                potential = args[1]
                if isinstance(potential, discord.Interaction):
                    interaction = potential
                elif isinstance(potential, commands.Context):
                    ctx = potential

            # Determine execution context
            if interaction:
                user = interaction.user
                guild = interaction.guild
                channel = interaction.channel
            elif ctx:
                user = ctx.author
                guild = ctx.guild
                channel = ctx.channel
            else:
                return await func(*args, **kwargs)

            settings = _resolve_settings(
                bot=bot,
                fallback_key=func.__name__,
                default_cooldown=cooldown,
                default_max_uses=max_uses,
                default_scope=_normalize_scope(per),
                config_key=config_key,
            )

            identifier = _get_scope_identifier(settings.scope, user, channel, guild)

            if admin_bypass and is_admin_from_bot(user, guild, bot):
                logger.info("Admin %s bypassed rate limit for %s (scope=%s, id=%s)", user.id, settings.key, settings.scope, identifier)
                await _send_audit_log(
                    bot=bot,
                    guild=guild,
                    title="🔓 Rate Limit Bypass",
                    description=(
                        f"**Admin:** {user.mention} ({user.id})\n"
                        f"**Command:** `{settings.key}`\n"
                        "**Reason:** Admin privilege"
                    ),
                    color=discord.Color.blue(),
                )
                return await func(*args, **kwargs)

            identifier = _get_scope_identifier(settings.scope, user, channel, guild)
            limiter = get_rate_limiter()
            allowed, retry_after, remaining = await limiter.try_acquire(
                command_key=settings.key,
                scope=settings.scope,
                identifier=identifier,
                cooldown=settings.cooldown,
                max_uses=settings.max_uses,
            )

            if not allowed:
                logger.warning(
                    "Rate limit triggered | command=%s user=%s scope=%s id=%s",
                    settings.key,
                    user.id,
                    settings.scope,
                    identifier,
                )
                violation_count, alert_staff = await limiter.record_violation(user.id, settings.key)
                message = _build_violation_message(retry_after, remaining, settings)

                # Respond to user
                if interaction:
                    if interaction.response.is_done():
                        await interaction.followup.send(message, ephemeral=True)
                    else:
                        await interaction.response.send_message(message, ephemeral=True)
                elif ctx:
                    await ctx.send(message, delete_after=15)

                if alert_staff:
                    await _send_audit_log(
                        bot=bot,
                        guild=guild,
                        title="⚠️ Rate Limit Violations",
                        description=(
                            f"**User:** {user.mention} ({user.id})\n"
                            f"**Command:** `{settings.key}`\n"
                            f"**Violations (5m window):** {violation_count}\n"
                            f"**Scope:** {settings.scope}\n"
                            f"**Limit:** {settings.max_uses} per {settings.cooldown}s"
                        ),
                        color=discord.Color.orange(),
                    )

                return None

            # Allowed - continue
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


async def enforce_interaction_rate_limit(
    interaction: discord.Interaction,
    *,
    command_key: str,
    cooldown: int,
    max_uses: int,
    per: RateLimitScope = "user",
    config_key: str | None = None,
    admin_bypass: bool = True,
) -> bool:
    """Apply rate limiting logic to arbitrary interaction callbacks (e.g., buttons)."""

    bot = interaction.client if isinstance(interaction.client, commands.Bot) else None
    settings = _resolve_settings(
        bot=bot,
        fallback_key=command_key,
        default_cooldown=cooldown,
        default_max_uses=max_uses,
        default_scope=_normalize_scope(per),
        config_key=config_key or command_key,
    )

    guild = interaction.guild
    channel = interaction.channel
    user = interaction.user

    identifier = _get_scope_identifier(settings.scope, user, channel, guild)

    if admin_bypass and is_admin_from_bot(user, guild, bot):
        logger.info("Admin %s bypassed rate limit for %s (scope=%s, id=%s)", user.id, settings.key, settings.scope, identifier)
        await _send_audit_log(
            bot=bot,
            guild=guild,
            title="🔓 Rate Limit Bypass",
            description=(
                f"**Admin:** {user.mention} ({user.id})\n"
                f"**Command:** `{settings.key}`\n"
                "**Reason:** Admin privilege"
            ),
            color=discord.Color.blue(),
        )
        return True

    identifier = _get_scope_identifier(settings.scope, user, channel, guild)
    limiter = get_rate_limiter()
    allowed, retry_after, remaining = await limiter.try_acquire(
        command_key=settings.key,
        scope=settings.scope,
        identifier=identifier,
        cooldown=settings.cooldown,
        max_uses=settings.max_uses,
    )

    if allowed:
        return True

    logger.warning(
        "Rate limit triggered | command=%s user=%s scope=%s id=%s",
        settings.key,
        user.id,
        settings.scope,
        identifier,
    )
    violation_count, alert_staff = await limiter.record_violation(user.id, settings.key)
    message = _build_violation_message(retry_after, remaining, settings)

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

    if alert_staff:
        await _send_audit_log(
            bot=bot,
            guild=guild,
            title="⚠️ Rate Limit Violations",
            description=(
                f"**User:** {user.mention} ({user.id})\n"
                f"**Command:** `{settings.key}`\n"
                f"**Violations (5m window):** {violation_count}\n"
                f"**Scope:** {settings.scope}\n"
                f"**Limit:** {settings.max_uses} per {settings.cooldown}s"
            ),
            color=discord.Color.orange(),
        )

    return False
