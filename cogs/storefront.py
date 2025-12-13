from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import discord
from discord.ext import commands

from apex_core.rate_limiter import enforce_interaction_rate_limit
from apex_core.utils import (
    calculate_vip_tier,
    create_embed,
    format_usd,
    handle_vip_promotion,
    process_post_purchase,
    render_operating_hours,
)
from apex_core.config import PaymentMethod

from apex_core.logger import get_logger

logger = get_logger()


def _validate_payment_method(method: Any) -> tuple[bool, str]:
    """
    Validate a payment method object for completeness and correctness.
    
    Checks that the payment method has required attributes (name, instructions,
    metadata) and that they are of the correct types. Provides detailed error
    messages for debugging invalid configurations.
    
    Args:
        method: Payment method object to validate
    
    Returns:
        Tuple of (is_valid, reason_if_invalid) where reason_if_invalid is
        empty string if valid
    """
    if method is None:
        return False, "Payment method is None"
    
    # Check if it has the expected attributes
    if not hasattr(method, 'name'):
        return False, "Payment method missing 'name' attribute"
    
    if not hasattr(method, 'instructions'):
        return False, "Payment method missing 'instructions' attribute"
    
    # Check name
    name = getattr(method, 'name', None)
    if not name or not isinstance(name, str):
        return False, f"Payment method name is invalid: {name!r}"
    
    # Check instructions
    instructions = getattr(method, 'instructions', None)
    if not instructions or not isinstance(instructions, str):
        return False, f"Payment method '{name}' has invalid instructions: {instructions!r}"
    
    # Check metadata
    metadata = getattr(method, 'metadata', None)
    if metadata is None:
        return False, f"Payment method '{name}' has None metadata"
    
    if not isinstance(metadata, dict):
        return False, f"Payment method '{name}' metadata is not a dict: {type(metadata).__name__}"
    
    return True, ""


def _safe_get_metadata(metadata: Any, key: str, default: Any = None) -> Any:
    """
    Safely retrieve metadata value with defensive programming.
    
    Returns the default value if metadata is not a dict or the key is not found.
    This prevents crashes when metadata is None or malformed.
    
    Args:
        metadata: Metadata object (should be dict, but defensive access allows any type)
        key: Key to look up in metadata
        default: Default value if key not found or metadata is invalid (default: None)
    
    Returns:
        Metadata value if found, otherwise the default value
    """
    if not isinstance(metadata, dict):
        return default
    
    return metadata.get(key, default)


