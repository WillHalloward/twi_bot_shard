"""
Performance benchmarks for critical operations.

This module contains performance tests to monitor and benchmark critical operations
including database queries, command processing, and external API calls.
"""

import asyncio
import os
import sys
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord.ext import commands

# Import cogs for benchmarking
from cogs.stats import StatsCogs
from cogs.twi import TwiCog

# Import test utilities
from tests.fixtures import DatabaseFixture, TestDataFixture
from tests.mock_factories import (
    MockUserFactory,
    MockMemberFactory,
    MockGuildFactory,
    MockChannelFactory,
    MockMessageFactory,
    MockInteractionFactory,
    MockContextFactory,
)
from tests.test_utils import TestSetup, TestTeardown, TestAssertions, TestHelpers


class PerformanceBenchmark:
    """Utility class for performance benchmarking."""

    @staticmethod
    async def time_async_function(func: Callable, *args, **kwargs) -> Tuple[Any, float]:
        """Time an async function and return result and execution time."""
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        return result, execution_time

    @staticmethod
    async def benchmark_async_function(
        func: Callable, iterations: int = 10, *args, **kwargs
    ) -> Dict[str, float]:
        """Benchmark an async function over multiple iterations."""
        times = []

        for _ in range(iterations):
            _, execution_time = await PerformanceBenchmark.time_async_function(
                func, *args, **kwargs
            )
            times.append(execution_time)

        return {
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
            "total": sum(times),
            "iterations": iterations,
        }

    @staticmethod
    def print_benchmark_results(operation_name: str, results: Dict[str, float]):
        """Print formatted benchmark results."""
        print(f"\n📊 {operation_name} Performance Benchmark:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Min time:   {results['min']:.4f}s")
        print(f"  Max time:   {results['max']:.4f}s")
        print(f"  Mean time:  {results['mean']:.4f}s")
        print(f"  Median:     {results['median']:.4f}s")
        print(f"  Std dev:    {results['stdev']:.4f}s")
        print(f"  Total time: {results['total']:.4f}s")


async def benchmark_database_operations():
    """Benchmark database operations."""
    print("\n🔍 Benchmarking database operations...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock database operations
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.executemany = AsyncMock()

    mock_pool = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock()

    db.pool = mock_pool

    # Benchmark single insert operation
    async def single_insert():
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "test_value"
            )

    results = await PerformanceBenchmark.benchmark_async_function(
        single_insert, iterations=100
    )
    PerformanceBenchmark.print_benchmark_results("Single Database Insert", results)

    # Benchmark bulk insert operation
    async def bulk_insert():
        data = [("user1", "email1"), ("user2", "email2"), ("user3", "email3")] * 10
        async with db.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO users (name, email) VALUES ($1, $2)", data
            )

    results = await PerformanceBenchmark.benchmark_async_function(
        bulk_insert, iterations=50
    )
    PerformanceBenchmark.print_benchmark_results(
        "Bulk Database Insert (30 records)", results
    )

    # Benchmark select operation
    async def select_operation():
        async with db.pool.acquire() as conn:
            await conn.fetch("SELECT * FROM test_table WHERE name = $1", "test_value")

    results = await PerformanceBenchmark.benchmark_async_function(
        select_operation, iterations=100
    )
    PerformanceBenchmark.print_benchmark_results("Database Select Operation", results)

    # Clean up
    await TestTeardown.teardown_database(db)

    print("✅ Database operations benchmarking completed")
    return True


