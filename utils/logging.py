"""
Structured logging configuration for the bot.

This module sets up structured logging using the structlog library,
providing more searchable and analyzable logs.
"""

import logging
import sys
import time
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import LoggerFactory

import config as secrets

# Configure standard logging
def configure_stdlib_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """Configure standard logging.

    Args:
        log_level: The logging level to use.
        log_file: Optional path to a log file.
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=f"{log_file}.log",
            encoding="utf-8",
            maxBytes=32 * 1024 * 1024,  # 32 MB
            backupCount=10
        )
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=handlers
    )

# Configure structlog
def configure_structlog() -> None:
    """Configure structlog with processors for formatting and output."""
    structlog.configure(
        processors=[
            # Add log level name
            structlog.stdlib.add_log_level,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Add caller information
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # Format the exception info
            structlog.processors.format_exc_info,
            # Format as JSON for machine readability
            structlog.processors.JSONRenderer()
        ],
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Initialize logging
def init_logging(log_level: int = None, log_file: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Initialize logging with both stdlib and structlog.

    Args:
        log_level: The logging level to use. Defaults to the level in secrets.
        log_file: Optional path to a log file. Defaults to the file in secrets.

    Returns:
        A structlog logger instance.
    """
    level = log_level or getattr(secrets, "logging_level", logging.INFO)
    file = log_file or getattr(secrets, "logfile", None)

    configure_stdlib_logging(level, file)
    configure_structlog()

    return structlog.get_logger()

# Create a logger for use throughout the application
logger = init_logging()

# Example usage:
# logger.info("message_received", user_id=123456, channel_id=789012, content_length=42)
# logger.error("command_failed", command="ping", error="Rate limited", retry_after=5.0)

# Utility function for timing operations
def log_timing(logger: structlog.stdlib.BoundLogger, operation_name: str):
    """Decorator for logging the execution time of functions.

    Args:
        logger: The logger to use.
        operation_name: A name for the operation being timed.

    Returns:
        The decorated function.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"{operation_name}_completed", 
                           duration=duration,
                           function=func.__name__)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"{operation_name}_failed",
                            duration=duration,
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__)
                raise
        return wrapper
    return decorator

# Context manager for timing blocks of code
class TimingContext:
    """Context manager for timing blocks of code.

    Example:
        ```python
        with TimingContext(logger, "database_query") as ctx:
            results = await db.fetch("SELECT * FROM users")
            ctx.add_info(row_count=len(results))
        ```
    """

    def __init__(self, logger: structlog.stdlib.BoundLogger, operation_name: str):
        """Initialize the timing context.

        Args:
            logger: The logger to use.
            operation_name: A name for the operation being timed.
        """
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
        self.additional_info = {}

    def add_info(self, **kwargs: Any) -> None:
        """Add additional information to be logged.

        Args:
            **kwargs: Key-value pairs to include in the log.
        """
        self.additional_info.update(kwargs)

    async def __aenter__(self) -> "TimingContext":
        """Enter the async context manager."""
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager."""
        duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(f"{self.operation_name}_completed", 
                           duration=duration,
                           **self.additional_info)
        else:
            self.logger.error(f"{self.operation_name}_failed",
                            duration=duration,
                            error=str(exc_val),
                            error_type=exc_type.__name__,
                            **self.additional_info)
