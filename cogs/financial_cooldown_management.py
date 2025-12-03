"""Admin commands for managing financial cooldowns."""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.financial_cooldown_manager import get_financial_cooldown_manager
from apex_core.utils import create_embed

logger = logging.getLogger(__name__)


class FinancialCooldownManagementCog(commands.Cog):
    """Admin commands for managing financial command cooldowns."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        """Only allow admins to use these commands."""
        if not ctx.guild:
            return False
        
        if not hasattr(self.bot, 'config') or not hasattr(self.bot.config, 'role_ids'):
            return False
        
        admin_role_id = getattr(self.bot.config.role_ids, 'admin', None)
        if not admin_role_id:
            return False
        
        member = ctx.guild.get_member(ctx.author.id)
        if not member:
            return False
        
        return any(role.id == admin_role_id for role in member.roles)
    
    @commands.command(name="cooldown-check", aliases=["cc"])
    @commands.guild_only()
    async def cooldown_check(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ) -> None:
        """
        Check active cooldowns for a user.
        
        Usage: !cooldown-check [@user]
        If no user is specified, checks your own cooldowns.
        """
        target_member = member or ctx.author
        
        manager = get_financial_cooldown_manager()
        cooldowns = await manager.get_all_user_cooldowns(target_member.id)
        
        if not cooldowns:
            embed = create_embed(
                title="📊 Cooldown Status",
                description=f"{target_member.mention} has no active financial cooldowns.",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)
            return
        
        # Build cooldown list
        cooldown_lines = []
        for command, remaining in cooldowns.items():
            if remaining >= 3600:
                time_str = f"{remaining // 3600}h {(remaining % 3600) // 60}m"
            elif remaining >= 60:
                time_str = f"{remaining // 60}m {remaining % 60}s"
            else:
                time_str = f"{remaining}s"
            
            cooldown_lines.append(f"**`{command}`**: {time_str}")
        
        embed = create_embed(
            title="📊 Active Cooldowns",
            description=f"Financial cooldowns for {target_member.mention}:\n\n" + "\n".join(cooldown_lines),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="Use !cooldown-reset to clear specific cooldowns")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="cooldown-reset", aliases=["cr"])
    @commands.guild_only()
    async def cooldown_reset(
        self,
        ctx: commands.Context,
        member: discord.Member,
        command: str,
    ) -> None:
        """
        Reset a specific cooldown for a user.
        
        Usage: !cooldown-reset @user command_name
        
        Examples:
        !cooldown-reset @user wallet_payment
        !cooldown-reset @user submitrefund
        !cooldown-reset @user balance
        """
        manager = get_financial_cooldown_manager()
        
        # Check if cooldown exists
        is_on_cooldown, remaining = await manager.check_cooldown(member.id, command)
        
        if not is_on_cooldown:
            embed = create_embed(
                title="❌ Cooldown Not Found",
                description=f"{member.mention} has no active cooldown for `{command}`.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return
        
        # Reset the cooldown
        was_reset = await manager.reset_cooldown(member.id, command)
        
        if was_reset:
            embed = create_embed(
                title="✅ Cooldown Reset",
                description=(
                    f"Reset `{command}` cooldown for {member.mention}.\n"
                    f"**Remaining time cleared:** {remaining}s"
                ),
                color=discord.Color.green(),
            )
            
            # Log to audit channel
            if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'logging_channels'):
                audit_channel_id = getattr(self.bot.config.logging_channels, 'audit', None)
                if audit_channel_id:
                    audit_channel = ctx.guild.get_channel(audit_channel_id)
                    if isinstance(audit_channel, discord.TextChannel):
                        audit_embed = create_embed(
                            title="🔧 Cooldown Reset by Admin",
                            description=(
                                f"**Admin:** {ctx.author.mention} ({ctx.author.id})\n"
                                f"**Target:** {member.mention} ({member.id})\n"
                                f"**Command:** `{command}`\n"
                                f"**Time Remaining:** {remaining}s"
                            ),
                            color=discord.Color.blue(),
                        )
                        await audit_channel.send(embed=audit_embed)
            
            await ctx.send(embed=embed)
        else:
            embed = create_embed(
                title="❌ Reset Failed",
                description=f"Failed to reset `{command}` cooldown for {member.mention}.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="cooldown-cleanup")
    @commands.guild_only()
    async def cooldown_cleanup(self, ctx: commands.Context) -> None:
        """Clean up all expired cooldowns from memory."""
        manager = get_financial_cooldown_manager()
        cleaned_count = await manager.cleanup_expired()
        
        embed = create_embed(
            title="🧹 Cooldown Cleanup",
            description=f"Cleaned up {cleaned_count} expired cooldown entries from memory.",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="financial-commands", aliases=["fc"])
    @commands.guild_only()
    async def financial_commands(self, ctx: commands.Context) -> None:
        """List all available financial commands for cooldown management."""
        commands_list = [
            "**Ultra-Sensitive Operations:**",
            "`wallet_payment` - 30s cooldown",
            "`submitrefund` - 5min cooldown", 
            "`manual_complete` - 10s cooldown",
            "",
            "**Sensitive Operations:**",
            "`setref` - 24h cooldown",
            "`refund_approve` - 5s cooldown",
            "`refund_reject` - 5s cooldown",
            "",
            "**Standard Operations:**",
            "`balance` - 10s cooldown",
            "`orders` - 30s cooldown",
            "`invites` - 30s cooldown",
        ]
        
        embed = create_embed(
            title="💰 Financial Commands",
            description="\n".join(commands_list),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Use !cooldown-reset @user command_name to reset cooldowns")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the financial cooldown management cog."""
    await bot.add_cog(FinancialCooldownManagementCog(bot))
    logger.info("Financial cooldown management cog loaded")