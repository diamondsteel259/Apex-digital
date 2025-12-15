"""Supplier API product import system with automatic categorization and markup."""

from __future__ import annotations

import logging
from typing import Optional, Dict, List
import json

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.supplier_apis import (
    SupplierAPI, SupplierProduct, get_supplier_api
)
from apex_core.utils import create_embed, format_usd
from apex_core.utils.admin_checks import admin_only
from apex_core.logger import get_logger

logger = get_logger()


class SupplierImportCog(commands.Cog):
    """Commands for importing products from supplier APIs."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.suppliers: Dict[str, SupplierAPI] = {}
        self._load_suppliers()
    
    def _load_suppliers(self) -> None:
        """Load configured suppliers."""
        # Default suppliers from user config
        suppliers_config = {
            "nicesmmpanel": {
                "api_key": "728484539585e93d6f0d71213444f3d6",
                "api_url": "https://nicesmmpanel.com/api/v2",
                "type": "nicesmmpanel"
            },
            "justanotherpanel": {
                "api_key": "fd7b95ab0a9d51a2f35d78e51e1d4d24",
                "api_url": "https://justanotherpanel.com/api/v2",
                "type": "justanotherpanel"
            },
            "magicsmm": {
                "api_key": "525556d660ed4f65923bacdbee65faac0f8571b73b0e74509f8fa59562f262de",
                "api_url": "https://magicsmm.com/api",
                "type": "magicsmm"
            },
            "platimarket": {
                "api_key": "217D2D4922AB457096EBFC649489E575",
                "api_url": "https://plati.market/api",
                "type": "platimarket"
            },
            "kinguin": {
                "api_key": "b3e99f3b3fcd1c61ba5b597b45aa9440",
                "api_url": "https://api.kinguin.net/v1",
                "type": "kinguin"
            },
        }
        
        for name, config in suppliers_config.items():
            try:
                api = get_supplier_api(config["type"], config["api_key"])
                if api:
                    self.suppliers[name] = api
                    logger.info(f"Loaded supplier: {name}")
            except Exception as e:
                logger.error(f"Failed to load supplier {name}: {e}")
    
    def _calculate_price_with_markup(self, supplier_price_cents: int, markup_percent: float) -> int:
        """Calculate final price with markup."""
        markup_multiplier = 1 + (markup_percent / 100)
        return int(supplier_price_cents * markup_multiplier)
    
    def _categorize_product(self, supplier_product: SupplierProduct) -> tuple[str, str, str]:
        """Auto-categorize product based on supplier data.
        
        Returns:
            (main_category, sub_category, service_name)
        """
        category = supplier_product.category or "Uncategorized"
        subcategory = supplier_product.subcategory or supplier_product.service_type or "General"
        name = supplier_product.name
        
        # Map common SMM categories
        category_mapping = {
            "instagram": "Instagram",
            "tiktok": "TikTok",
            "youtube": "YouTube",
            "twitter": "Twitter",
            "facebook": "Facebook",
            "telegram": "Telegram",
            "discord": "Discord",
            "twitch": "Twitch",
            "spotify": "Spotify",
            "soundcloud": "SoundCloud",
            "pinterest": "Pinterest",
            "linkedin": "LinkedIn",
            "reddit": "Reddit",
        }
        
        # Try to detect platform from category or name
        category_lower = category.lower()
        name_lower = name.lower()
        
        main_category = "Uncategorized"
        for platform, mapped in category_mapping.items():
            if platform in category_lower or platform in name_lower:
                main_category = mapped
                break
        
        # If category looks like a platform name, use it directly
        if category in category_mapping.values():
            main_category = category
        
        # Determine sub-category from service type or name
        sub_category = subcategory
        if not sub_category or sub_category == "Default":
            # Try to infer from name
            if "follower" in name_lower:
                sub_category = "Followers"
            elif "like" in name_lower:
                sub_category = "Likes"
            elif "view" in name_lower:
                sub_category = "Views"
            elif "comment" in name_lower:
                sub_category = "Comments"
            elif "share" in name_lower:
                sub_category = "Shares"
            else:
                sub_category = "General"
        
        # Service name is the product name
        service_name = name
        
        return main_category, sub_category, service_name
    
    async def _import_product(
        self, 
        supplier_product: SupplierProduct, 
        markup_percent: float,
        supplier_api_url: str
    ) -> Optional[int]:
        """Import a single product from supplier.
        
        Returns:
            Product ID if successful, None otherwise
        """
        try:
            # Calculate price with markup
            final_price_cents = self._calculate_price_with_markup(
                supplier_product.price_cents, 
                markup_percent
            )
            
            # Auto-categorize
            main_category, sub_category, service_name = self._categorize_product(supplier_product)
            
            # Create product in database
            product_id = await self.bot.db.create_product(
                main_category=main_category,
                sub_category=sub_category,
                service_name=service_name,
                variant_name=supplier_product.name,
                price_cents=final_price_cents,
                additional_info=supplier_product.description or f"Imported from {supplier_product.supplier_name}",
                supplier_id=supplier_product.supplier_id,
                supplier_name=supplier_product.supplier_name,
                supplier_service_id=supplier_product.service_id,
                supplier_price_cents=supplier_product.price_cents,
                markup_percent=markup_percent,
                supplier_api_url=supplier_api_url,
            )
            
            logger.info(
                f"Imported product | ID: {product_id} | Supplier: {supplier_product.supplier_name} | "
                f"Service: {supplier_product.service_id} | Price: {supplier_product.price_cents} -> {final_price_cents} cents"
            )
            
            return product_id
            
        except Exception as e:
            logger.error(f"Error importing product {supplier_product.name}: {e}", exc_info=True)
            return None
    
    @app_commands.command(name="importsupplier", description="Import products from supplier API (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(
        supplier="Supplier name",
        markup="Markup percentage (e.g., 20 for 20%)",
        category_filter="Only import products from this category (optional)"
    )
    async def import_supplier(
        self,
        interaction: discord.Interaction,
        supplier: str,
        markup: float = 20.0,
        category_filter: Optional[str] = None
    ) -> None:
        """Import products from a supplier API."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Get supplier API
        supplier_lower = supplier.lower().replace(' ', '')
        supplier_api = self.suppliers.get(supplier_lower)
        
        if not supplier_api:
            await interaction.followup.send(
                f"❌ Supplier '{supplier}' not found. Available suppliers: {', '.join(self.suppliers.keys())}",
                ephemeral=True
            )
            return
        
        # Store progress message for editing (ephemeral thinking responses can't be edited)
        progress_message = None
        
        try:
            # Fetch services from supplier
            progress_embed = create_embed(
                title="📥 Importing Products",
                description=f"Fetching products from **{supplier_api.supplier_name}**...",
                color=discord.Color.blue(),
            )
            progress_message = await interaction.followup.send(embed=progress_embed, ephemeral=True, wait=True)
            
            logger.info(f"📥 Starting product import | Supplier: {supplier_api.supplier_name} | Markup: {markup}%")
            
            supplier_products = await supplier_api.get_services()
            
            logger.info(f"📦 Fetched {len(supplier_products) if supplier_products else 0} products from {supplier_api.supplier_name}")
            
            if not supplier_products:
                if progress_message:
                    await progress_message.edit(
                        embed=create_embed(
                            title="❌ Import Failed",
                            description=f"No products found from {supplier_api.supplier_name}",
                            color=discord.Color.red(),
                        )
                    )
                else:
                    await interaction.followup.send(
                        embed=create_embed(
                            title="❌ Import Failed",
                            description=f"No products found from {supplier_api.supplier_name}",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True
                    )
                logger.warning(f"⚠️  No products found from {supplier_api.supplier_name}")
                return
            
            # Filter by category if specified
            if category_filter:
                supplier_products = [
                    p for p in supplier_products 
                    if category_filter.lower() in (p.category or "").lower()
                ]
                logger.info(f"🔍 Filtered to {len(supplier_products)} products in category: {category_filter}")
            
            # Import products
            imported = 0
            skipped = 0
            errors = 0
            
            progress_embed.description = (
                f"Importing {len(supplier_products)} products...\n"
                f"Markup: {markup}%\n\n"
                f"Progress: 0/{len(supplier_products)}"
            )
            # Update progress message if we have one, otherwise send new one
            if progress_message:
                try:
                    await progress_message.edit(embed=progress_embed)
                except (discord.NotFound, discord.HTTPException):
                    progress_message = await interaction.followup.send(embed=progress_embed, ephemeral=True, wait=True)
            else:
                progress_message = await interaction.followup.send(embed=progress_embed, ephemeral=True, wait=True)
            
            for i, supplier_product in enumerate(supplier_products, 1):
                try:
                    # Check if product already exists (by supplier service ID)
                    existing = await self.bot.db.get_product_by_supplier_service(
                        supplier_product.supplier_id,
                        supplier_product.service_id
                    )
                    
                    if existing:
                        skipped += 1
                        continue
                    
                    product_id = await self._import_product(
                        supplier_product,
                        markup,
                        supplier_api.api_url
                    )
                    
                    if product_id:
                        imported += 1
                    else:
                        errors += 1
                    
                    # Update progress every 10 products
                    if i % 10 == 0 or i == len(supplier_products):
                        progress_embed.description = (
                            f"Importing {len(supplier_products)} products...\n"
                            f"Markup: {markup}%\n\n"
                            f"Progress: {i}/{len(supplier_products)}\n"
                            f"✅ Imported: {imported} | ⏭️ Skipped: {skipped} | ❌ Errors: {errors}"
                        )
                        if progress_message:
                            try:
                                await progress_message.edit(embed=progress_embed)
                            except (discord.NotFound, discord.HTTPException):
                                logger.warning("Progress message was deleted, continuing import...")
                        logger.info(f"📊 Import progress: {i}/{len(supplier_products)} | Imported: {imported} | Skipped: {skipped} | Errors: {errors}")
                        
                except Exception as e:
                    logger.error(f"Error importing product: {e}", exc_info=True)
                    errors += 1
            
            # Send status update
            try:
                status_cog = self.bot.get_cog("BotStatusCog")
                if status_cog:
                    await status_cog.send_status_update(
                        "import",
                        f"Product import complete: {imported} imported, {skipped} skipped, {errors} errors from {supplier_api.supplier_name}",
                        discord.Color.green()
                    )
            except Exception as e:
                logger.error(f"Failed to send status update: {e}")
            
            # Final summary
            summary_embed = create_embed(
                title="✅ Import Complete",
                description=(
                    f"**Supplier:** {supplier_api.supplier_name}\n"
                    f"**Total Products:** {len(supplier_products)}\n"
                    f"**Markup:** {markup}%\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✅ **Imported:** {imported}\n"
                    f"⏭️ **Skipped:** {skipped} (already exist)\n"
                    f"❌ **Errors:** {errors}"
                ),
                color=discord.Color.green(),
            )
            
            # Edit the progress message we sent
            if progress_message:
                try:
                    await progress_message.edit(embed=summary_embed)
                except (discord.NotFound, discord.HTTPException):
                    await interaction.followup.send(embed=summary_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=summary_embed, ephemeral=True)
            
            logger.info(
                f"✅ Supplier import complete | Supplier: {supplier_api.supplier_name} | "
                f"Imported: {imported} | Skipped: {skipped} | Errors: {errors}"
            )
            
        except Exception as e:
            logger.error(f"❌ Error importing from supplier: {e}", exc_info=True)
            try:
                if progress_message:
                    await progress_message.edit(
                        embed=create_embed(
                            title="❌ Import Failed",
                            description=f"Error: {str(e)}",
                            color=discord.Color.red(),
                        )
                    )
                else:
                    await interaction.followup.send(
                        embed=create_embed(
                            title="❌ Import Failed",
                            description=f"Error: {str(e)}",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True
                    )
            except Exception as edit_error:
                logger.error(f"Failed to send error message: {edit_error}")
                await interaction.followup.send(
                    embed=create_embed(
                        title="❌ Import Failed",
                        description=f"Error: {str(e)}",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True
                )
    
    @app_commands.command(name="listsuppliers", description="List configured suppliers (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    async def list_suppliers(self, interaction: discord.Interaction) -> None:
        """List all configured suppliers."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        if not self.suppliers:
            await interaction.followup.send(
                "❌ No suppliers configured.",
                ephemeral=True
            )
            return
        
        embed = create_embed(
            title="📦 Configured Suppliers",
            description=f"**Total:** {len(self.suppliers)} supplier(s)\n\n━━━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.blue(),
        )
        
        for name, api in self.suppliers.items():
            try:
                balance = await api.get_balance()
                embed.add_field(
                    name=f"🔹 {api.supplier_name}",
                    value=(
                        f"**API URL:** {api.api_url}\n"
                        f"**Balance:** ${balance:.2f}\n"
                        f"**Status:** ✅ Active"
                    ),
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name=f"🔹 {api.supplier_name}",
                    value=(
                        f"**API URL:** {api.api_url}\n"
                        f"**Status:** ❌ Error: {str(e)[:50]}"
                    ),
                    inline=False
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="supplierbalance", description="Check supplier balance (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(supplier="Supplier name")
    async def supplier_balance(
        self,
        interaction: discord.Interaction,
        supplier: str
    ) -> None:
        """Check balance for a supplier."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        supplier_lower = supplier.lower().replace(' ', '')
        supplier_api = self.suppliers.get(supplier_lower)
        
        if not supplier_api:
            await interaction.followup.send(
                f"❌ Supplier '{supplier}' not found.",
                ephemeral=True
            )
            return
        
        try:
            balance = await supplier_api.get_balance()
            
            embed = create_embed(
                title=f"💰 {supplier_api.supplier_name} Balance",
                description=f"**Current Balance:** ${balance:.2f}",
                color=discord.Color.green(),
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting supplier balance: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SupplierImportCog(bot))

