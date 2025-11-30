"""Post-purchase processing utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config, VipTier

logger = logging.getLogger(__name__)


async def process_post_purchase(
    user_discord_id: int,
    amount_cents: int,
    db,
    config: Config,
    guild=None,
) -> tuple[VipTier | None, VipTier | None]:
    """
    Process post-purchase actions including VIP tier updates.
    
    Args:
        user_discord_id: Discord user ID
        amount_cents: Purchase amount in cents
        db: Database instance
        config: Bot configuration
        guild: Discord guild (optional, for role assignments)
    
    Returns:
        Tuple of (old_vip_tier, new_vip_tier)
    """
    from .vip import calculate_vip_tier
    
    # Get current user data
    user_row = await db.get_user(user_discord_id)
    if not user_row:
        logger.warning("User %s not found for post-purchase processing", user_discord_id)
        return None, None
    
    # Calculate current and new VIP tiers
    old_vip_tier = calculate_vip_tier(user_row["total_lifetime_spent_cents"], config)
    new_lifetime_spend = user_row["total_lifetime_spent_cents"] + amount_cents
    new_vip_tier = calculate_vip_tier(new_lifetime_spend, config)
    
    # Update VIP tier in database if it changed
    if new_vip_tier and (not old_vip_tier or new_vip_tier.name != old_vip_tier.name):
        await db.update_user_vip_tier(user_discord_id, new_vip_tier.name)
        logger.info(
            "Updated user %s VIP tier from %s to %s (lifetime spend: %s)",
            user_discord_id,
            old_vip_tier.name if old_vip_tier else "None",
            new_vip_tier.name,
            new_lifetime_spend,
        )
    
    return old_vip_tier, new_vip_tier


async def handle_vip_promotion(
    user_discord_id: int,
    old_vip_tier: VipTier | None,
    new_vip_tier: VipTier | None,
    config: Config,
    guild=None,
) -> None:
    """
    Handle VIP promotion notifications and role assignments.
    
    Args:
        user_discord_id: Discord user ID
        old_vip_tier: Previous VIP tier (can be None)
        new_vip_tier: New VIP tier (can be None)
        config: Bot configuration
        guild: Discord guild for role assignments
    """
    if not new_vip_tier or (old_vip_tier and new_vip_tier.name == old_vip_tier.name):
        return  # No promotion occurred
    
    try:
        import discord
        from .embeds import create_embed
        from .timestamps import discord_timestamp
        
        user = None
        if guild:
            user = guild.get_member(user_discord_id)
        
        # Assign VIP role
        if guild and user:
            role_id = getattr(config.role_ids, f"vip_{new_vip_tier.name}", None)
            if role_id:
                role = guild.get_role(role_id)
                if role:
                    await user.add_roles(role, reason=f"VIP promotion to {new_vip_tier.name}")
                    logger.info("Assigned VIP role %s to user %s", role.id, user_discord_id)
                else:
                    logger.warning("VIP role %s not found in guild", role_id)
        
        # Send congratulatory DM
        if user:
            from datetime import datetime, timezone
            
            embed = create_embed(
                title="🎉 VIP Promotion!",
                description=(
                    f"Congratulations! You've been promoted to **{new_vip_tier.name.upper()}** VIP status!\n\n"
                    f"**Lifetime Spend:** ${new_vip_tier.min_spend_cents / 100:.2f}+\n"
                    f"**Discount Benefit:** {new_vip_tier.discount_percent:.1f}% off\n"
                    f"**Promotion Date:** {discord_timestamp(datetime.now(timezone.utc), 'R')}"
                ),
                color=discord.Color.gold(),
            )
            
            try:
                await user.send(embed=embed)
                logger.info("Sent VIP promotion DM to user %s", user_discord_id)
            except discord.Forbidden:
                logger.warning("Could not DM user %s about VIP promotion", user_discord_id)
        
        # Log to staff channel
        if guild:
            log_channel_id = config.logging_channels.audit
            log_channel = guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                log_embed = create_embed(
                    title="VIP Promotion",
                    description=(
                        f"**User:** {user.mention if user else f'<@{user_discord_id}>'} ({user_discord_id})\n"
                        f"**Previous Tier:** {old_vip_tier.name.upper() if old_vip_tier else 'None'}\n"
                        f"**New Tier:** {new_vip_tier.name.upper()}\n"
                        f"**Discount:** {new_vip_tier.discount_percent:.1f}%\n"
                        f"**Min Spend:** ${new_vip_tier.min_spend_cents / 100:.2f}"
                    ),
                    color=discord.Color.gold(),
                )
                await log_channel.send(embed=log_embed)
                logger.info("Logged VIP promotion for user %s", user_discord_id)
    
    except Exception as e:
        logger.error("Error handling VIP promotion for user %s: %s", user_discord_id, e)