"""Cache management and monitoring commands for administrators."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.cache_manager import get_cache_manager
from apex_core.logger import get_logger

logger = get_logger()


class CacheManagementCog(commands.Cog):
    """Cache management and monitoring commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache_manager = get_cache_manager()

    def cog_check(self, ctx: commands.Context) -> bool:
        """Only allow administrators to use cache commands."""
        return ctx.author.guild_permissions.administrator

    @app_commands.command(name="cache-stats", description="Show cache statistics and performance metrics")
    async def cache_stats(self, interaction: discord.Interaction) -> None:
        """Display comprehensive cache statistics."""
        try:
            stats = self.cache_manager.get_stats()
            top_entries = await self.cache_manager.get_top_entries(10)
            
            # Create main statistics embed
            embed = discord.Embed(
                title="📊 Cache Statistics",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Performance metrics
            embed.add_field(
                name="🎯 Performance",
                value=f"**Hit Rate:** {stats['hit_rate']:.1%}\n"
                      f"**Total Hits:** {stats['total_hits']:,}\n"
                      f"**Total Misses:** {stats['total_misses']:,}\n"
                      f"**Total Sets:** {stats['total_sets']:,}",
                inline=True
            )
            
            # Memory usage
            embed.add_field(
                name="💾 Memory Usage",
                value=f"**Used:** {stats['memory_usage_mb']:.2f} MB\n"
                      f"**Max:** {stats['max_size_mb']:.0f} MB\n"
                      f"**Usage:** {stats['memory_usage_mb']/stats['max_size_mb']:.1%}\n"
                      f"**Entries:** {stats['entry_count']:,}",
                inline=True
            )
            
            # Cache health
            health_emoji = "🟢" if stats['hit_rate'] > 0.8 else "🟡" if stats['hit_rate'] > 0.5 else "🔴"
            embed.add_field(
                name=f"{health_emoji} Cache Health",
                value=f"**Status:** {'Excellent' if stats['hit_rate'] > 0.8 else 'Good' if stats['hit_rate'] > 0.5 else 'Poor'}\n"
                      f"**Invalidations:** {stats['total_invalidations']:,}\n"
                      f"**Oldest Entry:** {stats['oldest_entry_age']/3600:.1f}h ago",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
            
            # Show top cached entries if any exist
            if top_entries:
                top_embed = discord.Embed(
                    title="🔥 Top Cached Entries",
                    color=discord.Color.orange(),
                    description="Most frequently accessed cache entries"
                )
                
                for i, entry in enumerate(top_entries[:5], 1):
                    key = entry['key']
                    access_count = entry['access_count']
                    size_kb = entry['size_bytes'] / 1024
                    ttl_min = entry['ttl_remaining'] / 60
                    
                    top_embed.add_field(
                        name=f"{i}. {key}",
                        value=f"**Accesses:** {access_count:,}\n"
                              f"**Size:** {size_kb:.1f} KB\n"
                              f"**TTL:** {ttl_min:.0f} min",
                        inline=True
                    )
                
                await interaction.followup.send(embed=top_embed)
        
        except Exception as e:
            logger.error(f"Error in cache_stats command: {e}")
            await interaction.response.send_message(
                "❌ Failed to retrieve cache statistics.",
                ephemeral=True
            )

    @app_commands.command(name="cache-clear", description="Clear cache entries matching a pattern")
    @app_commands.describe(
        pattern="Pattern to match (use * for wildcard, or 'all' to clear everything)"
    )
    async def cache_clear(self, interaction: discord.Interaction, pattern: str) -> None:
        """Clear cache entries matching a pattern."""
        try:
            if pattern.lower() == "all":
                await self.cache_manager.clear_all()
                embed = discord.Embed(
                    title="🧹 Cache Cleared",
                    description="All cache entries have been cleared.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            else:
                count = await self.cache_manager.invalidate(pattern)
                embed = discord.Embed(
                    title="🧹 Cache Entries Cleared",
                    description=f"Cleared {count} cache entries matching: `{pattern}`",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in cache_clear command: {e}")
            await interaction.response.send_message(
                "❌ Failed to clear cache entries.",
                ephemeral=True
            )

    @app_commands.command(name="cache-warm", description="Manually warm up cache with fresh data")
    @app_commands.describe(
        scope="What to warm up: 'config', 'reference', 'all'"
    )
    async def cache_warm(self, interaction: discord.Interaction, scope: str = "all") -> None:
        """Manually warm up cache with fresh data."""
        if scope not in ["config", "reference", "all"]:
            await interaction.response.send_message(
                "❌ Invalid scope. Use: config, reference, or all",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer(thinking=True)
            
            # Warm up specific cache tiers
            if scope in ["config", "all"]:
                # Cache configuration data
                config = self.bot.config
                cache_manager = self.cache_manager
                
                if config.cache_settings and config.cache_settings.enabled:
                    # Cache VIP tiers
                    await cache_manager.get(
                        "config::vip_tiers",
                        lambda: config.roles,
                        config.cache_settings.ttl_config
                    )
                    
                    # Cache payment methods
                    payment_methods = (
                        config.payment_settings.payment_methods 
                        if config.payment_settings 
                        else config.payment_methods
                    )
                    await cache_manager.get(
                        "config::payment_methods",
                        lambda: payment_methods,
                        config.cache_settings.ttl_config
                    )
            
            if scope in ["reference", "all"]:
                # Warm reference data
                db = self.bot.db
                await db.get_distinct_main_categories()
                await db.get_all_products(active_only=True)
                await db.get_applicable_discounts(
                    user_id=None,
                    product_id=None,
                    vip_tier=None
                )
            
            embed = discord.Embed(
                title="🔥 Cache Warmed",
                description=f"Successfully warmed up {scope} cache.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in cache_warm command: {e}")
            await interaction.followup.send(
                "❌ Failed to warm up cache.",
                ephemeral=True
            )

    @app_commands.command(name="cache-info", description="Show detailed cache configuration and status")
    async def cache_info(self, interaction: discord.Interaction) -> None:
        """Display detailed cache configuration."""
        try:
            config = self.bot.config.cache_settings
            
            if not config or not config.enabled:
                embed = discord.Embed(
                    title="ℹ️ Cache Information",
                    description="Cache is **disabled** in configuration.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title="ℹ️ Cache Configuration",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Configuration details
            embed.add_field(
                name="⚙️ Configuration",
                value=f"**Status:** {'✅ Enabled' if config.enabled else '❌ Disabled'}\n"
                      f"**Max Size:** {config.max_size_mb} MB\n"
                      f"**Cleanup Interval:** {config.cleanup_interval}s",
                inline=True
            )
            
            # TTL settings
            embed.add_field(
                name="⏰ TTL Settings",
                value=f"**Config:** {config.ttl_config//3600}h\n"
                      f"**Reference:** {config.ttl_reference//3600}h\n"
                      f"**User:** {config.ttl_user//60}m\n"
                      f"**Query:** {config.ttl_query//60}m",
                inline=True
            )
            
            # Cache tiers explanation
            embed.add_field(
                name="📚 Cache Tiers",
                value="**Tier 1 (Config):** VIP tiers, payment methods\n"
                      "**Tier 2 (Reference):** Products, categories\n"
                      "**Tier 3 (User):** Profiles, orders\n"
                      "**Tier 4 (Query):** Search results",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in cache_info command: {e}")
            await interaction.response.send_message(
                "❌ Failed to retrieve cache information.",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the cache management cog."""
    await bot.add_cog(CacheManagementCog(bot))
    logger.info("CacheManagementCog loaded")