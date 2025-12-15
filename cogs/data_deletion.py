"""Data deletion command for users to request account data deletion."""

from __future__ import annotations

from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None or isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


class DataDeletionCog(commands.Cog):
    """Data deletion request system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)
    
    @app_commands.command(name="deletedata", description="Request deletion of your account data")
    @app_commands.describe(
        confirm="Type 'DELETE' to confirm data deletion request"
    )
    async def delete_data(
        self,
        interaction: discord.Interaction,
        confirm: str
    ) -> None:
        """Request deletion of your account data."""
        logger.info(f"Data deletion request | User: {interaction.user.id}")
        
        if confirm.upper() != "DELETE":
            embed = create_embed(
                title="❌ Invalid Confirmation",
                description=(
                    "**Confirmation required!**\n\n"
                    "To confirm data deletion, you must type `DELETE` (all caps) in the confirm field.\n\n"
                    "**This action cannot be undone!**\n"
                    "All your data will be permanently deleted:\n"
                    "• Account information\n"
                    "• Wallet balance\n"
                    "• Order history\n"
                    "• Transaction history\n"
                    "• Ticket history\n"
                    "• Review submissions\n"
                    "• Referral data\n\n"
                    "**Note:** Some data may be retained for legal/audit purposes (e.g., financial records)."
                ),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get user data summary
        await self.bot.db.ensure_user(interaction.user.id)
        user_data_row = await self.bot.db.get_user(interaction.user.id)
        user_data = _row_to_dict(user_data_row)
        
        if not user_data:
            embed = create_embed(
                title="ℹ️ No Data Found",
                description="No account data found for your Discord account.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create deletion request
        try:
            # Log deletion request to audit channel
            audit_channel_id = None
            if hasattr(self.bot.config, 'logging_channels') and hasattr(self.bot.config.logging_channels, 'audit'):
                audit_channel_id = self.bot.config.logging_channels.audit
            
            if audit_channel_id:
                audit_channel = self.bot.get_channel(audit_channel_id)
                if audit_channel and isinstance(audit_channel, discord.TextChannel):
                    audit_embed = create_embed(
                        title="🗑️ Data Deletion Request",
                        description=(
                            f"**User:** {interaction.user.mention} ({interaction.user.id})\n"
                            f"**Username:** {interaction.user.name}\n"
                            f"**Requested At:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n\n"
                            f"**Account Data:**\n"
                            f"• Wallet Balance: ${user_data.get('wallet_balance_cents', 0) / 100:.2f}\n"
                            f"• Total Spent: ${user_data.get('total_lifetime_spent_cents', 0) / 100:.2f}\n"
                            f"• Account Created: {user_data.get('created_at', 'Unknown')}\n\n"
                            "**Action Required:** Staff must process this deletion request manually."
                        ),
                        color=discord.Color.orange()
                    )
                    await audit_channel.send(embed=audit_embed)
            
            # Send confirmation to user
            embed = create_embed(
                title="✅ Deletion Request Submitted",
                description=(
                    "**Your data deletion request has been submitted!**\n\n"
                    "**What happens next:**\n"
                    "1. Your request has been logged\n"
                    "2. Staff will review your request\n"
                    "3. Deletion will be processed within **7 days**\n"
                    "4. You will be notified when deletion is complete\n\n"
                    "**Important Notes:**\n"
                    "• Your wallet balance will be forfeited\n"
                    "• All orders and transactions will be deleted\n"
                    "• Some financial records may be retained for legal purposes\n"
                    "• This action cannot be undone\n\n"
                    "**If you change your mind:**\n"
                    "Contact staff via support ticket within 24 hours to cancel this request."
                ),
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Send DM notification
            try:
                dm_embed = create_embed(
                    title="🗑️ Data Deletion Request Received",
                    description=(
                        f"Your data deletion request has been received and logged.\n\n"
                        f"**Request ID:** {interaction.id}\n"
                        f"**Requested At:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n\n"
                        f"Staff will process your request within 7 days.\n\n"
                        f"If you did not request this, please contact staff immediately via support ticket."
                    ),
                    color=discord.Color.orange()
                )
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send DM to user {interaction.user.id} for deletion request")
            
        except Exception as e:
            logger.error(f"Error processing data deletion request: {e}", exc_info=True)
            embed = create_embed(
                title="❌ Error",
                description="An error occurred while processing your deletion request. Please try again or contact staff.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="processdeletion", description="[Admin] Process a data deletion request")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        user="User to delete data for",
        confirm="Type 'CONFIRM DELETE' to proceed"
    )
    async def process_deletion(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        confirm: str
    ) -> None:
        """Process a data deletion request (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        if confirm.upper() != "CONFIRM DELETE":
            embed = create_embed(
                title="❌ Invalid Confirmation",
                description="You must type `CONFIRM DELETE` (all caps) to proceed with data deletion.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        logger.warning(f"Admin {interaction.user.id} processing data deletion for user {user.id}")
        
        # Get user data
        await self.bot.db.ensure_user(user.id)
        user_data_row = await self.bot.db.get_user(user.id)
        user_data = _row_to_dict(user_data_row)
        
        if not user_data:
            embed = create_embed(
                title="ℹ️ No Data Found",
                description=f"No account data found for {user.mention}.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Delete user data (this would need to be implemented in database.py)
        # For now, we'll just log it
        embed = create_embed(
            title="⚠️ Data Deletion",
            description=(
                f"**Processing data deletion for:** {user.mention}\n\n"
                "**Note:** Full data deletion functionality needs to be implemented in the database layer.\n"
                "This command currently only logs the deletion request.\n\n"
                "**Data to be deleted:**\n"
                "• User account\n"
                "• Wallet balance\n"
                "• Order history\n"
                "• Transaction history\n"
                "• Ticket history\n"
                "• Review submissions\n"
                "• Referral data"
            ),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # TODO: Implement actual data deletion in database.py
        # await self.bot.db.delete_user_data(user.id)


async def setup(bot: commands.Bot):
    """Load the Data Deletion cog."""
    await bot.add_cog(DataDeletionCog(bot))
    logger.info("Loaded extension: cogs.data_deletion")

