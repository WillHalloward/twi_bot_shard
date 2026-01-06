# Caching Strategy for Twi Bot Shard

This document outlines the caching strategy implemented in the Twi Bot Shard project to improve performance and reduce database load.

## Overview

The caching system is designed to store frequently accessed database query results in memory, reducing the need to repeatedly query the database for the same information. This improves response times and reduces database load.

## Implementation

The caching system is implemented in `utils/query_cache.py` and integrated with the database service in `utils/db.py`. It provides:

1. **In-memory cache**: An LRU (Least Recently Used) cache for database query results with configurable size limits.
2. **Cache invalidation**: Both time-based expiration (TTL) and table-based invalidation when data is modified.
3. **Performance monitoring**: Tracking of cache hits, misses, and other metrics.

### Key Components

#### QueryCache Class

The `QueryCache` class in `utils/query_cache.py` provides the core caching functionality:

```python
class QueryCache:
    def __init__(self, max_size=1000, default_ttl=60, logger=None):
        # Initialize cache with max size and default TTL
        
    def get(self, query, args):
        # Get a value from the cache
        
    def set(self, query, args, value, ttl=None):
        # Store a value in the cache
        
    def invalidate(self, query, args):
        # Invalidate a specific cached query
        
    def invalidate_by_table(self, table_name):
        # Invalidate all cached queries that depend on a specific table
        
    def invalidate_all(self):
        # Invalidate all cached queries
        
    def get_stats(self):
        # Get cache performance statistics
```

#### cached_query Decorator

The `cached_query` decorator makes it easy to apply caching to database query methods:

```python
@cached_query(ttl=300)  # Cache results for 5 minutes
async def fetch(self, query, *args, use_cache=True):
    # Execute query and return results
```

### Integration with Database Service

The caching system is integrated with the database service in `utils/db.py`:

```python
# Initialize query cache
self.cache = QueryCache(
    max_size=2000,  # Store up to 2000 query results
    default_ttl=300,  # Default TTL of 5 minutes
    logger=self.logger
)
```

The database methods `fetch`, `fetchrow`, and `fetchval` are decorated with `@cached_query` to enable caching of query results.

## Cache Invalidation

The caching system uses two approaches for cache invalidation:

1. **Time-based expiration**: Each cached item has a TTL (Time To Live) after which it expires.
2. **Table-based invalidation**: When a table is modified (via INSERT, UPDATE, DELETE), all cached queries that depend on that table are invalidated.

The `_invalidate_cache_for_query` method in `Database` class analyzes modification queries to determine which tables are affected and invalidates the corresponding cache entries.

## Monitoring

Cache performance can be monitored using the `get_cache_stats` method, which returns statistics such as:

- Number of cache hits
- Number of cache misses
- Cache hit rate
- Number of cache evictions
- Number of cache invalidations

Example:

```python
cache_stats = await bot.db.get_cache_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']:.2f}%")
```

## Best Practices

1. **Use the built-in database methods**: The methods `fetch`, `fetchrow`, and `fetchval` in the `Database` class are already configured to use caching.

2. **Control caching behavior**: You can control whether a query uses the cache with the `use_cache` parameter:

   ```python
   # Use cache (default)
   results = await self.bot.db.fetch("SELECT * FROM example")
   
   # Skip cache for this query
   results = await self.bot.db.fetch("SELECT * FROM example", use_cache=False)
   ```

3. **Custom TTL**: You can specify a custom TTL for specific queries by modifying the `@cached_query` decorator:

   ```python
   @cached_query(ttl=60)  # Cache for 1 minute
   async def fetch_short_lived_data(self, query, *args):
       # ...
   ```

4. **Avoid caching large result sets**: The cache is most effective for small to medium-sized result sets that are frequently accessed.

5. **Monitor cache performance**: Regularly check cache statistics to ensure the cache is providing benefits and adjust settings if needed.

## Conclusion

The caching strategy implemented in Twi Bot Shard provides an effective way to improve performance for frequently accessed data. By reducing database queries, it helps the bot respond more quickly and reduces load on the database server.