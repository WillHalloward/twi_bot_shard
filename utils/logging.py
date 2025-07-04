"""
Structured logging configuration for the bot.

This module sets up structured logging using the structlog library,
providing more searchable and analyzable logs.
"""

import logging
import sys
import time
import uuid
import contextvars
from typing import Any, Dict, Optional, Callable, Iterator

import structlog
from structlog.stdlib import LoggerFactory
from structlog.contextvars import merge_contextvars

import config

# Create a context variable to store the request ID
request_id_var = contextvars.ContextVar("request_id", default=None)


def generate_request_id() -> str:
    """Generate a unique request ID.

    Returns:
        A unique request ID string.
    """
    return str(uuid.uuid4())


def get_request_id() -> Optional[str]:
    """Get the current request ID.

    Returns:
        The current request ID or None if not set.
    """
    return request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> None:
    """Set the current request ID.

    Args:
        request_id: The request ID to set. If None, a new ID will be generated.
    """
    if request_id is None:
        request_id = generate_request_id()
    request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear the current request ID."""
    request_id_var.set(None)


# Configure standard logging
def configure_stdlib_logging(
    log_level: int = logging.INFO, log_file: Optional[str] = None
) -> None:
    """Configure standard logging.

    Args:
        log_level: The logging level to use.
        log_file: Optional path to a log file.
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        import os

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join("logs", f"{log_file}.log"),
            encoding="utf-8",
            maxBytes=32 * 1024 * 1024,  # 32 MB
            backupCount=10,
        )
        handlers.append(file_handler)

    logging.basicConfig(format="%(message)s", level=log_level, handlers=handlers)


# Configure structlog
def configure_structlog(log_format: str = "console") -> None:
    """Configure structlog with processors for formatting and output.

    Args:
        log_format: The format to use for log output. Either "json" or "console".
    """
    # Common processors for all formats
    processors = [
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
        # Add context variables (including request_id)
        merge_contextvars,
        # Format the exception info
        structlog.processors.format_exc_info,
    ]

    # Add format-specific renderer
    if log_format == "json":
        # Format as JSON for machine readability
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Format for console readability
        processors.extend([structlog.dev.ConsoleRenderer(colors=True)])

    structlog.configure(
        processors=processors,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Initialize logging
def init_logging(
    log_level: int = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> structlog.stdlib.BoundLogger:
    """Initialize logging with both stdlib and structlog.

    Args:
        log_level: The logging level to use. Defaults to the level in config.
        log_file: Optional path to a log file. Defaults to the file in config.
        log_format: The format to use for log output. Either "json" or "console".
            Defaults to the format in config.

    Returns:
        A structlog logger instance.
    """
    level = log_level or getattr(config, "logging_level", logging.INFO)
    file = log_file or getattr(config, "logfile", None)
    format_value = log_format

    if format_value is None:
        # Get the log format from config, defaulting to "console"
        if hasattr(config, "log_format"):
            format_value = config.log_format.value
        else:
            format_value = "console"

    configure_stdlib_logging(level, file)
    configure_structlog(format_value)

    return structlog.get_logger()


# Create a logger for use throughout the application
logger = init_logging()

# Example usage:
# logger.info("message_received", user_id=123456, channel_id=789012, content_length=42)
# logger.error("command_failed", command="ping", error="Rate limited", retry_after=5.0)


# Context manager for request tracking
class RequestContext:
    """Context manager for tracking requests with a unique ID.

    This context manager sets a unique request ID for the duration of the context,
    which will be included in all log messages within the context.

    Example:
        ```python
        async with RequestContext(logger, "process_command") as ctx:
            # All logs within this context will include the same request ID
            logger.info("processing_command", command="ping")
            await process_command(ctx.request_id)
        ```
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger,
        operation_name: str,
        request_id: Optional[str] = None,
    ):
        """Initialize the request context.

        Args:
            logger: The logger to use.
            operation_name: A name for the operation being tracked.
            request_id: An optional request ID. If not provided, a new one will be generated.
        """
        self.logger = logger
        self.operation_name = operation_name
        self.request_id = request_id or generate_request_id()
        self.token = None

    def __enter__(self) -> "RequestContext":
        """Enter the context manager."""
        self.token = set_request_id(self.request_id)
        self.logger.info(f"{self.operation_name}_started", request_id=self.request_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager."""
        if exc_type is None:
            self.logger.info(
                f"{self.operation_name}_completed", request_id=self.request_id
            )
        else:
            self.logger.error(
                f"{self.operation_name}_failed",
                request_id=self.request_id,
                error=str(exc_val),
                error_type=exc_type.__name__,
            )
        clear_request_id()

    async def __aenter__(self) -> "RequestContext":
        """Enter the async context manager."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager."""
        self.__exit__(exc_type, exc_val, exc_tb)


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
                logger.info(
                    f"{operation_name}_completed",
                    duration=duration,
                    function=func.__name__,
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"{operation_name}_failed",
                    duration=duration,
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                )
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
            self.logger.info(
                f"{self.operation_name}_completed",
                duration=duration,
                **self.additional_info,
            )
        else:
            self.logger.error(
                f"{self.operation_name}_failed",
                duration=duration,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.additional_info,
            )