async def benchmark_stats_cog_operations():
    """Benchmark StatsCogs operations."""
    print("\n🔍 Benchmarking StatsCogs operations...")

    # Create a test bot and cog
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Mock database operations
    bot.db.execute = AsyncMock()
    bot.db.fetch = AsyncMock(return_value=[])
    bot.db.fetchrow = AsyncMock(return_value={"total": 42})

    # Benchmark save_users operation
    async def save_users_operation():
        ctx = MockContextFactory.create()
        members = [MockMemberFactory.create() for _ in range(10)]
        mock_guild = MockGuildFactory.create()
        mock_guild.members = members
        bot.guilds = [mock_guild]
        await cog.save_users(ctx)

    results = await PerformanceBenchmark.benchmark_async_function(
        save_users_operation, iterations=20
    )
    PerformanceBenchmark.print_benchmark_results(
        "StatsCogs save_users (10 users)", results
    )

    # Benchmark save_servers operation
    async def save_servers_operation():
        ctx = MockContextFactory.create()
        mock_guilds = [MockGuildFactory.create() for _ in range(5)]
        bot.guilds = mock_guilds
        await cog.save_servers(ctx)

    results = await PerformanceBenchmark.benchmark_async_function(
        save_servers_operation, iterations=20
    )
    PerformanceBenchmark.print_benchmark_results(
        "StatsCogs save_servers (5 servers)", results
    )

    # Benchmark message_count command
    async def message_count_operation():
        interaction = MockInteractionFactory.create()
        channel = MockChannelFactory.create_text_channel()
        await cog.message_count.callback(cog, interaction, channel, 24)

    results = await PerformanceBenchmark.benchmark_async_function(
        message_count_operation, iterations=50
    )
    PerformanceBenchmark.print_benchmark_results(
        "StatsCogs message_count command", results
    )

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ StatsCogs operations benchmarking completed")
    return True


async def benchmark_twi_cog_operations():
    """Benchmark TwiCog operations."""
    print("\n🔍 Benchmarking TwiCog operations...")

    # Create a test bot and cog
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Benchmark Google search operation
    async def google_search_operation():
        interaction = MockInteractionFactory.create()
        with patch("cogs.twi.google_search") as mock_search:
            mock_search.return_value = {
                "items": [
                    {
                        "title": "Test Result",
                        "link": "https://example.com",
                        "snippet": "Test snippet",
                    }
                ]
            }
            await cog.wiki.callback(cog, interaction, "test query")

    results = await PerformanceBenchmark.benchmark_async_function(
        google_search_operation, iterations=30
    )
    PerformanceBenchmark.print_benchmark_results(
        "TwiCog wiki command (Google search)", results
    )

    # Benchmark password command
    async def password_operation():
        interaction = MockInteractionFactory.create()
        mock_data = {
            "passwords": {"test": {"password": "test", "link": "https://example.com"}}
        }
        with (
            patch("builtins.open"),
            patch("json.load", return_value=mock_data),
            patch("os.path.exists", return_value=True),
        ):
            await cog.password.callback(cog, interaction)

    results = await PerformanceBenchmark.benchmark_async_function(
        password_operation, iterations=50
    )
    PerformanceBenchmark.print_benchmark_results("TwiCog password command", results)

    # Benchmark invis_text command
    async def invis_text_operation():
        interaction = MockInteractionFactory.create()
        with (
            patch("builtins.open"),
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["test.txt"]),
        ):
            await cog.invis_text.callback(cog, interaction, "test")

    results = await PerformanceBenchmark.benchmark_async_function(
        invis_text_operation, iterations=30
    )
    PerformanceBenchmark.print_benchmark_results("TwiCog invis_text command", results)

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ TwiCog operations benchmarking completed")
    return True


