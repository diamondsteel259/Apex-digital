"""
Bot Status and Announcement System

Features:
- Bot overview messages to announcement channel
- Status updates (bot down, errors, product imports, etc.)
- System health monitoring
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

from apex_core.logger import get_logger
from apex_core.utils import create_embed

logger = get_logger()


class BotStatusCog(commands.Cog):
    """Bot status monitoring and announcements."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_status = "online"
        self.status_channel_id: Optional[int] = None
        self.announcement_channel_id: Optional[int] = None
    
    async def cog_load(self) -> None:
        """Initialize status channels."""
        # Get channel IDs from config (by name lookup)
        if hasattr(self.bot.config, 'channel_ids') and hasattr(self.bot.config.channel_ids, 'data'):
            channel_data = self.bot.config.channel_ids.data
            self.status_channel_id = channel_data.get("📊-status") or channel_data.get("status")
            self.announcement_channel_id = channel_data.get("📢-announcements") or channel_data.get("announcements")
        
        logger.info("Bot status system loaded")
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Send bot overview and status update when bot is ready."""
        # Wait a bit for channels to be available
        await asyncio.sleep(2)
        await self.send_bot_overview()
        await self.send_status_update(
            "info",
            "Bot is online and ready to serve!",
            discord.Color.green()
        )
    
    async def send_bot_overview(self) -> None:
        """Send bot overview message to announcement channel."""
        if not self.announcement_channel_id:
            return
        
        try:
            channel = self.bot.get_channel(self.announcement_channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return
            
            embed = create_embed(
                title="🤖 Apex Core Bot Overview",
                description="**Bot Status:** ✅ Online and Ready",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Bot Statistics",
                value=(
                    f"**Uptime:** Just started\n"
                    f"**Version:** Apex Core v2.0\n"
                    f"**Status:** Operational"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Available Features",
                value=(
                    "✅ Product Storefront\n"
                    "✅ Wallet System\n"
                    "✅ Ticket Management\n"
                    "✅ AI Support (Free/Premium/Ultra)\n"
                    "✅ Atto Integration (10% deposit + 2.5% payment bonus)\n"
                    "✅ Payment Automation (Tipbots, Crypto, etc.)\n"
                    "✅ Review System\n"
                    "✅ Referral System\n"
                    "✅ VIP Tiers\n"
                    "✅ Promo Codes"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔗 Quick Links",
                value=(
                    "`/buy` - Browse products\n"
                    "`/balance` - Check wallet\n"
                    "`/help` - View all commands"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            await channel.send(embed=embed)
            logger.info("Sent bot overview to announcement channel")
            
        except Exception as e:
            logger.error(f"Failed to send bot overview: {e}")
    
    async def send_status_update(self, status_type: str, message: str, color: discord.Color = discord.Color.blue()) -> None:
        """Send status update to status channel."""
        if not self.status_channel_id:
            return
        
        try:
            channel = self.bot.get_channel(self.status_channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return
            
            status_emoji = {
                "maintenance": "🔧",
                "error": "⚠️",
                "import": "📦",
                "ticket": "🎫",
                "payment": "💳",
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
            }
            
            emoji = status_emoji.get(status_type, "📊")
            
            embed = create_embed(
                title=f"{emoji} {status_type.title()} Update",
                description=message,
                color=color
            )
            
            embed.set_footer(text=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))
            
            await channel.send(embed=embed)
            logger.info(f"Sent status update: {status_type} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")
    
    
    @commands.Cog.listener()
    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Send error status update."""
        await self.send_status_update(
            "error",
            f"Error detected in event: {event}. Check logs for details.",
            discord.Color.red()
        )


async def setup(bot: commands.Bot):
    """Load the Bot Status cog."""
    await bot.add_cog(BotStatusCog(bot))
    logger.info("Loaded extension: cogs.bot_status")

