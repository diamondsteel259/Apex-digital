"""Order status management and notification commands."""

from __future__ import annotations

from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


async def send_order_status_notification(
    bot: commands.Bot,
    user_id: int,
    order_id: int,
    old_status: str,
    new_status: str,
    estimated_delivery: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    """Send DM notification about order status change."""
    try:
        user = await bot.fetch_user(user_id)
        if not user:
            return False
        
        status_emojis = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "delivered": "📦",
            "cancelled": "❌",
            "refunded": "↩️"
        }
        
        embed = create_embed(
            title=f"{status_emojis.get(new_status, '📋')} Order Status Updated",
            description=f"Your order #{order_id} status has been updated.",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Previous Status", value=old_status.title(), inline=True)
        embed.add_field(name="New Status", value=new_status.title(), inline=True)
        
        if estimated_delivery:
            embed.add_field(name="Estimated Delivery", value=estimated_delivery, inline=False)
        
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        
        embed.set_footer(text=f"Order ID: {order_id}")
        
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        logger.warning(f"Cannot send DM to user {user_id} - DMs disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to send order status notification: {e}")
        return False


class OrderManagementCog(commands.Cog):
    """Commands for managing order statuses."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="updateorderstatus")
    @app_commands.describe(
        order_id="Order ID",
        status="New order status",
        estimated_delivery="Estimated delivery time (optional)",
        notify_user="Send DM notification to user"
    )
    async def update_order_status(
        self,
        interaction: discord.Interaction,
        order_id: int,
        status: Literal["pending", "processing", "completed", "delivered", "cancelled", "refunded"],
        estimated_delivery: Optional[str] = None,
        notify_user: bool = True
    ) -> None:
        """Update order status and notify user (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get current order
            order = await self.bot.db.get_order_by_id(order_id)
            if not order:
                await interaction.followup.send(
                    f"❌ Order #{order_id} not found.",
                    ephemeral=True
                )
                return
            
            old_status = order.get("status", "pending")
            
            # Update status
            updated_order = await self.bot.db.update_order_status(
                order_id=order_id,
                status=status,
                estimated_delivery=estimated_delivery,
                notes=None
            )
            
            # Send notification using automated messages system
            notification_sent = False
            if notify_user:
                # Try automated messages system first
                automated_cog = self.bot.get_cog("AutomatedMessagesCog")
                if automated_cog:
                    try:
                        product = await self.bot.db.get_product(order["product_id"])
                        product_name = product.get("variant_name", "Product") if product else "Product"
                        await automated_cog.send_order_status_update(
                            user_id=order["user_discord_id"],
                            order_id=order_id,
                            old_status=old_status,
                            new_status=status,
                            product_name=product_name,
                            order_amount_cents=order["price_paid_cents"]
                        )
                        notification_sent = True
                    except Exception as e:
                        logger.error(f"Failed to send automated order update: {e}", exc_info=True)
                        # Fallback to original notification
                        notification_sent = await send_order_status_notification(
                            self.bot,
                            order["user_discord_id"],
                            order_id,
                            old_status,
                            status,
                            estimated_delivery
                        )
                else:
                    # Fallback to original notification
                    notification_sent = await send_order_status_notification(
                        self.bot,
                        order["user_discord_id"],
                        order_id,
                        old_status,
                        status,
                        estimated_delivery
                    )
            
            embed = create_embed(
                title="✅ Order Status Updated",
                description=(
                    f"**Order ID:** #{order_id}\n"
                    f"**Previous Status:** {old_status.title()}\n"
                    f"**New Status:** {status.title()}\n"
                    f"**User Notification:** {'✅ Sent' if notification_sent else '❌ Failed (DMs may be disabled)'}"
                ),
                color=discord.Color.green()
            )
            
            if estimated_delivery:
                embed.add_field(
                    name="Estimated Delivery",
                    value=estimated_delivery,
                    inline=False
                )
            
            # Add supplier info for admin (if product has supplier)
            if order["product_id"] != 0:
                product = await self.bot.db.get_product(order["product_id"])
                if product:
                    # Check if supplier fields exist - use product dict directly
                    try:
                        # product is a dict from database row
                        if "supplier_id" in product and product.get("supplier_id"):
                            supplier_name = product.get("supplier_name", "Unknown Supplier")
                            supplier_service_id = product.get("supplier_service_id", "")
                            supplier_api_url = product.get("supplier_api_url", "")
                            
                            supplier_info = f"**Supplier:** {supplier_name}\n"
                            supplier_info += f"**Service ID:** {supplier_service_id}\n"
                            if supplier_api_url:
                                supplier_info += f"**API URL:** {supplier_api_url}"
                            
                            embed.add_field(
                                name="🔗 Supplier Information (Admin Only)",
                                value=supplier_info,
                                inline=False
                            )
                    except Exception as e:
                        logger.debug(f"Could not add supplier info: {e}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Order {order_id} status updated from {old_status} to {status} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to update order status", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to update order status: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="bulkupdateorders")
    @app_commands.describe(
        order_ids="Comma-separated order IDs (e.g., 123,456,789)",
        status="New status for all orders"
    )
    async def bulk_update_orders(
        self,
        interaction: discord.Interaction,
        order_ids: str,
        status: Literal["processing", "completed", "delivered", "cancelled"]
    ) -> None:
        """Bulk update order statuses (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse order IDs
            try:
                ids = [int(id.strip()) for id in order_ids.split(",")]
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid order IDs format. Use comma-separated numbers (e.g., 123,456,789).",
                    ephemeral=True
                )
                return
            
            if len(ids) > 50:
                await interaction.followup.send(
                    "❌ Maximum 50 orders can be updated at once.",
                    ephemeral=True
                )
                return
            
            updated_count = 0
            failed_count = 0
            
            for order_id in ids:
                try:
                    order = await self.bot.db.get_order_by_id(order_id)
                    if order:
                        await self.bot.db.update_order_status(
                            order_id=order_id,
                            status=status,
                            estimated_delivery=None,
                            notes=None
                        )
                        updated_count += 1
                        
                        # Send notification
                        await send_order_status_notification(
                            self.bot,
                            order["user_discord_id"],
                            order_id,
                            order.get("status", "pending"),
                            status
                        )
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to update order {order_id}: {e}")
                    failed_count += 1
            
            embed = create_embed(
                title="✅ Bulk Update Complete",
                description=(
                    f"**Total Orders:** {len(ids)}\n"
                    f"**Updated:** {updated_count}\n"
                    f"**Failed:** {failed_count}"
                ),
                color=discord.Color.green() if failed_count == 0 else discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Bulk updated {updated_count} orders to {status} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to bulk update orders", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to bulk update orders: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Load the OrderManagementCog cog."""
    await bot.add_cog(OrderManagementCog(bot))

