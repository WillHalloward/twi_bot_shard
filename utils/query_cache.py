"""Query caching module for database operations.

This module provides a caching mechanism for database queries to improve
performance for frequently accessed data.
"""

import asyncio
import functools
import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TypeVar

# Type variables for generic functions
T = TypeVar("T")
CacheKey = tuple[str, tuple[Any, ...]]  # (query, args)
CacheValue = tuple[Any, datetime]  # (result, expiry)


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100.0

    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.invalidations = 0


class QueryCache:
    """Cache for database query results.

    This class provides an LRU (Least Recently Used) cache for database query results
    with configurable TTL (Time To Live) and size limits.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the query cache.

        Args:
            max_size: Maximum number of items to store in the cache.
            default_ttl: Default time-to-live in seconds for cached items.
            logger: Logger instance to use for logging.
        """
        self._cache: OrderedDict[CacheKey, CacheValue] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._logger = logger or logging.getLogger("query_cache")
        self._invalidation_patterns: dict[str, list[str]] = {}
        self._cleanup_task: asyncio.Task | None = None

        # Start background task to clean expired entries (deferred until event loop is available)
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start the cleanup task if an event loop is available."""
        try:
            # Only create the task if there's a running event loop
            loop = asyncio.get_running_loop()
            if loop and not loop.is_closed():
                self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        except RuntimeError:
            # No event loop running, task will be created later when needed
            pass

    def _ensure_cleanup_task(self) -> None:
        """Ensure the cleanup task is running if an event loop is available."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._start_cleanup_task()

    async def _cleanup_expired(self) -> None:
        """Background task to periodically clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                self._remove_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cache cleanup: {e}")

    def _remove_expired(self) -> None:
        """Remove all expired entries from the cache."""
        now = datetime.now()
        expired_keys = [key for key, (_, expiry) in self._cache.items() if expiry < now]

        for key in expired_keys:
            del self._cache[key]
            self._stats.evictions += 1

    def _make_key(self, query: str, args: tuple[Any, ...]) -> CacheKey:
        """Create a cache key from a query and its arguments.

        Args:
            query: The SQL query string.
            args: The query arguments.

        Returns:
            A tuple that can be used as a cache key.
        """

        def make_hashable(obj):
            """Convert unhashable types to hashable equivalents."""
            if isinstance(obj, list):
                return tuple(make_hashable(item) for item in obj)
            elif isinstance(obj, dict):
                return tuple(sorted((k, make_hashable(v)) for k, v in obj.items()))
            elif isinstance(obj, set):
                return tuple(sorted(make_hashable(item) for item in obj))
            elif isinstance(obj, tuple):
                return tuple(make_hashable(item) for item in obj)
            else:
                return obj

        hashable_args = tuple(make_hashable(arg) for arg in args)
        return (query, hashable_args)

    def get(self, query: str, args: tuple[Any, ...]) -> Any | None:
        """Get a value from the cache.

        Args:
            query: The SQL query string.
            args: The query arguments.

        Returns:
            The cached result, or None if not found or expired.
        """
        self._ensure_cleanup_task()
        key = self._make_key(query, args)

        if key in self._cache:
            result, expiry = self._cache[key]

            # Check if expired
            if expiry < datetime.now():
                del self._cache[key]
                self._stats.evictions += 1
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats.hits += 1
            return result

        self._stats.misses += 1
        return None

    def set(
        self, query: str, args: tuple[Any, ...], value: Any, ttl: int | None = None
    ) -> None:
        """Store a value in the cache.

        Args:
            query: The SQL query string.
            args: The query arguments.
            value: The value to cache.
            ttl: Time-to-live in seconds, or None to use the default.
        """
        # Don't cache None results
        if value is None:
            return

        self._ensure_cleanup_task()

        key = self._make_key(query, args)
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expiry = datetime.now() + timedelta(seconds=ttl_seconds)

        # If cache is full, remove least recently used item
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)  # Remove first item (LRU)
            self._stats.evictions += 1

        self._cache[key] = (value, expiry)

        # Register this query for invalidation patterns
        self._register_invalidation_patterns(query)

    def _register_invalidation_patterns(self, query: str) -> None:
        """Register a query for invalidation patterns.

        This analyzes the query to determine which tables it depends on,
        so that when those tables are modified, this query can be invalidated.

        Args:
            query: The SQL query string.
        """
        # Simple parsing to extract table names from SELECT queries
        query_lower = query.lower()
        if not query_lower.startswith("select"):
            return

        # Extract table names using a simple heuristic
        # This is a simplified approach and might not work for all queries
        from_parts = query_lower.split(" from ")
        if len(from_parts) < 2:
            return

        table_part = from_parts[1].split(" where ")[0].split(" join ")[0].strip()
        tables = [t.strip() for t in table_part.split(",")]

        for table in tables:
            if table not in self._invalidation_patterns:
                self._invalidation_patterns[table] = []

            if query not in self._invalidation_patterns[table]:
                self._invalidation_patterns[table].append(query)

    def invalidate(self, query: str, args: tuple[Any, ...]) -> None:
        """Invalidate a specific cached query.

        Args:
            query: The SQL query string.
            args: The query arguments.
        """
        key = self._make_key(query, args)
        if key in self._cache:
            del self._cache[key]
            self._stats.invalidations += 1

    def invalidate_by_table(self, table_name: str) -> None:
        """Invalidate all cached queries that depend on a specific table.

        Args:
            table_name: The name of the table that was modified.
        """
        if table_name not in self._invalidation_patterns:
            return

        invalidated = 0
        for query in self._invalidation_patterns[table_name]:
            # Find all keys that match this query pattern
            keys_to_remove = [key for key in self._cache if key[0] == query]

            for key in keys_to_remove:
                del self._cache[key]
                invalidated += 1

        self._stats.invalidations += invalidated
        if invalidated > 0:
            self._logger.debug(
                f"Invalidated {invalidated} cache entries for table {table_name}"
            )

    def invalidate_all(self) -> None:
        """Invalidate all cached queries."""
        invalidated = len(self._cache)
        self._cache.clear()
        self._stats.invalidations += invalidated
        self._logger.debug(f"Invalidated all {invalidated} cache entries")

    def get_stats(self) -> CacheStats:
        """Get cache performance statistics.

        Returns:
            A CacheStats object with current statistics.
        """
        return self._stats

    def reset_stats(self) -> None:
        """Reset cache performance statistics."""
        self._stats.reset()

    def shutdown(self) -> None:
        """Shutdown the cache and cancel background tasks."""
        if (
            hasattr(self, "_cleanup_task")
            and self._cleanup_task
            and not self._cleanup_task.done()
        ):
            self._cleanup_task.cancel()


def cached_query(
    ttl: int | None = None, cache_instance: QueryCache | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for caching query results.

    Args:
        ttl: Time-to-live in seconds, or None to use the default.
        cache_instance: QueryCache instance to use, or None to use a global instance.

    Returns:
        A decorator function.
    """
    # Use a global cache instance if none provided
    if cache_instance is None:
        global _global_cache
        if "_global_cache" not in globals():
            _global_cache = QueryCache()
        cache_instance = _global_cache

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract query and query args from function arguments
            # This assumes the function signature matches Database methods
            if len(args) < 2:
                # Not enough arguments to determine query and args
                return await func(*args, **kwargs)

            query = args[1]  # Assuming first arg is self, second is query
            query_args = args[2:]  # Remaining positional args

            # Check if caching is disabled for this call
            if kwargs.get("use_cache", True) is False:
                if "use_cache" in kwargs:
                    del kwargs["use_cache"]
                return await func(*args, **kwargs)

            # Remove cache-specific kwargs
            if "use_cache" in kwargs:
                del kwargs["use_cache"]

            # Check cache
            cached_result = cache_instance.get(query, query_args)

            if cached_result is not None:
                return cached_result

            # Execute query
            result = await func(*args, **kwargs)

            # Cache result if it's cacheable
            if result is not None:
                cache_instance.set(query, query_args, result, ttl)

            return result

        return wrapper

    return decorator