def _build_payment_embed(
    product: dict[str, Any],
    user: discord.User | discord.Member,
    final_price_cents: int,
    user_balance_cents: int,
    payment_methods: Sequence[PaymentMethod],
) -> discord.Embed:
    """
    Build comprehensive payment options embed with available payment methods.
    
    Validates and displays all enabled payment methods with method-specific
    details (wallet balance, Binance Pay ID, PayPal email, etc.). Invalid or
    disabled payment methods are skipped with logging.
    
    Args:
        product: Product dictionary containing variant_name, service_name, start_time
        user: Discord user or member initiating the purchase
        final_price_cents: Final price in cents
        user_balance_cents: User's wallet balance in cents
        payment_methods: Sequence of available payment methods to display
    
    Returns:
        Configured Discord Embed with payment options and method-specific details
    """
    variant_name = product.get("variant_name", "Unknown")
    service_name = product.get("service_name", "Unknown")
    start_time = product.get("start_time", "N/A")
    
    embed = create_embed(
        title=f"💳 Payment Options for {variant_name}",
        description=(
            f"**Service:** {service_name}\n"
            f"**Variant:** {variant_name}\n"
            f"**Price:** {format_usd(final_price_cents)}\n"
            f"**ETA:** {start_time}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.gold(),
    )
    
    # Add enabled payment methods with validation
    enabled_methods = []
    
    for method in payment_methods:
        # Validate the payment method first
        is_valid, reason = _validate_payment_method(method)
        if not is_valid:
            logger.warning(f"Skipping invalid payment method: {reason}")
            continue
        
        # Check if method is enabled (with defensive metadata access)
        is_enabled = _safe_get_metadata(method.metadata, "is_enabled", True)
        if is_enabled is False:
            continue
            
        enabled_methods.append(method)
    
    if enabled_methods:
        methods_text = "**Available Payment Methods:**\n\n"
        
        for method in enabled_methods:
            emoji = method.emoji or "💰"
            name = method.name
            instructions = method.instructions
            metadata = method.metadata
            
            methods_text += f"{emoji} **{name}**\n"
            methods_text += f"{instructions}\n"
            
            # Add specific metadata based on payment method with defensive access
            if name == "Wallet":
                sufficient = user_balance_cents >= final_price_cents
                status = "✅ Sufficient" if sufficient else "❌ Insufficient"
                methods_text += f"• Current Balance: {format_usd(user_balance_cents)} ({status})\n"
                methods_text += f"• Required: {format_usd(final_price_cents)}\n"
            
            elif name == "Binance":
                pay_id = _safe_get_metadata(metadata, "pay_id")
                if pay_id:
                    methods_text += f"• **Pay ID:** `{pay_id}`\n"
                
                warning = _safe_get_metadata(metadata, "warning")
                if warning:
                    methods_text += f"• {warning}\n"
                
                url = _safe_get_metadata(metadata, "url")
                if url:
                    methods_text += f"• [Open Binance Pay]({url})\n"
            
            elif name == "PayPal":
                payout_email = _safe_get_metadata(metadata, "payout_email")
                if payout_email:
                    methods_text += f"• **Email:** {payout_email}\n"
                
                payment_link = _safe_get_metadata(metadata, "payment_link")
                if payment_link:
                    methods_text += f"• [Send Payment]({payment_link})\n"
            
            elif name == "Tip.cc":
                command = _safe_get_metadata(metadata, "command")
                if command:
                    cmd = command.replace("{amount}", format_usd(final_price_cents))
                    methods_text += f"• **Command:** `{cmd}`\n"
                
                url = _safe_get_metadata(metadata, "url")
                if url:
                    methods_text += f"• [Visit Tip.cc]({url})\n"
                
                warning = _safe_get_metadata(metadata, "warning")
                if warning:
                    methods_text += f"• {warning}\n"
            
            elif name == "CryptoJar":
                command = _safe_get_metadata(metadata, "command")
                if command:
                    cmd = command.replace("{amount}", format_usd(final_price_cents))
                    methods_text += f"• **Command:** `{cmd}`\n"
                
                url = _safe_get_metadata(metadata, "url")
                if url:
                    methods_text += f"• [Visit CryptoJar]({url})\n"
                
                warning = _safe_get_metadata(metadata, "warning")
                if warning:
                    methods_text += f"• {warning}\n"
            
            elif name == "Crypto" and _safe_get_metadata(metadata, "type") == "custom_networks":
                networks = _safe_get_metadata(metadata, "networks")
                if networks and isinstance(networks, (list, tuple)):
                    networks_str = ", ".join(str(n) for n in networks)
                    methods_text += f"• **Available Networks:** {networks_str}\n"
                
                note = _safe_get_metadata(metadata, "note")
                if note:
                    methods_text += f"• {note}\n"
            
            methods_text += "\n"
        
        embed.add_field(
            name="",
            value=methods_text,
            inline=False,
        )
    
    # Add footer with additional info
    embed.add_field(
        name="ℹ️ Important Information",
        value=(
            "• Once payment is confirmed by staff, you'll receive access\n"
            "• Need help? Contact our support team\n"
            "• Upload payment proof using the button below"
        ),
        inline=False,
    )
    
    embed.set_footer(text="Apex Core • Payment System")
    embed.set_thumbnail(url=user.display_avatar.url)
    
    return embed


def _product_display_name(product: Any) -> str:
    """
    Extract display name from a product object using multiple strategies.
    
    Attempts to retrieve a product name by trying variant_name, service_name,
    and name attributes/keys in order. Falls back to "Unknown Product" if
    the product is None or no name can be determined.
    
    Args:
        product: Product object with get() method and/or subscript access
    
    Returns:
        Product display name or "Unknown Product" if not found
    """
    if not product:
        return "Unknown Product"

    getter = getattr(product, "get", None)
    getitem = getattr(product, "__getitem__", None)

    for key in ("variant_name", "service_name", "name"):
        value = None

        if callable(getter):
            try:
                value = getter(key)
            except Exception:
                value = None

        if value is None and callable(getitem):
            try:
                value = getitem(key)
            except (KeyError, TypeError, IndexError):
                value = None

        if value:
            return str(value)

    return "Unknown Product"


# ============================================================================
# LEVEL 1: Main Category Selection (Persistent)
# ============================================================================

class CategorySelect(discord.ui.Select["CategorySelectView"]):
    def __init__(self, categories: list[str]) -> None:
        options = [
            discord.SelectOption(
                label=category[:100],
                value=category[:100],
            )
            for category in categories[:25]
        ]
        
        if not options:
            options = [discord.SelectOption(label="No categories available", value="none")]
        
        super().__init__(
            placeholder="Select Category (Scroll down for more)",
            options=options,
            custom_id="storefront:category_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info(
            "Category selected: %s | User: %s (%s) | Guild: %s | Channel: %s",
            self.values[0] if self.values else "none",
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
            interaction.channel_id,
        )
        
        if self.values[0] == "none":
            logger.debug("No categories available for user %s", interaction.user.id)
            await interaction.response.send_message(
                "No products available at this time.",
                ephemeral=True,
            )
            return
        
        main_category = self.values[0]
        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            logger.error("StorefrontCog not loaded when category selected by user %s", interaction.user.id)
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return
        
        logger.debug("Showing sub-categories for category: %s | User: %s", main_category, interaction.user.id)
        await cog._show_sub_categories(interaction, main_category)


class CategorySelectView(discord.ui.View):
    PAGE_SIZE = 25

    def __init__(self, categories: list[str], page: int = 0) -> None:
        super().__init__(timeout=None)
        self.categories = categories
        self.page = page
        self.total_pages = max(1, (len(categories) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._build_view()

    def _current_slice(self) -> list[str]:
        start = self.page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        return self.categories[start:end]

    def _build_view(self) -> None:
        self.add_item(CategorySelect(self._current_slice()))
        if self.total_pages > 1:
            self.add_item(CategoryPaginatorButton(direction="previous"))
            self.add_item(CategoryPaginatorButton(direction="next"))


class CategoryPaginatorButton(discord.ui.Button["CategorySelectView"]):
    def __init__(self, direction: str) -> None:
        label = "◀️ Previous" if direction == "previous" else "Next ▶️"
        custom_id = f"storefront:category_page:{direction}"
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=custom_id)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction) -> None:
        # Apply rate limiting to prevent spam
        allowed = await enforce_interaction_rate_limit(
            interaction,
            command_key="storefront_pagination",
            cooldown=30,
            max_uses=10,
            per="user",
            admin_bypass=True,
            config_key="storefront_pagination",
        )

        if not allowed:
            # Rate limit message already sent by enforce_interaction_rate_limit
            return

        logger.info(
            "Category pagination: %s | User: %s (%s) | Guild: %s",
            self.direction,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
        )

        view = self.view
        if not isinstance(view, CategorySelectView):
            logger.warning("Invalid view type for category pagination | User: %s", interaction.user.id)
            await interaction.response.send_message(
                "Pagination unavailable. Please run the setup command again.",
                ephemeral=True,
            )
            return
        
        total_pages = view.total_pages
        if total_pages <= 1:
            logger.debug("Single page, no pagination needed | User: %s", interaction.user.id)
            await interaction.response.defer()
            return
        
        if self.direction == "next":
            new_page = (view.page + 1) % total_pages
        else:
            new_page = (view.page - 1) % total_pages
        
        logger.debug("Paginating categories: page %s -> %s | User: %s", view.page, new_page, interaction.user.id)
        new_view = CategorySelectView(view.categories, page=new_page)
        await interaction.response.edit_message(view=new_view)


# ============================================================================
# LEVEL 2: Sub Category Selection (Ephemeral)
# ============================================================================

class SubCategorySelect(discord.ui.Select["SubCategorySelectView"]):
    def __init__(self, main_category: str, sub_categories: list[str]) -> None:
        self.main_category = main_category
        options = [
            discord.SelectOption(
                label=sub_cat[:100],
                value=sub_cat[:100],
            )
            for sub_cat in sub_categories[:25]
        ]
        
        super().__init__(
            placeholder="Select Sub-Category...",
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sub_category = self.values[0]
        logger.info(
            "Sub-category selected: %s > %s | User: %s (%s) | Guild: %s",
            self.main_category,
            sub_category,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
        )
        
        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            logger.error("StorefrontCog not loaded when sub-category selected by user %s", interaction.user.id)
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return
        
        logger.debug("Fetching products for: %s > %s | User: %s", self.main_category, sub_category, interaction.user.id)
        await cog._show_products(interaction, self.main_category, sub_category)


class SubCategorySelectView(discord.ui.View):
    def __init__(self, main_category: str, sub_categories: list[str]) -> None:
        super().__init__(timeout=120)
        self.add_item(SubCategorySelect(main_category, sub_categories))


# ============================================================================
# LEVEL 3: Product Display with Ticket Button (Ephemeral)
# ============================================================================

class VariantSelect(discord.ui.Select["ProductDisplayView"]):
    def __init__(self, products: list[dict]) -> None:
        options: list[discord.SelectOption] = []
        for index, product in enumerate(products[:25]):
            option = discord.SelectOption(
                label=product["variant_name"][:100],
                value=str(product["id"]),
                description=f"{format_usd(product['price_cents'])}"[:100],
                default=index == 0,
            )
            options.append(option)

        super().__init__(
            placeholder="Select a service to include in your ticket...",
            options=options,
            custom_id="storefront:variant_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        selected_id = int(self.values[0])
        if isinstance(view, ProductDisplayView):
            view.selected_product_id = selected_id
        
        logger.info(
            "Product variant selected: ID=%s | User: %s (%s) | Guild: %s",
            selected_id,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
        )
        await interaction.response.defer()


class OpenTicketButton(discord.ui.Button["ProductDisplayView"]):
    def __init__(self, main_category: str, sub_category: str) -> None:
        super().__init__(
            label="📩 Open Ticket",
            style=discord.ButtonStyle.primary,
        )
        self.main_category = main_category
        self.sub_category = sub_category

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info(
            "Open ticket button clicked | Category: %s > %s | User: %s (%s) | Guild: %s",
            self.main_category,
            self.sub_category,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
        )
        
        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            logger.error("StorefrontCog not loaded when open ticket clicked by user %s", interaction.user.id)
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return
        
        view = self.view
        selected_product_id = None
        if isinstance(view, ProductDisplayView):
            selected_product_id = view.selected_product_id
        
        if selected_product_id is None:
            logger.warning("No product selected when opening ticket | User: %s", interaction.user.id)
            await interaction.response.send_message(
                "Please select a service before opening a ticket.",
                ephemeral=True,
            )
            return
        
        logger.debug("Opening ticket for product ID=%s | User: %s", selected_product_id, interaction.user.id)
        await cog._handle_open_ticket(
            interaction,
            self.main_category,
            self.sub_category,
            selected_product_id,
        )


class ProductDisplayView(discord.ui.View):
    def __init__(self, products: list[dict], main_category: str, sub_category: str) -> None:
        super().__init__(timeout=120)
        self.selected_product_id: int | None = products[0]["id"] if products else None
        if products:
            self.add_item(VariantSelect(products))
        self.add_item(OpenTicketButton(main_category, sub_category))


# ============================================================================
# Payment Method Buttons (for ticket channel)
# ============================================================================

class WalletPaymentButton(discord.ui.Button["PaymentOptionsView"]):
    def __init__(
        self,
        product_id: int,
        final_price_cents: int,
        user_balance_cents: int,
        sufficient: bool,
    ) -> None:
        style = discord.ButtonStyle.success if sufficient else discord.ButtonStyle.danger
        label = "💳 Pay with Wallet"
        super().__init__(
            label=label,
            style=style,
            disabled=not sufficient,
        )
        self.product_id = product_id
        self.final_price_cents = final_price_cents
        self.user_balance_cents = user_balance_cents

    async def callback(self, interaction: discord.Interaction) -> None:
        from bot import ApexCoreBot
        
        logger.info(
            "Wallet payment initiated | Product ID: %s | Price: %s cents | User: %s (%s) | Guild: %s | Channel: %s",
            self.product_id,
            self.final_price_cents,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
            interaction.channel_id,
        )
        
        if not isinstance(interaction.client, ApexCoreBot):
            logger.error("Invalid bot client type for wallet payment | User: %s", interaction.user.id)
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True
            )
            return
        
        bot: ApexCoreBot = interaction.client
        cog: StorefrontCog = bot.get_cog("StorefrontCog")  # type: ignore
        
        if not cog:
            logger.error("StorefrontCog not loaded for wallet payment | User: %s", interaction.user.id)
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return
        
        allowed = await enforce_interaction_rate_limit(
            interaction,
            command_key="wallet_payment",
            cooldown=300,
            max_uses=3,
            per="user",
            config_key="wallet_payment",
        )
        if not allowed:
            logger.warning("Rate limit exceeded for wallet payment | User: %s", interaction.user.id)
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        logger.debug("Fetching product: ID=%s | User: %s", self.product_id, interaction.user.id)
        product = await bot.db.get_product(self.product_id)
        if not product or not product["is_active"]:
            logger.warning("Product not available: ID=%s | User: %s", self.product_id, interaction.user.id)
            await interaction.followup.send(
                "This product is no longer available.", ephemeral=True
            )
            return
        
        logger.debug("Product found: %s | User: %s", _product_display_name(product), interaction.user.id)
        
        logger.debug("Fetching user balance | User: %s", interaction.user.id)
        user_row = await bot.db.get_user(interaction.user.id)
        if not user_row or user_row["wallet_balance_cents"] < self.final_price_cents:
            current_balance = user_row['wallet_balance_cents'] if user_row else 0
            logger.warning(
                "Insufficient balance | User: %s | Required: %s cents | Available: %s cents",
                interaction.user.id,
                self.final_price_cents,
                current_balance,
            )
            await interaction.followup.send(
                f"Insufficient balance. You need {format_usd(self.final_price_cents)} "
                f"but only have {format_usd(current_balance)}.",
                ephemeral=True,
            )
            return
        
        product_name = _product_display_name(product)
        
        try:
            vip_tier = calculate_vip_tier(
                user_row["total_lifetime_spent_cents"], bot.config
            )
            discount_percent = await cog._calculate_discount(
                interaction.user.id, self.product_id, vip_tier
            )
            
            logger.info(
                "Processing wallet payment | User: %s | Product: %s | VIP Tier: %s | Discount: %s%%",
                interaction.user.id,
                product_name,
                vip_tier.name if vip_tier else "None",
                discount_percent,
            )
            
            order_metadata = json.dumps({
                "product_name": product_name,
                "base_price_cents": product["price_cents"],
                "discount_percent": discount_percent,
                "vip_tier": vip_tier.name if vip_tier else None,
            })
            
            old_balance = user_row["wallet_balance_cents"]
            order_id, new_balance = await bot.db.purchase_product(
                user_discord_id=interaction.user.id,
                product_id=self.product_id,
                price_paid_cents=self.final_price_cents,
                discount_applied_percent=discount_percent,
                order_metadata=order_metadata,
            )
            
            logger.info(
                "Wallet payment successful | User: %s | Order ID: %s | Amount: %s cents | Balance: %s -> %s cents",
                interaction.user.id,
                order_id,
                self.final_price_cents,
                old_balance,
                new_balance,
            )
            
            # Log to wallet channel
            if hasattr(bot.config, 'logging_channels'):
                wallet_log_id = getattr(bot.config.logging_channels, 'wallet', None)
                if wallet_log_id:
                    wallet_channel = interaction.guild.get_channel(wallet_log_id)
                    if isinstance(wallet_channel, discord.TextChannel):
                        try:
                            await wallet_channel.send(
                                f"💰 **Wallet Payment**\n"
                                f"User: {interaction.user.mention}\n"
                                f"Product: {product_name}\n"
                                f"Amount: {format_usd(self.final_price_cents)}\n"
                                f"New Balance: {format_usd(new_balance)}\n"
                                f"Order ID: {order_id}"
                            )
                        except Exception as e:
                            logger.error("Failed to log wallet payment to channel: %s", e)
            
            success_embed = create_embed(
                title="Payment Confirmed!",
                description=(
                    f"✅ Payment successful via Wallet\n\n"
                    f"**Product:** {product_name}\n"
                    f"**Amount Paid:** {format_usd(self.final_price_cents)}\n"
                    f"**New Balance:** {format_usd(new_balance)}\n"
                    f"**Order ID:** #{order_id}\n\n"
                    "A staff member will process your order shortly."
                ),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            if isinstance(interaction.channel, discord.TextChannel):
                await interaction.channel.send(
                    f"✅ {interaction.user.mention} has paid {format_usd(self.final_price_cents)} via Wallet. Order ID: #{order_id}"
                )
            
        except ValueError as e:
            logger.error(
                "Wallet payment validation error | User: %s | Product: %s | Error: %s",
                interaction.user.id,
                self.product_id,
                str(e),
                exc_info=True,
            )
            await interaction.followup.send(
                f"Payment failed: {str(e)}", ephemeral=True
            )
        except Exception as e:
            logger.error(
                "Wallet payment exception | User: %s | Product: %s | Error: %s",
                interaction.user.id,
                self.product_id,
                str(e),
                exc_info=True,
            )
            await interaction.followup.send(
                "An error occurred while processing your payment. Please contact support.",
                ephemeral=True,
            )


class PaymentProofUploadButton(discord.ui.Button["PaymentOptionsView"]):
    def __init__(self) -> None:
        super().__init__(
            label="💾 Upload Payment Proof",
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info(
            "Payment proof upload requested | User: %s (%s) | Guild: %s | Channel: %s",
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
            interaction.channel_id,
        )
        await interaction.response.send_message(
            "📎 **Upload Your Payment Proof**\n\n"
            "Please upload a screenshot or proof of your payment in this channel.\n\n"
            "Once uploaded, our staff will verify it and confirm your order.\n"
            "You'll receive a DM once your payment is confirmed!",
            ephemeral=True,
        )


class RequestCryptoAddressButton(discord.ui.Button["PaymentOptionsView"]):
    def __init__(self, available_networks: list[str]) -> None:
        super().__init__(
            label="₿ Request Crypto Address",
            style=discord.ButtonStyle.secondary,
        )
        self.available_networks = available_networks

    async def callback(self, interaction: discord.Interaction) -> None:
        networks_text = ", ".join(self.available_networks)
        
        logger.info(
            "Crypto address requested | Networks: %s | User: %s (%s) | Guild: %s | Channel: %s",
            networks_text,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
            interaction.channel_id,
        )
        
        await interaction.response.send_message(
            f"**Crypto Payment Request Sent**\n\n"
            f"Available networks: {networks_text}\n\n"
            "An admin will provide you with the appropriate crypto address in this channel.\n"
            "Please wait for their response.",
            ephemeral=True,
        )
        
        if isinstance(interaction.channel, discord.TextChannel):
            logger.debug("Notifying staff of crypto address request | Channel: %s | User: %s", interaction.channel_id, interaction.user.id)
            await interaction.channel.send(
                f"🔔 {interaction.user.mention} is requesting a crypto address.\n"
                f"Available networks: {networks_text}\n\n"
                "**Staff:** Please provide the appropriate crypto address for this user."
            )


class PaymentOptionsView(discord.ui.View):
    def __init__(
        self,
        product_id: int,
        final_price_cents: int,
        user_balance_cents: int,
        payment_methods: list,
    ) -> None:
        super().__init__(timeout=None)
        
        # Check if wallet is enabled and add wallet button if user has sufficient balance
        has_wallet_method = any(
            m.name == "Wallet" and m.metadata.get("type") == "internal" 
            for m in payment_methods
        )
        
        if has_wallet_method:
            sufficient = user_balance_cents >= final_price_cents
            self.add_item(WalletPaymentButton(
                product_id=product_id,
                final_price_cents=final_price_cents,
                user_balance_cents=user_balance_cents,
                sufficient=sufficient,
            ))
        
        # Add payment proof upload button
        self.add_item(PaymentProofUploadButton())
        
        # Check if crypto method is enabled and add crypto address request button
        crypto_method = next(
            (m for m in payment_methods if m.name == "Crypto" and m.metadata.get("type") == "custom_networks"),
            None
        )
        if crypto_method:
            networks = crypto_method.metadata.get("networks", ["Bitcoin", "Ethereum", "Solana"])
            self.add_item(RequestCryptoAddressButton(networks))


# ============================================================================
# Legacy Components (kept for backward compatibility)
# ============================================================================

class ProductSelect(discord.ui.Select["ProductSelectView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Select a product to view details...",
            options=[
                discord.SelectOption(
                    label="Loading products...",
                    value="loading",
                )
            ],
            custom_id="storefront:product_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        product_id = self.values[0]
        
        if product_id == "loading":
            await interaction.response.send_message(
                "Products are still loading. Please try again in a moment.",
                ephemeral=True,
            )
            return

        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return

        product = await interaction.client.db.get_product(int(product_id))  # type: ignore
        if not product or not product["is_active"]:
            await interaction.response.send_message(
                "Product not found or no longer active.", ephemeral=True
            )
            return

        user_row = await interaction.client.db.get_user(interaction.user.id)  # type: ignore
        vip_tier = None
        if user_row:
            vip_tier = calculate_vip_tier(
                user_row["total_lifetime_spent_cents"], interaction.client.config  # type: ignore
            )

        base_price_cents = product["price_cents"]
        discount_percent = await cog._calculate_discount(
            interaction.user.id, int(product_id), vip_tier
        )
        final_price_cents = int(base_price_cents * (1 - discount_percent / 100))

        # Determine the appropriate display name for the product
        product_name = _product_display_name(product)
        
        embed = create_embed(
            title=product_name,
            description=f"**Base Price:** {format_usd(base_price_cents)}\n"
            f"**Your Discount:** {discount_percent:.1f}%\n"
            f"**Final Price:** {format_usd(final_price_cents)}",
            color=discord.Color.blue(),
        )

        operating_hours_text = render_operating_hours(interaction.client.config.operating_hours)  # type: ignore
        embed.add_field(
            name="Operating Hours",
            value=operating_hours_text,
            inline=False,
        )

        view = ProductActionView(product_id=int(product_id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ProductSelectView(discord.ui.View):
    def __init__(self, products: list[dict] | None = None) -> None:
        super().__init__(timeout=None)
        select = ProductSelect()
        if products:
            select.options = [
                discord.SelectOption(
                    label=_product_display_name(product)[:100],
                    value=str(product["id"]),
                    description=f"{format_usd(product['price_cents'])} • ID: {product['id']}"[:100],
                )
                for product in products[:25]
            ]
        self.add_item(select)


class BuyButton(discord.ui.Button["ProductActionView"]):
    def __init__(self, product_id: int) -> None:
        super().__init__(
            label="Buy with Wallet",
            style=discord.ButtonStyle.green,
            custom_id=f"storefront:buy:{product_id}",
        )
        self.product_id = product_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return

        await cog._handle_purchase_initiate(interaction, self.product_id)


class TicketButton(discord.ui.Button["ProductActionView"]):
    def __init__(self, product_id: int) -> None:
        super().__init__(
            label="Open Support Ticket",
            style=discord.ButtonStyle.gray,
            custom_id=f"storefront:ticket:{product_id}",
        )
        self.product_id = product_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return

        await cog._handle_support_ticket(interaction, self.product_id)


class ProductActionView(discord.ui.View):
    def __init__(self, product_id: int) -> None:
        super().__init__(timeout=300)
        self.product_id = product_id
        self.add_item(BuyButton(product_id))
        self.add_item(TicketButton(product_id))


class PurchaseConfirmModal(discord.ui.Modal):
    def __init__(self, product_id: int, product_name: str, final_price_cents: int) -> None:
        super().__init__(title=f"Confirm Purchase: {product_name[:50]}")  # Truncate for title limit
        self.product_id = product_id
        self.product_name = product_name
        self.final_price_cents = final_price_cents

        self.confirmation = discord.ui.TextInput(
            label=f"Type 'CONFIRM' to purchase for {format_usd(final_price_cents)}",
            placeholder="CONFIRM",
            required=True,
            max_length=7,
        )
        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.confirmation.value.strip().upper() != "CONFIRM":
            await interaction.response.send_message(
                "Purchase cancelled. You must type 'CONFIRM' to proceed.",
                ephemeral=True,
            )
            return

        cog: StorefrontCog = interaction.client.get_cog("StorefrontCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Storefront cog not loaded.", ephemeral=True
            )
            return

        await cog._complete_purchase(
            interaction, self.product_id, self.product_name, self.final_price_cents
        )


class StorefrontCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.bot.add_view(ProductSelectView())
        
        categories = await self.bot.db.get_distinct_main_categories()
        if categories:
            self.bot.add_view(CategorySelectView(categories))

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

    def _is_within_operating_hours(self) -> bool:
        now = datetime.now(timezone.utc)
        hours = self.bot.config.operating_hours
        current_hour = now.hour

        if hours.start_hour_utc <= hours.end_hour_utc:
            return hours.start_hour_utc <= current_hour < hours.end_hour_utc
        else:
            return current_hour >= hours.start_hour_utc or current_hour < hours.end_hour_utc

    async def _calculate_discount(
        self, user_id: int, product_id: int, vip_tier: Optional[object]
    ) -> float:
        """Calculate total discount for a user, enforcing discount expiry.
        
        This method calculates discounts from both role-based and legacy discount systems.
        As a defensive measure, it filters out any expired discounts even though the
        database query should already exclude them, ensuring expired discounts can
        never be applied.
        """
        from apex_core.utils.roles import get_user_roles
        
        total_discount = 0.0

        # Check all applicable roles for discounts
        user_roles = await get_user_roles(user_id, self.bot.db, self.bot.config)
        for role in user_roles:
            total_discount = max(total_discount, role.discount_percent)

        # Check legacy discount system
        user_row = await self.bot.db.get_user(user_id)
        db_user_id = user_row["id"] if user_row else None

        vip_tier_name = vip_tier.name if vip_tier else None
        discounts = await self.bot.db.get_applicable_discounts(
            user_id=db_user_id,
            product_id=product_id,
            vip_tier=vip_tier_name,
        )

        for discount in discounts:
            # Defensive check: ensure discount hasn't expired
            if discount["expires_at"]:
                try:
                    from datetime import datetime
                    expires_at = datetime.fromisoformat(discount["expires_at"])
                    if expires_at < datetime.now():
                        continue  # Skip expired discount
                except (ValueError, TypeError):
                    # If we can't parse the date, skip it for safety
                    continue
            
            if discount["is_stackable"]:
                total_discount += discount["discount_percent"]
            else:
                total_discount = max(total_discount, discount["discount_percent"])

        return min(total_discount, 100.0)

    async def _show_sub_categories(
        self, interaction: discord.Interaction, main_category: str
    ) -> None:
        sub_categories = await self.bot.db.get_distinct_sub_categories(main_category)
        
        if not sub_categories:
            await interaction.response.send_message(
                f"No sub-categories found for **{main_category}**.",
                ephemeral=True,
            )
            return
        
        embed = create_embed(
            title=f"Select Sub-Category: {main_category}",
            description="Choose a sub-category to view available products.",
            color=discord.Color.blue(),
        )
        
        view = SubCategorySelectView(main_category, sub_categories)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_products(
        self, interaction: discord.Interaction, main_category: str, sub_category: str
    ) -> None:
        products = await self.bot.db.get_products_by_category(main_category, sub_category)
        
        if not products:
            await interaction.response.send_message(
                f"No products found for **{main_category} - {sub_category}**.",
                ephemeral=True,
            )
            return
        
        product_dicts = [dict(product) for product in products]
        
        embed = create_embed(
            title=f"{main_category} {sub_category} (Service Selected)",
            description="Browse the available services below.",
            color=discord.Color.green(),
        )
        
        product_list = []
        for product in product_dicts:
            variant_name = product["variant_name"]
            price_usd = format_usd(product["price_cents"])
            start_time = product.get("start_time") or "N/A"
            duration = product.get("duration") or "N/A"
            refill_period = product.get("refill_period") or "N/A"
            additional_info = product.get("additional_info") or "N/A"
            
            product_text = (
                f"**{variant_name}**\n"
                f"Price: {price_usd}\n"
                f"Start Time: {start_time}\n"
                f"Duration: {duration}\n"
                f"Refill: {refill_period}\n"
                f"Additional: {additional_info}\n"
                f"───────────"
            )
            product_list.append(product_text)
        
        description_text = "\n".join(product_list)
        
        if len(description_text) > 4096:
            description_text = description_text[:4090] + "..."
        
        embed.description = description_text
        embed.set_footer(text="Select a service from the dropdown below, then press Open Ticket")
        
        view = ProductDisplayView(product_dicts, main_category, sub_category)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _handle_open_ticket(
        self, interaction: discord.Interaction, main_category: str, sub_category: str, product_id: int
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.", ephemeral=True
            )
            return

        member = self._resolve_member(interaction)
        if member is None:
            await interaction.response.send_message(
                "Unable to resolve your member profile. Please try again.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.bot.db.ensure_user(member.id)

        product = await self.bot.db.get_product(product_id)
        if not product or not product["is_active"]:
            await interaction.followup.send(
                "The selected product is no longer available.",
                ephemeral=True,
            )
            return
        
        if (
            product["main_category"] != main_category
            or product["sub_category"] != sub_category
        ):
            await interaction.followup.send(
                "Product selection mismatch. Please try again.",
                ephemeral=True,
            )
            return

        support_category_id = self.bot.config.ticket_categories.support
        category = interaction.guild.get_channel(support_category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "Support category is not configured correctly. Please contact an admin.",
                ephemeral=True,
            )
            return

        admin_role = interaction.guild.get_role(self.bot.config.role_ids.admin)
        if admin_role is None:
            await interaction.followup.send(
                "Admin role is missing or misconfigured. Please notify the server owner.",
                ephemeral=True,
            )
            return

        ticket_id, counter = await self.bot.db.create_ticket_with_counter(
            user_discord_id=member.id,
            channel_id=0,
            status="open",
            ticket_type="order",
        )

        sanitized_username = member.name.lower()
        sanitized_username = ''.join(c if c.isalnum() or c == '-' else '-' for c in sanitized_username)
        sanitized_username = sanitized_username.strip('-')[:20]
        if not sanitized_username:
            sanitized_username = "user"
        
        channel_name = f"ticket-{sanitized_username}-order{counter}"

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
            ),
            admin_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            ),
        }
        if interaction.guild.me:
            overwrites[interaction.guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            )

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=(
                    f"Storefront ticket #{counter} for {main_category}/{sub_category}/"
                    f"{product['variant_name']} by {member.display_name}"
                ),
            )
            
            await self.bot.db._connection.execute(
                "UPDATE tickets SET channel_id = ? WHERE id = ?",
                (channel.id, ticket_id)
            )
            await self.bot.db._connection.commit()
            
        except discord.HTTPException as error:
            logger.error("Failed to create support ticket: %s", error)
            await interaction.followup.send(
                "Unable to create a ticket channel right now. Please try again later.",
                ephemeral=True,
            )
            return

        user_row = await self.bot.db.get_user(member.id)
        if not user_row:
            await self.bot.db.ensure_user(member.id)
            user_row = await self.bot.db.get_user(member.id)
        
        user_balance_cents = user_row["wallet_balance_cents"] if user_row else 0
        
        vip_tier = calculate_vip_tier(
            user_row["total_lifetime_spent_cents"] if user_row else 0,
            self.bot.config
        )
        discount_percent = await self._calculate_discount(
            member.id, product_id, vip_tier
        )
        final_price_cents = int(product["price_cents"] * (1 - discount_percent / 100))
        
        payment_methods = []
        if self.bot.config.payment_settings:
            payment_methods = self.bot.config.payment_settings.payment_methods
        elif self.bot.config.payment_methods:
            payment_methods = self.bot.config.payment_methods
        
        enabled_methods = [
            m for m in payment_methods 
            if getattr(m, 'is_enabled', m.metadata.get('is_enabled', True)) != False
        ]
        
        payment_embed = _build_payment_embed(
            product=product,
            user=member,
            final_price_cents=final_price_cents,
            user_balance_cents=user_balance_cents,
            payment_methods=enabled_methods,
        )
        
        payment_view = PaymentOptionsView(
            product_id=product_id,
            final_price_cents=final_price_cents,
            user_balance_cents=user_balance_cents,
            payment_methods=enabled_methods,
        )
        
        price_text = format_usd(product["price_cents"])
        start_time = product.get("start_time") or "N/A"
        duration = product.get("duration") or "N/A"
        refill = product.get("refill_period") or "N/A"
        additional_info = product.get("additional_info") or "N/A"
        
        owner_embed = create_embed(
            title=f"📦 New Order Ticket: {main_category} • {sub_category}",
            description=(
                f"**Customer:** {member.mention} ({member.display_name})\n"
                f"**User ID:** {member.id}\n"
                f"**Ticket ID:** #{ticket_id}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue(),
        )
        owner_embed.add_field(
            name="📋 Product Details",
            value=(
                f"**Service:** {product['service_name']}\n"
                f"**Variant:** {product['variant_name']}\n"
                f"**Base Price:** {price_text}\n"
                f"**Final Price:** {format_usd(final_price_cents)}\n"
                f"**Discount:** {discount_percent:.1f}%"
            ),
            inline=False,
        )
        owner_embed.add_field(
            name="⏱️ Service Info",
            value=(
                f"**Start Time:** {start_time}\n"
                f"**Duration:** {duration}\n"
                f"**Refill:** {refill}"
            ),
            inline=True,
        )
        owner_embed.add_field(
            name="💰 Payment Info",
            value=(
                f"**Amount Due:** {format_usd(final_price_cents)}\n"
                f"**User Balance:** {format_usd(user_balance_cents)}\n"
                f"**Status:** Awaiting Payment"
            ),
            inline=True,
        )
        if additional_info and additional_info != "N/A":
            owner_embed.add_field(
                name="ℹ️ Additional Info",
                value=additional_info,
                inline=False,
            )
        owner_embed.add_field(
            name="🕒 Operating Hours",
            value=render_operating_hours(self.bot.config.operating_hours),
            inline=False,
        )
        owner_embed.set_thumbnail(url=member.display_avatar.url)
        owner_embed.set_footer(text="Apex Core • Order Management")

        await channel.send(
            content=f"{admin_role.mention} — New order ticket opened!",
            embed=owner_embed,
        )
        
        await channel.send(
            content=f"{member.mention}",
            embed=payment_embed,
            view=payment_view,
        )

        try:
            dm_embed = create_embed(
                title="Support Ticket Created",
                description=(
                    f"Your support ticket for **{product['variant_name']}** is live: {channel.mention}\n"
                    f"Price: {price_text}"
                ),
                color=discord.Color.green(),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            logger.warning("Could not DM user %s about ticket creation", member.id)

        await interaction.followup.send(
            f"Your support ticket is ready: {channel.mention}",
            ephemeral=True,
        )

    async def _handle_purchase_initiate(
        self, interaction: discord.Interaction, product_id: int
    ) -> None:
        product = await self.bot.db.get_product(product_id)
        if not product or not product["is_active"]:
            await interaction.response.send_message(
                "This product is no longer available.", ephemeral=True
            )
            return

        user_row = await self.bot.db.get_user(interaction.user.id)
        if not user_row:
            await self.bot.db.ensure_user(interaction.user.id)
            user_row = await self.bot.db.get_user(interaction.user.id)

        if not user_row:
            await interaction.response.send_message(
                "Unable to retrieve your user data. Please try again.", ephemeral=True
            )
            return

        vip_tier = calculate_vip_tier(
            user_row["total_lifetime_spent_cents"], self.bot.config
        )

        base_price_cents = product["price_cents"]
        discount_percent = await self._calculate_discount(
            interaction.user.id, product_id, vip_tier
        )
        final_price_cents = int(base_price_cents * (1 - discount_percent / 100))

        current_balance = user_row["wallet_balance_cents"]
        if current_balance < final_price_cents:
            await interaction.response.send_message(
                f"Insufficient balance. You need {format_usd(final_price_cents)} "
                f"but only have {format_usd(current_balance)}.",
                ephemeral=True,
            )
            return

        product_name = _product_display_name(product)
        modal = PurchaseConfirmModal(product_id, product_name, final_price_cents)
        await interaction.response.send_modal(modal)

    async def _complete_purchase(
        self,
        interaction: discord.Interaction,
        product_id: int,
        product_name: str,
        final_price_cents: int,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not self._is_within_operating_hours():
            hours_text = render_operating_hours(self.bot.config.operating_hours)
            await interaction.followup.send(
                f"Purchases can only be made during operating hours: {hours_text}",
                ephemeral=True,
            )
            return

        product = await self.bot.db.get_product(product_id)
        if not product or not product["is_active"]:
            await interaction.followup.send(
                "This product is no longer available.", ephemeral=True
            )
            return

        user_row = await self.bot.db.get_user(interaction.user.id)
        if not user_row:
            await interaction.followup.send(
                "Unable to retrieve your user data. Please try again.", ephemeral=True
            )
            return

        vip_tier = calculate_vip_tier(
            user_row["total_lifetime_spent_cents"], self.bot.config
        )
        discount_percent = await self._calculate_discount(
            interaction.user.id, product_id, vip_tier
        )
        recalc_final_price = int(product["price_cents"] * (1 - discount_percent / 100))

        if recalc_final_price != final_price_cents:
            await interaction.followup.send(
                "Price has changed since you started this purchase. Please try again.",
                ephemeral=True,
            )
            return

        product_name = _product_display_name(product)
        try:
            order_metadata = json.dumps({
                "product_name": product_name,
                "base_price_cents": product["price_cents"],
                "discount_percent": discount_percent,
                "vip_tier": vip_tier.name if vip_tier else None,
            })
            order_id, new_balance = await self.bot.db.purchase_product(
                user_discord_id=interaction.user.id,
                product_id=product_id,
                price_paid_cents=final_price_cents,
                discount_applied_percent=discount_percent,
                order_metadata=order_metadata,
            )
        except ValueError as e:
            await interaction.followup.send(
                f"Purchase failed: {str(e)}", ephemeral=True
            )
            return
        except Exception as e:
            logger.error("Purchase error for user %s: %s", interaction.user.id, e)
            await interaction.followup.send(
                "An error occurred while processing your purchase. Please contact support.",
                ephemeral=True,
            )
            return

        member = self._resolve_member(interaction)
        if member and product["role_id"]:
            role = interaction.guild.get_role(product["role_id"]) if interaction.guild else None
            if role:
                try:
                    await member.add_roles(role, reason=f"Purchased {product_name}")
                except discord.HTTPException as e:
                    logger.error("Failed to assign role %s to user %s: %s", role.id, member.id, e)

        success_embed = create_embed(
            title="Purchase Complete!",
            description=(
                f"You have successfully purchased **{product_name}**.\n\n"
                f"**Amount Paid:** {format_usd(final_price_cents)}\n"
                f"**New Balance:** {format_usd(new_balance)}\n"
                f"**Order ID:** #{order_id}"
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

        if product["content_payload"]:
            dm_embed = create_embed(
                title=f"Product Fulfillment: {product_name}",
                description=product["content_payload"],
                color=discord.Color.gold(),
            )
            dm_embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
            dm_embed.add_field(
                name="Amount Paid", value=format_usd(final_price_cents), inline=True
            )
            try:
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning("Could not DM user %s with fulfillment content", interaction.user.id)
                await interaction.followup.send(
                    "⚠️ Could not send fulfillment details via DM. Please enable DMs from server members.",
                    ephemeral=True,
                )

        if interaction.guild:
            log_channel_id = (
                self.bot.config.logging_channels.order_logs
                or self.bot.config.logging_channels.payments
            )
            log_channel = interaction.guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                log_embed = create_embed(
                    title="Order Completed",
                    description=(
                        f"**Customer:** {interaction.user.mention} ({interaction.user.id})\n"
                        f"**Product:** {product_name}\n"
                        f"**Base Price:** {format_usd(product['price_cents'])}\n"
                        f"**Discount Applied:** {discount_percent:.1f}%\n"
                        f"**Final Price:** {format_usd(final_price_cents)}\n"
                        f"**Order ID:** #{order_id}"
                    ),
                    color=discord.Color.dark_green(),
                )
                log_embed.set_footer(text=f"User ID: {interaction.user.id}")
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException as e:
                    logger.error("Failed to log order to channel %s: %s", log_channel_id, e)

        # Process post-purchase actions including VIP promotion
        old_vip_tier, new_vip_tier = await process_post_purchase(
            user_discord_id=interaction.user.id,
            amount_cents=final_price_cents,
            db=self.bot.db,
            config=self.bot.config,
            guild=interaction.guild,
        )
        
        # Handle VIP promotion notifications and role assignments
        if new_vip_tier and (not old_vip_tier or new_vip_tier.name != old_vip_tier.name):
            await handle_vip_promotion(
                user_discord_id=interaction.user.id,
                old_vip_tier=old_vip_tier,
                new_vip_tier=new_vip_tier,
                config=self.bot.config,
                guild=interaction.guild,
            )
        
        # Check and update all roles for the user
        if interaction.guild:
            from apex_core.utils import check_and_update_roles
            try:
                await check_and_update_roles(
                    interaction.user.id,
                    self.bot.db,
                    interaction.guild,
                    self.bot.config,
                )
            except Exception as e:
                logger.error("Error updating roles for user %s: %s", interaction.user.id, e)

    async def _handle_support_ticket(
        self, interaction: discord.Interaction, product_id: int
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.", ephemeral=True
            )
            return

        member = self._resolve_member(interaction)
        if member is None:
            await interaction.response.send_message(
                "Unable to resolve your member profile. Please try again.", ephemeral=True
            )
            return

        product = await self.bot.db.get_product(product_id)
        if not product:
            await interaction.response.send_message(
                "Product not found.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.bot.db.ensure_user(member.id)

        existing_ticket = await self.bot.db.get_open_ticket_for_user(member.id)
        if existing_ticket:
            channel = interaction.guild.get_channel(existing_ticket["channel_id"])
            if channel:
                await interaction.followup.send(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True,
                )
                return
            await self.bot.db.update_ticket_status(existing_ticket["channel_id"], "closed")

        support_category_id = self.bot.config.ticket_categories.support
        category = interaction.guild.get_channel(support_category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "Support category is not configured correctly. Please contact an admin.",
                ephemeral=True,
            )
            return

        admin_role = interaction.guild.get_role(self.bot.config.role_ids.admin)
        if admin_role is None:
            await interaction.followup.send(
                "Admin role is missing or misconfigured. Please notify the server owner.",
                ephemeral=True,
            )
            return

        channel_name = f"support-{member.name}"[:95]
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
            ),
            admin_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            ),
        }
        if interaction.guild.me:
            overwrites[interaction.guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            )

        product_name = _product_display_name(product)

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Support ticket for {product_name} by {member.display_name}",
            )
        except discord.HTTPException as error:
            logger.error("Failed to create support ticket: %s", error)
            await interaction.followup.send(
                "Unable to create a ticket channel right now. Please try again later.",
                ephemeral=True,
            )
            return

        embed = create_embed(
            title="Support Ticket",
            description=(
                f"{member.mention}, thanks for opening a support ticket.\n\n"
                f"**Product Inquiry:** {product_name}\n"
                f"**Price:** {format_usd(product['price_cents'])}\n\n"
                "Our team will assist you shortly."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Operating Hours",
            value=render_operating_hours(self.bot.config.operating_hours),
            inline=False,
        )
        embed.set_footer(text="Apex Core • Support")

        await channel.send(
            content=f"{admin_role.mention} {member.mention} — New support ticket opened.",
            embed=embed,
        )
        await self.bot.db.create_ticket(user_discord_id=member.id, channel_id=channel.id)

        await interaction.followup.send(
            f"Your support ticket is ready: {channel.mention}",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for payment proof uploads in ticket channels."""
        if message.author.bot:
            return
        
        if not message.attachments:
            return
        
        if not isinstance(message.channel, discord.TextChannel):
            return
        
        channel_name = message.channel.name
        if not channel_name.startswith("ticket-") or "-order" not in channel_name:
            return
        
        ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket["status"] != "open":
            return
        
        if message.guild is None:
            return
        
        admin_role = message.guild.get_role(self.bot.config.role_ids.admin)
        if not admin_role:
            return
        
        proof_embed = create_embed(
            title="💾 Payment Proof Uploaded",
            description=(
                f"**User:** {message.author.mention}\n"
                f"**Ticket ID:** #{ticket['id']}\n"
                f"**Attachments:** {len(message.attachments)}\n\n"
                "Staff: Please verify the payment proof and confirm the order."
            ),
            color=discord.Color.orange(),
        )
        
        for i, attachment in enumerate(message.attachments, 1):
            proof_embed.add_field(
                name=f"Attachment {i}",
                value=f"[{attachment.filename}]({attachment.url})",
                inline=False,
            )
        
        proof_embed.set_footer(text="Apex Core • Payment Verification")
        
        await message.channel.send(
            content=f"🔔 {admin_role.mention}",
            embed=proof_embed,
        )
        
        try:
            dm_embed = create_embed(
                title="Payment Proof Received",
                description=(
                    "✅ Your payment proof has been received!\n\n"
                    "Our staff team will verify your payment shortly.\n"
                    "You'll receive a confirmation once your payment is approved."
                ),
                color=discord.Color.green(),
            )
            await message.author.send(embed=dm_embed)
        except discord.Forbidden:
            logger.warning("Could not DM user %s about payment proof receipt", message.author.id)

    @commands.command(name="setup_store")
    async def setup_store(self, ctx: commands.Context) -> None:
        """Setup the permanent storefront message with cascading dropdowns."""
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return

        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(member):
            await ctx.send("You do not have permission to use this command.")
            return

        categories = await self.bot.db.get_distinct_main_categories()
        if not categories:
            await ctx.send("No active products found in the database.")
            return

        embed = create_embed(
            title="Apex Core: Products",
            description="Select a product from the drop-down menu to view details and open a support ticket.",
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Apex Core • Storefront")

        view = CategorySelectView(categories)
        await ctx.send(embed=embed, view=view)
        
        await ctx.send("✅ Store setup complete in this channel", delete_after=5)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StorefrontCog(bot))