async def benchmark_message_processing():
    """Benchmark message processing operations."""
    print("\n🔍 Benchmarking message processing...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Mock database operations
    bot.db.prepare_statement = AsyncMock()
    bot.db.transaction = AsyncMock()
    bot.db.execute_many = AsyncMock()

    mock_stmt = AsyncMock()
    mock_stmt.execute = AsyncMock()
    bot.db.prepare_statement.return_value = mock_stmt

    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    bot.db.transaction.return_value = mock_transaction

    # Benchmark single message processing
    async def process_single_message():
        message = MockMessageFactory.create()
        await cog.save_listener(message)

    results = await PerformanceBenchmark.benchmark_async_function(
        process_single_message, iterations=100
    )
    PerformanceBenchmark.print_benchmark_results("Single Message Processing", results)

    # Benchmark batch message processing
    async def process_batch_messages():
        messages = [MockMessageFactory.create() for _ in range(10)]
        for message in messages:
            await cog.save_listener(message)

    results = await PerformanceBenchmark.benchmark_async_function(
        process_batch_messages, iterations=20
    )
    PerformanceBenchmark.print_benchmark_results(
        "Batch Message Processing (10 messages)", results
    )

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ Message processing benchmarking completed")
    return True


async def benchmark_reaction_processing():
    """Benchmark reaction processing operations."""
    print("\n🔍 Benchmarking reaction processing...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Mock database operations
    bot.db.execute_many = AsyncMock()

    # Benchmark single reaction processing
    async def process_single_reaction():
        from tests.mock_factories import MockReactionFactory

        reaction = MockReactionFactory.create()
        await cog.reaction_add(reaction)

    results = await PerformanceBenchmark.benchmark_async_function(
        process_single_reaction, iterations=100
    )
    PerformanceBenchmark.print_benchmark_results("Single Reaction Processing", results)

    # Benchmark batch reaction processing
    async def process_batch_reactions():
        from tests.mock_factories import MockReactionFactory

        reactions = [MockReactionFactory.create() for _ in range(10)]
        for reaction in reactions:
            await cog.reaction_add(reaction)

    results = await PerformanceBenchmark.benchmark_async_function(
        process_batch_reactions, iterations=20
    )
    PerformanceBenchmark.print_benchmark_results(
        "Batch Reaction Processing (10 reactions)", results
    )

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ Reaction processing benchmarking completed")
    return True


async def benchmark_memory_usage():
    """Benchmark memory usage of critical operations."""
    print("\n🔍 Benchmarking memory usage...")

    import psutil
    import gc

    # Get initial memory usage
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Create test data
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Mock database operations
    bot.db.execute = AsyncMock()
    bot.db.fetch = AsyncMock(return_value=[])

    # Test memory usage with large data sets
    large_guild_count = 100
    large_member_count = 1000

    # Create large dataset
    mock_guilds = []
    for i in range(large_guild_count):
        guild = MockGuildFactory.create()
        guild.members = [
            MockMemberFactory.create() for _ in range(10)
        ]  # 10 members per guild
        mock_guilds.append(guild)

    bot.guilds = mock_guilds

    # Measure memory before operation
    gc.collect()
    memory_before = process.memory_info().rss / 1024 / 1024  # MB

    # Perform memory-intensive operation
    ctx = MockContextFactory.create()
    await cog.save_users(ctx)

    # Measure memory after operation
    gc.collect()
    memory_after = process.memory_info().rss / 1024 / 1024  # MB

    memory_used = memory_after - memory_before

    print(f"\n💾 Memory Usage Benchmark:")
    print(f"  Initial memory: {initial_memory:.2f} MB")
    print(f"  Before operation: {memory_before:.2f} MB")
    print(f"  After operation: {memory_after:.2f} MB")
    print(f"  Memory used by operation: {memory_used:.2f} MB")
    print(
        f"  Dataset size: {large_guild_count} guilds, {large_guild_count * 10} members"
    )

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ Memory usage benchmarking completed")
    return True


async def benchmark_concurrent_operations():
    """Benchmark concurrent operations performance."""
    print("\n🔍 Benchmarking concurrent operations...")

    # Create multiple test bots for concurrent testing
    bots = []
    cogs = []

    for i in range(5):
        bot = await TestSetup.create_test_bot()
        cog = await TestSetup.setup_cog(bot, StatsCogs)
        bot.db.execute = AsyncMock()
        bot.db.fetch = AsyncMock(return_value=[])
        bots.append(bot)
        cogs.append(cog)

    # Benchmark concurrent message processing
    async def concurrent_message_processing():
        tasks = []
        for i, cog in enumerate(cogs):
            message = MockMessageFactory.create()
            task = cog.save_listener(message)
            tasks.append(task)

        await asyncio.gather(*tasks)

    results = await PerformanceBenchmark.benchmark_async_function(
        concurrent_message_processing, iterations=20
    )
    PerformanceBenchmark.print_benchmark_results(
        "Concurrent Message Processing (5 concurrent)", results
    )

    # Benchmark concurrent database operations
    async def concurrent_database_operations():
        tasks = []
        for i, cog in enumerate(cogs):
            ctx = MockContextFactory.create()
            mock_guild = MockGuildFactory.create()
            mock_guild.members = [MockMemberFactory.create() for _ in range(5)]
            cog.bot.guilds = [mock_guild]
            task = cog.save_users(ctx)
            tasks.append(task)

        await asyncio.gather(*tasks)

    results = await PerformanceBenchmark.benchmark_async_function(
        concurrent_database_operations, iterations=10
    )
    PerformanceBenchmark.print_benchmark_results(
        "Concurrent Database Operations (5 concurrent)", results
    )

    # Clean up
    for i, bot in enumerate(bots):
        await TestTeardown.teardown_cog(bot, "stats")
        await TestTeardown.teardown_bot(bot)

    print("✅ Concurrent operations benchmarking completed")
    return True


async def benchmark_startup_performance():
    """Benchmark bot startup performance."""
    print("\n🔍 Benchmarking startup performance...")

    # Benchmark bot creation
    async def create_bot():
        return await TestSetup.create_test_bot()

    results = await PerformanceBenchmark.benchmark_async_function(
        create_bot, iterations=10
    )
    PerformanceBenchmark.print_benchmark_results("Bot Creation", results)

    # Benchmark cog loading
    async def load_cog():
        bot = await TestSetup.create_test_bot()
        cog = await TestSetup.setup_cog(bot, StatsCogs)
        await TestTeardown.teardown_cog(bot, "stats")
        await TestTeardown.teardown_bot(bot)

    results = await PerformanceBenchmark.benchmark_async_function(
        load_cog, iterations=10
    )
    PerformanceBenchmark.print_benchmark_results("Cog Loading (StatsCogs)", results)

    # Benchmark TwiCog loading
    async def load_twi_cog():
        bot = await TestSetup.create_test_bot()
        cog = await TestSetup.setup_cog(bot, TwiCog)
        await TestTeardown.teardown_cog(bot, "The Wandering Inn")
        await TestTeardown.teardown_bot(bot)

    results = await PerformanceBenchmark.benchmark_async_function(
        load_twi_cog, iterations=10
    )
    PerformanceBenchmark.print_benchmark_results("Cog Loading (TwiCog)", results)

    print("✅ Startup performance benchmarking completed")
    return True


# Main function to run all benchmarks
async def main():
    """Run all performance benchmarks."""
    print("🚀 Running comprehensive performance benchmarks...")
    print("=" * 60)

    # Run all benchmark suites
    await benchmark_database_operations()
    await benchmark_stats_cog_operations()
    await benchmark_twi_cog_operations()
    await benchmark_message_processing()
    await benchmark_reaction_processing()
    await benchmark_memory_usage()
    await benchmark_concurrent_operations()
    await benchmark_startup_performance()

    print("\n" + "=" * 60)
    print("🎯 All performance benchmarks completed!")
    print("✅ Performance benchmark test coverage implemented!")
    print("\n📈 Performance insights:")
    print("  - Monitor operations taking >100ms for optimization opportunities")
    print("  - Watch for memory usage spikes during bulk operations")
    print("  - Ensure concurrent operations scale linearly")
    print("  - Optimize startup time for better user experience")


if __name__ == "__main__":
    asyncio.run(main())
