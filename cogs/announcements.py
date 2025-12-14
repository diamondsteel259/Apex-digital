"""Announcement system for broadcasting messages to users."""

from __future__ import annotations

import asyncio
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()

# Rate limiting constants
DM_BATCH_SIZE = 5  # Discord allows 5 DMs per 5 seconds
DM_DELAY_SECONDS = 1.2  # Slightly more than 1 second between batches


class AnnouncementsCog(commands.Cog):
    """Commands for sending announcements."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    async def _get_target_users(
        self,
        guild: discord.Guild,
        target: Optional[str] = None
    ) -> list[discord.Member]:
        """Get list of users to send announcement to."""
        users = []
        
        if target is None or target.lower() == "all":
            # All members
            logger.info(f"Getting all members for announcement | Guild: {guild.id}")
            async for member in guild.fetch_members(limit=None):
                if not member.bot:
                    users.append(member)
        elif target.startswith("role:"):
            # Specific role
            try:
                role_id = int(target.split(":")[1])
                role = guild.get_role(role_id)
                if role:
                    logger.info(f"Getting members with role {role.name} ({role_id}) for announcement")
                    for member in role.members:
                        if not member.bot:
                            users.append(member)
                else:
                    logger.warning(f"Role {role_id} not found for announcement")
            except (ValueError, IndexError):
                logger.error(f"Invalid role target format: {target}")
        elif target.startswith("vip:"):
            # VIP tier
            tier_name = target.split(":")[1]
            logger.info(f"Getting VIP tier {tier_name} members for announcement")
            # This would need VIP tier checking logic
            # For now, return empty - can be implemented later
        elif target.lower() == "customers":
            # Users with orders
            logger.info("Getting customers (users with orders) for announcement")
            if self.bot.db._connection:
                cursor = await self.bot.db._connection.execute(
                    "SELECT DISTINCT user_discord_id FROM orders"
                )
                rows = await cursor.fetchall()
                for row in rows:
                    member = guild.get_member(row["user_discord_id"])
                    if member and not member.bot:
                        users.append(member)
        
        logger.info(f"Found {len(users)} target users for announcement")
        return users

    async def _send_dm_announcement(
        self,
        user: discord.Member,
        title: str,
        message: str
    ) -> bool:
        """Send DM announcement to a user.
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            embed = create_embed(
                title=title,
                description=message,
                color=discord.Color.blue()
            )
            embed.set_footer(text="Apex Digital Announcement")
            
            await user.send(embed=embed)
            logger.debug(f"Announcement DM sent successfully | User: {user.id}")
            return True
        except discord.Forbidden:
            logger.debug(f"Cannot send DM to user {user.id} - DMs disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to send DM to user {user.id}: {e}")
            return False

    @app_commands.command(name="announce")
    @app_commands.describe(
        title="Announcement title",
        message="Announcement message",
        method="Delivery method (DM or channel)",
        target="Target audience (optional - leave empty for all)"
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str,
        method: Literal["dm", "channel"],
        target: Optional[str] = None
    ) -> None:
        """Send announcement to users (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted announce | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logger.info(
            f"Announcement started | Admin: {interaction.user.id} | "
            f"Method: {method} | Target: {target or 'all'} | Guild: {interaction.guild.id}"
        )
        
        try:
            if method == "dm":
                # Get target users
                users = await self._get_target_users(interaction.guild, target)
                
                if not users:
                    await interaction.followup.send(
                        "❌ No users found matching the target criteria.",
                        ephemeral=True
                    )
                    return
                
                # Show progress embed
                progress_embed = create_embed(
                    title="📢 Sending Announcements",
                    description=f"Progress: 0/{len(users)}",
                    color=discord.Color.blue()
                )
                progress_msg = await interaction.followup.send(embed=progress_embed, ephemeral=True)
                
                # Send in batches with rate limiting
                sent = 0
                failed = 0
                total = len(users)
                
                logger.info(f"Sending announcements to {total} users in batches of {DM_BATCH_SIZE}")
                
                for i in range(0, total, DM_BATCH_SIZE):
                    batch = users[i:i + DM_BATCH_SIZE]
                    
                    # Send batch
                    results = await asyncio.gather(
                        *[self._send_dm_announcement(user, title, message) for user in batch],
                        return_exceptions=True
                    )
                    
                    # Count results
                    for result in results:
                        if result is True:
                            sent += 1
                        else:
                            failed += 1
                    
                    # Update progress every batch
                    progress_embed.description = f"Progress: {sent + failed}/{total} sent, {sent} successful, {failed} failed"
                    try:
                        await progress_msg.edit(embed=progress_embed)
                    except:
                        pass
                    
                    logger.debug(f"Announcement batch complete | Sent: {sent} | Failed: {failed} | Total: {total}")
                    
                    # Rate limit delay (except for last batch)
                    if i + DM_BATCH_SIZE < total:
                        await asyncio.sleep(DM_DELAY_SECONDS)
                
                # Record announcement
                announcement_id = await self.bot.db.create_announcement(
                    title=title,
                    message=message,
                    announcement_type=target or "all",
                    delivery_method="dm",
                    created_by_staff_id=interaction.user.id
                )
                
                await self.bot.db.update_announcement_stats(
                    announcement_id,
                    total_recipients=total,
                    successful_deliveries=sent,
                    failed_deliveries=failed
                )
                
                # Final update
                final_embed = create_embed(
                    title="✅ Announcements Sent",
                    description=(
                        f"**Total Recipients:** {total}\n"
                        f"**Successful:** {sent}\n"
                        f"**Failed:** {failed}\n"
                        f"**Success Rate:** {(sent/total*100):.1f}%"
                    ),
                    color=discord.Color.green() if failed == 0 else discord.Color.orange()
                )
                
                await progress_msg.edit(embed=final_embed)
                
                logger.info(
                    f"Announcement completed | ID: {announcement_id} | "
                    f"Sent: {sent} | Failed: {failed} | Total: {total}"
                )
                
            elif method == "channel":
                # Channel announcement
                if target is None:
                    await interaction.followup.send(
                        "❌ Please specify a channel ID for channel announcements.",
                        ephemeral=True
                    )
                    return
                
                try:
                    channel_id = int(target)
                    channel = interaction.guild.get_channel(channel_id)
                    
                    if not isinstance(channel, discord.TextChannel):
                        await interaction.followup.send(
                            "❌ Channel not found or is not a text channel.",
                            ephemeral=True
                        )
                        return
                    
                    embed = create_embed(
                        title=title,
                        description=message,
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Apex Digital Announcement")
                    
                    await channel.send(embed=embed)
                    
                    logger.info(
                        f"Channel announcement sent | Channel: {channel_id} | "
                        f"Admin: {interaction.user.id}"
                    )
                    
                    await interaction.followup.send(
                        f"✅ Announcement sent to {channel.mention}!",
                        ephemeral=True
                    )
                except ValueError:
                    await interaction.followup.send(
                        "❌ Invalid channel ID format.",
                        ephemeral=True
                    )
            
        except Exception as e:
            logger.exception(f"Failed to send announcement | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to send announcement: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="announcements")
    @app_commands.describe(limit="Number of announcements to show")
    async def list_announcements(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ) -> None:
        """View announcement history (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted announcements | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(f"Admin viewing announcements | Admin: {interaction.user.id} | Limit: {limit}")
            
            announcements = await self.bot.db.get_announcements(limit=limit, offset=0)
            
            if not announcements:
                await interaction.followup.send(
                    "📭 No announcements found.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="📢 Announcement History",
                description=f"Showing last {len(announcements)} announcement(s):",
                color=discord.Color.blue()
            )
            
            for ann in announcements[:10]:
                embed.add_field(
                    name=f"{ann['title']} ({ann['delivery_method'].upper()})",
                    value=(
                        f"**Recipients:** {ann['total_recipients']}\n"
                        f"**Successful:** {ann['successful_deliveries']}\n"
                        f"**Failed:** {ann['failed_deliveries']}\n"
                        f"**Date:** {ann['created_at'][:10]}"
                    ),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Failed to list announcements | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to load announcements: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="testannouncement")
    @app_commands.describe(
        title="Announcement title",
        message="Announcement message"
    )
    async def test_announcement(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str
    ) -> None:
        """Send test announcement to yourself (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted testannouncement | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(f"Admin testing announcement | Admin: {interaction.user.id}")
            
            success = await self._send_dm_announcement(
                interaction.user,  # type: ignore
                title,
                message
            )
            
            if success:
                await interaction.followup.send(
                    "✅ Test announcement sent! Check your DMs.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to send test announcement. Make sure DMs are enabled.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.exception(f"Failed to send test announcement | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to send test: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Load the AnnouncementsCog cog."""
    await bot.add_cog(AnnouncementsCog(bot))

