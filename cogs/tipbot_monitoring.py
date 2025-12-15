"""
Tipbot Message Monitoring Cog

Automatically verifies payments from Discord tipbots by monitoring their messages.
Supports: Tip.cc, CryptoJar, Gemma, Seto Chan, and other tipbots.

Note: Tipbot confirmation messages are typically authored by bots; this cog must
process bot-authored messages and should only run in relevant channels.
"""

from __future__ import annotations

import re
from typing import Optional

import discord
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd

logger = get_logger()

# Tipbot Bot IDs (update these with actual bot IDs from your server)
TIPBOT_IDS = {
    "tip.cc": 617037497574359050,  # Update with actual bot ID
    "cryptojar": 1414376186024296638,  # Update with actual bot ID
    "gemma": 1346973323745296524,  # Update with actual bot ID
    "seto": None,  # Update with actual bot ID
}

# Message patterns for each tipbot
TIPBOT_PATTERNS = {
    "tip.cc": [
        r"(?:✅|✓|✓)\s*@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
        r"@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
    ],
    "cryptojar": [
        r"(?:💰|💵)\s*@?(\w+)\s+sent\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?\s+to\s+@?(\w+)",
        r"@?(\w+)\s+sent\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?\s+to\s+@?(\w+)",
    ],
    "gemma": [
        r"(?:💎|✨)\s*@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
        r"@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
    ],
    "seto": [
        r"(?:🤖|💸)\s*@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
        r"@?(\w+)\s+tipped\s+@?(\w+)\s+\$?([\d,]+\.?\d*)\s*(?:USD|usd)?",
    ],
}


def _parse_tip_amount(text: str) -> Optional[float]:
    """Parse tip amount from text."""
    text = text.replace(",", "")
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _extract_tip_info(message: discord.Message) -> Optional[dict]:
    """Extract tip information from tipbot message."""
    content = message.content

    tipbot_name = None
    for name, bot_id in TIPBOT_IDS.items():
        if bot_id and message.author.id == bot_id:
            tipbot_name = name
            break

    if not tipbot_name:
        content_lower = content.lower()
        if "tip.cc" in content_lower or "tipped" in content_lower:
            tipbot_name = "tip.cc"
        elif "cryptojar" in content_lower or "jar" in content_lower:
            tipbot_name = "cryptojar"
        elif "gemma" in content_lower:
            tipbot_name = "gemma"
        elif "seto" in content_lower:
            tipbot_name = "seto"
        else:
            return None

    patterns = TIPBOT_PATTERNS.get(tipbot_name, [])
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            continue

        groups = match.groups()
        if tipbot_name == "cryptojar":
            if len(groups) < 3:
                continue
            sender, amount_text, recipient = groups[0], groups[1], groups[2]
        else:
            if len(groups) < 3:
                continue
            sender, recipient, amount_text = groups[0], groups[1], groups[2]

        amount_float = _parse_tip_amount(amount_text)
        if amount_float is None:
            continue

        guild_me = message.guild.me if message.guild else None
        bot_mention = f"<@{guild_me.id}>" if guild_me else None
        bot_name_lower = guild_me.name.lower() if guild_me else ""

        recipient_lower = recipient.lower()
        is_for_bot = (
            recipient_lower in {"apexcore", "apex core", bot_name_lower}
            or (bot_mention and bot_mention in content)
        )

        if not is_for_bot:
            return None

        sender_id = None
        if message.mentions:
            for user in message.mentions:
                if user.name.lower() == sender.lower() or user.display_name.lower() == sender.lower():
                    sender_id = user.id
                    break

        if not sender_id and message.guild:
            member = message.guild.get_member_named(sender)
            if member:
                sender_id = member.id

        if not sender_id and message.mentions:
            sender_id = message.mentions[0].id

        if not sender_id:
            return None

        return {
            "sender_id": sender_id,
            "amount": amount_float,
            "amount_cents": int(round(amount_float * 100)),
            "tipbot": tipbot_name,
            "message_id": message.id,
            "channel_id": message.channel.id,
        }

    return None


