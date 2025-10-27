"""
Property-based tests for query cache utilities in Twi Bot Shard.

This module contains property-based tests using the Hypothesis library
to verify that query cache functions in utils/query_cache.py maintain
certain properties for a wide range of inputs.
"""

import asyncio
import logging
import os
import sys
from collections import OrderedDict
from typing import Any

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Hypothesis for property-based testing
try:
    from hypothesis import HealthCheck, assume, given, settings
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy
except ImportError:
    print("Hypothesis is not installed. Please install it with:")
    print("uv pip install hypothesis")
    sys.exit(1)

# Import query cache components
from utils.query_cache import CacheKey, CacheStats, CacheValue, QueryCache


# Create a subclass of QueryCache that doesn't start the background task
class TestQueryCache(QueryCache):
    """QueryCache subclass for testing that doesn't start the background task."""

    __test__ = False  # Tell pytest this is not a test class

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the query cache without starting the background task."""
        self._cache: OrderedDict[CacheKey, CacheValue] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._logger = logger or logging.getLogger("query_cache")
        self._invalidation_patterns: dict[str, list[str]] = {}


# Define strategies for generating test data

# Strategy for generating SQL queries
sql_query_strategy = st.one_of(
    # SELECT queries
    st.builds(
        lambda table, columns, condition: f"SELECT {columns} FROM {table} WHERE {condition}",
        table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
        columns=st.sampled_from(["*", "id, name", "count(*)", "user_id, message_id"]),
        condition=st.sampled_from(
            [
                "id = $1",
                "user_id = $1",
                "guild_id = $1",
                "channel_id = $1",
                "created_at > $1",
            ]
        ),
    ),
    # INSERT queries
    st.builds(
        lambda table, columns, values: f"INSERT INTO {table} ({columns}) VALUES ({values})",
        table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
        columns=st.sampled_from(
            ["id, name", "user_id, message_id", "guild_id, channel_id"]
        ),
        values=st.sampled_from(["$1, $2", "$1, $2, $3", "$1, $2, $3, $4"]),
    ),
    # UPDATE queries
    st.builds(
        lambda table, set_clause, condition: f"UPDATE {table} SET {set_clause} WHERE {condition}",
        table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
        set_clause=st.sampled_from(
            ["name = $1", "count = count + 1", "updated_at = $1"]
        ),
        condition=st.sampled_from(
            ["id = $2", "user_id = $2", "guild_id = $2", "channel_id = $2"]
        ),
    ),
    # DELETE queries
    st.builds(
        lambda table, condition: f"DELETE FROM {table} WHERE {condition}",
        table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
        condition=st.sampled_from(
            ["id = $1", "user_id = $1", "guild_id = $1", "channel_id = $1"]
        ),
    ),
)

# Strategy for generating query arguments
query_args_strategy = st.lists(
    st.one_of(
        st.integers(),
        st.text(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    min_size=0,
    max_size=5,
)

# Strategy for generating cache values
cache_value_strategy = st.one_of(
    st.integers(),
    st.text(),
    st.lists(st.integers(), max_size=10),
    st.dictionaries(keys=st.text(), values=st.integers(), max_size=10),
)

# Strategy for generating TTL values
ttl_strategy = st.one_of(
    st.none(),
    st.integers(min_value=1, max_value=3600),
)

# Tests for _make_key


@given(
    query=sql_query_strategy,
    args=query_args_strategy,
)
def test_make_key_properties(query: str, args: list[Any]) -> None:
    """Test properties of _make_key function."""
    # Create a TestQueryCache instance
    cache = TestQueryCache()

    # Convert args list to tuple for the function
    args_tuple = tuple(args)

    # Call the function
    key = cache._make_key(query, args_tuple)

    # Property 1: Result should be a tuple
    assert isinstance(key, tuple)

    # Property 2: Result should have 2 elements
    assert len(key) == 2

    # Property 3: First element should be the query
    assert key[0] == query

    # Property 4: Second element should be the args tuple
    assert key[1] == args_tuple

    # Property 5: Keys should be deterministic (same inputs produce same key)
    key2 = cache._make_key(query, args_tuple)
    assert key == key2

    # Property 6: Different queries should produce different keys
    if query:
        modified_query = query + " LIMIT 10"
        different_key = cache._make_key(modified_query, args_tuple)
        assert key != different_key

    # Property 7: Different args should produce different keys
    if args:
        modified_args = args_tuple + (999,)
        different_key = cache._make_key(query, modified_args)
        assert key != different_key


# Tests for _register_invalidation_patterns


@pytest.mark.skip(reason="Async event loop issues need to be resolved")
@given(
    query=st.builds(
        lambda table, columns, condition: f"SELECT {columns} FROM {table} WHERE {condition}",
        table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
        columns=st.sampled_from(["*", "id, name", "count(*)", "user_id, message_id"]),
        condition=st.sampled_from(
            [
                "id = $1",
                "user_id = $1",
                "guild_id = $1",
                "channel_id = $1",
                "created_at > $1",
            ]
        ),
    ),
)
def test_register_invalidation_patterns_properties(query: str) -> None:
    """Test properties of _register_invalidation_patterns function."""
    # Create a QueryCache instance
    cache = QueryCache()

    # Call the function
    cache._register_invalidation_patterns(query)

    # Extract the table name from the query
    # This is a simplified approach and might not work for all queries
    from_parts = query.lower().split(" from ")
    if len(from_parts) >= 2:
        table_part = from_parts[1].split(" where ")[0].strip()
        table = table_part.split(",")[0].strip()

        # Property 1: Table should be in invalidation_patterns
        assert table in cache._invalidation_patterns

        # Property 2: Query should be in the list for this table
        assert query in cache._invalidation_patterns[table]

        # Property 3: Calling again should not duplicate the query
        cache._register_invalidation_patterns(query)
        assert cache._invalidation_patterns[table].count(query) == 1


# Tests for get and set


@pytest.mark.skip(reason="Async event loop issues need to be resolved")
@given(
    query=sql_query_strategy,
    args=query_args_strategy,
    value=cache_value_strategy,
    ttl=ttl_strategy,
)
def test_get_set_properties(
    query: str, args: list[Any], value: Any, ttl: int | None
) -> None:
    """Test properties of get and set functions."""

    # Create a synchronous version of QueryCache for testing
    class SyncQueryCache(QueryCache):
        def get(self, query, args):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().get(query, args))
            finally:
                loop.close()

        def set(self, query, args, value, ttl=None):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().set(query, args, value, ttl))
            finally:
                loop.close()

    # Create a QueryCache instance
    cache = SyncQueryCache()

    # Convert args list to tuple for the function
    args_tuple = tuple(args)

    # Initially, the value should not be in the cache
    initial_result = cache.get(query, args_tuple)
    assert initial_result is None

    # Set the value in the cache
    cache.set(query, args_tuple, value, ttl)

    # Get the value from the cache
    result = cache.get(query, args_tuple)

    # Property 1: After setting, get should return the value
    assert result == value

    # Property 2: Cache stats should be updated
    assert cache._stats.hits == 1
    assert cache._stats.misses == 1

    # Property 3: Different query or args should not return the value
    if query:
        modified_query = query + " LIMIT 10"
        assert cache.get(modified_query, args_tuple) is None

    if args:
        modified_args = args_tuple + (999,)
        assert cache.get(query, modified_args) is None


# Tests for invalidate


@pytest.mark.skip(reason="Async event loop issues need to be resolved")
@given(
    query=sql_query_strategy,
    args=query_args_strategy,
    value=cache_value_strategy,
)
def test_invalidate_properties(query: str, args: list[Any], value: Any) -> None:
    """Test properties of invalidate function."""

    # Create a synchronous version of QueryCache for testing
    class SyncQueryCache(QueryCache):
        def get(self, query, args):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().get(query, args))
            finally:
                loop.close()

        def set(self, query, args, value, ttl=None):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().set(query, args, value, ttl))
            finally:
                loop.close()

        def invalidate(self, query, args):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().invalidate(query, args))
            finally:
                loop.close()

    # Create a QueryCache instance
    cache = SyncQueryCache()

    # Convert args list to tuple for the function
    args_tuple = tuple(args)

    # Set the value in the cache
    cache.set(query, args_tuple, value)

    # Verify it's in the cache
    assert cache.get(query, args_tuple) == value

    # Invalidate the cache entry
    cache.invalidate(query, args_tuple)

    # Property 1: After invalidation, get should return None
    assert cache.get(query, args_tuple) is None

    # Property 2: Cache stats should be updated
    assert cache._stats.invalidations == 1


# Tests for invalidate_by_table


@pytest.mark.skip(reason="Async event loop issues need to be resolved")
@given(
    table=st.sampled_from(["users", "messages", "guilds", "channels", "reactions"]),
    query=st.builds(
        lambda columns, condition: f"SELECT {columns} FROM users WHERE {condition}",
        columns=st.sampled_from(["*", "id, name", "count(*)", "user_id, message_id"]),
        condition=st.sampled_from(
            [
                "id = $1",
                "user_id = $1",
                "guild_id = $1",
                "channel_id = $1",
                "created_at > $1",
            ]
        ),
    ),
    args=query_args_strategy,
    value=cache_value_strategy,
)
def test_invalidate_by_table_properties(
    table: str, query: str, args: list[Any], value: Any
) -> None:
    """Test properties of invalidate_by_table function."""

    # Create a synchronous version of QueryCache for testing
    class SyncQueryCache(QueryCache):
        def get(self, query, args):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().get(query, args))
            finally:
                loop.close()

        def set(self, query, args, value, ttl=None):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().set(query, args, value, ttl))
            finally:
                loop.close()

        def invalidate_by_table(self, table):
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(super().invalidate_by_table(table))
            finally:
                loop.close()

    # Create a QueryCache instance
    cache = SyncQueryCache()

    # Convert args list to tuple for the function
    args_tuple = tuple(args)

    # Create a query that uses the specified table
    table_query = query.replace("users", table)

    # Set the value in the cache
    cache.set(table_query, args_tuple, value)

    # Verify it's in the cache
    assert cache.get(table_query, args_tuple) == value

    # Invalidate by table
    cache.invalidate_by_table(table)

    # Property 1: After invalidation by table, get should return None
    assert cache.get(table_query, args_tuple) is None


# Main function to run the tests
def main() -> None:
    """Run all property-based tests for query cache functions."""
    print("Running property-based tests for query cache functions...")

    # Run tests
    test_make_key_properties()
    test_register_invalidation_patterns_properties()
    test_get_set_properties()
    test_invalidate_properties()
    test_invalidate_by_table_properties()

    print("All property-based tests for query cache functions passed!")


if __name__ == "__main__":
    main()
