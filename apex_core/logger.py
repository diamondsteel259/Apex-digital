"""
Enhanced logging module for Apex Core Discord bot.

Provides centralized logging with Discord channel integration,
structured logging, and enhanced features for production use.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import discord

# Global logger instance
logger: Optional[logging.Logger] = None


class DiscordHandler(logging.Handler):
    """Custom logging handler that sends messages to Discord channels."""
    
    def __init__(self, bot=None, channel_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Discord channel if available."""
        # Short-circuit when bot/channel is unavailable
        if not (self.bot and self.channel_id):
            return
        
        # Check if channel exists before formatting message
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        
        # Format the message once
        try:
            base_msg = f"**{record.levelname}**: {record.getMessage()}"
            if hasattr(record, 'exc_info') and record.exc_info:
                formatted_trace = self.format(record)
                # Truncate traceback if needed to fit in code block (roughly)
                if len(formatted_trace) > 1850:
                    formatted_trace = formatted_trace[:1850] + "... (truncated)"
                msg = f"{base_msg}\n```{formatted_trace}```"
            else:
                msg = base_msg
                
            if len(msg) > 2000:
                msg = msg[:1997] + "..."
        except Exception:
            # If formatting fails, use a basic message
            msg = f"**{record.levelname}**: {record.getMessage()}"
            if len(msg) > 2000:
                msg = msg[:1997] + "..."
        
        # Schedule delivery via dedicated helper
        self._schedule_send(channel, msg)
    
    def _schedule_send(self, channel, message: str) -> None:
        """Schedule message delivery to Discord channel safely."""
        try:
            # Try to get the current running loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, use bot's loop
                if self.bot and hasattr(self.bot, 'loop'):
                    loop = self.bot.loop
                else:
                    # No available loop, cannot send
                    return
            
            # Schedule the send operation
            if loop.is_running():
                # Use run_coroutine_threadsafe for thread safety
                asyncio.run_coroutine_threadsafe(self._send_to_discord(channel, message), loop)
            else:
                # If loop is not running, we can't send
                return
                
        except Exception as e:
            # Log to stderr to prevent recursive logging failures
            print(f"DiscordHandler: Failed to schedule message: {e}", file=sys.stderr)
    
    async def _send_to_discord(self, channel, message: str) -> None:
        """Send message to Discord channel asynchronously."""
        try:
            await channel.send(message)
        except Exception as e:
            # Log to stderr to prevent recursive logging failures
            print(f"DiscordHandler: Failed to send message: {e}", file=sys.stderr)


def setup_logger(
    level: int = logging.INFO,
    enable_discord: bool = False,
    bot=None,
    audit_channel_id: Optional[int] = None,
    error_channel_id: Optional[int] = None
) -> logging.Logger:
    """
    Set up the enhanced logger with console and optional Discord handlers.
    
    Args:
        level: Logging level (default: INFO)
        enable_discord: Whether to enable Discord channel logging
        bot: Discord bot instance for channel logging
        audit_channel_id: Channel ID for audit logs
        error_channel_id: Channel ID for error logs
    
    Returns:
        Configured logger instance
    """
    global logger
    
    # Create or get the logger
    logger = logging.getLogger("apex_core")
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with nice formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s:%(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Discord handlers (if enabled)
    if enable_discord and bot:
        if audit_channel_id:
            audit_handler = DiscordHandler(bot, audit_channel_id)
            audit_handler.setLevel(logging.INFO)
            # Only send audit logs, not debug/info
            audit_handler.addFilter(lambda record: record.levelno >= logging.INFO and 'audit' in record.name.lower())
            logger.addHandler(audit_handler)
        
        if error_channel_id:
            error_handler = DiscordHandler(bot, error_channel_id)
            error_handler.setLevel(logging.ERROR)
            logger.addHandler(error_handler)
    
    # Prevent propagation to root logger to avoid duplicates
    logger.propagate = False
    
    return logger


def get_logger() -> logging.Logger:
    """
    Get the global logger instance.
    
    Returns:
        Logger instance or creates a basic one if not initialized
    """
    global logger
    if logger is None:
        # Create a basic logger if setup_logger hasn't been called yet
        logger = logging.getLogger("apex_core")
        logger.setLevel(logging.INFO)
        
        # Only add console handler if none exist
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s:%(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
    
    return logger


# Initialize a basic logger for immediate use
logger = get_logger()


# For backward compatibility, provide module-level logger
module_logger = get_logger()