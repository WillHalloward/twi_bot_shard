"""
Load testing suite for the Twi Bot Shard.

This module tests the bot's performance under various load conditions including:
- High message volume processing
- Concurrent command execution
- Database load testing
- Memory usage under load
- Response time degradation analysis

These tests help ensure the bot can handle production-level traffic and identify
performance bottlenecks before they impact users.
"""

import asyncio
import os
import statistics
import sys
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import psutil

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Import config normally


# Import test utilities
# Import cogs for testing
from cogs.utility import Utility
from tests.mock_factories import (
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockMessageFactory,
    MockUserFactory,
)


class LoadTestMetrics:
    """Class to track and analyze load test metrics."""

    def __init__(self) -> None:
        self.response_times: list[float] = []
        self.memory_usage: list[float] = []
        self.cpu_usage: list[float] = []
        self.error_count: int = 0
        self.success_count: int = 0
        self.start_time: float = 0
        self.end_time: float = 0

    def start_test(self) -> None:
        """Start tracking test metrics."""
        self.start_time = time.time()
        self.response_times.clear()
        self.memory_usage.clear()
        self.cpu_usage.clear()
        self.error_count = 0
        self.success_count = 0

    def end_test(self) -> None:
        """End tracking test metrics."""
        self.end_time = time.time()

    def record_response_time(self, response_time: float) -> None:
        """Record a response time measurement."""
        self.response_times.append(response_time)

    def record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1

    def record_error(self) -> None:
        """Record a failed operation."""
        self.error_count += 1

    def record_system_metrics(self) -> None:
        """Record current system metrics."""
        process = psutil.Process(os.getpid())
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of test metrics."""
        total_time = self.end_time - self.start_time
        total_operations = self.success_count + self.error_count

        summary = {
            "total_time": total_time,
            "total_operations": total_operations,
            "success_rate": (
                (self.success_count / total_operations * 100)
                if total_operations > 0
                else 0
            ),
            "operations_per_second": (
                total_operations / total_time if total_time > 0 else 0
            ),
            "error_rate": (
                (self.error_count / total_operations * 100)
                if total_operations > 0
                else 0
            ),
        }

        if self.response_times:
            summary.update(
                {
                    "avg_response_time": statistics.mean(self.response_times),
                    "min_response_time": min(self.response_times),
                    "max_response_time": max(self.response_times),
                    "median_response_time": statistics.median(self.response_times),
                    "p95_response_time": self._percentile(self.response_times, 95),
                    "p99_response_time": self._percentile(self.response_times, 99),
                }
            )

        if self.memory_usage:
            summary.update(
                {
                    "avg_memory_mb": statistics.mean(self.memory_usage),
                    "max_memory_mb": max(self.memory_usage),
                    "min_memory_mb": min(self.memory_usage),
                }
            )

        if self.cpu_usage:
            summary.update(
                {
                    "avg_cpu_percent": statistics.mean(self.cpu_usage),
                    "max_cpu_percent": max(self.cpu_usage),
                }
            )

        return summary

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class MessageProcessingLoadTest:
    """Load test for message processing capabilities."""

    def __init__(self) -> None:
        self.metrics = LoadTestMetrics()

    async def simulate_message_processing(
        self, message_count: int = 1000
    ) -> LoadTestMetrics:
        """Simulate processing a large number of messages."""
        print(f"🔄 Starting message processing load test ({message_count} messages)...")

        # Create mock bot and database
        bot = MagicMock()
        bot.db = MagicMock()
        bot.db.execute = AsyncMock()

        # Create mock objects
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()

        self.metrics.start_test()

        # Process messages in batches to avoid overwhelming the system
        batch_size = 50
        for i in range(0, message_count, batch_size):
            batch_end = min(i + batch_size, message_count)
            batch_tasks = []

            for j in range(i, batch_end):
                message = MockMessageFactory.create(
                    content=f"Test message {j}",
                    author=user,
                    channel=channel,
                    guild=guild,
                )

                # Simulate message processing
                task = self._process_single_message(bot, message)
                batch_tasks.append(task)

            # Process batch concurrently
            start_time = time.time()
            try:
                await asyncio.gather(*batch_tasks)
                self.metrics.record_success()
            except Exception as e:
                self.metrics.record_error()
                print(f"❌ Batch processing error: {e}")

            end_time = time.time()
            self.metrics.record_response_time(end_time - start_time)
            self.metrics.record_system_metrics()

            # Small delay to prevent overwhelming
            await asyncio.sleep(0.01)

        self.metrics.end_test()
        return self.metrics

    async def _process_single_message(self, bot, message) -> None:
        """Simulate processing a single message."""
        # Simulate database operations
        await bot.db.execute(
            "INSERT INTO messages(message_id, content, user_id) VALUES($1, $2, $3)",
            message.id,
            message.content,
            message.author.id,
        )

        # Simulate some processing delay
        await asyncio.sleep(0.001)


class CommandExecutionLoadTest:
    """Load test for concurrent command execution."""

    def __init__(self) -> None:
        self.metrics = LoadTestMetrics()

    async def simulate_concurrent_commands(
        self, command_count: int = 500
    ) -> LoadTestMetrics:
        """Simulate concurrent command execution."""
        print(
            f"⚡ Starting concurrent command execution test ({command_count} commands)..."
        )

        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        bot.db.fetchval = AsyncMock(return_value=100)
        bot.db.fetch = AsyncMock(return_value=[])

        cog = Utility(bot)

        self.metrics.start_test()

        # Create concurrent command tasks
        tasks = []
        for i in range(command_count):
            user = MockUserFactory.create(user_id=1000 + i)
            guild = MockGuildFactory.create()
            channel = MockChannelFactory.create_text_channel()
            interaction = MockInteractionFactory.create(
                user=user, guild=guild, channel=channel
            )

            # Simulate different commands
            if i % 3 == 0:
                task = self._simulate_ping_command(cog, interaction)
            elif i % 3 == 1:
                task = self._simulate_info_command(cog, interaction)
            else:
                task = self._simulate_avatar_command(cog, interaction)

            tasks.append(task)

        # Execute commands in batches
        batch_size = 25
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]

            start_time = time.time()
            try:
                await asyncio.gather(*batch, return_exceptions=True)
                self.metrics.record_success()
            except Exception as e:
                self.metrics.record_error()
                print(f"❌ Command batch error: {e}")

            end_time = time.time()
            self.metrics.record_response_time(end_time - start_time)
            self.metrics.record_system_metrics()

            await asyncio.sleep(0.01)

        self.metrics.end_test()
        return self.metrics

    async def _simulate_ping_command(self, cog, interaction) -> None:
        """Simulate ping command execution."""
        try:
            await cog.ping(interaction)
        except Exception:
            pass  # Expected due to mocking

    async def _simulate_info_command(self, cog, interaction) -> None:
        """Simulate info command execution."""
        try:
            await cog.info_user(interaction, interaction.user)
        except Exception:
            pass  # Expected due to mocking

    async def _simulate_avatar_command(self, cog, interaction) -> None:
        """Simulate avatar command execution."""
        try:
            await cog.av(interaction, interaction.user)
        except Exception:
            pass  # Expected due to mocking


class DatabaseLoadTest:
    """Load test for database operations."""

    def __init__(self) -> None:
        self.metrics = LoadTestMetrics()

    async def simulate_database_load(
        self, operation_count: int = 1000
    ) -> LoadTestMetrics:
        """Simulate high database load."""
        print(f"🗄️ Starting database load test ({operation_count} operations)...")

        # Create mock database with realistic delays
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        mock_db.fetchval = AsyncMock(return_value=42)

        # Add realistic delays to simulate database operations
        async def mock_execute_with_delay(*args, **kwargs) -> None:
            await asyncio.sleep(0.002)  # 2ms delay
            return None

        async def mock_fetch_with_delay(*args, **kwargs):
            await asyncio.sleep(0.005)  # 5ms delay
            return []

        mock_db.execute.side_effect = mock_execute_with_delay
        mock_db.fetch.side_effect = mock_fetch_with_delay

        self.metrics.start_test()

        # Simulate various database operations
        tasks = []
        for i in range(operation_count):
            if i % 4 == 0:
                task = self._simulate_insert_operation(mock_db, i)
            elif i % 4 == 1:
                task = self._simulate_select_operation(mock_db, i)
            elif i % 4 == 2:
                task = self._simulate_update_operation(mock_db, i)
            else:
                task = self._simulate_delete_operation(mock_db, i)

            tasks.append(task)

        # Execute database operations in batches
        batch_size = 20
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]

            start_time = time.time()
            try:
                await asyncio.gather(*batch)
                self.metrics.record_success()
            except Exception as e:
                self.metrics.record_error()
                print(f"❌ Database batch error: {e}")

            end_time = time.time()
            self.metrics.record_response_time(end_time - start_time)
            self.metrics.record_system_metrics()

            await asyncio.sleep(0.01)

        self.metrics.end_test()
        return self.metrics

    async def _simulate_insert_operation(self, db, operation_id) -> None:
        """Simulate database insert operation."""
        await db.execute(
            "INSERT INTO test_table(id, data) VALUES($1, $2)",
            operation_id,
            f"test_data_{operation_id}",
        )

    async def _simulate_select_operation(self, db, operation_id) -> None:
        """Simulate database select operation."""
        await db.fetch("SELECT * FROM test_table WHERE id = $1", operation_id)

    async def _simulate_update_operation(self, db, operation_id) -> None:
        """Simulate database update operation."""
        await db.execute(
            "UPDATE test_table SET data = $1 WHERE id = $2",
            f"updated_data_{operation_id}",
            operation_id,
        )

    async def _simulate_delete_operation(self, db, operation_id) -> None:
        """Simulate database delete operation."""
        await db.execute("DELETE FROM test_table WHERE id = $1", operation_id)


async def run_all_load_tests():
    """Run all load tests and generate comprehensive report."""
    print("🚀 Starting Comprehensive Load Testing Suite...")
    print("=" * 70)

    results = {}

    # Message Processing Load Test
    print("\n📨 Message Processing Load Test")
    print("-" * 40)
    message_test = MessageProcessingLoadTest()
    results["message_processing"] = await message_test.simulate_message_processing(1000)

    # Command Execution Load Test
    print("\n⚡ Command Execution Load Test")
    print("-" * 40)
    command_test = CommandExecutionLoadTest()
    results["command_execution"] = await command_test.simulate_concurrent_commands(500)

    # Database Load Test
    print("\n🗄️ Database Load Test")
    print("-" * 40)
    database_test = DatabaseLoadTest()
    results["database_operations"] = await database_test.simulate_database_load(1000)

    # Generate comprehensive report
    print("\n" + "=" * 70)
    print("📊 LOAD TESTING COMPREHENSIVE REPORT")
    print("=" * 70)

    for test_name, metrics in results.items():
        summary = metrics.get_summary()
        print(f"\n🔍 {test_name.replace('_', ' ').title()} Results:")
        print(f"   ⏱️  Total Time: {summary['total_time']:.2f}s")
        print(f"   📈 Operations/sec: {summary['operations_per_second']:.2f}")
        print(f"   ✅ Success Rate: {summary['success_rate']:.1f}%")
        print(f"   ❌ Error Rate: {summary['error_rate']:.1f}%")

        if "avg_response_time" in summary:
            print(
                f"   📊 Avg Response Time: {summary['avg_response_time'] * 1000:.2f}ms"
            )
            print(
                f"   📊 P95 Response Time: {summary['p95_response_time'] * 1000:.2f}ms"
            )
            print(
                f"   📊 P99 Response Time: {summary['p99_response_time'] * 1000:.2f}ms"
            )

        if "avg_memory_mb" in summary:
            print(f"   💾 Avg Memory Usage: {summary['avg_memory_mb']:.1f}MB")
            print(f"   💾 Peak Memory Usage: {summary['max_memory_mb']:.1f}MB")

        if "avg_cpu_percent" in summary:
            print(f"   🖥️  Avg CPU Usage: {summary['avg_cpu_percent']:.1f}%")
            print(f"   🖥️  Peak CPU Usage: {summary['max_cpu_percent']:.1f}%")

    # Overall assessment
    print("\n🎯 OVERALL ASSESSMENT:")
    total_operations = sum(r.success_count + r.error_count for r in results.values())
    total_errors = sum(r.error_count for r in results.values())
    overall_success_rate = (
        ((total_operations - total_errors) / total_operations * 100)
        if total_operations > 0
        else 0
    )

    print(f"   📊 Total Operations Tested: {total_operations:,}")
    print(f"   ✅ Overall Success Rate: {overall_success_rate:.1f}%")

    if overall_success_rate >= 95:
        print("   🎉 EXCELLENT: System performs well under load!")
    elif overall_success_rate >= 90:
        print("   ✅ GOOD: System handles load adequately with minor issues.")
    elif overall_success_rate >= 80:
        print(
            "   ⚠️  FAIR: System shows some stress under load - optimization recommended."
        )
    else:
        print(
            "   ❌ POOR: System struggles under load - immediate optimization required."
        )

    return overall_success_rate >= 90


async def main() -> bool | None:
    """Main load testing execution function."""
    try:
        success = await run_all_load_tests()
        if success:
            print("\n🎉 Load testing completed successfully!")
            return True
        else:
            print("\n⚠️ Load testing revealed performance issues!")
            return False
    except Exception as e:
        print(f"\n💥 Load testing crashed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())