class TipbotMonitoringCog(commands.Cog):
    """Monitor tipbot messages and auto-verify payments."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processed_messages: set[int] = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor messages for tipbot payments."""
        if not message.guild:
            return

        # Ignore our own bot messages but allow other bots (tipbots) to be processed.
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        if message.id in self.processed_messages:
            return

        channel_name = getattr(message.channel, "name", "").lower()
        is_ticket_channel = (
            channel_name.startswith("ticket-")
            or channel_name.startswith("deposit-")
            or "payment" in channel_name
            or "order" in channel_name
        )

        if not is_ticket_channel:
            return

        tip_info = _extract_tip_info(message)
        if not tip_info:
            return

        sender_id = tip_info.get("sender_id")
        if not sender_id:
            logger.warning("Could not identify sender from tipbot message: %s", message.content)
            return

        self.processed_messages.add(message.id)

        try:
            ticket_row = await self.bot.db.get_ticket_by_channel(message.channel.id)
            ticket = dict(ticket_row) if ticket_row and not isinstance(ticket_row, dict) else ticket_row
            if not ticket:
                return

            # Prefer the order linked to this ticket if present.
            candidate_orders: list[dict] = []
            ticket_order_id = ticket.get("order_id")
            if ticket_order_id:
                order_row = await self.bot.db.get_order_by_id(ticket_order_id)
                order = dict(order_row) if order_row and not isinstance(order_row, dict) else order_row
                if (
                    order
                    and order.get("user_discord_id") == sender_id
                    and order.get("status") == "pending"
                ):
                    candidate_orders = [order]

            if not candidate_orders:
                order_rows = await self.bot.db.get_orders_for_user(sender_id, limit=10, offset=0)
                candidate_orders = [
                    dict(row) if not isinstance(row, dict) else row
                    for row in order_rows
                    if (row["status"] if not isinstance(row, dict) else row.get("status")) == "pending"
                ]

            matching_order = None
            amount_cents = int(tip_info["amount_cents"])
            for order in candidate_orders:
                order_price = int(order.get("price_paid_cents") or 0)
                if abs(order_price - amount_cents) <= 50:
                    matching_order = order
                    break

            if not matching_order:
                logger.info(
                    "No matching pending order found for tipbot payment | User: %s | Amount: %s",
                    sender_id,
                    tip_info.get("amount"),
                )
                return

            order_id = int(matching_order["id"])
            await self.bot.db.update_order_status(order_id, "fulfilled")

            await self.bot.db.ensure_user(sender_id)
            user_row = await self.bot.db.get_user(sender_id)
            balance_after = int(user_row["wallet_balance_cents"]) if user_row else 0

            await self.bot.db.log_wallet_transaction(
                user_discord_id=sender_id,
                amount_cents=0,
                balance_after_cents=balance_after,
                transaction_type="external_payment",
                description=f"External payment via {tip_info['tipbot']} for order #{order_id}",
                order_id=order_id,
                ticket_id=ticket.get("id"),
                metadata={
                    "provider": tip_info["tipbot"],
                    "external_amount_cents": amount_cents,
                    "message_id": message.id,
                    "channel_id": message.channel.id,
                },
            )

            try:
                user = await self.bot.fetch_user(sender_id)
                if user:
                    embed = create_embed(
                        title="✅ Payment Verified",
                        description=f"Your payment of {format_usd(amount_cents)} has been verified!",
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="📦 Order", value=f"Order #{order_id}", inline=True)
                    embed.add_field(name="🤖 Provider", value=tip_info["tipbot"].title(), inline=True)

                    try:
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        await message.channel.send(f"{user.mention}", embed=embed)
            except Exception as e:
                logger.error("Failed to notify user of payment verification: %s", e)

            confirm_embed = create_embed(
                title="✅ Payment Verified Automatically",
                description=f"Payment of {format_usd(amount_cents)} verified via {tip_info['tipbot'].title()}",
                color=discord.Color.green(),
            )
            confirm_embed.add_field(name="Order", value=f"#{order_id}", inline=True)
            confirm_embed.add_field(name="Status", value="Fulfilled", inline=True)

            await message.channel.send(embed=confirm_embed)

            logger.info(
                "Auto-verified tipbot payment | User: %s | Order: %s | Amount: %s | Provider: %s",
                sender_id,
                order_id,
                format_usd(amount_cents),
                tip_info["tipbot"],
            )

        except Exception:
            logger.exception("Error processing tipbot payment")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Remove from processed set if message is deleted."""
        self.processed_messages.discard(message.id)


async def setup(bot: commands.Bot):
    """Load the Tipbot Monitoring cog."""
    await bot.add_cog(TipbotMonitoringCog(bot))
    logger.info("Loaded extension: cogs.tipbot_monitoring")
    logger.info("Tipbot monitoring active - will auto-verify payments from tipbots")
