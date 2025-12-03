"""Financial command cooldown management with enhanced user feedback."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Literal, Optional, TypeVar

import discord
from discord.ext import commands

from apex_core.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CooldownTier(Enum):
    """Cooldown tiers with different messaging styles."""
    ULTRA_SENSITIVE = "ultra_sensitive"
    SENSITIVE = "sensitive"
    STANDARD = "standard"


@dataclass(frozen=True)
class FinancialCooldownConfig:
    """Configuration for financial cooldowns."""
    seconds: int
    tier: CooldownTier
    operation_type: str


class FinancialCooldownManager:
    """Manages financial command cooldowns with enhanced feedback."""
    
    def __init__(self) -> None:
        self._cooldowns: dict[tuple[int, str], float] = {}  # (user_id, command) -> expiry_time
        self._lock = asyncio.Lock()
    
    def _get_config(self, command_key: str, bot: commands.Bot | None = None) -> FinancialCooldownConfig:
        """Get cooldown configuration for a specific command."""
        # Default configurations based on ticket requirements
        default_configs = {
            "wallet_payment": FinancialCooldownConfig(30, CooldownTier.ULTRA_SENSITIVE, "payment"),
            "submitrefund": FinancialCooldownConfig(300, CooldownTier.ULTRA_SENSITIVE, "refund"),
            "manual_complete": FinancialCooldownConfig(10, CooldownTier.ULTRA_SENSITIVE, "order"),
            "setref": FinancialCooldownConfig(86400, CooldownTier.SENSITIVE, "referral"),
            "refund_approve": FinancialCooldownConfig(5, CooldownTier.SENSITIVE, "staff"),
            "refund_reject": FinancialCooldownConfig(5, CooldownTier.SENSITIVE, "staff"),
            "balance": FinancialCooldownConfig(10, CooldownTier.STANDARD, "query"),
            "orders": FinancialCooldownConfig(30, CooldownTier.STANDARD, "query"),
            "invites": FinancialCooldownConfig(30, CooldownTier.STANDARD, "query"),
        }
        
        # Check if there's a custom config in the bot config
        if bot and hasattr(bot, 'config') and hasattr(bot.config, 'financial_cooldowns'):
            custom_configs = getattr(bot.config, 'financial_cooldowns', {})
            if command_key in custom_configs:
                custom_seconds = custom_configs[command_key]
                default_config = default_configs.get(command_key)
                if default_config:
                    return FinancialCooldownConfig(
                        custom_seconds, 
                        default_config.tier, 
                        default_config.operation_type
                    )
        
        return default_configs.get(command_key, FinancialCooldownConfig(60, CooldownTier.STANDARD, "unknown"))
    
    def _build_enhanced_message(self, config: FinancialCooldownConfig, remaining_seconds: int) -> str:
        """Build enhanced cooldown message based on tier."""
        if config.tier == CooldownTier.ULTRA_SENSITIVE:
            return (
                "⚠️ **Financial operation in progress**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Last used: Just now\n"
                f"Cooldown: {config.seconds} seconds\n"
                f"Ready in: {remaining_seconds} seconds ⏳\n\n"
                "💡 **Tip:** Financial operations have a cooldown to prevent accidental double-charges."
            )
        elif config.tier == CooldownTier.SENSITIVE:
            return f"⏱️ **Sensitive operation**\nYou can use this again in {remaining_seconds} seconds."
        else:  # STANDARD
            if remaining_seconds >= 60:
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
            else:
                time_str = f"{remaining_seconds}s"
            return f"Please wait {time_str} before checking again."
    
    async def check_cooldown(self, user_id: int, command_key: str) -> tuple[bool, int]:
        """
        Check if a user is on cooldown for a specific command.
        
        Returns:
            (is_on_cooldown, remaining_seconds)
        """
        async with self._lock:
            now = time.monotonic()
            key = (user_id, command_key)
            
            if key not in self._cooldowns:
                return False, 0
            
            expiry_time = self._cooldowns[key]
            if now >= expiry_time:
                # Cooldown expired, clean it up
                del self._cooldowns[key]
                return False, 0
            
            remaining = int(expiry_time - now)
            return True, remaining
    
    async def set_cooldown(self, user_id: int, command_key: str, seconds: int) -> None:
        """Set a cooldown for a user and command."""
        async with self._lock:
            now = time.monotonic()
            expiry_time = now + seconds
            self._cooldowns[(user_id, command_key)] = expiry_time
    
    async def reset_cooldown(self, user_id: int, command_key: str) -> bool:
        """Reset a specific cooldown. Returns True if cooldown existed and was reset."""
        async with self._lock:
            key = (user_id, command_key)
            if key in self._cooldowns:
                del self._cooldowns[key]
                return True
            return False
    
    async def get_all_user_cooldowns(self, user_id: int) -> dict[str, int]:
        """Get all active cooldowns for a user. Returns {command: remaining_seconds}."""
        async with self._lock:
            now = time.monotonic()
            result = {}
            
            for (uid, command), expiry_time in list(self._cooldowns.items()):
                if uid == user_id:
                    if now >= expiry_time:
                        # Clean up expired cooldown
                        del self._cooldowns[(uid, command)]
                    else:
                        remaining = int(expiry_time - now)
                        result[command] = remaining
            
            return result
    
    async def cleanup_expired(self) -> int:
        """Clean up all expired cooldowns. Returns count of cleaned up entries."""
        async with self._lock:
            now = time.monotonic()
            expired_keys = []
            
            for key, expiry_time in self._cooldowns.items():
                if now >= expiry_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cooldowns[key]
            
            return len(expired_keys)


# Global instance
_FINANCIAL_COOLDOWN_MANAGER = FinancialCooldownManager()


def get_financial_cooldown_manager() -> FinancialCooldownManager:
    """Get the global financial cooldown manager."""
    return _FINANCIAL_COOLDOWN_MANAGER


def _is_admin(user: discord.abc.User, guild: Optional[discord.Guild], bot: commands.Bot | None) -> bool:
    """Check if a user has admin privileges."""
    if not guild or not bot or not getattr(bot, "config", None):
        return False
    
    admin_role_id = getattr(bot.config.role_ids, "admin", None)
    if not admin_role_id:
        return False
    
    member = guild.get_member(user.id)
    if not member:
        return False
    
    return any(role.id == admin_role_id for role in getattr(member, "roles", []))


async def _send_audit_log(
    *,
    bot: commands.Bot | None,
    guild: Optional[discord.Guild],
    title: str,
    description: str,
    color: discord.Color,
) -> None:
    """Send a log message to the audit channel."""
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


def financial_cooldown(
    *,
    seconds: int | None = None,
    tier: CooldownTier | None = None,
    operation_type: str | None = None,
    admin_bypass: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for financial commands with enhanced cooldown feedback.
    
    Args:
        seconds: Override cooldown duration. If None, uses default config.
        tier: Override cooldown tier. If None, uses default config.
        operation_type: Override operation type. If None, uses default config.
        admin_bypass: Whether admins bypass cooldowns.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not args:
                return await func(*args, **kwargs)
            
            self_obj = args[0]
            bot = getattr(self_obj, "bot", None)
            
            # Extract Discord context
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
            elif ctx:
                user = ctx.author
                guild = ctx.guild
            else:
                return await func(*args, **kwargs)
            
            command_key = func.__name__
            manager = get_financial_cooldown_manager()
            
            # Get configuration
            config = manager._get_config(command_key, bot)
            
            # Override with decorator parameters if provided
            if seconds is not None:
                config = FinancialCooldownConfig(seconds, tier or config.tier, operation_type or config.operation_type)
            elif tier is not None:
                config = FinancialCooldownConfig(config.seconds, tier, operation_type or config.operation_type)
            elif operation_type is not None:
                config = FinancialCooldownConfig(config.seconds, config.tier, operation_type)
            
            # Check admin bypass
            if admin_bypass and _is_admin(user, guild, bot):
                logger.debug("Admin %s bypassed financial cooldown for %s", user.id, command_key)
                await _send_audit_log(
                    bot=bot,
                    guild=guild,
                    title="🔓 Financial Cooldown Bypass",
                    description=(
                        f"**Admin:** {user.mention} ({user.id})\n"
                        f"**Command:** `{command_key}`\n"
                        "**Reason:** Admin privilege"
                    ),
                    color=discord.Color.blue(),
                )
                return await func(*args, **kwargs)
            
            # Check cooldown
            is_on_cooldown, remaining = await manager.check_cooldown(user.id, command_key)
            
            if is_on_cooldown:
                logger.warning(
                    "Financial cooldown triggered | command=%s user=%s remaining=%ds",
                    command_key,
                    user.id,
                    remaining,
                )
                
                message = manager._build_enhanced_message(config, remaining)
                
                # Send user feedback
                if interaction:
                    if interaction.response.is_done():
                        await interaction.followup.send(message, ephemeral=True)
                    else:
                        await interaction.response.send_message(message, ephemeral=True)
                elif ctx:
                    await ctx.send(message, delete_after=15)
                
                # Log to audit for ultra-sensitive operations
                if config.tier == CooldownTier.ULTRA_SENSITIVE:
                    await _send_audit_log(
                        bot=bot,
                        guild=guild,
                        title="⚠️ Financial Cooldown Triggered",
                        description=(
                            f"**User:** {user.mention} ({user.id})\n"
                            f"**Command:** `{command_key}`\n"
                            f"**Operation Type:** {config.operation_type}\n"
                            f"**Cooldown:** {config.seconds}s\n"
                            f"**Remaining:** {remaining}s"
                        ),
                        color=discord.Color.orange(),
                    )
                
                return None
            
            # Execute the command
            try:
                result = await func(*args, **kwargs)
                
                # Only set cooldown if command succeeded
                await manager.set_cooldown(user.id, command_key, config.seconds)
                
                return result
                
            except Exception as exc:
                # Don't set cooldown if command failed
                logger.error(
                    "Financial command %s failed for user %s: %s",
                    command_key,
                    user.id,
                    exc,
                )
                raise
        
        return wrapper  # type: ignore[return-value]
    
    return decorator