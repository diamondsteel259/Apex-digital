"""
Product Tags Management Cog

Allows admins to manage product tags for better organization and search.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.admin_checks import admin_only

logger = get_logger()


class ProductTagsCog(commands.Cog):
    """Product tags management commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="addtag", description="[Admin] Add a tag to a product")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(product_id="The product ID", tag="The tag to add")
    async def add_tag_command(self, interaction: discord.Interaction, product_id: int, tag: str):
        """Add tag to product."""
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
            
            # Add tag
            success = await self.bot.db.add_product_tag(product_id, tag)
            
            if success:
                product_name = product.get("variant_name", "Product")
                await interaction.followup.send(
                    f"✅ Added tag '{tag}' to **{product_name}**",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to add tag. It may already exist.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error adding tag: {e}")
            await interaction.followup.send(
                "❌ Error adding tag. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="removetag", description="[Admin] Remove a tag from a product")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(product_id="The product ID", tag="The tag to remove")
    async def remove_tag_command(self, interaction: discord.Interaction, product_id: int, tag: str):
        """Remove tag from product."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Remove tag
            success = await self.bot.db.remove_product_tag(product_id, tag)
            
            if success:
                await interaction.followup.send(
                    f"✅ Removed tag '{tag}' from product {product_id}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to remove tag. It may not exist.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error removing tag: {e}")
            await interaction.followup.send(
                "❌ Error removing tag. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="producttags", description="View tags for a product")
    @app_commands.describe(product_id="The product ID")
    async def product_tags_command(self, interaction: discord.Interaction, product_id: int):
        """View product tags."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            tags = await self.bot.db.get_product_tags(product_id)
            
            if not tags:
                await interaction.followup.send(
                    f"ℹ️ Product {product_id} has no tags.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title=f"🏷️ Tags for Product {product_id}",
                description=", ".join(f"`{tag}`" for tag in tags),
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting product tags: {e}")
            await interaction.followup.send(
                "❌ Error loading tags. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="searchtag", description="Search products by tag")
    @app_commands.describe(tag="The tag to search for")
    async def search_tag_command(self, interaction: discord.Interaction, tag: str):
        """Search products by tag."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            products = await self.bot.db.search_products_by_tag(tag)
            
            if not products:
                await interaction.followup.send(
                    f"❌ No products found with tag '{tag}'",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title=f"🔍 Products with tag '{tag}'",
                description=f"Found {len(products)} product(s):",
                color=discord.Color.green()
            )
            
            # Show first 10 products
            for product in products[:10]:
                name = product.get("variant_name", "Unknown")
                price_cents = product.get("price_cents", 0)
                price = f"${price_cents / 100:.2f}"
                product_id = product.get("id")
                
                embed.add_field(
                    name=f"🛍️ {name}",
                    value=f"Price: {price} | ID: {product_id}",
                    inline=False
                )
            
            if len(products) > 10:
                embed.set_footer(text=f"... and {len(products) - 10} more products")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error searching by tag: {e}")
            await interaction.followup.send(
                "❌ Error searching products. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the Product Tags cog."""
    await bot.add_cog(ProductTagsCog(bot))
    logger.info("Loaded extension: cogs.product_tags")

