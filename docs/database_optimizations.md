# Database Optimizations

This document describes the database optimizations implemented in the Twi Bot Shard project to improve query performance and reduce database load.

## Overview

The database optimizations consist of three main components:

1. **Additional Indexes**: New indexes for frequently queried tables to improve query performance.
2. **Materialized Views**: Pre-computed views for complex queries to reduce computation time.
3. **Query Caching**: In-memory caching of query results to reduce database load.

## Additional Indexes

The following additional indexes have been added to improve query performance:

### Message-related Indexes

- `idx_messages_created_at_range`: Index for message queries by date range, with a partial condition to only include recent messages.
- `idx_active_messages`: Partial index for non-deleted messages in active channels.

### Thread-related Indexes

- `idx_threads_parent_archived`: Index for thread queries by parent and archived status.
- `idx_active_threads`: Partial index for active threads (not archived and not deleted).

### Role-related Indexes

- `idx_role_membership_by_server`: Index for role membership queries by server.

### Reaction-related Indexes

- `idx_reactions_recent`: Partial index for recent reactions.

### Other Indexes

- `idx_updates_date`: Index for the updates table by date.
- `idx_updates_table_action`: Index for the updates table by table and action.
- `idx_join_leave_server_date`: Index for join_leave table by server and date.

## Materialized Views

The following materialized views have been added to pre-compute complex queries:

### User Activity Views

- `user_channel_activity`: User activity by channel for the last 30 days.
- `weekly_message_stats`: Weekly message statistics for the last 90 days.

### Existing Views (Updated)

The existing materialized views have been updated to include additional information:

- `daily_message_stats`: Daily message statistics.
- `daily_member_stats`: Daily member join/leave statistics.
- `user_activity_stats`: User activity statistics.
- `channel_hourly_stats`: Channel activity by hour.

## Query Caching

A query caching mechanism has been implemented to reduce database load for frequently accessed data. The caching system includes:

### Cache Configuration

- **Max Size**: 2000 query results
- **Default TTL**: 5 minutes (300 seconds)
- **Cache Invalidation**: Automatic invalidation when tables are modified

### Cached Methods

The following database methods now support caching:

- `fetch`: Execute a query and return all results.
- `fetchrow`: Execute a query and return the first row.
- `fetchval`: Execute a query and return a single value.

### Cache Control

You can control caching behavior with the following parameters:

- `use_cache`: Whether to use cache for a specific query (default: True).
- `invalidate_cache`: Whether to invalidate cache for affected tables when executing a modification query (default: True).

### Cache Statistics

You can get cache statistics using the `get_cache_stats` method, which returns:

- `hits`: Number of cache hits
- `misses`: Number of cache misses
- `hit_rate`: Cache hit rate as a percentage
- `evictions`: Number of cache entries evicted due to size limits or expiration
- `invalidations`: Number of cache entries invalidated due to table modifications
- `total_requests`: Total number of cache requests

## How to Apply Optimizations

The optimizations can be applied by running the `run_additional_optimizations.py` script:

```bash
python run_additional_optimizations.py
```

This script will:

1. Apply the additional indexes and materialized views defined in `database/additional_optimizations.sql`.
2. Refresh the materialized views to ensure they're populated.
3. Print the results of the optimization process.

## Usage Examples

### Using Cached Queries

```python
# Fetch data with caching (default)
results = await db.fetch("SELECT * FROM messages WHERE channel_id = $1", channel_id)

# Fetch data without caching
results = await db.fetch("SELECT * FROM messages WHERE channel_id = $1", channel_id, use_cache=False)

# Get cache statistics
stats = await db.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']}%")
```

### Using Materialized Views

```python
# Get user activity by channel
results = await db.fetch("SELECT * FROM user_channel_activity WHERE user_id = $1", user_id)

# Get weekly message statistics
results = await db.fetch("SELECT * FROM weekly_message_stats WHERE server_id = $1", server_id)

# Refresh materialized views
await db.refresh_materialized_views()
```

## Performance Impact

The implemented optimizations should significantly improve performance for:

- Queries that filter by date range
- Queries that join multiple tables
- Frequently repeated queries
- Complex statistical queries

Monitor the slow query logs to identify any remaining performance issues.