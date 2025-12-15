"""Automated message system for welcome, order updates, reminders, etc."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks

from apex_core.utils import create_embed, format_usd
from apex_core.logger import get_logger

logger = get_logger()


class AutomatedMessagesCog(commands.Cog):
    """Handles all automated messages: welcome, order updates, reminders, etc."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.pending_payment_reminders: dict[int, datetime] = {}  # user_id -> reminder_time
        self.abandoned_carts: dict[int, dict] = {}  # user_id -> cart_data
        
    async def cog_load(self) -> None:
        """Start background tasks when cog loads."""
        self.payment_reminder_task.start()
        self.abandoned_cart_task.start()
        logger.info("Automated messages system loaded")
    
    async def cog_unload(self) -> None:
        """Stop background tasks when cog unloads."""
        self.payment_reminder_task.cancel()
        self.abandoned_cart_task.cancel()
        logger.info("Automated messages system unloaded")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Send welcome message when user joins server."""
        try:
            await self.send_welcome_message(member)
        except Exception as e:
            logger.error(f"Failed to send welcome message to {member.id}: {e}", exc_info=True)
    
    async def send_welcome_message(self, member: discord.Member) -> None:
        """Send personalized welcome message to new member."""
        try:
            # Get welcome channel
            welcome_channel_id = None
            if hasattr(self.bot.config, 'channel_ids') and self.bot.config.channel_ids:
                welcome_channel_id = self.bot.config.channel_ids.data.get("🎉-welcome")
            
            # Send DM welcome message
            welcome_embed = create_embed(
                title="🎉 Welcome to Apex Core!",
                description=(
                    f"**Hey {member.display_name}!** 👋\n\n"
                    "We're thrilled to have you join our community!\n\n"
                    "**Here's what you need to know:**\n\n"
                    "📦 **Browse Products** - Check out #🛍️-products to see our catalog\n"
                    "❓ **Need Help?** - Visit #❓-help or open a support ticket\n"
                    "💰 **Get Started** - Use code **WELCOME10** for 10% off your first order!\n"
                    "⭐ **Earn Rewards** - Leave reviews to earn the @⭐ Apex Insider role\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "**Quick Links:**\n"
                    "• Read our rules: #📜-rules\n"
                    "• Check FAQ: #❓-faq\n"
                    "• View testimonials: #🏆-testimonials\n\n"
                    "Questions? We're here to help! 🚀"
                ),
                color=discord.Color.blue(),
            )
            welcome_embed.set_footer(text="✨ Apex Core • Welcome to the Community")
            
            try:
                await member.send(embed=welcome_embed)
                logger.info(f"Welcome message sent to {member.id} ({member.name})")
            except discord.Forbidden:
                logger.warning(f"Could not send welcome DM to {member.id} (DMs disabled)")
            
            # Post in welcome channel if configured
            if welcome_channel_id:
                welcome_channel = member.guild.get_channel(welcome_channel_id)
                if isinstance(welcome_channel, discord.TextChannel):
                    channel_embed = create_embed(
                        title="🎉 New Member Joined!",
                        description=f"Welcome {member.mention} to **Apex Core**! 🚀\n\nMake sure to read #📜-rules and check out #❓-help to get started!",
                        color=discord.Color.green(),
                    )
                    await welcome_channel.send(embed=channel_embed)
                    
        except Exception as e:
            logger.error(f"Error in send_welcome_message: {e}", exc_info=True)
    
    async def send_order_status_update(
        self, user_id: int, order_id: int, old_status: str, new_status: str, 
        product_name: str, order_amount_cents: int
    ) -> None:
        """Send order status update DM to user."""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found for order status update")
                return
            
            status_emojis = {
                "pending": "⏳",
                "processing": "🔄",
                "completed": "✅",
                "cancelled": "❌",
                "refunded": "💰",
            }
            
            status_descriptions = {
                "pending": "Your order is pending payment confirmation.",
                "processing": "Your order is being processed by our team.",
                "completed": "Your order has been completed!",
                "cancelled": "Your order has been cancelled.",
                "refunded": "Your order has been refunded.",
            }
            
            emoji = status_emojis.get(new_status, "📦")
            description = status_descriptions.get(new_status, f"Your order status has been updated to: {new_status}")
            
            embed = create_embed(
                title=f"{emoji} Order Status Update",
                description=(
                    f"**Order ID:** #{order_id}\n"
                    f"**Product:** {product_name}\n"
                    f"**Amount:** {format_usd(order_amount_cents)}\n"
                    f"**Status:** {old_status.title()} → **{new_status.title()}**\n\n"
                    f"{description}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.green() if new_status == "completed" else discord.Color.blue(),
            )
            
            if new_status == "completed":
                embed.add_field(
                    name="✅ Order Complete!",
                    value="Thank you for your purchase! If you have any questions, please open a support ticket.",
                    inline=False
                )
            
            embed.set_footer(text="✨ Apex Core • Order Management")
            
            try:
                await user.send(embed=embed)
                logger.info(f"Order status update sent | User: {user_id} | Order: {order_id} | Status: {new_status}")
            except discord.Forbidden:
                logger.warning(f"Could not send order update DM to {user_id} (DMs disabled)")
                
        except Exception as e:
            logger.error(f"Error sending order status update: {e}", exc_info=True)
    
    async def schedule_payment_reminder(self, user_id: int, order_id: int, hours: int = 24) -> None:
        """Schedule a payment reminder for a user."""
        reminder_time = datetime.now(timezone.utc) + timedelta(hours=hours)
        self.pending_payment_reminders[user_id] = reminder_time
        logger.info(f"Payment reminder scheduled | User: {user_id} | Order: {order_id} | Reminder in {hours}h")
    
    async def send_payment_reminder(self, user_id: int, order_id: int, product_name: str, amount_cents: int) -> None:
        """Send payment reminder to user."""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            embed = create_embed(
                title="💳 Payment Reminder",
                description=(
                    f"**Order ID:** #{order_id}\n"
                    f"**Product:** {product_name}\n"
                    f"**Amount:** {format_usd(amount_cents)}\n\n"
                    "Your payment is still pending. Please complete your payment to proceed with your order.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="💡 Need Help?",
                value="If you've already paid, please contact support. Otherwise, complete your payment in the ticket channel.",
                inline=False
            )
            embed.set_footer(text="✨ Apex Core • Payment Reminder")
            
            try:
                await user.send(embed=embed)
                logger.info(f"Payment reminder sent | User: {user_id} | Order: {order_id}")
            except discord.Forbidden:
                logger.warning(f"Could not send payment reminder DM to {user_id}")
                
        except Exception as e:
            logger.error(f"Error sending payment reminder: {e}", exc_info=True)
    
    @tasks.loop(minutes=30.0)
    async def payment_reminder_task(self) -> None:
        """Check for pending payment reminders and send them."""
        try:
            current_time = datetime.now(timezone.utc)
            users_to_remind = [
                user_id for user_id, reminder_time in self.pending_payment_reminders.items()
                if current_time >= reminder_time
            ]
            
            for user_id in users_to_remind:
                # Get order info from database
                # This would need to be implemented based on your order structure
                del self.pending_payment_reminders[user_id]
                
        except Exception as e:
            logger.error(f"Error in payment_reminder_task: {e}", exc_info=True)
    
    @tasks.loop(hours=6.0)
    async def abandoned_cart_task(self) -> None:
        """Check for abandoned carts and send reminders."""
        try:
            # This would check for tickets that were opened but payment wasn't completed
            # Implementation depends on your ticket/order structure
            pass
        except Exception as e:
            logger.error(f"Error in abandoned_cart_task: {e}", exc_info=True)
    
    async def send_new_product_announcement(
        self, product_name: str, product_id: int, price_cents: int, 
        category: str, description: Optional[str] = None
    ) -> None:
        """Send new product announcement to announcements channel."""
        try:
            announcements_channel_id = None
            if hasattr(self.bot.config, 'channel_ids') and self.bot.config.channel_ids:
                announcements_channel_id = self.bot.config.channel_ids.data.get("📢-announcements")
            
            if not announcements_channel_id:
                return
            
            # Get all guilds the bot is in
            for guild in self.bot.guilds:
                channel = guild.get_channel(announcements_channel_id)
                if isinstance(channel, discord.TextChannel):
                    embed = create_embed(
                        title="🆕 New Product Available!",
                        description=(
                            f"**{product_name}** is now available!\n\n"
                            f"**Price:** {format_usd(price_cents)}\n"
                            f"**Category:** {category}\n"
                            f"{f'**Description:** {description}\n' if description else ''}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🎯 **Get it now:** Check out #🛍️-products!\n"
                            f"💎 **VIP Members:** Early access available in #💎-vip-lounge"
                        ),
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text="✨ Apex Core • New Product")
                    await channel.send(embed=embed)
                    logger.info(f"New product announcement sent | Product: {product_name} | Guild: {guild.id}")
                    
        except Exception as e:
            logger.error(f"Error sending new product announcement: {e}", exc_info=True)
    
    async def send_milestone_celebration(
        self, user_id: int, milestone_type: str, milestone_value: str
    ) -> None:
        """Send milestone celebration message to user."""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            milestone_messages = {
                "10th_order": "🎉 Congratulations on your 10th order!",
                "100th_order": "🏆 Amazing! You've reached 100 orders!",
                "1000_spent": "💎 You've spent over $1000 with us!",
                "birthday": "🎂 Happy Birthday! Here's a special gift!",
            }
            
            embed = create_embed(
                title="🎉 Milestone Achieved!",
                description=(
                    f"{milestone_messages.get(milestone_type, '🎉 Congratulations!')}\n\n"
                    f"**Milestone:** {milestone_value}\n\n"
                    "Thank you for being an amazing customer! 🚀"
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="✨ Apex Core • Milestone Celebration")
            
            try:
                await user.send(embed=embed)
                logger.info(f"Milestone celebration sent | User: {user_id} | Type: {milestone_type}")
            except discord.Forbidden:
                logger.warning(f"Could not send milestone DM to {user_id}")
                
        except Exception as e:
            logger.error(f"Error sending milestone celebration: {e}", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutomatedMessagesCog(bot))

