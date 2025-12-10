"""Atomic configuration writer for safe config updates."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import load_config, Config

logger = logging.getLogger(__name__)


class ConfigWriter:
    """Handles safe, atomic writes to config.json with backup and reload."""

    def __init__(self, config_path: str | Path = "config.json"):
        """Initialize the config writer.
        
        Args:
            config_path: Path to the config.json file
        """
        self.config_path = Path(config_path)
        self.backups_dir = self.config_path.parent / "config_backups"

    async def _ensure_backups_dir(self) -> None:
        """Ensure the backups directory exists."""
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    async def _create_backup(self) -> Path:
        """Create a timestamped backup of the current config.
        
        Returns:
            Path to the backup file
        """
        await self._ensure_backups_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f"config_backup_{timestamp}.json"
        
        if self.config_path.exists():
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        return backup_path

    async def update_config_section(
        self,
        section: str,
        updates: dict[str, Any],
        bot: Optional[Any] = None,
        create_backup: bool = True,
    ) -> None:
        """Update a section of the config file atomically.
        
        Args:
            section: The config section to update (e.g., "role_ids", "channel_ids")
            updates: Dictionary of updates to apply to the section
            bot: Optional bot instance to reload config into
            create_backup: Whether to create a backup before updating
        """
        # Create backup
        if create_backup:
            await self._create_backup()

        # Load current config
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Update section
        if section not in data:
            data[section] = {}
        
        if not isinstance(data[section], dict):
            raise ValueError(f"Config section '{section}' is not a dictionary")

        data[section].update(updates)

        # Write to temp file first
        temp_path = self.config_path.with_suffix(".json.tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(self.config_path)
            logger.info(f"Updated config section: {section}")
            
            # Reload config in bot if provided
            if bot:
                await self._reload_bot_config(bot)
        
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Failed to update config: {e}")
            raise

    async def set_role_ids(
        self,
        role_id_updates: dict[str, int],
        bot: Optional[Any] = None,
    ) -> None:
        """Update role_ids section.
        
        Args:
            role_id_updates: Dict of role name to ID mappings
            bot: Optional bot instance to reload config into
        """
        await self.update_config_section("role_ids", role_id_updates, bot)

    async def set_ticket_categories(
        self,
        category_updates: dict[str, int],
        bot: Optional[Any] = None,
    ) -> None:
        """Update ticket_categories section.
        
        Args:
            category_updates: Dict of category name to ID mappings
            bot: Optional bot instance to reload config into
        """
        await self.update_config_section("ticket_categories", category_updates, bot)

    async def set_logging_channels(
        self,
        channel_updates: dict[str, int],
        bot: Optional[Any] = None,
    ) -> None:
        """Update logging_channels section.
        
        Args:
            channel_updates: Dict of channel name to ID mappings
            bot: Optional bot instance to reload config into
        """
        await self.update_config_section("logging_channels", channel_updates, bot)

    async def set_category_ids(
        self,
        category_updates: dict[str, int],
        bot: Optional[Any] = None,
    ) -> None:
        """Update category_ids section.
        
        Args:
            category_updates: Dict of category name to ID mappings
            bot: Optional bot instance to reload config into
        """
        await self.update_config_section("category_ids", category_updates, bot)

    async def set_channel_ids(
        self,
        channel_updates: dict[str, int],
        bot: Optional[Any] = None,
    ) -> None:
        """Update channel_ids section.
        
        Args:
            channel_updates: Dict of channel name to ID mappings
            bot: Optional bot instance to reload config into
        """
        await self.update_config_section("channel_ids", channel_updates, bot)

    async def _reload_bot_config(self, bot: Any) -> None:
        """Reload the config in the bot instance.
        
        Args:
            bot: The bot instance to reload config into
        """
        try:
            new_config = load_config(self.config_path)
            bot.config = new_config
            logger.info("Reloaded bot config from file")
        except Exception as e:
            logger.error(f"Failed to reload bot config: {e}")
            raise


async def update_config_atomically(
    section: str,
    updates: dict[str, Any],
    config_path: str | Path = "config.json",
    bot: Optional[Any] = None,
) -> None:
    """Convenience function to update config atomically.
    
    Args:
        section: The config section to update
        updates: Dictionary of updates to apply
        config_path: Path to config.json
        bot: Optional bot instance to reload
    """
    writer = ConfigWriter(config_path)
    await writer.update_config_section(section, updates, bot)
