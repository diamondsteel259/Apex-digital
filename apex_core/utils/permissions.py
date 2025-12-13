"""Permission checking utilities for role-based access control."""

from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from apex_core.config import Config


def is_admin(
    user: discord.abc.User,
    guild: Optional[discord.Guild],
    config: Config,
) -> bool:
    """
    Check if a user has admin privileges based on configured admin role.

    Args:
        user: Discord user to check
        guild: Guild context (None if in DMs)
        config: Bot configuration containing role IDs

    Returns:
        True if user has admin role, False otherwise

    Examples:
        >>> is_admin(interaction.user, interaction.guild, bot.config)
        True
    """
    if guild is None:
        return False

    admin_role_id = getattr(config.role_ids, "admin", None)
    if not admin_role_id:
        return False

    member = guild.get_member(user.id)
    if not member:
        return False

    return any(role.id == admin_role_id for role in getattr(member, "roles", []))


def is_admin_from_bot(
    user: discord.abc.User,
    guild: Optional[discord.Guild],
    bot: commands.Bot | None,
) -> bool:
    """
    Check if user is admin using bot instance (convenience wrapper).

    This is a convenience wrapper for cases where you have bot instance
    instead of config directly.

    Args:
        user: Discord user to check
        guild: Guild context
        bot: Bot instance with config attribute

    Returns:
        True if user has admin role, False otherwise
    """
    if not bot or not getattr(bot, "config", None):
        return False

    return is_admin(user, guild, bot.config)


def is_admin_member(
    member: discord.Member | None,
    config: Config,
) -> bool:
    """
    Check if a Discord member has admin role.

    Simplified version that takes a Member directly (already has guild context).

    Args:
        member: Discord member to check (None if not in guild)
        config: Bot configuration containing role IDs

    Returns:
        True if member has admin role, False otherwise
    """
    if member is None:
        return False

    admin_role_id = config.role_ids.admin
    return any(role.id == admin_role_id for role in getattr(member, "roles", []))
