"""Promo code management and redemption commands."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.error_messages import get_error_message
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


class PromoCodesCog(commands.Cog):
    """Commands for managing and redeeming promo codes."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="createcode")
    @app_commands.describe(
        code="Promo code (e.g., SUMMER25)",
        type="Type of discount",
        value="Discount value (percentage 0-100 or fixed amount in dollars)",
        max_uses="Maximum total uses (leave empty for unlimited)",
        max_per_user="Maximum uses per user (default: 1)",
        expires_days="Days until expiration (leave empty for no expiration)",
        stackable="Can be combined with VIP discounts",
        first_time_only="Only for first-time buyers",
        min_purchase="Minimum purchase amount in dollars"
    )
    async def create_code(
        self,
        interaction: discord.Interaction,
        code: str,
        type: Literal["percentage", "fixed_amount"],
        value: float,
        max_uses: Optional[int] = None,
        max_per_user: int = 1,
        expires_days: Optional[int] = None,
        stackable: bool = False,
        first_time_only: bool = False,
        min_purchase: float = 0.0
    ) -> None:
        """Create a promo code (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate code format
            if len(code) < 3 or len(code) > 20:
                await interaction.followup.send(
                    "❌ Code must be between 3 and 20 characters.",
                    ephemeral=True
                )
                return
            
            # Validate value
            if type == "percentage" and (value < 0 or value > 100):
                await interaction.followup.send(
                    "❌ Percentage must be between 0 and 100.",
                    ephemeral=True
                )
                return
            
            if type == "fixed_amount" and value < 0:
                await interaction.followup.send(
                    "❌ Fixed amount must be positive.",
                    ephemeral=True
                )
                return
            
            # Calculate expiration
            expires_at = None
            if expires_days:
                expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
            
            # Create promo code
            code_id = await self.bot.db.create_promo_code(
                code=code.upper(),
                code_type=type,
                discount_value=value,
                max_uses=max_uses,
                max_uses_per_user=max_per_user,
                minimum_purchase_cents=int(min_purchase * 100),
                first_time_only=first_time_only,
                expires_at=expires_at,
                is_active=True,
                is_stackable=stackable,
                created_by_staff_id=interaction.user.id
            )
            
            value_display = f"{value}%" if type == "percentage" else f"${value:.2f}"
            
            embed = create_embed(
                title="✅ Promo Code Created",
                description=(
                    f"**Code:** `{code.upper()}`\n"
                    f"**Type:** {type.replace('_', ' ').title()}\n"
                    f"**Value:** {value_display}\n"
                    f"**Max Uses:** {max_uses or 'Unlimited'}\n"
                    f"**Max Per User:** {max_per_user}\n"
                    f"**Stackable:** {'Yes' if stackable else 'No'}\n"
                    f"**First Time Only:** {'Yes' if first_time_only else 'No'}\n"
                    f"**Min Purchase:** ${min_purchase:.2f}\n"
                    f"**Expires:** {expires_days and f'{expires_days} days' or 'Never'}"
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Promo code created: {code.upper()} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to create promo code", exc_info=True)
            if "UNIQUE constraint" in str(e):
                await interaction.followup.send(
                    f"❌ Promo code `{code.upper()}` already exists.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to create promo code: {str(e)}",
                    ephemeral=True
                )

    @app_commands.command(name="listcodes")
    @app_commands.describe(active_only="Show only active codes")
    async def list_codes(
        self,
        interaction: discord.Interaction,
        active_only: bool = True
    ) -> None:
        """List all promo codes (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            codes = await self.bot.db.get_all_promo_codes(active_only=active_only)
            
            if not codes:
                await interaction.followup.send(
                    "📭 No promo codes found.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title=f"📋 Promo Codes ({'Active' if active_only else 'All'})",
                description=f"Found {len(codes)} code(s):",
                color=discord.Color.blue()
            )
            
            for code in codes[:10]:
                value_display = (
                    f"{code['discount_value']}%"
                    if code['code_type'] == 'percentage'
                    else f"${code['discount_value']:.2f}"
                )
                status = "✅ Active" if code['is_active'] else "❌ Inactive"
                uses = f"{code['current_uses']}/{code['max_uses'] or '∞'}"
                
                embed.add_field(
                    name=f"`{code['code']}` - {status}",
                    value=(
                        f"**Value:** {value_display}\n"
                        f"**Uses:** {uses}\n"
                        f"**Stackable:** {'Yes' if code['is_stackable'] else 'No'}"
                    ),
                    inline=False
                )
            
            if len(codes) > 10:
                embed.set_footer(text=f"Showing 10 of {len(codes)} codes")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to list promo codes", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to list codes: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="codeinfo")
    @app_commands.describe(code="Promo code to view")
    async def code_info(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """View promo code details and usage stats (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            promo = await self.bot.db.get_promo_code(code)
            if not promo:
                await interaction.followup.send(
                    f"❌ Promo code `{code.upper()}` not found.",
                    ephemeral=True
                )
                return
            
            stats = await self.bot.db.get_promo_code_usage_stats(code)
            
            value_display = (
                f"{promo['discount_value']}%"
                if promo['code_type'] == 'percentage'
                else f"${promo['discount_value']:.2f}"
            )
            
            embed = create_embed(
                title=f"📋 Promo Code: `{promo['code']}`",
                description=(
                    f"**Type:** {promo['code_type'].replace('_', ' ').title()}\n"
                    f"**Value:** {value_display}\n"
                    f"**Status:** {'✅ Active' if promo['is_active'] else '❌ Inactive'}\n"
                    f"**Stackable:** {'Yes' if promo['is_stackable'] else 'No'}\n"
                    f"**First Time Only:** {'Yes' if promo['first_time_only'] else 'No'}\n"
                    f"**Min Purchase:** ${promo['minimum_purchase_cents']/100:.2f}"
                ),
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Usage Limits",
                value=(
                    f"**Max Uses:** {promo['max_uses'] or 'Unlimited'}\n"
                    f"**Current Uses:** {promo['current_uses']}\n"
                    f"**Max Per User:** {promo['max_uses_per_user']}"
                ),
                inline=False
            )
            
            if stats:
                embed.add_field(
                    name="Statistics",
                    value=(
                        f"**Total Uses:** {stats['total_uses']}\n"
                        f"**Unique Users:** {stats['unique_users']}\n"
                        f"**Total Discount:** {format_usd(stats['total_discount_cents'])}"
                    ),
                    inline=False
                )
            
            if promo['expires_at']:
                try:
                    expires = datetime.fromisoformat(promo['expires_at'])
                    embed.add_field(
                        name="Expiration",
                        value=f"Expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}",
                        inline=False
                    )
                except ValueError:
                    pass
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to get code info", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to get code info: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="deactivatecode")
    @app_commands.describe(code="Promo code to deactivate")
    async def deactivate_code(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """Deactivate a promo code (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            success = await self.bot.db.deactivate_promo_code(code)
            if success:
                await interaction.followup.send(
                    f"✅ Promo code `{code.upper()}` has been deactivated.",
                    ephemeral=True
                )
                logger.info(f"Promo code {code.upper()} deactivated by {interaction.user.id}")
            else:
                await interaction.followup.send(
                    f"❌ Promo code `{code.upper()}` not found.",
                    ephemeral=True
                )
        except Exception as e:
            logger.exception("Failed to deactivate promo code", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to deactivate code: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="deletecode")
    @app_commands.describe(code="Promo code to delete")
    async def delete_code(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """Permanently delete a promo code (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            success = await self.bot.db.delete_promo_code(code)
            if success:
                await interaction.followup.send(
                    f"✅ Promo code `{code.upper()}` has been permanently deleted.",
                    ephemeral=True
                )
                logger.info(f"Promo code {code.upper()} deleted by {interaction.user.id}")
            else:
                await interaction.followup.send(
                    f"❌ Promo code `{code.upper()}` not found.",
                    ephemeral=True
                )
        except Exception as e:
            logger.exception("Failed to delete promo code", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to delete code: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="redeem")
    @app_commands.describe(code="Promo code to redeem")
    async def redeem(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """Apply a promo code to your next purchase."""
        await interaction.response.send_message(
            f"💡 To use promo code `{code.upper()}`, select it during checkout when purchasing a product.\n"
            "Use `/buy` to browse products and make a purchase.",
            ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    """Load the PromoCodesCog cog."""
    await bot.add_cog(PromoCodesCog(bot))

