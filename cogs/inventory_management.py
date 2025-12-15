"""Inventory management commands for product stock tracking."""

from __future__ import annotations

from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None or isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


class InventoryManagementCog(commands.Cog):
    """Commands for managing product inventory."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="setstock")
    @app_commands.describe(
        product_id="Product ID",
        quantity="Stock quantity (leave empty for unlimited)"
    )
    async def set_stock(
        self,
        interaction: discord.Interaction,
        product_id: int,
        quantity: Optional[int] = None
    ) -> None:
        """Set product stock quantity (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            product = await self.bot.db.get_product(product_id)
            if not product:
                await interaction.followup.send(
                    f"❌ Product #{product_id} not found.",
                    ephemeral=True
                )
                return
            
            await self.bot.db.update_product_stock(product_id, quantity)
            
            stock_display = "Unlimited" if quantity is None else str(quantity)
            
            embed = create_embed(
                title="✅ Stock Updated",
                description=(
                    f"**Product:** {product['variant_name']}\n"
                    f"**New Stock:** {stock_display}"
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Stock updated for product {product_id} to {stock_display} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to set stock", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to update stock: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="addstock")
    @app_commands.describe(
        product_id="Product ID",
        quantity="Quantity to add"
    )
    async def add_stock(
        self,
        interaction: discord.Interaction,
        product_id: int,
        quantity: int
    ) -> None:
        """Add stock to a product (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            product_row = await self.bot.db.get_product(product_id)
            product = _row_to_dict(product_row)
            if not product:
                await interaction.followup.send(
                    f"❌ Product #{product_id} not found.",
                    ephemeral=True
                )
                return
            
            current_stock = product.get("stock_quantity")
            
            # Can't add to unlimited stock
            if current_stock is None:
                await interaction.followup.send(
                    "❌ This product has unlimited stock. Use `/setstock` to set a specific quantity first.",
                    ephemeral=True
                )
                return
            
            new_stock = current_stock + quantity
            await self.bot.db.update_product_stock(product_id, new_stock)
            
            embed = create_embed(
                title="✅ Stock Added",
                description=(
                    f"**Product:** {product['variant_name']}\n"
                    f"**Added:** {quantity}\n"
                    f"**Previous Stock:** {current_stock}\n"
                    f"**New Stock:** {new_stock}"
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Added {quantity} stock to product {product_id} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to add stock", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to add stock: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="checkstock")
    @app_commands.describe(product_id="Product ID (optional)")
    async def check_stock(
        self,
        interaction: discord.Interaction,
        product_id: Optional[int] = None
    ) -> None:
        """Check stock levels (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if product_id:
                # Check specific product
                product_row = await self.bot.db.get_product(product_id)
                product = _row_to_dict(product_row)
                if not product:
                    await interaction.followup.send(
                        f"❌ Product #{product_id} not found.",
                        ephemeral=True
                    )
                    return
                
                stock = product.get("stock_quantity")
                stock_display = "Unlimited" if stock is None else str(stock)
                
                embed = create_embed(
                    title=f"📦 Stock: {product['variant_name']}",
                    description=f"**Current Stock:** {stock_display}",
                    color=discord.Color.blue()
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # Show low stock products
                low_stock = await self.bot.db.get_low_stock_products(threshold=10)
                out_of_stock = await self.bot.db.get_out_of_stock_products()
                
                embed = create_embed(
                    title="📦 Stock Overview",
                    description=(
                        f"**Low Stock (≤10):** {len(low_stock)}\n"
                        f"**Out of Stock:** {len(out_of_stock)}"
                    ),
                    color=discord.Color.orange() if low_stock or out_of_stock else discord.Color.green()
                )
                
                if low_stock:
                    low_stock_list = "\n".join([
                        f"• {p['variant_name']}: {p['stock_quantity']} left"
                        for p in low_stock[:10]
                    ])
                    embed.add_field(
                        name="⚠️ Low Stock Products",
                        value=low_stock_list[:1024],
                        inline=False
                    )
                
                if out_of_stock:
                    out_of_stock_list = "\n".join([
                        f"• {p['variant_name']}"
                        for p in out_of_stock[:10]
                    ])
                    embed.add_field(
                        name="🔴 Out of Stock",
                        value=out_of_stock_list[:1024],
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.exception("Failed to check stock", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to check stock: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="stockalert")
    @app_commands.describe(threshold="Alert when stock falls below this number")
    async def stock_alert(
        self,
        interaction: discord.Interaction,
        threshold: int = 10
    ) -> None:
        """View products with low stock (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            low_stock = await self.bot.db.get_low_stock_products(threshold=threshold)
            
            if not low_stock:
                embed = create_embed(
                    title="✅ All Products Stocked",
                    description=f"No products with stock below {threshold}.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            embed = create_embed(
                title=f"⚠️ Low Stock Alert (≤{threshold})",
                description=f"Found {len(low_stock)} product(s) with low stock:",
                color=discord.Color.orange()
            )
            
            stock_list = "\n".join([
                f"• **{p['variant_name']}** (ID: {p['id']}): {p['stock_quantity']} left"
                for p in low_stock[:20]
            ])
            
            embed.add_field(
                name="Products",
                value=stock_list[:1024],
                inline=False
            )
            
            if len(low_stock) > 20:
                embed.set_footer(text=f"Showing 20 of {len(low_stock)} products")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to get stock alerts", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to get stock alerts: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Load the InventoryManagementCog cog."""
    await bot.add_cog(InventoryManagementCog(bot))

