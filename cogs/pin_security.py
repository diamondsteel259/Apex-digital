"""
PIN Security System Cog

Allows users to set a 4-6 digit PIN for securing wallet operations.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.admin_checks import admin_only

logger = get_logger()


def _hash_pin(pin: str) -> str:
    """Hash PIN using SHA-256."""
    return hashlib.sha256(pin.encode()).hexdigest()


def _validate_pin(pin: str) -> tuple[bool, str]:
    """Validate PIN format (4-6 digits)."""
    if not pin.isdigit():
        return False, "PIN must contain only digits (0-9)"
    
    if len(pin) < 4 or len(pin) > 6:
        return False, "PIN must be between 4 and 6 digits"
    
    return True, ""


class PINSecurityCog(commands.Cog):
    """PIN security management commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="setpin", description="Set or change your PIN (4-6 digits)")
    @app_commands.describe(pin="Your PIN (4-6 digits)", confirm_pin="Confirm your PIN")
    async def set_pin_command(
        self,
        interaction: discord.Interaction,
        pin: str,
        confirm_pin: str
    ):
        """Set user PIN."""
        await interaction.response.defer(ephemeral=True)
        
        # Validate PIN format
        is_valid, error_msg = _validate_pin(pin)
        if not is_valid:
            await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
            return
        
        # Check if PINs match
        if pin != confirm_pin:
            await interaction.followup.send(
                "❌ PINs do not match. Please try again.",
                ephemeral=True
            )
            return
        
        try:
            # Hash PIN
            pin_hash = _hash_pin(pin)
            
            # Set PIN in database
            success = await self.bot.db.set_user_pin(interaction.user.id, pin_hash)
            
            if success:
                await interaction.followup.send(
                    "✅ PIN set successfully! Use `/verifypin` to verify it works.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to set PIN. Please contact support.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error setting PIN: {e}")
            await interaction.followup.send(
                "❌ Error setting PIN. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="verifypin", description="Verify your PIN")
    @app_commands.describe(pin="Your PIN to verify")
    async def verify_pin_command(self, interaction: discord.Interaction, pin: str):
        """Verify user PIN."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            pin_hash = _hash_pin(pin)
            is_valid = await self.bot.db.verify_user_pin(interaction.user.id, pin_hash)
            
            if is_valid:
                await interaction.followup.send(
                    "✅ PIN verified successfully!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Invalid PIN. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error verifying PIN: {e}")
            await interaction.followup.send(
                "❌ Error verifying PIN. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="resetpin", description="[Admin] Reset a user's PIN")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(user="The user to reset PIN for")
    async def reset_pin_command(self, interaction: discord.Interaction, user: discord.User):
        """Admin: Reset user PIN."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Clear PIN
            success = await self.bot.db.set_user_pin(user.id, "")
            
            if success:
                await interaction.followup.send(
                    f"✅ Reset PIN for {user.mention}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to reset PIN. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error resetting PIN: {e}")
            await interaction.followup.send(
                "❌ Error resetting PIN. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the PIN Security cog."""
    await bot.add_cog(PINSecurityCog(bot))
    logger.info("Loaded extension: cogs.pin_security")

