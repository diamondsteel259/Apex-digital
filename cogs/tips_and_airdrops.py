"""Tip and Airdrop features for wallet transfers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.admin_checks import admin_only
from apex_core.rate_limiter import rate_limit
from apex_core.financial_cooldown_manager import financial_cooldown

logger = get_logger()


class TipsAndAirdropsCog(commands.Cog):
    """Commands for tipping users and creating airdrops."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_airdrops: dict[str, dict] = {}  # airdrop_code -> airdrop_data
    
    @app_commands.command(name="tip", description="Tip another user from your wallet")
    @app_commands.guild_only()
    @app_commands.describe(
        user="User to tip",
        amount="Amount in USD (e.g., 5.00) - Min: $0.01, Max: $10,000",
        message="Optional message with your tip"
    )
    @rate_limit(cooldown=60, max_uses=10, per="user", config_key="tip")
    @financial_cooldown()
    async def tip_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: float,
        message: Optional[str] = None
    ) -> None:
        """Tip another user from your wallet."""
        await interaction.response.defer(ephemeral=True)
        
        if user.id == interaction.user.id:
            await interaction.followup.send(
                "❌ You cannot tip yourself!",
                ephemeral=True
            )
            return
        
        if user.bot:
            await interaction.followup.send(
                "❌ You cannot tip bots!",
                ephemeral=True
            )
            return
        
        # Validate amount range
        if amount < 0.01 or amount > 10000.0:
            await interaction.followup.send(
                "❌ Amount must be between $0.01 and $10,000.00",
                ephemeral=True
            )
            return
        
        amount_cents = int(amount * 100)
        
        try:
            # Ensure both users exist
            await self.bot.db.ensure_user(interaction.user.id)
            await self.bot.db.ensure_user(user.id)
            
            # Get sender balance
            sender = await self.bot.db.get_user(interaction.user.id)
            if not sender:
                await interaction.followup.send(
                    "❌ Error: Your account not found.",
                    ephemeral=True
                )
                return
            
            if sender["wallet_balance_cents"] < amount_cents:
                await interaction.followup.send(
                    f"❌ Insufficient balance. You have {format_usd(sender['wallet_balance_cents'])}",
                    ephemeral=True
                )
                return
            
            # Transfer funds
            async with self.bot.db._wallet_lock:
                await self.bot.db._connection.execute("BEGIN IMMEDIATE;")
                
                # Deduct from sender
                await self.bot.db._connection.execute(
                    """
                    UPDATE users
                    SET wallet_balance_cents = wallet_balance_cents - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                    """,
                    (amount_cents, interaction.user.id)
                )
                
                # Add to recipient
                await self.bot.db._connection.execute(
                    """
                    UPDATE users
                    SET wallet_balance_cents = wallet_balance_cents + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                    """,
                    (amount_cents, user.id)
                )
                
                # Log transaction for sender
                sender_balance = sender["wallet_balance_cents"] - amount_cents
                await self.bot.db._connection.execute(
                    """
                    INSERT INTO wallet_transactions (
                        user_discord_id, amount_cents, balance_after_cents,
                        transaction_type, description, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        interaction.user.id,
                        -amount_cents,
                        sender_balance,
                        "tip_sent",
                        f"Tip sent to {user.display_name}",
                        f'{{"recipient_id": {user.id}, "recipient_name": "{user.display_name}"}}'
                    )
                )
                
                # Log transaction for recipient
                recipient = await self.bot.db.get_user(user.id)
                recipient_balance = (recipient["wallet_balance_cents"] if recipient else 0) + amount_cents
                await self.bot.db._connection.execute(
                    """
                    INSERT INTO wallet_transactions (
                        user_discord_id, amount_cents, balance_after_cents,
                        transaction_type, description, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.id,
                        amount_cents,
                        recipient_balance,
                        "tip_received",
                        f"Tip received from {interaction.user.display_name}",
                        f'{{"sender_id": {interaction.user.id}, "sender_name": "{interaction.user.display_name}"}}'
                    )
                )
                
                await self.bot.db._connection.commit()
            
            # Send confirmation to sender
            embed = create_embed(
                title="💰 Tip Sent!",
                description=(
                    f"You sent {format_usd(amount_cents)} to {user.mention}\n\n"
                    f"**Your new balance:** {format_usd(sender_balance)}"
                ),
                color=discord.Color.green()
            )
            if message:
                embed.add_field(name="Message", value=message, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Notify recipient
            try:
                recipient_embed = create_embed(
                    title="💰 You Received a Tip!",
                    description=(
                        f"{interaction.user.mention} sent you {format_usd(amount_cents)}!\n\n"
                        f"**Your new balance:** {format_usd(recipient_balance)}"
                    ),
                    color=discord.Color.gold()
                )
                if message:
                    recipient_embed.add_field(name="Message", value=message, inline=False)
                await user.send(embed=recipient_embed)
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to {user.id} - DMs disabled")
            
            logger.info(
                f"Tip sent | Sender: {interaction.user.id} | Recipient: {user.id} | "
                f"Amount: {format_usd(amount_cents)}"
            )
            
        except Exception as e:
            logger.error(f"Error processing tip: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error processing tip: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="airdrop", description="Create an airdrop that multiple users can claim")
    @app_commands.guild_only()
    @app_commands.describe(
        amount="Total amount in USD to distribute (Min: $0.01, Max: $10,000)",
        max_claims="Maximum number of users who can claim (1-100, default: 10)",
        expires_hours="Hours until airdrop expires (1-168, default: 24)",
        message="Optional message for the airdrop"
    )
    @rate_limit(cooldown=300, max_uses=5, per="user", config_key="airdrop")
    @financial_cooldown()
    async def create_airdrop(
        self,
        interaction: discord.Interaction,
        amount: float,
        max_claims: int = 10,
        expires_hours: int = 24,
        message: Optional[str] = None
    ) -> None:
        """Create an airdrop that multiple users can claim."""
        await interaction.response.defer(ephemeral=True)
        
        # Validate ranges
        if amount < 0.01 or amount > 10000.0:
            await interaction.followup.send(
                "❌ Amount must be between $0.01 and $10,000.00",
                ephemeral=True
            )
            return
        
        if max_claims < 1 or max_claims > 100:
            await interaction.followup.send(
                "❌ Max claims must be between 1 and 100",
                ephemeral=True
            )
            return
        
        if expires_hours < 1 or expires_hours > 168:
            await interaction.followup.send(
                "❌ Expires hours must be between 1 and 168 (7 days)",
                ephemeral=True
            )
            return
        
        amount_cents = int(amount * 100)
        per_claim_cents = amount_cents // max_claims
        
        if per_claim_cents < 1:
            await interaction.followup.send(
                "❌ Amount per claim must be at least $0.01. Increase amount or decrease max claims.",
                ephemeral=True
            )
            return
        
        try:
            # Ensure user exists
            await self.bot.db.ensure_user(interaction.user.id)
            
            # Get sender balance
            sender = await self.bot.db.get_user(interaction.user.id)
            if not sender:
                await interaction.followup.send(
                    "❌ Error: Your account not found.",
                    ephemeral=True
                )
                return
            
            if sender["wallet_balance_cents"] < amount_cents:
                await interaction.followup.send(
                    f"❌ Insufficient balance. You have {format_usd(sender['wallet_balance_cents'])}",
                    ephemeral=True
                )
                return
            
            # Generate airdrop code
            import secrets
            airdrop_code = secrets.token_urlsafe(8).upper()[:8]
            
            # Reserve funds
            async with self.bot.db._wallet_lock:
                await self.bot.db._connection.execute("BEGIN IMMEDIATE;")
                
                # Deduct from sender
                await self.bot.db._connection.execute(
                    """
                    UPDATE users
                    SET wallet_balance_cents = wallet_balance_cents - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                    """,
                    (amount_cents, interaction.user.id)
                )
                
                # Log transaction
                sender_balance = sender["wallet_balance_cents"] - amount_cents
                await self.bot.db._connection.execute(
                    """
                    INSERT INTO wallet_transactions (
                        user_discord_id, amount_cents, balance_after_cents,
                        transaction_type, description, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        interaction.user.id,
                        -amount_cents,
                        sender_balance,
                        "airdrop_created",
                        f"Airdrop created: {airdrop_code}",
                        f'{{"airdrop_code": "{airdrop_code}", "max_claims": {max_claims}, "per_claim": {per_claim_cents}}}'
                    )
                )
                
                await self.bot.db._connection.commit()
            
            # Store airdrop data
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
            self.active_airdrops[airdrop_code] = {
                "creator_id": interaction.user.id,
                "creator_name": interaction.user.display_name,
                "total_amount_cents": amount_cents,
                "per_claim_cents": per_claim_cents,
                "max_claims": max_claims,
                "current_claims": 0,
                "claimed_by": set(),
                "expires_at": expires_at,
                "message": message,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Send confirmation
            embed = create_embed(
                title="🎁 Airdrop Created!",
                description=(
                    f"**Airdrop Code:** `{airdrop_code}`\n"
                    f"**Total Amount:** {format_usd(amount_cents)}\n"
                    f"**Per Claim:** {format_usd(per_claim_cents)}\n"
                    f"**Max Claims:** {max_claims}\n"
                    f"**Expires:** {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"Share this code with users to claim!"
                ),
                color=discord.Color.blue()
            )
            if message:
                embed.add_field(name="Message", value=message, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Post in airdrops channel if it exists
            airdrop_channel_id = None
            try:
                if hasattr(self.bot.config, "channel_ids"):
                    channel_ids = self.bot.config.channel_ids
                    if hasattr(channel_ids, "data") and isinstance(channel_ids.data, dict):
                        airdrop_channel_id = channel_ids.data.get("airdrops")
                    elif hasattr(channel_ids, "airdrops"):
                        airdrop_channel_id = channel_ids.airdrops
            except (AttributeError, TypeError):
                pass
            
            if airdrop_channel_id and interaction.guild:
                channel = interaction.guild.get_channel(airdrop_channel_id)
                if isinstance(channel, discord.TextChannel):
                    public_embed = create_embed(
                        title="🎁 New Airdrop Available!",
                        description=(
                            f"**Code:** `{airdrop_code}`\n"
                            f"**Amount per claim:** {format_usd(per_claim_cents)}\n"
                            f"**Claims remaining:** {max_claims}\n"
                            f"**Expires:** {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                            f"Use `/claimairdrop code:{airdrop_code}` to claim!"
                        ),
                        color=discord.Color.gold()
                    )
                    if message:
                        public_embed.add_field(name="Message", value=message, inline=False)
                    await channel.send(embed=public_embed)
            
            logger.info(
                f"Airdrop created | Creator: {interaction.user.id} | Code: {airdrop_code} | "
                f"Amount: {format_usd(amount_cents)} | Max claims: {max_claims}"
            )
            
        except Exception as e:
            logger.error(f"Error creating airdrop: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error creating airdrop: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="claimairdrop", description="Claim an airdrop using the code")
    @app_commands.guild_only()
    @app_commands.describe(code="Airdrop code to claim")
    @rate_limit(cooldown=60, max_uses=10, per="user", config_key="claim_airdrop")
    @financial_cooldown()
    async def claim_airdrop(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """Claim an airdrop using the code."""
        await interaction.response.defer(ephemeral=True)
        
        code_upper = code.upper().strip()
        
        if code_upper not in self.active_airdrops:
            await interaction.followup.send(
                "❌ Invalid airdrop code or airdrop has expired.",
                ephemeral=True
            )
            return
        
        airdrop = self.active_airdrops[code_upper]
        
        # Check if expired
        if datetime.now(timezone.utc) > airdrop["expires_at"]:
            del self.active_airdrops[code_upper]
            await interaction.followup.send(
                "❌ This airdrop has expired.",
                ephemeral=True
            )
            return
        
        # Check if user already claimed
        if interaction.user.id in airdrop["claimed_by"]:
            await interaction.followup.send(
                "❌ You have already claimed this airdrop!",
                ephemeral=True
            )
            return
        
        # Check if creator trying to claim their own
        if interaction.user.id == airdrop["creator_id"]:
            await interaction.followup.send(
                "❌ You cannot claim your own airdrop!",
                ephemeral=True
            )
            return
        
        # Check if max claims reached
        if airdrop["current_claims"] >= airdrop["max_claims"]:
            await interaction.followup.send(
                "❌ This airdrop has reached its maximum number of claims.",
                ephemeral=True
            )
            return
        
        try:
            # Ensure user exists
            await self.bot.db.ensure_user(interaction.user.id)
            
            # Add funds to user
            async with self.bot.db._wallet_lock:
                await self.bot.db._connection.execute("BEGIN IMMEDIATE;")
                
                # Add to recipient
                await self.bot.db._connection.execute(
                    """
                    UPDATE users
                    SET wallet_balance_cents = wallet_balance_cents + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                    """,
                    (airdrop["per_claim_cents"], interaction.user.id)
                )
                
                # Log transaction
                recipient = await self.bot.db.get_user(interaction.user.id)
                recipient_balance = (recipient["wallet_balance_cents"] if recipient else 0) + airdrop["per_claim_cents"]
                await self.bot.db._connection.execute(
                    """
                    INSERT INTO wallet_transactions (
                        user_discord_id, amount_cents, balance_after_cents,
                        transaction_type, description, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        interaction.user.id,
                        airdrop["per_claim_cents"],
                        recipient_balance,
                        "airdrop_claimed",
                        f"Airdrop claimed: {code_upper}",
                        f'{{"airdrop_code": "{code_upper}", "creator_id": {airdrop["creator_id"]}}}'
                    )
                )
                
                await self.bot.db._connection.commit()
            
            # Update airdrop
            airdrop["current_claims"] += 1
            airdrop["claimed_by"].add(interaction.user.id)
            
            # Send confirmation
            embed = create_embed(
                title="🎁 Airdrop Claimed!",
                description=(
                    f"You claimed {format_usd(airdrop['per_claim_cents'])} from airdrop `{code_upper}`!\n\n"
                    f"**Your new balance:** {format_usd(recipient_balance)}\n"
                    f"**Remaining claims:** {airdrop['max_claims'] - airdrop['current_claims']}"
                ),
                color=discord.Color.green()
            )
            if airdrop.get("message"):
                embed.add_field(name="Message from Creator", value=airdrop["message"], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(
                f"Airdrop claimed | User: {interaction.user.id} | Code: {code_upper} | "
                f"Amount: {format_usd(airdrop['per_claim_cents'])}"
            )
            
        except Exception as e:
            logger.error(f"Error claiming airdrop: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error claiming airdrop: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="airdropinfo", description="View information about an airdrop")
    @app_commands.guild_only()
    @app_commands.describe(code="Airdrop code to check")
    async def airdrop_info(
        self,
        interaction: discord.Interaction,
        code: str
    ) -> None:
        """View information about an airdrop."""
        await interaction.response.defer(ephemeral=True)
        
        code_upper = code.upper().strip()
        
        if code_upper not in self.active_airdrops:
            await interaction.followup.send(
                "❌ Invalid airdrop code or airdrop has expired.",
                ephemeral=True
            )
            return
        
        airdrop = self.active_airdrops[code_upper]
        
        # Check if expired
        if datetime.now(timezone.utc) > airdrop["expires_at"]:
            del self.active_airdrops[code_upper]
            await interaction.followup.send(
                "❌ This airdrop has expired.",
                ephemeral=True
            )
            return
        
        # Check if user already claimed
        has_claimed = interaction.user.id in airdrop["claimed_by"]
        
        embed = create_embed(
            title=f"🎁 Airdrop: {code_upper}",
            description=(
                f"**Creator:** {airdrop['creator_name']}\n"
                f"**Amount per claim:** {format_usd(airdrop['per_claim_cents'])}\n"
                f"**Total amount:** {format_usd(airdrop['total_amount_cents'])}\n"
                f"**Claims:** {airdrop['current_claims']}/{airdrop['max_claims']}\n"
                f"**Expires:** {airdrop['expires_at'].strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"**Status:** {'✅ You have claimed this' if has_claimed else '⏳ Available to claim'}"
            ),
            color=discord.Color.blue()
        )
        if airdrop.get("message"):
            embed.add_field(name="Message", value=airdrop["message"], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TipsAndAirdropsCog(bot))

