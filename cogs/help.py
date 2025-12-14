"""Enhanced help command with categories and search."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


class EnhancedHelpCog(commands.Cog):
    """Enhanced help command with categories and search."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="help")
    @app_commands.describe(
        command="Specific command to get help for",
        category="Command category to browse"
    )
    async def help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
        category: Optional[str] = None
    ) -> None:
        """Get help with bot commands."""
        logger.info(f"Help command used | User: {interaction.user.id} | Command: {command} | Category: {category}")
        
        if command:
            await self._show_command_help(interaction, command)
        elif category:
            await self._show_category_help(interaction, category)
        else:
            await self._show_main_help(interaction)

    async def _show_main_help(self, interaction: discord.Interaction) -> None:
        """Show main help page with categories."""
        is_admin = self._is_admin(interaction.user, interaction.guild)
        
        embed = create_embed(
            title="📚 Apex Core Help",
            description="Browse commands by category or use `/help <command>` for details.",
            color=discord.Color.blue()
        )
        
        # Customer Commands
        embed.add_field(
            name="🛍️ Shopping",
            value=(
                "`/buy` - Browse and purchase products\n"
                "`/orders` - View your order history\n"
                "`/faq` - Frequently asked questions"
            ),
            inline=False
        )
        
        # Wallet Commands
        embed.add_field(
            name="💰 Wallet",
            value=(
                "`/balance` - Check your wallet balance\n"
                "`/deposit` - Add funds to wallet\n"
                "`/transactions` - View transaction history"
            ),
            inline=False
        )
        
        # Support Commands
        embed.add_field(
            name="🎫 Support",
            value=(
                "`/ticket` - Open support ticket\n"
                "`/submitrefund` - Request a refund"
            ),
            inline=False
        )
        
        # VIP & Referrals
        embed.add_field(
            name="⭐ VIP & Rewards",
            value=(
                "`/profile` - View your profile\n"
                "`/invites` - Check referral earnings\n"
                "`/setref` - Set your referrer"
            ),
            inline=False
        )
        
        # Gifts
        embed.add_field(
            name="🎁 Gifts",
            value=(
                "`/sendgift` - Send a gift to another user\n"
                "`/claimgift` - Claim a gift with code\n"
                "`/mygifts` - View your gifts"
            ),
            inline=False
        )
        
        # Promo Codes
        embed.add_field(
            name="🎟️ Promo Codes",
            value="`/redeem <code>` - Apply promo code to purchase",
            inline=False
        )
        
        # Reviews
        embed.add_field(
            name="⭐ Reviews",
            value=(
                "`/review` - Submit a review for an order\n"
                "`/myreviews` - View your submitted reviews"
            ),
            inline=False
        )
        
        # Admin Commands (only show to admins)
        if is_admin:
            embed.add_field(
                name="🔧 Admin Commands",
                value=(
                    "`/help category:admin` - View all admin commands\n"
                    "Includes: product management, user management, "
                    "announcements, backups, and more"
                ),
                inline=False
            )
        
        embed.set_footer(text="Use /help <command> for detailed command information")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _show_category_help(self, interaction: discord.Interaction, category: str) -> None:
        """Show help for specific category."""
        category_lower = category.lower()
        
        if category_lower == "admin":
            if not self._is_admin(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "🚫 You don't have permission to view admin commands.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="🔧 Admin Commands",
                description="Administrative commands for managing the bot:",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="📦 Product Management",
                value=(
                    "`/setstock` - Manage product inventory\n"
                    "`/addstock` - Add stock to product\n"
                    "`/checkstock` - Check stock levels\n"
                    "`/stockalert` - View low stock products"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🎟️ Promo Codes",
                value=(
                    "`/createcode` - Create promo code\n"
                    "`/listcodes` - List all codes\n"
                    "`/codeinfo` - View code details\n"
                    "`/deactivatecode` - Deactivate code\n"
                    "`/deletecode` - Delete code"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👥 User Management",
                value=(
                    "`/addbalance` - Add wallet balance\n"
                    "`/balance <member>` - Check member balance\n"
                    "`/orders <member>` - View member orders"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📦 Order Management",
                value=(
                    "`/updateorderstatus` - Update order status\n"
                    "`/bulkupdateorders` - Bulk update orders"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🎁 Gifts",
                value=(
                    "`/giftproduct` - Gift product to user\n"
                    "`/giftwallet` - Gift wallet balance\n"
                    "`/giftcode` - Generate gift code"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📢 Announcements",
                value=(
                    "`/announce` - Send announcement\n"
                    "`/announcements` - View announcement history\n"
                    "`/testannouncement` - Test announcement"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⭐ Reviews",
                value=(
                    "`/pendingreviews` - View pending reviews\n"
                    "`/approvereview` - Approve review\n"
                    "`/rejectreview` - Reject review\n"
                    "`/reviewstats` - View review statistics"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💾 Database",
                value=(
                    "`/backup` - Create database backup\n"
                    "`/listbackups` - List backups\n"
                    "`/exportdata` - Export data to CSV"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ Category '{category}' not found. Use `/help` to see available categories.",
                ephemeral=True
            )

    async def _show_command_help(self, interaction: discord.Interaction, command: str) -> None:
        """Show detailed help for specific command."""
        # This is a simplified version - can be expanded with actual command details
        embed = create_embed(
            title=f"Command: /{command}",
            description=f"Detailed information about the `/{command}` command.",
            color=discord.Color.blue()
        )
        
        # Add command-specific help (can be expanded)
        command_help = {
            "buy": "Browse and purchase products from the storefront.",
            "balance": "Check your wallet balance and lifetime spending.",
            "deposit": "Open a deposit ticket to add funds to your wallet.",
            "orders": "View your order history with pagination.",
            "transactions": "View your wallet transaction history.",
            "ticket": "Open a support ticket for assistance.",
        }
        
        if command.lower() in command_help:
            embed.description = command_help[command.lower()]
        else:
            embed.description = f"Use `/help` to see all available commands."
        
        embed.set_footer(text="Use /help to see all commands")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the EnhancedHelpCog cog."""
    await bot.add_cog(EnhancedHelpCog(bot))

