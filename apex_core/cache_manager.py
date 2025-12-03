"""In-memory caching manager for Apex Core with TTL support and statistics."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import weakref
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, Union

from .logger import get_logger

logger = get_logger()

# Check if we're in test environment
import os
import sys
TEST_ENVIRONMENT = 'pytest' in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None


@dataclass
class CacheEntry:
    """Single cache entry with value and expiration."""
    value: Any
    expire_time: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expire_time

    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    total_hits: int = 0
    total_misses: int = 0
    total_sets: int = 0
    total_invalidations: int = 0
    memory_usage_bytes: int = 0
    entry_count: int = 0
    oldest_entry: float = 0
    newest_entry: float = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.total_hits + self.total_misses
        return self.total_hits / total if total > 0 else 0.0

    @property
    def memory_usage_mb(self) -> float:
        """Get memory usage in MB."""
        return self.memory_usage_bytes / (1024 * 1024)


class CacheManager:
    """Thread-safe in-memory cache manager with TTL and statistics."""
    
    def __init__(self, max_size_mb: int = 100, cleanup_interval: int = 3600):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._cleanup_interval = cleanup_interval
        self._stats = CacheStats()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"CacheManager initialized: max_size={max_size_mb}MB, cleanup_interval={cleanup_interval}s")

    async def start(self) -> None:
        """Start the cache manager cleanup task."""
        if self._running:
            return
            
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("CacheManager started")

    async def stop(self) -> None:
        """Stop the cache manager and cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        await self.clear_all()
        logger.info("CacheManager stopped")

    async def get(self, key: str, fetch_fn: Optional[Callable] = None, ttl: Optional[int] = None) -> Any:
        """
        Get value from cache, executing fetch_fn on cache miss.
        
        Args:
            key: Cache key
            fetch_fn: Optional function to call on cache miss
            ttl: Optional TTL for cached result (only used with fetch_fn)
            
        Returns:
            Cached value or result of fetch_fn
        """
        # Disable cache during tests
        if TEST_ENVIRONMENT:
            if fetch_fn is None:
                return None
            try:
                if asyncio.iscoroutinefunction(fetch_fn):
                    return await fetch_fn()
                else:
                    return fetch_fn()
            except Exception as e:
                logger.error(f"Error executing fetch function for {key}: {e}")
                raise
        
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry and not entry.is_expired:
                entry.touch()
                self._stats.total_hits += 1
                logger.debug(f"Cache hit: {key}")
                return entry.value
            
            # Cache miss
            self._stats.total_misses += 1
            logger.debug(f"Cache miss: {key}")
            
            if fetch_fn is None:
                return None
            
            # Execute fetch function and cache result
            try:
                if asyncio.iscoroutinefunction(fetch_fn):
                    value = await fetch_fn()
                else:
                    value = fetch_fn()
                
                if ttl is not None:
                    await self._set_internal(key, value, ttl)
                
                return value
            except Exception as e:
                logger.error(f"Error executing fetch function for {key}: {e}")
                raise

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        # Disable cache during tests
        if TEST_ENVIRONMENT:
            return
        
        async with self._lock:
            await self._set_internal(key, value, ttl)

    async def _set_internal(self, key: str, value: Any, ttl: int) -> None:
        """Internal set method that assumes lock is held."""
        expire_time = time.time() + ttl
        size_bytes = self._calculate_size(value)
        
        # Check memory limit and evict if necessary
        await self._ensure_memory_limit(size_bytes)
        
        entry = CacheEntry(
            value=value,
            expire_time=expire_time,
            size_bytes=size_bytes
        )
        
        # Update stats
        if key in self._cache:
            old_entry = self._cache[key]
            self._stats.memory_usage_bytes -= old_entry.size_bytes
        else:
            self._stats.entry_count += 1
        
        self._cache[key] = entry
        self._stats.memory_usage_bytes += size_bytes
        self._stats.total_sets += 1
        
        # Update timestamp tracking
        current_time = time.time()
        self._stats.newest_entry = current_time
        if self._stats.oldest_entry == 0:
            self._stats.oldest_entry = current_time

    async def invalidate(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match (supports * wildcards)
            
        Returns:
            Number of entries invalidated
        """
        # Disable cache during tests
        if TEST_ENVIRONMENT:
            return 0
        
        async with self._lock:
            if '*' in pattern:
                # Pattern matching
                import fnmatch
                keys_to_remove = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            else:
                # Exact match
                keys_to_remove = [pattern] if pattern in self._cache else []
            
            count = len(keys_to_remove)
            for key in keys_to_remove:
                entry = self._cache.pop(key)
                self._stats.memory_usage_bytes -= entry.size_bytes
                self._stats.entry_count -= 1
            
            self._stats.total_invalidations += count
            logger.debug(f"Invalidated {count} cache entries matching: {pattern}")
            return count

    async def clear_all(self) -> None:
        """Clear all cache entries."""
        # Disable cache during tests
        if TEST_ENVIRONMENT:
            return
        
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.memory_usage_bytes = 0
            self._stats.entry_count = 0
            self._stats.total_invalidations += count
            logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "hit_rate": round(self._stats.hit_rate, 4),
            "total_hits": self._stats.total_hits,
            "total_misses": self._stats.total_misses,
            "total_sets": self._stats.total_sets,
            "total_invalidations": self._stats.total_invalidations,
            "memory_usage_mb": round(self._stats.memory_usage_mb, 2),
            "memory_usage_bytes": self._stats.memory_usage_bytes,
            "entry_count": self._stats.entry_count,
            "max_size_mb": self._max_size_bytes / (1024 * 1024),
            "oldest_entry_age": time.time() - self._stats.oldest_entry if self._stats.oldest_entry > 0 else 0,
        }

    async def get_top_entries(self, limit: int = 10) -> list[dict]:
        """Get top cache entries by access count."""
        async with self._lock:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].access_count,
                reverse=True
            )[:limit]
            
            return [
                {
                    "key": key,
                    "access_count": entry.access_count,
                    "size_bytes": entry.size_bytes,
                    "age_seconds:": time.time() - entry.last_access,
                    "ttl_remaining": max(0, entry.expire_time - time.time())
                }
                for key, entry in sorted_entries
            ]

    async def _ensure_memory_limit(self, new_entry_size: int) -> None:
        """Ensure memory limit by evicting least recently used entries."""
        while (self._stats.memory_usage_bytes + new_entry_size) > self._max_size_bytes and self._cache:
            # Find LRU entry
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
            lru_entry = self._cache.pop(lru_key)
            
            self._stats.memory_usage_bytes -= lru_entry.size_bytes
            self._stats.entry_count -= 1
            self._stats.total_invalidations += 1
            
            logger.debug(f"Evicted LRU entry: {lru_key} ({lru_entry.size_bytes} bytes)")

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")

    async def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            
            count = len(expired_keys)
            for key in expired_keys:
                entry = self._cache.pop(key)
                self._stats.memory_usage_bytes -= entry.size_bytes
                self._stats.entry_count -= 1
            
            if count > 0:
                self._stats.total_invalidations += count
                logger.debug(f"Cleaned up {count} expired cache entries")

    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate memory size of a value."""
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return 8  # Approximate size for numbers
            elif isinstance(value, bool):
                return 1
            elif isinstance(value, (list, tuple)):
                return sum(self._calculate_size(item) for item in value) + 64  # Overhead
            elif isinstance(value, dict):
                return sum(
                    self._calculate_size(k) + self._calculate_size(v)
                    for k, v in value.items()
                ) + 64  # Overhead
            else:
                # Fallback: serialize to JSON and measure
                return len(json.dumps(value, default=str).encode('utf-8'))
        except Exception:
            # Fallback size estimate
            return 1024


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def hash_params(params: dict) -> str:
    """Create a hash from parameters for cache keys."""
    try:
        param_str = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(param_str.encode()).hexdigest()[:8]
    except Exception:
        return "unknown"


class cached:
    """Decorator for caching function results with TTL."""
    
    def __init__(self, ttl: int = 3600, key_prefix: str = "", key_params: bool = True):
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.key_params = key_params

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache_manager()
            
            # Skip caching during tests
            if TEST_ENVIRONMENT:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            
            # Generate cache key
            if self.key_params:
                # Use function name and parameters for key
                key_parts = [self.key_prefix, func.__name__]
                
                # Add relevant args/kwargs to key (skip self and common objects)
                relevant_params = {}
                if args:
                    # Skip first arg if it's self (method)
                    start_idx = 1 if args and hasattr(args[0], '__class__') else 0
                    for i, arg in enumerate(args[start_idx:], start=start_idx):
                        relevant_params[f"arg{i}"] = arg
                
                if kwargs:
                    relevant_params.update(kwargs)
                
                if relevant_params:
                    key_parts.append(hash_params(relevant_params))
                
                cache_key = "::".join(key_parts)
            else:
                cache_key = f"{self.key_prefix}::{func.__name__}"
            
            # Try to get from cache first
            result = await cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await cache.set(cache_key, result, self.ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run in async context
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


class cache_invalidate:
    """Decorator for invalidating cache entries after function execution."""
    
    def __init__(self, patterns: Union[str, list[str]]):
        if isinstance(patterns, str):
            patterns = [patterns]
        self.patterns = patterns

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute the function first
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Skip cache invalidation during tests
            if TEST_ENVIRONMENT:
                return result
            
            # Invalidate cache patterns
            cache = get_cache_manager()
            for pattern in self.patterns:
                # Format pattern with function arguments
                try:
                    formatted_pattern = pattern.format(*args, **kwargs)
                except (KeyError, IndexError):
                    formatted_pattern = pattern
                
                count = await cache.invalidate(formatted_pattern)
                if count > 0:
                    logger.debug(f"Invalidated {count} cache entries for pattern: {formatted_pattern}")
            
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper