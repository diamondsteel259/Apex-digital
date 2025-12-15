"""
Apex Core - Discord Bot for automated product distribution and ticketing.

This is the main entrypoint for the bot.
"""

import asyncio
import logging
import os
import re
import sys
from dataclasses import replace
from pathlib import Path

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from apex_core import load_config, load_payment_settings, Database, TranscriptStorage
from apex_core.logger import setup_logger

# Load environment variables from .env file
load_dotenv()

# Set up enhanced logger
logger = setup_logger(level=logging.INFO)

# Check for optional dependencies
try:
    import chat_exporter
    CHAT_EXPORTER_AVAILABLE = True
except ImportError:
    CHAT_EXPORTER_AVAILABLE = False

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def _validate_token_format(token: str) -> bool:
    """
    Validates that the token matches the expected Discord token format.
    
    Expected format: three base64-like segments separated by dots.
    Segments should be alphanumeric with - or _.
    """
    if not token or not isinstance(token, str):
        return False
        
    parts = token.split('.')
    if len(parts) != 3:
        return False
        
    # Check that each part matches base64-like pattern
    # We use a slightly lenient regex to allow for potential future format tweaks
    # but strictly enforce the 3-part structure and allowed characters.
    token_part_pattern = r'^[A-Za-z0-9_-]+$'
    
    if not all(re.match(token_part_pattern, part) for part in parts):
        return False
        
    # Reasonable length checks to filter out obviously bad inputs
    if len(parts[0]) < 10 or len(parts[1]) < 3 or len(parts[2]) < 10:
        return False
        
    return True


class ApexCoreBot(commands.Bot):
    """Extended Bot class with database and config management."""

    def __init__(self, *args, **kwargs):
        self.config = kwargs.pop("config")
        self.config_path = kwargs.pop("config_path", "config.json")
        self.db = Database()
        self.storage = TranscriptStorage()
        super().__init__(*args, **kwargs)
    
    async def reload_config(self) -> None:
        """Reload configuration from file."""
        try:
            from apex_core import load_config, load_payment_settings
            from dataclasses import replace
            
            new_config = load_config(self.config_path)
            
            # Preserve token if it was set from environment
            if hasattr(self.config, 'token') and self.config.token:
                new_config = replace(new_config, token=self.config.token)
            
            self.config = new_config
            
            # Reload payment settings
            try:
                payment_settings = load_payment_settings()
                self.config = replace(self.config, payment_settings=payment_settings)
            except FileNotFoundError:
                logger.warning("Payments config not found, skipping reload")
            
            logger.info("Bot configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
            raise

    async def setup_hook(self):
        await self.db.connect()
        logger.info("Database connected and schema initialized.")
        
        self.storage.initialize()
        logger.info("Transcript storage initialized.")
        
        # Set up Discord channel logging if channels are configured
        if hasattr(self.config, 'logging_channels') and self.config.logging_channels:
            from apex_core.logger import setup_logger
            setup_logger(
                level=logging.INFO,
                enable_discord=True,
                bot=self,
                audit_channel_id=getattr(self.config.logging_channels, 'audit', None),
                error_channel_id=getattr(self.config.logging_channels, 'errors', None)
            )
            logger.info("Discord channel logging enabled.")
        
        # Log optional dependency status
        if CHAT_EXPORTER_AVAILABLE:
            logger.info("✓ chat_exporter library available - enhanced transcript formatting enabled")
        else:
            logger.warning("⚠ chat_exporter library not found - basic transcript format will be used")
            logger.warning("  Install with: pip install -r requirements-optional.txt")
        
        if BOTO3_AVAILABLE:
            logger.info("✓ boto3 library available - S3 storage support enabled")
        else:
            logger.info("ℹ boto3 library not found - transcripts will be stored locally")
            logger.info("  Install with: pip install -r requirements-optional.txt (for S3 support)")

        await self._load_cogs()

        for guild_id in self.config.guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Command tree synced for guild {guild_id}")

    async def _load_cogs(self):
        cogs_dir = Path("cogs")
        if not cogs_dir.exists():
            logger.warning("No cogs directory found. Skipping cog loading.")
            return

        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.stem.startswith("_"):
                continue

            extension = f"cogs.{cog_file.stem}"
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Apex Core is ready!")

    async def close(self):
        # Cancel background tasks
        if cleanup_expired_sessions_task.is_running():
            cleanup_expired_sessions_task.cancel()
            logger.info("Background cleanup task cancelled.")
        
        if daily_backup_task.is_running():
            daily_backup_task.cancel()
            logger.info("Daily backup task cancelled.")

        await self.db.close()
        logger.info("Database connection closed.")
        await super().close()


# Background Tasks
@tasks.loop(hours=1.0)
async def cleanup_expired_sessions_task():
    """
    Cleanup expired setup wizard sessions every hour.

    Removes sessions older than their configured timeout to prevent database bloat.
    """
    try:
        # Get the bot instance from the task
        bot = cleanup_expired_sessions_task.bot
        count = await bot.db.cleanup_expired_sessions()
        if count > 0:
            logger.info(f"Cleaned up {count} expired setup wizard session(s)")
    except Exception as error:
        logger.error(f"Failed to cleanup expired sessions: {error}", exc_info=True)


@cleanup_expired_sessions_task.before_loop
async def before_cleanup_task():
    """Wait for bot to be ready before starting cleanup task."""
    bot = cleanup_expired_sessions_task.bot
    await bot.wait_until_ready()


@tasks.loop(hours=24.0)
async def daily_backup_task():
    """
    Create automatic daily database backup.
    
    Runs once per day at 3 AM UTC (or when bot starts if configured).
    """
    try:
        bot = daily_backup_task.bot
        from pathlib import Path
        import shutil
        from datetime import datetime, timedelta
        
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"apex_core_backup_{timestamp}.db"
        
        # Copy database file
        db_path = Path(bot.db.db_path)
        if db_path.exists():
            shutil.copy2(db_path, backup_file)
            
            # Clean old backups (keep last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            deleted_count = 0
            for old_backup in backup_dir.glob("apex_core_backup_*.db"):
                try:
                    date_str = old_backup.stem.split("_")[-2]
                    backup_date = datetime.strptime(date_str, "%Y%m%d")
                    if backup_date < cutoff_date:
                        old_backup.unlink()
                        deleted_count += 1
                except (ValueError, IndexError):
                    continue
            
            logger.info(f"Daily backup created: {backup_file} (deleted {deleted_count} old backups)")
        else:
            logger.warning("Database file not found for daily backup")
            
    except Exception as error:
        logger.error(f"Failed to create daily backup: {error}", exc_info=True)


@daily_backup_task.before_loop
async def before_daily_backup_task():
    """Wait for bot to be ready before starting daily backup task."""
    bot = daily_backup_task.bot
    await bot.wait_until_ready()


async def main():
    config_path = os.environ.get("CONFIG_PATH", "config.json")
    token = os.environ.get("DISCORD_TOKEN")
    
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if token:
        # Validate token format
        if not _validate_token_format(token):
            logger.error("Invalid DISCORD_TOKEN format in environment variables.")
            sys.exit(1)
            
        config = replace(config, token=token)
        logger.info("Using token from environment variable")
    
    # Validate payments configuration if it exists
    try:
        payment_settings = load_payment_settings()
        logger.info("Payments configuration loaded successfully")
        if not config.payment_settings:
            # This shouldn't happen if load_payment_settings succeeded
            logger.warning("Payments config loaded but not attached to main config")
    except FileNotFoundError:
        logger.info("Payments configuration file not found - using legacy inline payment methods")
    except Exception as e:
        logger.error("Payments configuration validation failed: %s", e)
        sys.exit(1)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = ApexCoreBot(
        command_prefix=config.bot_prefix,
        intents=intents,
        config=config,
        config_path=config_path,
    )

    # Start background tasks
    cleanup_expired_sessions_task.bot = bot
    cleanup_expired_sessions_task.start()
    logger.info("Started background cleanup tasks")
    
    daily_backup_task.bot = bot
    daily_backup_task.start()
    logger.info("Started daily backup task")

    async with bot:
        await bot.start(config.token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shut down by user.")
