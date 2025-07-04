"""
Resource monitoring utility module.

This module provides utilities for monitoring resource usage, including memory usage,
CPU usage, disk I/O, network I/O, and other metrics. It helps identify potential
performance issues and optimize resource usage.
"""

import asyncio
import gc
import logging
import os
import platform
import sys
import time
import traceback
import tracemalloc
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set

import psutil


class ResourceMonitor:
    """
    Resource monitoring utility class.

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
        memory_leak_threshold: int = 10485760,  # 10 MB
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the resource monitor.

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

        # Initialize monitoring state
        self._monitoring_task = None
        self._process = psutil.Process(os.getpid())
        self._stats_history: List[Dict[str, Any]] = []
        self._max_history_size = 60  # Keep history for 60 intervals

        # Initialize I/O counters
        self._last_disk_io = psutil.disk_io_counters()
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
            self._memory_snapshots: List[Tuple[datetime, tracemalloc.Snapshot]] = []
            self._memory_growth: Dict[str, int] = {}
            self._potential_leaks: Set[str] = set()

        # Initialize connection tracking
        self._connection_stats = {
            "by_type": defaultdict(int),
            "by_status": defaultdict(int),
            "by_remote_ip": defaultdict(int),
        }

    async def start_monitoring(self) -> None:
        """
        Start the resource monitoring background task.
        """
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitor_resources())
            self.logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """
        Stop the resource monitoring background task.
        """
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Resource monitoring stopped")

    async def _monitor_resources(self) -> None:
        """
        Background task that periodically checks resource usage.
        """
        while True:
            try:
                # Get current resource usage
                stats = self.get_resource_stats()

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

                # Check for high connection count
                if stats["connection_count"] > 100:  # Arbitrary threshold
                    self.logger.warning(
                        f"High connection count detected: {stats['connection_count']} connections"
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

    def get_resource_stats(self) -> Dict[str, Any]:
        """
        Get current resource usage statistics.

        Returns:
            A dictionary with resource usage statistics.
        """
        # Update process info
        self._process.cpu_percent()  # First call returns 0, so call it once before getting real value
        time.sleep(0.1)  # Short sleep to get more accurate CPU measurement

        memory_info = self._process.memory_info()
        current_time = time.time()

        # Basic stats
        stats = {
            "timestamp": datetime.now(),
            "memory_rss": memory_info.rss,
            "memory_vms": memory_info.vms,
            "memory_percent": self._process.memory_percent(),
            "cpu_percent": self._process.cpu_percent(),
            "thread_count": self._process.num_threads(),
            "open_files_count": len(self._process.open_files()),
            "connection_count": len(self._process.connections()),
            "uptime": current_time - self._process.create_time(),
            "system_memory_percent": psutil.virtual_memory().percent,
            "system_cpu_percent": psutil.cpu_percent(),
        }

        # Disk I/O stats
        current_disk_io = psutil.disk_io_counters()
        time_diff = current_time - self._last_io_time

        if self._last_disk_io and time_diff > 0:
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
                    "disk_read_time": current_disk_io.read_time,
                    "disk_write_time": current_disk_io.write_time,
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

        # Connection tracking
        if hasattr(self, "_connection_stats"):
            connections = self._process.connections()

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
            current_snapshot = tracemalloc.take_snapshot()
            current_time = datetime.now()

            # Keep only the last 5 snapshots
            self._memory_snapshots.append((current_time, current_snapshot))
            if len(self._memory_snapshots) > 5:
                self._memory_snapshots.pop(0)

            # Compare with previous snapshot if available
            if len(self._memory_snapshots) > 1:
                prev_time, prev_snapshot = self._memory_snapshots[-2]
                current_time, current_snapshot = self._memory_snapshots[-1]

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
                        "memory_growth_top10": {
                            k: v
                            for k, v in sorted(
                                self._memory_growth.items(),
                                key=lambda item: item[1],
                                reverse=True,
                            )[:10]
                        },
                    }
                )

        return stats

    def get_stats_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of resource usage statistics.

        Returns:
            A list of dictionaries with resource usage statistics.
        """
        return self._stats_history.copy()

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics of resource usage.

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

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.

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
