"""
Database utility module for Cognita bot.

This module provides utility functions and classes for database operations,
including transaction management, error handling, and connection management.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar, TypeAlias, Optional, Coroutine, AsyncGenerator

# Python 3.11+ has asyncio.timeout
try:
    from asyncio import timeout
except ImportError:
    # Fallback for Python < 3.11
    from async_timeout import timeout

import asyncpg

# Define type aliases for complex types
QueryResult: TypeAlias = dict[str, Any]
Record: TypeAlias = asyncpg.Record

T = TypeVar('T')

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass

class RetryableError(DatabaseError):
    """Exception for errors that can be retried."""
    pass

class DatabaseTransaction:
    """Async context manager for database transactions.

    This class provides a convenient way to manage database transactions
    using the async context manager protocol.

    Example:
        ```python
        async with DatabaseTransaction(db) as transaction:
            await db.execute("INSERT INTO users(name) VALUES($1)", "John")
            await db.execute("INSERT INTO profiles(user_id) VALUES($1)", user_id)
        ```
    """

    def __init__(self, db):
        """Initialize the transaction context manager.

        Args:
            db: The Database instance to use for the transaction.
        """
        self.db = db
        self.transaction = None

    async def __aenter__(self):
        """Enter the context manager, starting a new transaction.

        Returns:
            The transaction context manager instance.
        """
        self.transaction = self.db.transaction()
        await self.transaction.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, committing or rolling back the transaction.

        Args:
            exc_type: The exception type, if an exception was raised.
            exc_val: The exception value, if an exception was raised.
            exc_tb: The exception traceback, if an exception was raised.

        Returns:
            True if the exception was handled, False otherwise.
        """
        await self.transaction.__aexit__(exc_type, exc_val, exc_tb)

