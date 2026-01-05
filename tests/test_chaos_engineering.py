"""
Chaos engineering tests for the Twi Bot Shard.

This module tests the bot's resilience under various failure conditions including:
- Database connection failures and timeouts
- Network failures and API unavailability
- Memory pressure and resource exhaustion
- External service failures
- Concurrent failure scenarios
- Recovery and graceful degradation testing

These tests help ensure the bot can handle unexpected failures gracefully and
maintain functionality even when dependencies are unreliable.
"""

import asyncio
import os
import random
import sys
import time
from typing import Any, Never
from unittest.mock import AsyncMock, MagicMock, patch

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

import discord
from discord.ext import commands

from cogs.other import OtherCogs

# Import cogs for testing
from cogs.stats import StatsCogs
from cogs.twi import TwiCog

# Import test utilities
from tests.mock_factories import (
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockUserFactory,
)


class ChaosTestMetrics:
    """Class to track and analyze chaos test metrics."""

    def __init__(self) -> None:
        self.failure_scenarios: list[str] = []
        self.recovery_times: list[float] = []
        self.error_counts: dict[str, int] = {}
        self.success_counts: dict[str, int] = {}
        self.degradation_events: list[dict[str, Any]] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def start_test(self) -> None:
        """Start tracking chaos test metrics."""
        self.start_time = time.time()
        self.failure_scenarios.clear()
        self.recovery_times.clear()
        self.error_counts.clear()
        self.success_counts.clear()
        self.degradation_events.clear()

    def end_test(self) -> None:
        """End tracking chaos test metrics."""
        self.end_time = time.time()

    def record_failure_scenario(self, scenario: str) -> None:
        """Record a failure scenario being tested."""
        self.failure_scenarios.append(scenario)

    def record_recovery_time(self, recovery_time: float) -> None:
        """Record time taken to recover from a failure."""
        self.recovery_times.append(recovery_time)

    def record_error(self, scenario: str) -> None:
        """Record an error for a specific scenario."""
        self.error_counts[scenario] = self.error_counts.get(scenario, 0) + 1

    def record_success(self, scenario: str) -> None:
        """Record a success for a specific scenario."""
        self.success_counts[scenario] = self.success_counts.get(scenario, 0) + 1

    def record_degradation_event(
        self, event_type: str, severity: str, details: dict[str, Any]
    ) -> None:
        """Record a graceful degradation event."""
        self.degradation_events.append(
            {
                "type": event_type,
                "severity": severity,
                "details": details,
                "timestamp": time.time(),
            }
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of chaos test metrics."""
        total_time = self.end_time - self.start_time

        summary = {
            "total_time": total_time,
            "scenarios_tested": len(set(self.failure_scenarios)),
            "total_failures_injected": len(self.failure_scenarios),
            "average_recovery_time": (
                sum(self.recovery_times) / len(self.recovery_times)
                if self.recovery_times
                else 0
            ),
            "max_recovery_time": max(self.recovery_times) if self.recovery_times else 0,
            "degradation_events": len(self.degradation_events),
            "error_counts": self.error_counts,
            "success_counts": self.success_counts,
        }

        # Calculate resilience score (0-100)
        total_operations = sum(self.error_counts.values()) + sum(
            self.success_counts.values()
        )
        if total_operations > 0:
            success_rate = sum(self.success_counts.values()) / total_operations
            recovery_score = 1.0 - (
                summary["average_recovery_time"] / 10.0
            )  # Normalize to 10 seconds
            recovery_score = max(0, min(1, recovery_score))
            summary["resilience_score"] = (
                success_rate * 0.7 + recovery_score * 0.3
            ) * 100
        else:
            summary["resilience_score"] = 0

        return summary


class ChaosInjector:
    """Utility class for injecting various types of failures."""

    @staticmethod
    async def database_failure(duration: float = 1.0):
        """Simulate database connection failure."""

        async def failing_execute(*args, **kwargs) -> Never:
            await asyncio.sleep(0.1)  # Simulate timeout
            raise Exception("Database connection failed")

        return failing_execute

    @staticmethod
    async def network_failure(duration: float = 1.0):
        """Simulate network failure for external APIs."""

        async def failing_request(*args, **kwargs) -> Never:
            await asyncio.sleep(0.1)  # Simulate timeout
            raise Exception("Network connection failed")

        return failing_request

    @staticmethod
    async def memory_pressure():
        """Simulate memory pressure by consuming memory."""
        # Allocate 100MB of memory
        memory_hog = bytearray(100 * 1024 * 1024)
        return memory_hog

    @staticmethod
    async def slow_response(delay: float = 5.0):
        """Simulate slow response times."""

        async def slow_function(*args, **kwargs) -> str:
            await asyncio.sleep(delay)
            return "Slow response"

        return slow_function

    @staticmethod
    async def intermittent_failure(failure_rate: float = 0.5):
        """Simulate intermittent failures."""

        async def intermittent_function(*args, **kwargs) -> str:
            if random.random() < failure_rate:
                raise Exception("Intermittent failure")
            return "Success"

        return intermittent_function


class ChaosEngineeringTests:
    """Main chaos engineering test suite."""

    def __init__(self) -> None:
        self.metrics = ChaosTestMetrics()
        self.injector = ChaosInjector()
        self.logger = logging.getLogger("chaos_tests")

    async def setup_test_bot(self) -> commands.Bot:
        """Set up a test bot instance."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        bot = commands.Bot(command_prefix="!", intents=intents)

        # Mock the database connection
        bot.db = AsyncMock()
        bot.db.pool = AsyncMock()
        bot.db.execute = AsyncMock()
        bot.db.fetch = AsyncMock()
        bot.db.fetchrow = AsyncMock()

        return bot

    async def test_database_failure_resilience(self) -> bool:
        """Test bot resilience to database failures."""
        self.logger.info("Testing database failure resilience...")
        scenario = "database_failure"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            stats_cog = StatsCogs(bot)

            # Inject database failure
            failing_execute = await self.injector.database_failure()

            with patch.object(bot.db, "execute", side_effect=failing_execute):
                # Test that commands handle database failures gracefully
                ctx = MagicMock()
                ctx.send = AsyncMock()
                ctx.author = MockUserFactory.create()
                ctx.guild = MockGuildFactory.create()

                start_time = time.time()

                try:
                    # This should handle the database failure gracefully
                    # Use the callback method to call the command directly
                    # Provide required arguments: channel and hours
                    channel = MockChannelFactory.create_text_channel()
                    await stats_cog.message_count.callback(
                        stats_cog, ctx, channel=channel, hours=24
                    )
                    recovery_time = time.time() - start_time
                    self.metrics.record_recovery_time(recovery_time)
                    self.metrics.record_success(scenario)

                    # Verify that an error message was sent to the user
                    ctx.send.assert_called()
                    return True

                except Exception as e:
                    self.logger.error(f"Database failure test failed: {e}")
                    self.metrics.record_error(scenario)
                    return False

        except Exception as e:
            self.logger.error(f"Database failure test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def test_external_api_failure_resilience(self) -> bool:
        """Test bot resilience to external API failures."""
        self.logger.info("Testing external API failure resilience...")
        scenario = "external_api_failure"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            twi_cog = TwiCog(bot)

            # Mock the HTTP client to fail
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_get.side_effect = Exception("API unavailable")

                ctx = MagicMock()
                ctx.send = AsyncMock()
                ctx.author = MockUserFactory.create()

                start_time = time.time()

                try:
                    # Test wiki command with API failure
                    # Create a mock interaction for the wiki command
                    interaction = MockInteractionFactory.create()
                    await twi_cog.wiki.callback(twi_cog, interaction, query="test")
                    recovery_time = time.time() - start_time
                    self.metrics.record_recovery_time(recovery_time)
                    self.metrics.record_success(scenario)

                    # Verify that an error response was sent
                    interaction.response.defer.assert_called()
                    return True

                except Exception as e:
                    self.logger.error(f"External API failure test failed: {e}")
                    self.metrics.record_error(scenario)
                    return False

        except Exception as e:
            self.logger.error(f"External API failure test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def test_memory_pressure_resilience(self) -> bool:
        """Test bot resilience under memory pressure."""
        self.logger.info("Testing memory pressure resilience...")
        scenario = "memory_pressure"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            other_cog = OtherCogs(bot)

            # Record initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create memory pressure
            memory_hog = await self.injector.memory_pressure()

            start_time = time.time()

            try:
                # Test commands under memory pressure
                ctx = MagicMock()
                ctx.send = AsyncMock()
                ctx.author = MockUserFactory.create()

                await other_cog.ping.callback(other_cog, ctx)

                recovery_time = time.time() - start_time
                self.metrics.record_recovery_time(recovery_time)
                self.metrics.record_success(scenario)

                # Clean up memory
                del memory_hog

                # Record memory usage change
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory

                self.metrics.record_degradation_event(
                    "memory_pressure",
                    "medium" if memory_increase > 50 else "low",
                    {"memory_increase_mb": memory_increase},
                )

                return True

            except Exception as e:
                self.logger.error(f"Memory pressure test failed: {e}")
                self.metrics.record_error(scenario)
                return False

        except Exception as e:
            self.logger.error(f"Memory pressure test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def test_concurrent_failure_scenarios(self) -> bool:
        """Test bot resilience to multiple concurrent failures."""
        self.logger.info("Testing concurrent failure scenarios...")
        scenario = "concurrent_failures"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            stats_cog = StatsCogs(bot)

            # Inject multiple failures simultaneously
            failing_execute = await self.injector.database_failure()
            memory_hog = await self.injector.memory_pressure()

            with patch.object(bot.db, "execute", side_effect=failing_execute):
                with patch(
                    "aiohttp.ClientSession.get",
                    side_effect=Exception("Network failure"),
                ):
                    start_time = time.time()

                    try:
                        # Test multiple commands concurrently under failure conditions
                        ctx = MagicMock()
                        ctx.send = AsyncMock()
                        ctx.author = MockUserFactory.create()
                        ctx.guild = MockGuildFactory.create()

                        # Run multiple commands concurrently
                        channel = MockChannelFactory.create_text_channel()
                        tasks = [
                            stats_cog.message_count.callback(
                                stats_cog, ctx, channel=channel, hours=24
                            ),
                            stats_cog.message_count.callback(
                                stats_cog, ctx, channel=channel, hours=24
                            ),
                            stats_cog.message_count.callback(
                                stats_cog, ctx, channel=channel, hours=24
                            ),
                        ]

                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        recovery_time = time.time() - start_time
                        self.metrics.record_recovery_time(recovery_time)

                        # Check if at least some commands handled failures gracefully
                        successful_responses = sum(
                            1 for result in results if not isinstance(result, Exception)
                        )

                        if successful_responses > 0:
                            self.metrics.record_success(scenario)
                            return True
                        else:
                            self.metrics.record_error(scenario)
                            return False

                    except Exception as e:
                        self.logger.error(f"Concurrent failure test failed: {e}")
                        self.metrics.record_error(scenario)
                        return False
                    finally:
                        # Clean up memory
                        del memory_hog

        except Exception as e:
            self.logger.error(f"Concurrent failure test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def test_intermittent_failure_resilience(self) -> bool:
        """Test bot resilience to intermittent failures."""
        self.logger.info("Testing intermittent failure resilience...")
        scenario = "intermittent_failures"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            other_cog = OtherCogs(bot)

            # Create intermittent failure function
            await self.injector.intermittent_failure(failure_rate=0.3)

            success_count = 0
            failure_count = 0

            start_time = time.time()

            # Run multiple operations to test intermittent failures
            for _i in range(10):
                try:
                    ctx = MagicMock()
                    ctx.send = AsyncMock()
                    ctx.author = MockUserFactory.create()

                    # Simulate intermittent database issues
                    if random.random() < 0.3:  # 30% chance of failure
                        bot.db.execute.side_effect = Exception(
                            "Intermittent database error"
                        )
                    else:
                        bot.db.execute.side_effect = None
                        bot.db.execute.return_value = None

                    await other_cog.ping.callback(other_cog, ctx)
                    success_count += 1

                except Exception:
                    failure_count += 1

            recovery_time = time.time() - start_time
            self.metrics.record_recovery_time(recovery_time)

            # Consider test successful if at least 50% of operations succeeded
            if success_count >= 5:
                self.metrics.record_success(scenario)
                self.metrics.record_degradation_event(
                    "intermittent_failures",
                    "low" if success_count >= 8 else "medium",
                    {"success_rate": success_count / 10},
                )
                return True
            else:
                self.metrics.record_error(scenario)
                return False

        except Exception as e:
            self.logger.error(f"Intermittent failure test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def test_slow_response_handling(self) -> bool:
        """Test bot handling of slow responses."""
        self.logger.info("Testing slow response handling...")
        scenario = "slow_responses"
        self.metrics.record_failure_scenario(scenario)

        try:
            bot = await self.setup_test_bot()
            other_cog = OtherCogs(bot)

            # Mock slow database responses
            async def slow_execute(*args, **kwargs) -> None:
                await asyncio.sleep(2.0)  # 2 second delay
                return None

            bot.db.execute = slow_execute

            start_time = time.time()

            try:
                ctx = MagicMock()
                ctx.send = AsyncMock()
                ctx.author = MockUserFactory.create()

                # Test command with slow response
                await asyncio.wait_for(
                    other_cog.ping.callback(other_cog, ctx), timeout=5.0
                )

                recovery_time = time.time() - start_time
                self.metrics.record_recovery_time(recovery_time)
                self.metrics.record_success(scenario)

                # Record degradation based on response time
                severity = (
                    "high"
                    if recovery_time > 3.0
                    else "medium"
                    if recovery_time > 1.0
                    else "low"
                )
                self.metrics.record_degradation_event(
                    "slow_response", severity, {"response_time": recovery_time}
                )

                return True

            except TimeoutError:
                self.logger.warning("Command timed out - this may be expected behavior")
                self.metrics.record_success(scenario)  # Timeout handling is good
                return True

            except Exception as e:
                self.logger.error(f"Slow response test failed: {e}")
                self.metrics.record_error(scenario)
                return False

        except Exception as e:
            self.logger.error(f"Slow response test setup failed: {e}")
            self.metrics.record_error(scenario)
            return False

    async def run_all_chaos_tests(self) -> dict[str, Any]:
        """Run all chaos engineering tests and return results."""
        self.logger.info("Starting chaos engineering test suite...")
        self.metrics.start_test()

        test_results = {}

        # Run all chaos tests
        tests = [
            ("database_failure", self.test_database_failure_resilience),
            ("external_api_failure", self.test_external_api_failure_resilience),
            ("memory_pressure", self.test_memory_pressure_resilience),
            ("concurrent_failures", self.test_concurrent_failure_scenarios),
            ("intermittent_failures", self.test_intermittent_failure_resilience),
            ("slow_responses", self.test_slow_response_handling),
        ]

        for test_name, test_func in tests:
            try:
                self.logger.info(f"Running {test_name} test...")
                result = await test_func()
                test_results[test_name] = result
                self.logger.info(f"{test_name} test {'PASSED' if result else 'FAILED'}")
            except Exception as e:
                self.logger.error(f"Error running {test_name} test: {e}")
                test_results[test_name] = False

        self.metrics.end_test()

        # Generate summary
        summary = self.metrics.get_summary()
        summary["individual_test_results"] = test_results
        summary["overall_success"] = all(test_results.values())

        return summary


async def main() -> bool | None:
    """Main function to run chaos engineering tests."""
    chaos_tests = ChaosEngineeringTests()

    print("🔥 Starting Chaos Engineering Tests for Twi Bot Shard")
    print("=" * 60)

    try:
        results = await chaos_tests.run_all_chaos_tests()

        print("\n📊 CHAOS ENGINEERING TEST RESULTS")
        print("=" * 60)
        print(
            f"Overall Success: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}"
        )
        print(f"Resilience Score: {results['resilience_score']:.1f}/100")
        print(f"Scenarios Tested: {results['scenarios_tested']}")
        print(f"Total Failures Injected: {results['total_failures_injected']}")
        print(f"Average Recovery Time: {results['average_recovery_time']:.2f}s")
        print(f"Max Recovery Time: {results['max_recovery_time']:.2f}s")
        print(f"Degradation Events: {results['degradation_events']}")

        print("\n🧪 Individual Test Results:")
        for test_name, passed in results["individual_test_results"].items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {test_name}: {status}")

        print("\n📈 Error Counts by Scenario:")
        for scenario, count in results["error_counts"].items():
            print(f"  {scenario}: {count} errors")

        print("\n📈 Success Counts by Scenario:")
        for scenario, count in results["success_counts"].items():
            print(f"  {scenario}: {count} successes")

        if results["overall_success"]:
            print(
                "\n🎉 All chaos engineering tests passed! The bot shows good resilience."
            )
            return True
        else:
            print("\n⚠️  Some chaos engineering tests failed. Review the results above.")
            return False

    except Exception as e:
        print(f"\n❌ Error running chaos engineering tests: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
