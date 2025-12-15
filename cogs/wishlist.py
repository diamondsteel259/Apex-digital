"""
Wishlist System Cog

Allows users to save products to their wishlist for later purchase.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd

logger = get_logger()


class WishlistCog(commands.Cog):
    """Wishlist management commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="wishlist", description="View your wishlist")
    async def wishlist_command(self, interaction: discord.Interaction):
        """View user's wishlist."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            wishlist = await self.bot.db.get_wishlist(interaction.user.id)
            
            if not wishlist:
                await interaction.followup.send(
                    "📋 Your wishlist is empty!\n\nUse `/addwishlist` to add products.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="📋 Your Wishlist",
                description=f"You have {len(wishlist)} item(s) in your wishlist:",
                color=discord.Color.purple()
            )
            
            # Show first 10 items
            for item in wishlist[:10]:
                product_name = item.get("variant_name", "Unknown Product")
                price_cents = item.get("price_cents", 0)
                price = format_usd(price_cents)
                product_id = item.get("product_id")
                
                embed.add_field(
                    name=f"🛍️ {product_name}",
                    value=f"Price: {price}\nID: {product_id}",
                    inline=True
                )
            
            if len(wishlist) > 10:
                embed.set_footer(text=f"... and {len(wishlist) - 10} more items")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error viewing wishlist: {e}")
            await interaction.followup.send(
                "❌ Error loading wishlist. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="addwishlist", description="Add a product to your wishlist")
    @app_commands.describe(product_id="The product ID to add")
    async def add_wishlist_command(self, interaction: discord.Interaction, product_id: int):
        """Add product to wishlist."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if product exists
            product = await self.bot.db.get_product(product_id)
            if not product:
                await interaction.followup.send(
                    f"❌ Product with ID {product_id} not found.",
                    ephemeral=True
                )
                return
            
            # Check if already in wishlist
            if await self.bot.db.is_in_wishlist(interaction.user.id, product_id):
                await interaction.followup.send(
                    "ℹ️ This product is already in your wishlist!",
                    ephemeral=True
                )
                return
            
            # Add to wishlist
            success = await self.bot.db.add_to_wishlist(interaction.user.id, product_id)
            
            if success:
                product_name = product.get("variant_name", "Product")
                await interaction.followup.send(
                    f"✅ Added **{product_name}** to your wishlist!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to add product to wishlist. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error adding to wishlist: {e}")
            await interaction.followup.send(
                "❌ Error adding product to wishlist. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="removewishlist", description="Remove a product from your wishlist")
    @app_commands.describe(product_id="The product ID to remove")
    async def remove_wishlist_command(self, interaction: discord.Interaction, product_id: int):
        """Remove product from wishlist."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if in wishlist
            if not await self.bot.db.is_in_wishlist(interaction.user.id, product_id):
                await interaction.followup.send(
                    "ℹ️ This product is not in your wishlist.",
                    ephemeral=True
                )
                return
            
            # Remove from wishlist
            success = await self.bot.db.remove_from_wishlist(interaction.user.id, product_id)
            
            if success:
                await interaction.followup.send(
                    f"✅ Removed product {product_id} from your wishlist!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to remove product from wishlist. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error removing from wishlist: {e}")
            await interaction.followup.send(
                "❌ Error removing product from wishlist. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the Wishlist cog."""
    await bot.add_cog(WishlistCog(bot))
    logger.info("Loaded extension: cogs.wishlist")

