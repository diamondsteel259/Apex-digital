"""Admin check utilities for hiding commands from non-admins."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands

from apex_core.utils.permissions import is_admin


def admin_only():
    """Decorator to hide admin commands from non-admins in Discord command tree."""
    def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        if not hasattr(interaction.client, 'config'):
            return False
        return is_admin(interaction.user, interaction.guild, interaction.client.config)
    return app_commands.check(predicate)


def admin_command_check(interaction: discord.Interaction) -> bool:
    """Check if user is admin for app_commands."""
    if not interaction.guild:
        return False
    if not hasattr(interaction.client, 'config'):
        return False
    return is_admin(interaction.user, interaction.guild, interaction.client.config)

