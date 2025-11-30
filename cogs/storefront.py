from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import (
    calculate_vip_tier,
    create_embed,
    format_usd,
    handle_vip_promotion,
    operating_hours_window,
    process_post_purchase,
    render_operating_hours,
)

logger = logging.getLogger(__name__)


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

        embed = create_embed(
            title=product["name"],
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
                    label=product["name"][:100],
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
        super().__init__(title=f"Confirm Purchase: {product_name}")
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
            if discount["is_stackable"]:
                total_discount += discount["discount_percent"]
            else:
                total_discount = max(total_discount, discount["discount_percent"])

        return min(total_discount, 100.0)

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

        modal = PurchaseConfirmModal(product_id, product["name"], final_price_cents)
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

        try:
            order_metadata = json.dumps({
                "product_name": product["name"],
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
                    await member.add_roles(role, reason=f"Purchased {product['name']}")
                except discord.HTTPException as e:
                    logger.error("Failed to assign role %s to user %s: %s", role.id, member.id, e)

        success_embed = create_embed(
            title="Purchase Complete!",
            description=(
                f"You have successfully purchased **{product['name']}**.\n\n"
                f"**Amount Paid:** {format_usd(final_price_cents)}\n"
                f"**New Balance:** {format_usd(new_balance)}\n"
                f"**Order ID:** #{order_id}"
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

        if product["content_payload"]:
            dm_embed = create_embed(
                title=f"Product Fulfillment: {product['name']}",
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
                        f"**Product:** {product['name']}\n"
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

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Support ticket for {product['name']} by {member.display_name}",
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
                f"**Product Inquiry:** {product['name']}\n"
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

    @commands.command(name="setup_store")
    async def setup_store(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return

        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(member):
            await ctx.send("You do not have permission to use this command.")
            return

        products = await self.bot.db.get_all_products(active_only=True)
        if not products:
            await ctx.send("No active products found in the database.")
            return

        product_dicts = [dict(p) for p in products]

        embed = create_embed(
            title="🛒 Apex Core Store",
            description=(
                "Welcome to the Apex Core Store!\n\n"
                "Browse our products using the dropdown menu below.\n"
                "Select a product to view pricing, apply discounts, and purchase using your wallet balance."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Operating Hours",
            value=render_operating_hours(self.bot.config.operating_hours),
            inline=False,
        )
        embed.add_field(
            name="Payment Methods",
            value="💳 Wallet Balance • 🎫 Support Ticket",
            inline=False,
        )
        embed.set_footer(text="Apex Core • Storefront")

        view = ProductSelectView(product_dicts)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StorefrontCog(bot))
