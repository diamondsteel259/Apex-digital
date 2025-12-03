"""User cache warming utilities for Apex Core."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cache_warmer import CacheWarmer
from .logger import get_logger

if TYPE_CHECKING:
    from .database import Database
    from .config import Config

logger = get_logger()


class UserCacheWarmer:
    """Handles warming up cache for individual users on-demand."""
    
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self._warmer = CacheWarmer(db, config)
        
    async def warm_user_on_interaction(self, user_id: int) -> None:
        """Warm up cache for a user when they interact with the bot.
        
        This should be called when a user executes a command or interacts
        with the bot to ensure their frequently accessed data is cached.
        """
        if not self.config.cache_settings or not self.config.cache_settings.enabled:
            return
        
        try:
            await self._warmer.warm_user_cache(user_id)
        except Exception as e:
            logger.debug(f"Failed to warm cache for user {user_id}: {e}")


# Global instance for easy access
_user_cache_warmer: UserCacheWarmer | None = None


def get_user_cache_warmer() -> UserCacheWarmer | None:
    """Get the global user cache warmer instance."""
    return _user_cache_warmer


def initialize_user_cache_warmer(db: Database, config: Config) -> None:
    """Initialize the global user cache warmer instance."""
    global _user_cache_warmer
    _user_cache_warmer = UserCacheWarmer(db, config)


async def warm_user_cache(user_id: int) -> None:
    """Convenience function to warm cache for a user."""
    warmer = get_user_cache_warmer()
    if warmer:
        await warmer.warm_user_on_interaction(user_id)