"""
Affiliate System Cog

Locked/Coming Soon - Placeholder for future affiliate system.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed

logger = get_logger()


class AffiliateCog(commands.Cog):
    """Affiliate system (locked/coming soon)."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="affiliate", description="Affiliate system - Coming soon!")
    async def affiliate_command(self, interaction: discord.Interaction):
        """Affiliate system placeholder."""
        await interaction.response.send_message(
            "🔒 **Affiliate System - Coming Soon!**\n\n"
            "This feature is currently locked and will be released soon.\n"
            "Stay tuned for updates!",
            ephemeral=True
        )
    
    @app_commands.command(name="referral", description="Referral system - Coming soon!")
    async def referral_command(self, interaction: discord.Interaction):
        """Referral system placeholder."""
        await interaction.response.send_message(
            "🔒 **Referral System - Coming Soon!**\n\n"
            "This feature is currently locked and will be released soon.\n"
            "Stay tuned for updates!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Load the Affiliate cog."""
    await bot.add_cog(AffiliateCog(bot))
    logger.info("Loaded extension: cogs.affiliate")

