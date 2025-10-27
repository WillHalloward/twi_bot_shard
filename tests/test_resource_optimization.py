import asyncio
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from utils.http_client import HTTPClient
from utils.resource_monitor import ResourceMonitor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_resource_optimization")


async def test_http_client() -> None:
    """Test the enhanced HTTP client with connection pooling and circuit breaker."""
    logger.info("Testing HTTP client with connection pooling and circuit breaker")

    # Create HTTP client with custom settings
    http_client = HTTPClient(
        timeout=10,
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_timeout=30,
        retry_attempts=2,
        retry_start_timeout=0.1,
        logger=logger.getChild("http_client"),
    )

    try:
        # Test successful request
        logger.info("Testing successful request")
        response = await http_client.get("https://httpbin.org/get")
        logger.info(f"Response status: {response.status}")

        # Test request with retry
        logger.info("Testing request with retry (will fail)")
        try:
            await http_client.get(
                "https://httpbin.org/status/500", retry_for_statuses=[500]
            )
        except Exception as e:
            logger.info(f"Expected error: {e}")

        # Test circuit breaker
        logger.info("Testing circuit breaker")
        # Force circuit breaker to open
        domain = "https://httpbin.org"
        for _ in range(5):
            http_client.circuit_breaker.record_failure(domain)

        try:
            await http_client.get("https://httpbin.org/get")
        except Exception as e:
            logger.info(f"Expected circuit breaker error: {e}")

        # Get stats
        stats = http_client.get_stats()
        logger.info(f"HTTP client stats: {stats}")

        endpoint_stats = http_client.get_endpoint_stats()
        logger.info(f"Endpoint stats: {endpoint_stats}")

    finally:
        await http_client.close()


async def test_resource_monitor() -> None:
    """Test the enhanced resource monitor."""
    logger.info("Testing resource monitor")

    # Create resource monitor with custom settings
    resource_monitor = ResourceMonitor(
        check_interval=5,
        memory_threshold=80.0,
        cpu_threshold=80.0,
        disk_io_threshold=50.0,
        network_io_threshold=50.0,
        enable_gc_monitoring=True,
        enable_memory_leak_detection=True,
        logger=logger.getChild("resource_monitor"),
    )

    try:
        # Start monitoring
        await resource_monitor.start_monitoring()

        # Generate some load
        logger.info("Generating some load")
        data = []
        for i in range(100000):
            data.append(f"test data {i}" * 10)

        # Wait for monitoring to collect some data
        await asyncio.sleep(10)

        # Get stats
        stats = resource_monitor.get_resource_stats()
        logger.info(f"Resource stats: {stats}")

        summary_stats = resource_monitor.get_summary_stats()
        logger.info(f"Summary stats: {summary_stats}")

        system_info = resource_monitor.get_system_info()
        logger.info(f"System info: {system_info}")

    finally:
        await resource_monitor.stop_monitoring()


async def main() -> None:
    """Run all tests."""
    logger.info("Starting resource optimization tests")

    await test_http_client()
    await test_resource_monitor()

    logger.info("All tests completed")


if __name__ == "__main__":
    asyncio.run(main())