class Database:
    """Database utility class for managing database operations."""

    def __init__(self, pool: asyncpg.Pool):
        """Initialize the database utility with a connection pool.

        Args:
            pool: The asyncpg connection pool to use for database operations.
        """
        self.pool = pool
        self.logger = logging.getLogger('database')
        self.prepared_statements = {}
        self.slow_query_threshold = 0.5  # Log queries taking more than 500ms

    async def check_connection_health(self) -> bool:
        """Check if the database connection is healthy.

        Returns:
            True if the connection is healthy, False otherwise.
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
            self.logger.error(f"Connection health check failed: {e}")
            return False

    async def validate_connections(self) -> None:
        """Validate all connections in the pool.

        This method will close any invalid connections in the pool,
        allowing the pool to create new ones as needed.
        """
        try:
            await self.pool.execute("SELECT 1")
            self.logger.debug("Connection pool validated")
        except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
            self.logger.warning(f"Connection pool validation failed: {e}")
            # The pool will automatically handle reconnection

    async def prepare_statement(self, name: str, query: str) -> Any:
        """Prepare a statement and cache it for future use

        Args:
            name: A unique name for the prepared statement.
            query: The SQL query to prepare.

        Returns:
            The prepared statement.
        """
        if name not in self.prepared_statements:
            async with self.pool.acquire() as conn:
                stmt = await conn.prepare(query)
                self.prepared_statements[name] = stmt
        return self.prepared_statements[name]

    async def execute(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> str | None:
        """Execute a query that doesn't return rows.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            The command tag for the query.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                result = await self.pool.execute(query, *args, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e
        return None

    async def fetch(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> Sequence[Record]:
        """Execute a query and return all results.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            A list of records from the query.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                result = await self.pool.fetch(query, *args, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def fetchrow(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> Optional[Record]:
        """Execute a query and return the first row.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            The first record from the query, or None if no records.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                result = await self.pool.fetchrow(query, *args, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def fetchval(
        self, 
        query: str, 
        *args, 
        column: int = 0,
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> Any:
        """Execute a query and return a single value.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            column: The column index to return.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            The value from the specified column of the first row.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                result = await self.pool.fetchval(query, *args, column=column, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def transaction(self) -> asyncpg.transaction.Transaction:
        """Start a new transaction.

        Returns:
            A transaction object that can be used as a context manager.
        """
        return self.pool.transaction()

    async def execute_in_transaction(
        self, 
        queries: Sequence[tuple[str, tuple]],
        retries: int = 3,
        retry_delay: float = 0.5
    ) -> None:
        """Execute multiple queries in a single transaction.

        Args:
            queries: A list of (query, args) tuples to execute.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.

        Raises:
            DatabaseError: If the transaction fails after all retries.
        """
        for attempt in range(retries):
            try:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        for query, args in queries:
                            await conn.execute(query, *args)
                return
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                self.logger.error(f"Transaction error: {e}")
                raise DatabaseError(f"Failed to execute transaction: {e}") from e

    async def execute_many(
        self,
        query: str,
        args_list: Sequence[tuple],
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> None:
        """Execute a query with multiple sets of parameters.

        Args:
            query: The SQL query to execute.
            args_list: A list of parameter tuples, one for each execution.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                async with self.pool.acquire() as conn:
                    await conn.executemany(query, args_list, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow batch query ({duration:.2f}s): {query} with {len(args_list)} records")

                return
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error in batch operation: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error in batch operation: {e}")
                self.logger.error(f"Database error in batch operation: {e}")
                raise DatabaseError(f"Failed to execute batch query: {e}") from e

    async def copy_records_to_table(
        self,
        table_name: str,
        records: Sequence[tuple],
        columns: Optional[Sequence[str]] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> None:
        """Copy records to a table efficiently using COPY.

        Args:
            table_name: The name of the table to copy records to.
            records: A list of record tuples to copy.
            columns: Optional list of column names. If not provided, all columns are used.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor execution time.

        Raises:
            DatabaseError: If the operation fails after all retries.
        """
        start_time = time.time() if monitor else None

        column_str = f"({','.join(columns)})" if columns else ""

        for attempt in range(retries):
            try:
                async with self.pool.acquire() as conn:
                    await conn.copy_records_to_table(
                        table_name, 
                        records=records,
                        columns=columns
                    )

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow COPY operation ({duration:.2f}s): COPY {len(records)} records to {table_name}{column_str}")

                return
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                self.logger.error(f"Database error in COPY operation: {e}")
                raise DatabaseError(f"Failed to copy records to table: {e}") from e

    async def execute_with_callback(
        self, 
        callback: Callable[..., T], 
        *args, 
        **kwargs
    ) -> T:
        """Execute a callback function with a database connection.

        Args:
            callback: The function to call with a database connection.
            *args: Arguments to pass to the callback.
            **kwargs: Keyword arguments to pass to the callback.

        Returns:
            The result of the callback function.

        Raises:
            DatabaseError: If the callback fails.
        """
        try:
            async with self.pool.acquire() as conn:
                return await callback(conn, *args, **kwargs)
        except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
            self.logger.error(f"Database error in callback: {e}")
            raise DatabaseError(f"Failed to execute callback: {e}") from e

    async def execute_script(
        self, 
        script_path: str, 
        timeout: Optional[float] = 300.0,  # Default 5 minutes timeout
        retries: int = 3,
        retry_delay: float = 1.0,
        monitor: bool = True
    ) -> None:
        """Execute a SQL script file.

        Args:
            script_path: Path to the SQL script file.
            timeout: Optional timeout for the script execution in seconds (default: 300s).
            retries: Number of retries for transient errors (default: 3).
            retry_delay: Delay between retries in seconds (default: 1.0s).
            monitor: Whether to monitor script execution time.

        Raises:
            DatabaseError: If the script execution fails after all retries.
            FileNotFoundError: If the script file is not found.
            asyncio.TimeoutError: If the script execution times out.
        """
        try:
            with open(script_path, 'r') as f:
                script = f.read()

            start_time = time.time() if monitor else None

            for attempt in range(retries):
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute(script, timeout=timeout)

                    if monitor:
                        duration = time.time() - start_time
                        if duration > self.slow_query_threshold:
                            self.logger.warning(f"Slow script execution ({duration:.2f}s): {script_path}")

                    self.logger.info(f"Successfully executed script: {script_path}")
                    return
                except asyncio.TimeoutError:
                    if attempt < retries - 1:
                        self.logger.warning(f"Script execution timed out after {timeout}s on attempt {attempt + 1}/{retries}, retrying...")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    self.logger.error(f"Script execution timed out after {timeout}s: {script_path}")
                    raise
                except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                    if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                        # These errors are retryable
                        if attempt < retries - 1:
                            self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                            await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                            continue
                    elif isinstance(e, asyncpg.UniqueViolationError):
                        self.logger.warning(f"Unique violation error: {e}")
                    elif isinstance(e, asyncpg.ForeignKeyViolationError):
                        self.logger.warning(f"Foreign key violation error: {e}")
                    self.logger.error(f"Database error: {e}")
                    raise DatabaseError(f"Failed to execute script: {e}") from e
        except FileNotFoundError:
            self.logger.error(f"Script file not found: {script_path}")
            raise

    async def fetch_with_timeout(
        self, 
        query: str, 
        *args, 
        timeout_seconds: float = 5.0,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> Sequence[Record]:
        """Execute a query with a timeout and return all results.

        This method uses asyncio.timeout for more readable timeout handling.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout_seconds: Timeout in seconds.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            A list of records from the query.

        Raises:
            DatabaseError: If the query fails after all retries.
            asyncio.TimeoutError: If the query times out.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                async with timeout(timeout_seconds):
                    result = await self.pool.fetch(query, *args)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except asyncio.TimeoutError:
                self.logger.error(f"Query timed out after {timeout_seconds}s: {query}")
                raise
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def fetchrow_with_timeout(
        self, 
        query: str, 
        *args, 
        timeout_seconds: float = 5.0,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True
    ) -> Optional[Record]:
        """Execute a query with a timeout and return the first row.

        This method uses asyncio.timeout for more readable timeout handling.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout_seconds: Timeout in seconds.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.

        Returns:
            The first record from the query, or None if no records.

        Raises:
            DatabaseError: If the query fails after all retries.
            asyncio.TimeoutError: If the query times out.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                async with timeout(timeout_seconds):
                    result = await self.pool.fetchrow(query, *args)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except asyncio.TimeoutError:
                self.logger.error(f"Query timed out after {timeout_seconds}s: {query}")
                raise
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def paginate(
        self, 
        query: str, 
        *args, 
        page_size: int = 100,
        timeout_seconds: float = 30.0
    ) -> AsyncGenerator[Sequence[Record], None]:
        """Execute a query and yield results in pages.

        This method is an async generator that yields pages of results,
        which is useful for processing large result sets without loading
        everything into memory at once.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            page_size: Number of records to fetch per page.
            timeout_seconds: Timeout in seconds for the entire operation.

        Yields:
            Pages of records from the query.

        Raises:
            DatabaseError: If the query fails.
            asyncio.TimeoutError: If the operation times out.
        """
        try:
            # Use a single timeout for the entire pagination operation
            async with timeout(timeout_seconds):
                offset = 0
                while True:
                    paginated_query = f"{query} LIMIT {page_size} OFFSET {offset}"
                    results = await self.pool.fetch(paginated_query, *args)

                    if not results:
                        break

                    yield results

                    if len(results) < page_size:
                        break

                    offset += page_size
        except asyncio.TimeoutError:
            self.logger.error(f"Pagination timed out after {timeout_seconds}s: {query}")
            raise
        except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
            self.logger.error(f"Database error during pagination: {e}")
            raise DatabaseError(f"Failed to paginate query: {e}") from e

    async def refresh_materialized_views(self) -> None:
        """Refresh all materialized views.

        Raises:
            DatabaseError: If the refresh operation fails.
        """
        try:
            await self.execute("SELECT refresh_materialized_views()")
            self.logger.info("Successfully refreshed materialized views")
        except DatabaseError as e:
            self.logger.error(f"Error refreshing materialized views: {e}")
            raise
