"""
Tipbot Message Monitoring Cog

Automatically verifies payments from Discord tipbots by monitoring their messages.
Supports: Tip.cc, CryptoJar, Gemma, Seto Chan, and other tipbots.
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
    # Remove commas and extract number
    text = text.replace(",", "")
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def _extract_tip_info(message: discord.Message) -> Optional[dict]:
    """Extract tip information from tipbot message."""
    content = message.content
    
    # Check which tipbot sent the message
    tipbot_name = None
    for name, bot_id in TIPBOT_IDS.items():
        if bot_id and message.author.id == bot_id:
            tipbot_name = name
            break
    
    if not tipbot_name:
        # Try to detect by message content
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
    
    # Get patterns for this tipbot
    patterns = TIPBOT_PATTERNS.get(tipbot_name, [])
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if tipbot_name == "cryptojar":
                # Format: @sender sent $amount to @recipient
                if len(groups) >= 3:
                    sender = groups[0]
                    amount = groups[1]
                    recipient = groups[2]
                else:
                    continue
            else:
                # Format: @sender tipped @recipient $amount
                if len(groups) >= 3:
                    sender = groups[0]
                    recipient = groups[1]
                    amount = groups[2]
                else:
                    continue
            
            # Parse amount
            amount_float = _parse_tip_amount(amount)
            if not amount_float:
                continue
            
            # Check if recipient is the bot or mentions the bot
            bot_mention = f"<@{message.guild.me.id}>" if message.guild and message.guild.me else None
            bot_name_lower = message.guild.me.name.lower() if message.guild and message.guild.me else ""
            
            recipient_lower = recipient.lower()
            is_for_bot = (
                recipient_lower == "apexcore" or
                recipient_lower == "apex core" or
                recipient_lower == bot_name_lower or
                (bot_mention and bot_mention in content)
            )
            
            if not is_for_bot:
                return None
            
            # Get sender user ID
            sender_id = None
            if message.mentions:
                for user in message.mentions:
                    if user.name.lower() == sender.lower() or user.display_name.lower() == sender.lower():
                        sender_id = user.id
                        break
            
            # If no mention, try to find by name
            if not sender_id and message.guild:
                member = message.guild.get_member_named(sender)
                if member:
                    sender_id = member.id
            
            if not sender_id:
                # Try to extract from message
                for user in message.mentions:
                    sender_id = user.id
                    break
            
            return {
                "sender_id": sender_id,
                "amount": amount_float,
                "amount_cents": int(amount_float * 100),
                "tipbot": tipbot_name,
                "message_id": message.id,
                "channel_id": message.channel.id,
            }
    
    return None


class TipbotMonitoringCog(commands.Cog):
    """Monitor tipbot messages and auto-verify payments."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processed_messages = set()  # Track processed messages to avoid duplicates
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor messages for tipbot payments."""
        # Skip if bot message or no guild
        if message.author.bot or not message.guild:
            return
        
        # Skip if already processed
        if message.id in self.processed_messages:
            return
        
        # Only monitor ticket channels and payment channels
        channel_name = message.channel.name.lower()
        is_ticket_channel = (
            channel_name.startswith("ticket-") or
            channel_name.startswith("deposit-") or
            "payment" in channel_name or
            "order" in channel_name
        )
        
        if not is_ticket_channel:
            return
        
        # Extract tip info
        tip_info = _extract_tip_info(message)
        if not tip_info:
            return
        
        sender_id = tip_info.get("sender_id")
        if not sender_id:
            logger.warning(f"Could not identify sender from tipbot message: {message.content}")
            return
        
        # Mark as processed
        self.processed_messages.add(message.id)
        
        # Find matching pending order
        try:
            # Get ticket for this channel
            ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
            if not ticket:
                return
            
            # Get pending orders for this user
            cursor = await self.bot.db._connection.execute(
                """
                SELECT * FROM orders 
                WHERE user_discord_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (sender_id,)
            )
            orders = await cursor.fetchall()
            
            # Find order with matching amount (within $0.50 tolerance)
            matching_order = None
            amount_cents = tip_info["amount_cents"]
            
            for order in orders:
                order_price = order.get("price_paid_cents", 0)
                # Allow $0.50 difference for rounding
                if abs(order_price - amount_cents) <= 50:
                    matching_order = order
                    break
            
            if not matching_order:
                logger.info(f"No matching order found for tip: ${tip_info['amount']} from user {sender_id}")
                return
            
            # Verify payment
            order_id = matching_order["id"]
            
            # Update order status
            await self.bot.db.update_order_status(order_id, "fulfilled")
            
            # Log payment
            await self.bot.db._connection.execute(
                """
                INSERT INTO wallet_transactions 
                (user_discord_id, transaction_type, amount_cents, description, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (sender_id, "tipbot_payment", amount_cents, f"Tipbot payment via {tip_info['tipbot']} for order #{order_id}")
            )
            await self.bot.db._connection.commit()
            
            # Notify user
            try:
                user = await self.bot.fetch_user(sender_id)
                if user:
                    embed = create_embed(
                        title="✅ Payment Verified",
                        description=f"Your payment of {format_usd(amount_cents)} has been verified!",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📦 Order",
                        value=f"Order #{order_id}",
                        inline=True
                    )
                    embed.add_field(
                        name="🤖 Tipbot",
                        value=tip_info["tipbot"].title(),
                        inline=True
                    )
                    
                    try:
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        # User has DMs disabled, send in channel
                        await message.channel.send(f"{user.mention}", embed=embed)
            except Exception as e:
                logger.error(f"Failed to notify user of payment verification: {e}")
            
            # Send confirmation in channel
            confirm_embed = create_embed(
                title="✅ Payment Verified Automatically",
                description=f"Payment of {format_usd(amount_cents)} verified via {tip_info['tipbot'].title()}",
                color=discord.Color.green()
            )
            confirm_embed.add_field(name="Order", value=f"#{order_id}", inline=True)
            confirm_embed.add_field(name="Status", value="Fulfilled", inline=True)
            
            await message.channel.send(embed=confirm_embed)
            
            logger.info(
                f"Auto-verified tipbot payment: User {sender_id}, Order {order_id}, "
                f"Amount {format_usd(amount_cents)}, Tipbot {tip_info['tipbot']}"
            )
            
        except Exception as e:
            logger.error(f"Error processing tipbot payment: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Remove from processed set if message is deleted."""
        if message.id in self.processed_messages:
            self.processed_messages.discard(message.id)


async def setup(bot: commands.Bot):
    """Load the Tipbot Monitoring cog."""
    await bot.add_cog(TipbotMonitoringCog(bot))
    logger.info("Loaded extension: cogs.tipbot_monitoring")
    logger.info("Tipbot monitoring active - will auto-verify payments from tipbots")

