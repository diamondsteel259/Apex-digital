"""
Wishlist System Cog

Allows users to save products to their wishlist for later purchase.
"""

from __future__ import annotations

from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd

logger = get_logger()


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None or isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


class WishlistCog(commands.Cog):
    """Wishlist management commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="wishlist", description="View your wishlist")
    async def wishlist_command(self, interaction: discord.Interaction):
        """View user's wishlist."""
        await interaction.response.defer(ephemeral=True)

        try:
            wishlist_rows = await self.bot.db.get_wishlist(interaction.user.id)
            wishlist = [row for row in (_row_to_dict(item) for item in wishlist_rows) if row]

            if not wishlist:
                await interaction.followup.send(
                    "📋 Your wishlist is empty!\n\nUse `/addwishlist` to add products.",
                    ephemeral=True,
                )
                return

            embed = create_embed(
                title="📋 Your Wishlist",
                description=f"You have {len(wishlist)} item(s) in your wishlist:",
                color=discord.Color.purple(),
            )

            for item in wishlist[:10]:
                product_name = item.get("variant_name") or "Unknown Product"
                price_cents = int(item.get("price_cents") or 0)
                price = format_usd(price_cents)
                product_id = item.get("product_id") or item.get("id")

                embed.add_field(
                    name=f"🛍️ {product_name}",
                    value=f"Price: {price}\nID: {product_id}",
                    inline=True,
                )

            if len(wishlist) > 10:
                embed.set_footer(text=f"... and {len(wishlist) - 10} more items")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            logger.exception("Error viewing wishlist")
            await interaction.followup.send(
                "❌ Error loading wishlist. Please try again later.",
                ephemeral=True,
            )

    @app_commands.command(name="addwishlist", description="Add a product to your wishlist")
    @app_commands.describe(product_id="The product ID to add")
    async def add_wishlist_command(self, interaction: discord.Interaction, product_id: int):
        """Add product to wishlist."""
        await interaction.response.defer(ephemeral=True)

        try:
            product_row = await self.bot.db.get_product(product_id)
            product = _row_to_dict(product_row)
            if not product:
                await interaction.followup.send(
                    f"❌ Product with ID {product_id} not found.",
                    ephemeral=True,
                )
                return

            if await self.bot.db.is_in_wishlist(interaction.user.id, product_id):
                await interaction.followup.send(
                    "ℹ️ This product is already in your wishlist!",
                    ephemeral=True,
                )
                return

            success = await self.bot.db.add_to_wishlist(interaction.user.id, product_id)

            if success:
                product_name = product.get("variant_name") or "Product"
                await interaction.followup.send(
                    f"✅ Added **{product_name}** to your wishlist!",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to add product to wishlist. Please try again.",
                    ephemeral=True,
                )

        except Exception:
            logger.exception("Error adding to wishlist")
            await interaction.followup.send(
                "❌ Error adding product to wishlist. Please try again later.",
                ephemeral=True,
            )

    @app_commands.command(name="removewishlist", description="Remove a product from your wishlist")
    @app_commands.describe(product_id="The product ID to remove")
    async def remove_wishlist_command(self, interaction: discord.Interaction, product_id: int):
        """Remove product from wishlist."""
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self.bot.db.is_in_wishlist(interaction.user.id, product_id):
                await interaction.followup.send(
                    "ℹ️ This product is not in your wishlist.",
                    ephemeral=True,
                )
                return

            success = await self.bot.db.remove_from_wishlist(interaction.user.id, product_id)

            if success:
                await interaction.followup.send(
                    f"✅ Removed product {product_id} from your wishlist!",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to remove product from wishlist. Please try again.",
                    ephemeral=True,
                )

        except Exception:
            logger.exception("Error removing from wishlist")
            await interaction.followup.send(
                "❌ Error removing product from wishlist. Please try again later.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    """Load the Wishlist cog."""
    await bot.add_cog(WishlistCog(bot))
    logger.info("Loaded extension: cogs.wishlist")
