"""Resource monitoring utility module.

This module provides utilities for monitoring resource usage, including memory usage,
CPU usage, disk I/O, network I/O, and other metrics. It helps identify potential
performance issues and optimize resource usage.
"""

import asyncio
import contextlib
import gc
import logging
import os
import platform
import time
import traceback
import tracemalloc
from collections import defaultdict
from datetime import datetime
from typing import Any

import psutil  # type: ignore[import-untyped]  # types-psutil not installed


class ResourceMonitor:
    """Resource monitoring utility class.

    This class provides methods for monitoring resource usage, including memory usage,
    CPU usage, and other metrics. It can be used to track resource usage over time
    and identify potential performance issues.
    """

    def __init__(
        self,
        check_interval: int = 60,
        memory_threshold: float = 85.0,
        cpu_threshold: float = 80.0,
        disk_io_threshold: float = 80.0,
        network_io_threshold: float = 80.0,
        enable_gc_monitoring: bool = False,
        enable_memory_leak_detection: bool = True,
        memory_leak_threshold: int = 52428800,  # 50 MB (increased from 10MB)
        logger: logging.Logger | None = None,
        pool: Any = None,
    ) -> None:
        """Initialize the resource monitor.

        Args:
            check_interval: Interval in seconds between resource checks.
            memory_threshold: Memory usage threshold percentage for warnings.
            cpu_threshold: CPU usage threshold percentage for warnings.
            disk_io_threshold: Disk I/O usage threshold percentage for warnings.
            network_io_threshold: Network I/O usage threshold percentage for warnings.
            enable_gc_monitoring: Whether to enable garbage collection monitoring.
            enable_memory_leak_detection: Whether to enable memory leak detection.
            memory_leak_threshold: Threshold in bytes for memory leak detection.
            logger: Logger instance to use for logging.
            pool: Optional asyncpg connection pool to monitor for utilization /
                saturation. Accepted as Any to avoid importing asyncpg here.
        """
        self.check_interval = check_interval
        self.memory_threshold = memory_threshold
        self.cpu_threshold = cpu_threshold
        self.disk_io_threshold = disk_io_threshold
        self.network_io_threshold = network_io_threshold
        self.enable_gc_monitoring = enable_gc_monitoring
        self.enable_memory_leak_detection = enable_memory_leak_detection
        self.memory_leak_threshold = memory_leak_threshold
        self.logger = logger or logging.getLogger("resource_monitor")
        self.pool = pool

        # Initialize monitoring state
        self._monitoring_task: asyncio.Task[None] | None = None
        self._process = psutil.Process(os.getpid())
        self._stats_history: list[dict[str, Any]] = []
        self._max_history_size = 60  # Keep history for 60 intervals

        # Prime the CPU counters: cpu_percent(interval=None) is non-blocking
        # and measures usage since the *previous* call, so it needs a baseline
        # call here (the very first call always returns 0.0).
        self._process.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)

        # Initialize I/O counters
        self._last_disk_io = self._get_process_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_io_time = time.time()

        # Initialize garbage collection monitoring
        if self.enable_gc_monitoring:
            gc.set_debug(gc.DEBUG_STATS)
            self._gc_stats = {
                "collections": [0, 0, 0],  # Count for each generation
                "collected": 0,
                "uncollectable": 0,
            }

        # Initialize memory leak detection
        if self.enable_memory_leak_detection:
            tracemalloc.start()
            self._memory_snapshots: list[tuple[datetime, tracemalloc.Snapshot]] = []
            self._memory_growth: dict[str, int] = {}
            self._potential_leaks: set[str] = set()
            # Exclude tracemalloc's own allocations — they grow with the
            # snapshot list itself and surface as false-positive leaks.
            self._snapshot_filters: tuple[tracemalloc.Filter, ...] = (
                tracemalloc.Filter(False, tracemalloc.__file__),
            )

        # Initialize connection tracking
        self._connection_stats: dict[str, defaultdict[Any, int]] = {
            "by_type": defaultdict(int),
            "by_status": defaultdict(int),
            "by_remote_ip": defaultdict(int),
        }

    def _get_process_io_counters(self) -> Any:
        """Return this process's I/O counters, or None if unavailable.

        Scoped to the bot process on purpose: ``psutil.disk_io_counters()`` is
        host-wide (reads ``/proc/diskstats``), so on shared infra like Railway it
        reports the whole node's disk activity — noisy neighbours included — which
        the bot neither causes nor can control, and trips the threshold falsely.
        ``Process.io_counters()`` is unsupported on some platforms (e.g. macOS),
        so failures degrade gracefully to None.
        """
        try:
            return self._process.io_counters()
        except (psutil.AccessDenied, NotImplementedError, AttributeError):
            return None

    async def start_monitoring(self) -> None:
        """Start the resource monitoring background task."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitor_resources())
            self.logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the resource monitoring background task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
            self.logger.info("Resource monitoring stopped")

    async def _monitor_resources(self) -> None:
        """Background task that periodically checks resource usage."""
        while True:
            try:
                # Get current resource usage (off the event loop — the psutil
                # /proc scans and tracemalloc snapshots are not free).
                stats = await self.get_resource_stats_async()

                # Add to history
                self._stats_history.append(stats)
                if len(self._stats_history) > self._max_history_size:
                    self._stats_history.pop(0)

                # Check for threshold violations - Memory and CPU
                if stats["memory_percent"] > self.memory_threshold:
                    self.logger.warning(
                        f"Memory usage above threshold: {stats['memory_percent']:.1f}% "
                        f"(threshold: {self.memory_threshold}%)"
                    )

                if stats["cpu_percent"] > self.cpu_threshold:
                    self.logger.warning(
                        f"CPU usage above threshold: {stats['cpu_percent']:.1f}% "
                        f"(threshold: {self.cpu_threshold}%)"
                    )

                # Check for disk I/O threshold violations
                if (
                    "disk_read_bytes_per_sec" in stats
                    and "disk_write_bytes_per_sec" in stats
                ):
                    disk_read_mb = stats["disk_read_bytes_per_sec"] / (1024 * 1024)
                    disk_write_mb = stats["disk_write_bytes_per_sec"] / (1024 * 1024)

                    if (
                        disk_read_mb > self.disk_io_threshold
                        or disk_write_mb > self.disk_io_threshold
                    ):
                        self.logger.warning(
                            f"Disk I/O usage above threshold: Read: {disk_read_mb:.2f} MB/s, "
                            f"Write: {disk_write_mb:.2f} MB/s (threshold: {self.disk_io_threshold} MB/s)"
                        )

                # Check for network I/O threshold violations
                if (
                    "net_bytes_sent_per_sec" in stats
                    and "net_bytes_recv_per_sec" in stats
                ):
                    net_sent_mb = stats["net_bytes_sent_per_sec"] / (1024 * 1024)
                    net_recv_mb = stats["net_bytes_recv_per_sec"] / (1024 * 1024)

                    if (
                        net_sent_mb > self.network_io_threshold
                        or net_recv_mb > self.network_io_threshold
                    ):
                        self.logger.warning(
                            f"Network I/O usage above threshold: Sent: {net_sent_mb:.2f} MB/s, "
                            f"Received: {net_recv_mb:.2f} MB/s (threshold: {self.network_io_threshold} MB/s)"
                        )

                # Warn on an unusually high open-connection count for the process.
                if stats["connection_count"] > 50:
                    self.logger.warning(
                        f"High connection count detected: {stats['connection_count']} connections"
                    )

                # Warn only on genuine saturation: every connection the pool can
                # open is checked out, so the next acquirer must wait. Requiring
                # in_use >= max avoids a false positive on a quiescent pool, which
                # also reports 0 idle simply because asyncpg has closed its idle
                # connections (max_inactive_connection_lifetime) and shrunk to 0.
                pool_max = stats.get("db_pool_max", 0)
                if pool_max > 0 and stats.get("db_pool_in_use", 0) >= pool_max:
                    self.logger.warning(
                        f"DB connection pool saturated: "
                        f"{stats['db_pool_in_use']}/{pool_max} connections in use, "
                        f"0 idle — further queries will wait to acquire a connection"
                    )

                # Check for garbage collection issues
                if self.enable_gc_monitoring and "gc_objects" in stats:
                    if stats["gc_objects"] > 1000000:  # Arbitrary threshold
                        self.logger.warning(
                            f"High object count detected: {stats['gc_objects']} objects"
                        )

                    if "gc_uncollectable" in stats and stats["gc_uncollectable"] > 0:
                        self.logger.warning(
                            f"Uncollectable objects detected: {stats['gc_uncollectable']} objects"
                        )

                # Log detailed stats at debug level
                self.logger.debug(
                    f"Resource stats: Memory: {stats['memory_percent']:.1f}%, "
                    f"CPU: {stats['cpu_percent']:.1f}%, "
                    f"Threads: {stats['thread_count']}, "
                    f"Open files: {stats['open_files_count']}, "
                    f"Connections: {stats['connection_count']}"
                )

                # Log I/O stats if available
                if (
                    "disk_read_bytes_per_sec" in stats
                    and "net_bytes_sent_per_sec" in stats
                ):
                    self.logger.debug(
                        f"I/O stats: Disk read: {stats['disk_read_bytes_per_sec'] / 1024:.1f} KB/s, "
                        f"Disk write: {stats['disk_write_bytes_per_sec'] / 1024:.1f} KB/s, "
                        f"Net sent: {stats['net_bytes_sent_per_sec'] / 1024:.1f} KB/s, "
                        f"Net recv: {stats['net_bytes_recv_per_sec'] / 1024:.1f} KB/s"
                    )

                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                self.logger.error(traceback.format_exc())
                await asyncio.sleep(self.check_interval)

    async def get_resource_stats_async(self) -> dict[str, Any]:
        """Get current resource usage statistics without blocking the event loop.

        ``get_resource_stats()`` is non-blocking by design (no sleeps), but its
        psutil /proc scans and tracemalloc snapshots still cost real CPU time,
        so async callers should prefer this wrapper, which runs the collection
        in a worker thread.

        Returns:
            A dictionary with resource usage statistics.
        """
        return await asyncio.to_thread(self.get_resource_stats)

    def get_resource_stats(self) -> dict[str, Any]:
        """Get current resource usage statistics.

        This method must stay cheap and non-blocking: it is called from async
        contexts (use :meth:`get_resource_stats_async` where possible). CPU
        usage is sampled with ``cpu_percent(interval=None)``, which measures
        against the previous call (primed in ``__init__``) instead of sleeping.

        Returns:
            A dictionary with resource usage statistics.
        """
        memory_info = self._process.memory_info()
        current_time = time.time()
        # Fetch the connection list once and reuse it for both the count and
        # the per-type/status/IP breakdown below (it's a /proc scan).
        connections = self._process.net_connections()

        # Basic stats
        stats = {
            "timestamp": datetime.now(),
            "memory_rss": memory_info.rss,
            "memory_vms": memory_info.vms,
            "memory_percent": self._process.memory_percent(),
            "cpu_percent": self._process.cpu_percent(interval=None),
            "thread_count": self._process.num_threads(),
            "open_files_count": len(self._process.open_files()),
            "connection_count": len(connections),
            "uptime": current_time - self._process.create_time(),
            "system_memory_percent": psutil.virtual_memory().percent,
            "system_cpu_percent": psutil.cpu_percent(interval=None),
        }

        # Disk I/O stats (scoped to this process — see _get_process_io_counters)
        current_disk_io = self._get_process_io_counters()
        time_diff = current_time - self._last_io_time

        if self._last_disk_io and current_disk_io and time_diff > 0:
            read_bytes_per_sec = (
                current_disk_io.read_bytes - self._last_disk_io.read_bytes
            ) / time_diff
            write_bytes_per_sec = (
                current_disk_io.write_bytes - self._last_disk_io.write_bytes
            ) / time_diff

            stats.update(
                {
                    "disk_read_bytes_per_sec": read_bytes_per_sec,
                    "disk_write_bytes_per_sec": write_bytes_per_sec,
                    "disk_read_count": current_disk_io.read_count,
                    "disk_write_count": current_disk_io.write_count,
                }
            )

        self._last_disk_io = current_disk_io

        # Network I/O stats
        current_net_io = psutil.net_io_counters()

        if self._last_net_io and time_diff > 0:
            bytes_sent_per_sec = (
                current_net_io.bytes_sent - self._last_net_io.bytes_sent
            ) / time_diff
            bytes_recv_per_sec = (
                current_net_io.bytes_recv - self._last_net_io.bytes_recv
            ) / time_diff

            stats.update(
                {
                    "net_bytes_sent_per_sec": bytes_sent_per_sec,
                    "net_bytes_recv_per_sec": bytes_recv_per_sec,
                    "net_packets_sent": current_net_io.packets_sent,
                    "net_packets_recv": current_net_io.packets_recv,
                    "net_errin": current_net_io.errin,
                    "net_errout": current_net_io.errout,
                    "net_dropin": current_net_io.dropin,
                    "net_dropout": current_net_io.dropout,
                }
            )

        self._last_net_io = current_net_io
        self._last_io_time = current_time

        # Database connection pool stats (asyncpg). Surfacing idle/in-use makes
        # pool saturation — the usual cause of "slow" trivial queries waiting to
        # acquire a connection — visible over time.
        if self.pool is not None:
            try:
                pool_max = self.pool.get_max_size()
                pool_size = self.pool.get_size()
                pool_idle = self.pool.get_idle_size()
                stats.update(
                    {
                        "db_pool_max": pool_max,
                        "db_pool_size": pool_size,
                        "db_pool_idle": pool_idle,
                        "db_pool_in_use": pool_size - pool_idle,
                    }
                )
            except Exception as e:
                self.logger.debug(f"Could not read DB pool stats: {e}")

        # Garbage collection stats
        if self.enable_gc_monitoring:
            # Get current counts
            counts = gc.get_count()
            # Get stats from last collection
            stats_last = (
                gc.get_stats()[-1]
                if gc.get_stats()
                else {"collected": 0, "uncollectable": 0}
            )

            stats.update(
                {
                    "gc_counts": counts,
                    "gc_collected": stats_last["collected"],
                    "gc_uncollectable": stats_last["uncollectable"],
                    "gc_objects": len(gc.get_objects()),
                }
            )

        # Connection tracking (reuses the connection list fetched above)
        if hasattr(self, "_connection_stats"):
            # Reset counters
            self._connection_stats["by_type"] = defaultdict(int)
            self._connection_stats["by_status"] = defaultdict(int)
            self._connection_stats["by_remote_ip"] = defaultdict(int)

            for conn in connections:
                self._connection_stats["by_type"][conn.type] += 1
                self._connection_stats["by_status"][conn.status] += 1
                if conn.raddr:
                    self._connection_stats["by_remote_ip"][conn.raddr.ip] += 1

            stats.update(
                {
                    "connections_by_type": dict(self._connection_stats["by_type"]),
                    "connections_by_status": dict(self._connection_stats["by_status"]),
                    "connections_by_remote_ip": dict(
                        self._connection_stats["by_remote_ip"]
                    ),
                }
            )

        # Memory leak detection
        if self.enable_memory_leak_detection and hasattr(self, "_memory_snapshots"):
            current_snapshot = tracemalloc.take_snapshot().filter_traces(
                self._snapshot_filters
            )
            snapshot_time = datetime.now()

            # Keep only the last 5 snapshots
            self._memory_snapshots.append((snapshot_time, current_snapshot))
            if len(self._memory_snapshots) > 5:
                self._memory_snapshots.pop(0)

            # Compare with previous snapshot if available
            if len(self._memory_snapshots) > 1:
                _prev_time, prev_snapshot = self._memory_snapshots[-2]
                _current_time, current_snapshot = self._memory_snapshots[-1]

                # Get top 10 differences
                top_stats = current_snapshot.compare_to(prev_snapshot, "lineno")

                # Track memory growth by file
                for stat in top_stats[:10]:
                    key = f"{stat.traceback[0].filename}:{stat.traceback[0].lineno}"
                    size_diff = stat.size_diff

                    if size_diff > 0:
                        self._memory_growth[key] = (
                            self._memory_growth.get(key, 0) + size_diff
                        )

                        # Check for potential memory leaks
                        if self._memory_growth[key] > self.memory_leak_threshold:
                            self._potential_leaks.add(key)
                            self.logger.warning(
                                f"Potential memory leak detected at {key}: "
                                f"{self._memory_growth[key] / 1024 / 1024:.2f} MB accumulated"
                            )

                stats.update(
                    {
                        "memory_leak_candidates": list(self._potential_leaks),
                        "memory_growth_top10": dict(
                            sorted(
                                self._memory_growth.items(),
                                key=lambda item: item[1],
                                reverse=True,
                            )[:10]
                        ),
                    }
                )

        return stats

    def get_stats_history(self) -> list[dict[str, Any]]:
        """Get the history of resource usage statistics.

        Returns:
            A list of dictionaries with resource usage statistics.
        """
        return self._stats_history.copy()

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics of resource usage.

        Returns:
            A dictionary with summary statistics.
        """
        if not self._stats_history:
            return {}

        # Calculate averages and maximums
        memory_percentages = [stats["memory_percent"] for stats in self._stats_history]
        cpu_percentages = [stats["cpu_percent"] for stats in self._stats_history]
        thread_counts = [stats["thread_count"] for stats in self._stats_history]

        return {
            "avg_memory_percent": sum(memory_percentages) / len(memory_percentages),
            "max_memory_percent": max(memory_percentages),
            "avg_cpu_percent": sum(cpu_percentages) / len(cpu_percentages),
            "max_cpu_percent": max(cpu_percentages),
            "avg_thread_count": sum(thread_counts) / len(thread_counts),
            "max_thread_count": max(thread_counts),
            "current_stats": self._stats_history[-1] if self._stats_history else {},
            "history_duration_minutes": len(self._stats_history)
            * (self.check_interval / 60),
        }

    def get_system_info(self) -> dict[str, Any]:
        """Get system information.

        Returns:
            A dictionary with system information.
        """
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "total_memory": psutil.virtual_memory().total,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
