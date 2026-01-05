"""
Unit tests for query cache functionality.

Tests the basic operations of the QueryCache class including get, set,
invalidation, and cache statistics.
"""

import asyncio
import os
import sys

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from utils.query_cache import QueryCache


def test_query_cache_get_set():
    """Test basic get and set operations."""
    cache = QueryCache(max_size=10, default_ttl=60)

    query = "SELECT * FROM users WHERE id = $1"
    args = (123,)
    value = {"id": 123, "name": "Test User"}

    # Initially, cache should be empty
    result = cache.get(query, args)
    assert result is None

    # Set a value
    cache.set(query, args, value)

    # Get the value back
    result = cache.get(query, args)
    assert result == value

    # Check stats
    stats = cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1


@pytest.mark.asyncio
async def test_query_cache_expiry():
    """Test that cached items expire after TTL."""
    cache = QueryCache(max_size=10, default_ttl=1)  # 1 second TTL

    query = "SELECT * FROM users WHERE id = $1"
    args = (123,)
    value = {"id": 123, "name": "Test User"}

    # Set a value
    cache.set(query, args, value, ttl=1)

    # Should be available immediately
    result = cache.get(query, args)
    assert result == value

    # Wait for expiry
    await asyncio.sleep(1.1)

    # Should be expired now
    result = cache.get(query, args)
    assert result is None


def test_query_cache_max_size():
    """Test that cache respects max_size limit."""
    cache = QueryCache(max_size=3, default_ttl=60)

    # Add 4 items (exceeds max_size of 3)
    for i in range(4):
        query = f"SELECT * FROM users WHERE id = ${i}"
        args = (i,)
        value = {"id": i, "name": f"User {i}"}
        cache.set(query, args, value)

    # First item should have been evicted
    result = cache.get("SELECT * FROM users WHERE id = $0", (0,))
    assert result is None

    # Last 3 items should still be there
    for i in range(1, 4):
        query = f"SELECT * FROM users WHERE id = ${i}"
        args = (i,)
        result = cache.get(query, args)
        assert result is not None

    # Check eviction stat
    stats = cache.get_stats()
    assert stats.evictions == 1


def test_query_cache_invalidate():
    """Test cache invalidation."""
    cache = QueryCache(max_size=10, default_ttl=60)

    query = "SELECT * FROM users WHERE id = $1"
    args = (123,)
    value = {"id": 123, "name": "Test User"}

    # Set a value
    cache.set(query, args, value)

    # Verify it's there
    result = cache.get(query, args)
    assert result == value

    # Invalidate by table
    cache.invalidate_by_table("users")

    # Should be gone now
    result = cache.get(query, args)
    assert result is None

    # Check invalidation stat
    stats = cache.get_stats()
    assert stats.invalidations >= 1


def test_query_cache_clear():
    """Test clearing the entire cache."""
    cache = QueryCache(max_size=10, default_ttl=60)

    # Add multiple items
    for i in range(3):
        query = f"SELECT * FROM users WHERE id = ${i}"
        args = (i,)
        value = {"id": i, "name": f"User {i}"}
        cache.set(query, args, value)

    # Clear the cache (use invalidate_all)
    cache.invalidate_all()

    # All items should be gone
    for i in range(3):
        query = f"SELECT * FROM users WHERE id = ${i}"
        args = (i,)
        result = cache.get(query, args)
        assert result is None


def test_query_cache_stats():
    """Test cache statistics tracking."""
    cache = QueryCache(max_size=10, default_ttl=60)

    query = "SELECT * FROM users WHERE id = $1"
    args = (123,)
    value = {"id": 123, "name": "Test User"}

    # Initial stats
    stats = cache.get_stats()
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.total_requests == 0
    assert stats.hit_rate == 0.0

    # Miss
    cache.get(query, args)
    stats = cache.get_stats()
    assert stats.misses == 1
    assert stats.total_requests == 1

    # Set and hit
    cache.set(query, args, value)
    cache.get(query, args)
    stats = cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.total_requests == 2
    assert stats.hit_rate == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
