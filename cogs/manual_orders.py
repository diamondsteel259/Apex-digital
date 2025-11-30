from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import (
    create_embed,
    format_usd,
    handle_vip_promotion,
    process_post_purchase,
    render_operating_hours,
)

logger = logging.getLogger(__name__)


class ManualOrdersCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # region Helpers
    def _to_cents(self, amount: float) -> int:
        """Convert USD amount to cents with proper rounding."""
        cents = int((Decimal(str(amount)) * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))
        return cents

    def _is_admin(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

    def _resolve_member(self, interaction: discord.Interaction) -> discord.Member | None:
        if isinstance(interaction.user, discord.Member):
            return interaction.user
        if interaction.guild:
            return interaction.guild.get_member(interaction.user.id)
        return None

    def _operating_hours_text(self) -> str:
        return render_operating_hours(self.bot.config.operating_hours)
    # endregion

    @app_commands.command(name="manual_complete", description="Complete a manual order for a user.")
    @app_commands.describe(
        user="User who made the purchase",
        amount="Amount in USD that was paid",
        product_name="Name of the product purchased",
        notes="Additional notes about the order",
    )
    async def manual_complete(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[float, 0.01, 100000.0],
        product_name: str,
        notes: str = "",
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        requester = self._resolve_member(interaction)
        if not self._is_admin(requester):
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate and convert amount
        try:
            cents = self._to_cents(amount)
        except (InvalidOperation, ValueError):
            await interaction.followup.send("Invalid amount provided.", ephemeral=True)
            return

        # Validate product name
        product_name = product_name.strip()
        if not product_name:
            await interaction.followup.send("Product name is required.", ephemeral=True)
            return

        # Clean up notes
        notes = notes.strip() if notes else None

        try:
            # Create manual order without affecting wallet balance
            order_id, new_lifetime_spend = await self.bot.db.create_manual_order(
                user_discord_id=user.id,
                product_name=product_name,
                price_paid_cents=cents,
                notes=notes,
            )

            amount_str = format_usd(cents)

            # Process post-purchase actions including VIP promotion
            old_vip_tier, new_vip_tier = await process_post_purchase(
                user_discord_id=user.id,
                amount_cents=cents,
                db=self.bot.db,
                config=self.bot.config,
                guild=interaction.guild,
            )

            # Handle VIP promotion notifications and role assignments
            if new_vip_tier and (not old_vip_tier or new_vip_tier.name != old_vip_tier.name):
                await handle_vip_promotion(
                    user_discord_id=user.id,
                    old_vip_tier=old_vip_tier,
                    new_vip_tier=new_vip_tier,
                    config=self.bot.config,
                    guild=interaction.guild,
                )

            # Send confirmation to admin
            embed = create_embed(
                title="Manual Order Completed",
                description=(
                    f"**Customer:** {user.mention} ({user.id})\n"
                    f"**Product:** {product_name}\n"
                    f"**Amount:** {amount_str}\n"
                    f"**Order ID:** #{order_id}\n"
                    f"**New Lifetime Spend:** {format_usd(new_lifetime_spend)}"
                ),
                color=discord.Color.green(),
            )
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)
            embed.add_field(name="Operating Hours", value=self._operating_hours_text(), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            # DM customer about their order
            dm_embed = create_embed(
                title="Order Confirmation",
                description=(
                    f"Your order has been manually completed!\n\n"
                    f"**Product:** {product_name}\n"
                    f"**Amount Paid:** {amount_str}\n"
                    f"**Order ID:** #{order_id}\n"
                    f"**Lifetime Spend:** {format_usd(new_lifetime_spend)}"
                ),
                color=discord.Color.blue(),
            )
            if notes:
                dm_embed.add_field(name="Notes", value=notes, inline=False)

            try:
                await user.send(embed=dm_embed)
                logger.info("Sent manual order confirmation DM to user %s", user.id)
            except discord.Forbidden:
                logger.warning("Could not DM user %s about manual order", user.id)
                # Note to admin that DM failed
                await interaction.followup.send(
                    "⚠️ Could not send confirmation DM to the user. They may have DMs disabled.",
                    ephemeral=True,
                )

            # Log to order log channel
            log_channel_id = (
                self.bot.config.logging_channels.order_logs
                or self.bot.config.logging_channels.payments
            )
            log_channel = interaction.guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                log_embed = create_embed(
                    title="Manual Order Completed",
                    description=(
                        f"**Staff Member:** {requester.mention} ({requester.id})\n"
                        f"**Customer:** {user.mention} ({user.id})\n"
                        f"**Product:** {product_name}\n"
                        f"**Amount:** {amount_str}\n"
                        f"**Order ID:** #{order_id}\n"
                        f"**Lifetime Spend:** {format_usd(new_lifetime_spend)}"
                    ),
                    color=discord.Color.dark_green(),
                )
                if notes:
                    log_embed.add_field(name="Notes", value=notes, inline=False)
                log_embed.set_footer(text=f"User ID: {user.id} | Order ID: {order_id}")
                
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException as e:
                    logger.error("Failed to log manual order to channel %s: %s", log_channel_id, e)
            else:
                logger.warning("Order log channel %s not found", log_channel_id)

        except Exception as e:
            logger.error("Error completing manual order for user %s: %s", user.id, e)
            await interaction.followup.send(
                "An error occurred while processing the manual order. Please try again.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ManualOrdersCog(bot))