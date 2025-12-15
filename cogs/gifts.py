"""Gift system commands for sending and claiming gifts."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.error_messages import get_error_message
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


def generate_gift_code() -> str:
    """Generate a unique gift code."""
    return f"GIFT-{''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))}"


class GiftsCog(commands.Cog):
    """Commands for gift system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="giftproduct")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        recipient="User to gift the product to",
        product_id="Product ID to gift",
        message="Optional gift message",
        anonymous="Send gift anonymously"
    )
    async def gift_product(
        self,
        interaction: discord.Interaction,
        recipient: discord.Member,
        product_id: int,
        message: Optional[str] = None,
        anonymous: bool = False
    ) -> None:
        """Gift a product to a user (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted gift_product | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(
                f"Admin gifting product | Admin: {interaction.user.id} | "
                f"Recipient: {recipient.id} | Product: {product_id}"
            )
            
            product = await self.bot.db.get_product(product_id)
            if not product:
                logger.warning(f"Gift product failed: Product {product_id} not found")
                await interaction.followup.send(
                    f"❌ Product #{product_id} not found.",
                    ephemeral=True
                )
                return
            
            # Create gift
            gift_id = await self.bot.db.create_gift(
                gift_type="product",
                sender_discord_id=interaction.user.id,
                recipient_discord_id=recipient.id,
                product_id=product_id,
                gift_message=message,
                anonymous=anonymous
            )
            
            logger.info(f"Gift created | Gift ID: {gift_id} | Type: product")
            
            # Send notification to recipient
            try:
                embed = create_embed(
                    title="🎁 You Received a Gift!",
                    description=(
                        f"{'Someone' if anonymous else interaction.user.mention} sent you a gift!\n\n"
                        f"**Product:** {product['variant_name']}\n"
                        f"**Value:** {format_usd(product['price_cents'])}"
                    ),
                    color=discord.Color.gold()
                )
                
                if message:
                    embed.add_field(name="Message", value=message, inline=False)
                
                embed.add_field(
                    name="How to Claim",
                    value="The product will be automatically added to your account. Check your orders!",
                    inline=False
                )
                
                await recipient.send(embed=embed)
                logger.info(f"Gift notification sent to recipient | User: {recipient.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to recipient {recipient.id} - DMs disabled")
            
            await interaction.followup.send(
                f"✅ Gift sent to {recipient.mention}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Failed to gift product | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to send gift: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="giftwallet")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        recipient="User to gift wallet balance to",
        amount="Amount in dollars (e.g., 10.50)",
        message="Optional gift message",
        anonymous="Send gift anonymously"
    )
    async def gift_wallet(
        self,
        interaction: discord.Interaction,
        recipient: discord.Member,
        amount: str,
        message: Optional[str] = None,
        anonymous: bool = False
    ) -> None:
        """Gift wallet balance to a user (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted gift_wallet | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse amount
            try:
                amount_float = float(amount)
                amount_cents = int(amount_float * 100)
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid amount format. Use a number like '10.50'.",
                    ephemeral=True
                )
                return
            
            if amount_cents <= 0:
                await interaction.followup.send(
                    "❌ Amount must be positive.",
                    ephemeral=True
                )
                return
            
            logger.info(
                f"Admin gifting wallet | Admin: {interaction.user.id} | "
                f"Recipient: {recipient.id} | Amount: {format_usd(amount_cents)}"
            )
            
            # Create gift
            gift_id = await self.bot.db.create_gift(
                gift_type="wallet",
                sender_discord_id=interaction.user.id,
                recipient_discord_id=recipient.id,
                wallet_amount_cents=amount_cents,
                gift_message=message,
                anonymous=anonymous
            )
            
            # Claim gift immediately (admin gifts are auto-claimed)
            success = await self.bot.db.claim_gift(gift_id, recipient.id)
            
            if success:
                logger.info(f"Gift claimed automatically | Gift ID: {gift_id}")
                
                # Send notification
                try:
                    embed = create_embed(
                        title="🎁 You Received a Gift!",
                        description=(
                            f"{'Someone' if anonymous else interaction.user.mention} sent you a gift!\n\n"
                            f"**Amount:** {format_usd(amount_cents)}\n"
                            f"✅ Added to your wallet balance!"
                        ),
                        color=discord.Color.gold()
                    )
                    
                    if message:
                        embed.add_field(name="Message", value=message, inline=False)
                    
                    await recipient.send(embed=embed)
                    logger.info(f"Gift notification sent to recipient | User: {recipient.id}")
                except discord.Forbidden:
                    logger.warning(f"Cannot send DM to recipient {recipient.id} - DMs disabled")
                
                await interaction.followup.send(
                    f"✅ Gifted {format_usd(amount_cents)} to {recipient.mention}!",
                    ephemeral=True
                )
            else:
                logger.error(f"Failed to claim gift | Gift ID: {gift_id}")
                await interaction.followup.send(
                    "❌ Failed to process gift. Please try again.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.exception(f"Failed to gift wallet | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to send gift: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="sendgift")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        recipient="User to send gift to",
        product_id="Product ID to gift",
        anonymous="Send gift anonymously",
        message="Optional gift message"
    )
    async def send_gift(
        self,
        interaction: discord.Interaction,
        recipient: discord.Member,
        product_id: int,
        anonymous: bool = False,
        message: Optional[str] = None
    ) -> None:
        """Purchase and send a product as a gift to another user."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(
                f"User sending gift | User: {interaction.user.id} | "
                f"Recipient: {recipient.id} | Product: {product_id}"
            )
            
            product = await self.bot.db.get_product(product_id)
            if not product:
                logger.warning(f"Send gift failed: Product {product_id} not found")
                await interaction.followup.send(
                    f"❌ Product #{product_id} not found.",
                    ephemeral=True
                )
                return
            
            # Check user balance
            user = await self.bot.db.get_user(interaction.user.id)
            if not user:
                await self.bot.db.ensure_user(interaction.user.id)
                user = await self.bot.db.get_user(interaction.user.id)
            
            price_cents = product["price_cents"]
            
            if user["wallet_balance_cents"] < price_cents:
                error_msg = get_error_message(
                    "insufficient_balance",
                    current_balance=format_usd(user["wallet_balance_cents"]),
                    required_amount=format_usd(price_cents)
                )
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            # Create gift
            gift_id = await self.bot.db.create_gift(
                gift_type="product",
                sender_discord_id=interaction.user.id,
                recipient_discord_id=recipient.id,
                product_id=product_id,
                gift_message=message,
                anonymous=anonymous
            )
            
            # Process purchase
            order_id, new_balance = await self.bot.db.purchase_product(
                user_discord_id=interaction.user.id,
                product_id=product_id,
                price_paid_cents=price_cents,
                discount_applied_percent=0.0,
                order_metadata=f'{{"gift_id": {gift_id}, "recipient": {recipient.id}}}'
            )
            
            logger.info(
                f"Gift purchase completed | Order: {order_id} | Gift: {gift_id} | "
                f"User: {interaction.user.id} | New balance: {format_usd(new_balance)}"
            )
            
            # Send notification to recipient
            try:
                embed = create_embed(
                    title="🎁 You Received a Gift!",
                    description=(
                        f"{'Someone' if anonymous else interaction.user.mention} sent you a gift!\n\n"
                        f"**Product:** {product['variant_name']}\n"
                        f"**Value:** {format_usd(price_cents)}"
                    ),
                    color=discord.Color.gold()
                )
                
                if message:
                    embed.add_field(name="Message", value=message, inline=False)
                
                await recipient.send(embed=embed)
                logger.info(f"Gift notification sent to recipient | User: {recipient.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to recipient {recipient.id} - DMs disabled")
            
            await interaction.followup.send(
                f"✅ Gift sent to {recipient.mention}! Order #{order_id}",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Failed to send gift | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to send gift: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="giftcode")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        product_id="Product ID for gift code",
        expires_days="Days until expiration (default: 30)"
    )
    async def create_gift_code(
        self,
        interaction: discord.Interaction,
        product_id: int,
        expires_days: int = 30
    ) -> None:
        """Generate a one-time gift code for a product (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted giftcode | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(
                f"Admin creating gift code | Admin: {interaction.user.id} | "
                f"Product: {product_id} | Expires: {expires_days} days"
            )
            
            product = await self.bot.db.get_product(product_id)
            if not product:
                logger.warning(f"Gift code creation failed: Product {product_id} not found")
                await interaction.followup.send(
                    f"❌ Product #{product_id} not found.",
                    ephemeral=True
                )
                return
            
            gift_code = generate_gift_code()
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
            
            gift_id = await self.bot.db.create_gift(
                gift_type="gift_code",
                sender_discord_id=interaction.user.id,
                product_id=product_id,
                gift_code=gift_code,
                expires_at=expires_at
            )
            
            logger.info(f"Gift code created | Code: {gift_code} | Gift ID: {gift_id}")
            
            # Send code to admin via DM
            try:
                embed = create_embed(
                    title="🎁 Gift Code Generated",
                    description=(
                        f"**Product:** {product['variant_name']}\n"
                        f"**Code:** `{gift_code}`\n"
                        f"**Expires:** {expires_days} days"
                    ),
                    color=discord.Color.gold()
                )
                
                await interaction.user.send(embed=embed)
                logger.info(f"Gift code sent to admin via DM | Admin: {interaction.user.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to admin {interaction.user.id} - DMs disabled")
            
            await interaction.followup.send(
                f"✅ Gift code generated! Check your DMs for the code.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Failed to create gift code | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to create gift code: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="claimgift")
    @app_commands.describe(gift_code="Gift code to claim")
    async def claim_gift(
        self,
        interaction: discord.Interaction,
        gift_code: str
    ) -> None:
        """Claim a gift using a gift code."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(f"User attempting to claim gift | User: {interaction.user.id} | Code: {gift_code}")
            
            gift = await self.bot.db.get_gift_by_code(gift_code)
            if not gift:
                logger.warning(f"Gift code not found | Code: {gift_code} | User: {interaction.user.id}")
                error_msg = get_error_message("gift_code_invalid", code=gift_code)
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            if gift["status"] != "pending":
                logger.warning(
                    f"Gift already claimed | Code: {gift_code} | Status: {gift['status']} | "
                    f"User: {interaction.user.id}"
                )
                error_msg = get_error_message("gift_already_claimed", claimed_date="Previously")
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            # Check expiration
            if gift["expires_at"]:
                expires = datetime.fromisoformat(gift["expires_at"])
                if datetime.now() > expires:
                    logger.warning(f"Gift code expired | Code: {gift_code} | User: {interaction.user.id}")
                    error_msg = get_error_message("gift_code_expired", code=gift_code, expired_date=expires.strftime("%Y-%m-%d"))
                    await interaction.followup.send(error_msg, ephemeral=True)
                    return
            
            # Claim gift
            success = await self.bot.db.claim_gift(gift["id"], interaction.user.id)
            
            if success:
                logger.info(f"Gift claimed successfully | Gift ID: {gift['id']} | User: {interaction.user.id}")
                
                embed = create_embed(
                    title="✅ Gift Claimed!",
                    description="Your gift has been successfully claimed and added to your account.",
                    color=discord.Color.green()
                )
                
                if gift["product_id"]:
                    product = await self.bot.db.get_product(gift["product_id"])
                    if product:
                        embed.add_field(name="Product", value=product["variant_name"], inline=False)
                
                if gift["wallet_amount_cents"]:
                    embed.add_field(
                        name="Wallet Credit",
                        value=format_usd(gift["wallet_amount_cents"]),
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                logger.error(f"Failed to claim gift | Gift ID: {gift['id']} | User: {interaction.user.id}")
                await interaction.followup.send(
                    "❌ Failed to claim gift. Please contact support.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.exception(f"Failed to claim gift | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to claim gift: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="mygifts")
    async def my_gifts(self, interaction: discord.Interaction) -> None:
        """View gifts you've sent and received."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(f"User viewing gifts | User: {interaction.user.id}")
            
            sent = await self.bot.db.get_user_gifts_sent(interaction.user.id)
            received = await self.bot.db.get_user_gifts_received(interaction.user.id)
            
            embed = create_embed(
                title="🎁 Your Gifts",
                description=(
                    f"**Sent:** {len(sent)} gift(s)\n"
                    f"**Received:** {len(received)} gift(s)"
                ),
                color=discord.Color.gold()
            )
            
            if sent:
                sent_list = "\n".join([
                    f"• Gift #{g['id']}: {g['status']} - {g.get('gift_type', 'unknown')}"
                    for g in sent[:10]
                ])
                embed.add_field(
                    name="📤 Sent Gifts",
                    value=sent_list[:1024],
                    inline=False
                )
            
            if received:
                received_list = "\n".join([
                    f"• Gift #{g['id']}: {g['status']} - {g.get('gift_type', 'unknown')}"
                    for g in received[:10]
                ])
                embed.add_field(
                    name="📥 Received Gifts",
                    value=received_list[:1024],
                    inline=False
                )
            
            if not sent and not received:
                embed.description = "You haven't sent or received any gifts yet."
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Failed to get user gifts | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to load gifts: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Load the GiftsCog cog."""
    await bot.add_cog(GiftsCog(bot))

