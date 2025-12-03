"""Cache warming utilities for Apex Core."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .cache_manager import get_cache_manager
from .logger import get_logger

if TYPE_CHECKING:
    from .database import Database
    from .config import Config

logger = get_logger()


class CacheWarmer:
    """Handles warming up the cache with frequently accessed data."""
    
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self.cache_manager = get_cache_manager()
        
    async def warm_all_caches(self) -> None:
        """Warm up all cache tiers with essential data."""
        if not self.config.cache_settings or not self.config.cache_settings.enabled:
            logger.info("Cache warming skipped - cache disabled")
            return
            
        logger.info("Starting cache warming...")
        
        try:
            await self._warm_config_cache()
            await self._warm_reference_cache()
            logger.info("Cache warming completed successfully")
        except Exception as e:
            logger.error(f"Error during cache warming: {e}")
    
    async def _warm_config_cache(self) -> None:
        """Warm up configuration cache (Tier 1 - longest TTL)."""
        logger.debug("Warming configuration cache...")
        
        # Cache VIP tiers and roles
        try:
            await self.cache_manager.get(
                "config::vip_tiers",
                lambda: self.config.roles,
                self.config.cache_settings.ttl_config
            )
        except Exception as e:
            logger.warning(f"Failed to warm VIP tiers cache: {e}")
        
        # Cache payment methods
        try:
            payment_methods = (
                self.config.payment_settings.payment_methods 
                if self.config.payment_settings 
                else self.config.payment_methods
            )
            await self.cache_manager.get(
                "config::payment_methods",
                lambda: payment_methods,
                self.config.cache_settings.ttl_config
            )
        except Exception as e:
            logger.warning(f"Failed to warm payment methods cache: {e}")
    
    async def _warm_reference_cache(self) -> None:
        """Warm up reference data cache (Tier 2 - medium TTL)."""
        logger.debug("Warming reference data cache...")
        
        # Cache product categories
        try:
            await self.db.get_distinct_main_categories()
        except Exception as e:
            logger.warning(f"Failed to warm main categories cache: {e}")
        
        # Cache all products
        try:
            await self.db.get_all_products(active_only=True)
        except Exception as e:
            logger.warning(f"Failed to warm products cache: {e}")
        
        # Cache discounts
        try:
            await self.db.get_applicable_discounts(
                user_id=None,
                product_id=None,
                vip_tier=None
            )
        except Exception as e:
            logger.warning(f"Failed to warm discounts cache: {e}")
    
    async def warm_user_cache(self, user_id: int) -> None:
        """Warm up cache for a specific user (Tier 3 - shorter TTL)."""
        if not self.config.cache_settings or not self.config.cache_settings.enabled:
            return
            
        logger.debug(f"Warming cache for user {user_id}...")
        
        try:
            # Cache user profile
            await self.db.get_user(user_id)
            
            # Cache user orders
            await self.db.get_orders_for_user(user_id, limit=5)
            
        except Exception as e:
            logger.warning(f"Failed to warm user cache for {user_id}: {e}")
    
    async def schedule_periodic_warming(self) -> None:
        """Schedule periodic cache warming in the background."""
        if not self.config.cache_settings or not self.config.cache_settings.enabled:
            return
        
        async def warming_loop():
            while True:
                try:
                    # Warm reference cache every 6 hours
                    await asyncio.sleep(6 * 3600)
                    await self._warm_reference_cache()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic cache warming: {e}")
        
        # Start background task
        asyncio.create_task(warming_loop())
        logger.info("Started periodic cache warming (every 6 hours)")


async def warm_cache_on_startup(db: Database, config: Config) -> None:
    """Convenience function to warm cache on bot startup."""
    warmer = CacheWarmer(db, config)
    await warmer.warm_all_caches()
    await warmer.schedule_periodic_warming()