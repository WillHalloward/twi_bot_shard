"""Database utility module for Cognita bot.

This module provides utility functions and classes for database operations,
including transaction management, error handling, connection management,
and query caching.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable, Sequence
from typing import Any, TypeVar

# Python 3.11+ has asyncio.timeout
try:
    from asyncio import timeout
except ImportError:
    # Fallback for Python < 3.11
    from async_timeout import timeout

import asyncpg

from utils.query_cache import QueryCache, cached_query

# Define type aliases for complex types
type QueryResult = dict[str, Any]
type Record = asyncpg.Record

T = TypeVar("T")


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

    def __init__(self, db) -> None:
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
        self.transaction = await self.db.transaction()
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

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Initialize the database utility with a connection pool.

        Args:
            pool: The asyncpg connection pool to use for database operations.
        """
        self.pool = pool
        self.logger = logging.getLogger("database")
        self.prepared_statements = {}
        self.slow_query_threshold = 0.5  # Log queries taking more than 500ms

        # Initialize query cache
        self.cache = QueryCache(
            max_size=2000,  # Store up to 2000 query results
            default_ttl=300,  # Default TTL of 5 minutes
            logger=self.logger,
        )

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
        """Prepare a statement and cache it for future use.

        Args:
            name: A unique name for the prepared statement.
            query: The SQL query to prepare.

        Returns:
            A wrapper around the prepared statement that provides execute, fetchval, fetchrow, and fetch methods.
        """

        class PreparedStatementWrapper:
            def __init__(self, db, stmt, query) -> None:
                self.db = db
                self.stmt = stmt
                self.query = query

            async def execute(self, *args, **kwargs):
                """Execute the prepared statement with the given arguments."""
                async with self.db.pool.acquire() as conn:
                    return await conn.execute(self.query, *args, **kwargs)

            async def fetchval(self, *args, column=0, **kwargs):
                """Execute the prepared statement and return a single value."""
                async with self.db.pool.acquire() as conn:
                    return await conn.fetchval(
                        self.query, *args, column=column, **kwargs
                    )

            async def fetchrow(self, *args, **kwargs):
                """Execute the prepared statement and return a single row."""
                async with self.db.pool.acquire() as conn:
                    return await conn.fetchrow(self.query, *args, **kwargs)

            async def fetch(self, *args, **kwargs):
                """Execute the prepared statement and return all rows."""
                async with self.db.pool.acquire() as conn:
                    return await conn.fetch(self.query, *args, **kwargs)

        if name not in self.prepared_statements:
            async with self.pool.acquire() as conn:
                stmt = await conn.prepare(query)
                self.prepared_statements[name] = PreparedStatementWrapper(
                    self, stmt, query
                )
        return self.prepared_statements[name]

    async def execute(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
        invalidate_cache: bool = True,  # Whether to invalidate cache for this query
    ) -> str | None:
        """Execute a query that doesn't return rows.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.
            invalidate_cache: Whether to invalidate cache for affected tables.

        Returns:
            The command tag for the query.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        # Extract table name from query for cache invalidation
        if invalidate_cache:
            self._invalidate_cache_for_query(query)

        for attempt in range(retries):
            try:
                result = await self.pool.execute(query, *args, timeout=timeout)

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e
        return None

    def _invalidate_cache_for_query(self, query: str) -> None:
        """Invalidate cache entries for tables affected by a query.

        Args:
            query: The SQL query that modifies data.
        """
        # Simple parsing to extract table names from modification queries
        query_lower = query.lower().strip()

        # Skip SELECT queries as they don't modify data
        if query_lower.startswith("select"):
            return

        # Extract table name based on query type
        table_name = None

        if query_lower.startswith("insert into"):
            # INSERT INTO table_name ...
            parts = query_lower.split(" ")
            if len(parts) > 2:
                table_name = parts[2].strip("()")
        elif query_lower.startswith("update"):
            # UPDATE table_name ...
            parts = query_lower.split(" ")
            if len(parts) > 1:
                table_name = parts[1].strip()
        elif query_lower.startswith("delete from"):
            # DELETE FROM table_name ...
            parts = query_lower.split(" ")
            if len(parts) > 2:
                table_name = parts[2].strip()

        # Invalidate cache for the affected table
        if table_name:
            self.cache.invalidate_by_table(table_name)
            self.logger.debug(f"Invalidated cache for table: {table_name}")

    @cached_query(ttl=300)  # Cache results for 5 minutes by default
    async def fetch(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
        use_cache: bool = True,  # Whether to use cache for this query
    ) -> Sequence[Record]:
        """Execute a query and return all results.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.
            use_cache: Whether to use cache for this query.

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
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    @cached_query(ttl=300)  # Cache results for 5 minutes by default
    async def fetchrow(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
        use_cache: bool = True,  # Whether to use cache for this query
    ) -> Record | None:
        """Execute a query and return the first row.

        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            monitor: Whether to monitor query execution time.
            use_cache: Whether to use cache for this query.

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
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    @cached_query(ttl=300)  # Cache results for 5 minutes by default
    async def fetchval(
        self,
        query: str,
        *args,
        column: int = 0,
        timeout: float | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
        use_cache: bool = True,  # Whether to use cache for this query
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
            use_cache: Whether to use cache for this query.

        Returns:
            The value from the specified column of the first row.

        Raises:
            DatabaseError: If the query fails after all retries.
        """
        start_time = time.time() if monitor else None

        for attempt in range(retries):
            try:
                result = await self.pool.fetchval(
                    query, *args, column=column, timeout=timeout
                )

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(f"Slow query ({duration:.2f}s): {query}")

                return result
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def transaction(self):
        """Start a new transaction.

        Returns:
            A transaction object that can be used as a context manager.

        Note:
            This method returns a custom transaction wrapper that ensures
            the connection is released when the transaction is done.
        """

        class TransactionWrapper:
            def __init__(self, conn, transaction) -> None:
                self.conn = conn
                self.transaction = transaction

            async def __aenter__(self):
                await self.transaction.__aenter__()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                try:
                    await self.transaction.__aexit__(exc_type, exc_val, exc_tb)
                finally:
                    await self.conn.close()

        conn = await self.pool.acquire()
        transaction = conn.transaction()
        return TransactionWrapper(conn, transaction)

    async def execute_in_transaction(
        self,
        queries: Sequence[tuple[str, tuple]],
        retries: int = 3,
        retry_delay: float = 0.5,
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
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                self.logger.error(f"Transaction error: {e}")
                raise DatabaseError(f"Failed to execute transaction: {e}") from e

    async def execute_many(
        self,
        query: str,
        args_list: Sequence[tuple],
        timeout: float | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
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
                        self.logger.warning(
                            f"Slow batch query ({duration:.2f}s): {query} with {len(args_list)} records"
                        )

                return
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(
                        f"Unique violation error in batch operation: {e}"
                    )
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(
                        f"Foreign key violation error in batch operation: {e}"
                    )
                self.logger.error(f"Database error in batch operation: {e}")
                raise DatabaseError(f"Failed to execute batch query: {e}") from e

    async def copy_records_to_table(
        self,
        table_name: str,
        records: Sequence[tuple],
        columns: Sequence[str] | None = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        monitor: bool = True,
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
                        table_name, records=records, columns=columns
                    )

                if monitor:
                    duration = time.time() - start_time
                    if duration > self.slow_query_threshold:
                        self.logger.warning(
                            f"Slow COPY operation ({duration:.2f}s): COPY {len(records)} records to {table_name}{column_str}"
                        )

                return
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                self.logger.error(f"Database error in COPY operation: {e}")
                raise DatabaseError(f"Failed to copy records to table: {e}") from e

    async def execute_with_callback(
        self, callback: Callable[..., T], *args, **kwargs
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
        timeout: float | None = 300.0,  # Default 5 minutes timeout
        retries: int = 3,
        retry_delay: float = 1.0,
        monitor: bool = True,
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
            with open(script_path) as f:
                script = f.read()

            start_time = time.time() if monitor else None

            for attempt in range(retries):
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute(script, timeout=timeout)

                    if monitor:
                        duration = time.time() - start_time
                        if duration > self.slow_query_threshold:
                            self.logger.warning(
                                f"Slow script execution ({duration:.2f}s): {script_path}"
                            )

                    self.logger.info(f"Successfully executed script: {script_path}")
                    return
                except TimeoutError:
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Script execution timed out after {timeout}s on attempt {attempt + 1}/{retries}, retrying..."
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                    self.logger.error(
                        f"Script execution timed out after {timeout}s: {script_path}"
                    )
                    raise
                except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                    if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                        # These errors are retryable
                        if attempt < retries - 1:
                            self.logger.warning(
                                f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                            )
                            await asyncio.sleep(
                                retry_delay * (2**attempt)
                            )  # Exponential backoff
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
        monitor: bool = True,
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
            except TimeoutError:
                self.logger.error(f"Query timed out after {timeout_seconds}s: {query}")
                raise
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
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
        monitor: bool = True,
    ) -> Record | None:
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
            except TimeoutError:
                self.logger.error(f"Query timed out after {timeout_seconds}s: {query}")
                raise
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError | asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(
                            f"Retryable error on attempt {attempt + 1}/{retries}: {e}"
                        )
                        await asyncio.sleep(
                            retry_delay * (2**attempt)
                        )  # Exponential backoff
                        continue
                elif isinstance(e, asyncpg.UniqueViolationError):
                    self.logger.warning(f"Unique violation error: {e}")
                elif isinstance(e, asyncpg.ForeignKeyViolationError):
                    self.logger.warning(f"Foreign key violation error: {e}")
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e

    async def paginate(
        self, query: str, *args, page_size: int = 100, timeout_seconds: float = 30.0
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
        except TimeoutError:
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

    async def apply_additional_optimizations(self) -> None:
        """Apply additional database optimizations.

        This method executes the SQL script in database/additional_optimizations.sql
        to apply additional indexes, materialized views, and other optimizations.

        Raises:
            DatabaseError: If the optimization script fails.
            FileNotFoundError: If the optimization script is not found.
        """
        try:
            script_path = "database/additional_optimizations.sql"
            self.logger.info(
                f"Applying additional database optimizations from {script_path}"
            )
            await self.execute_script(script_path)
            self.logger.info("Successfully applied additional database optimizations")

            # Refresh materialized views to ensure they're populated
            await self.refresh_materialized_views()
        except (DatabaseError, FileNotFoundError) as e:
            self.logger.error(f"Error applying additional database optimizations: {e}")
            raise

    async def get_cache_stats(self) -> dict:
        """Get statistics about the query cache.

        Returns:
            A dictionary with cache statistics.
        """
        stats = self.cache.get_stats()
        return {
            "hits": stats.hits,
            "misses": stats.misses,
            "hit_rate": stats.hit_rate,
            "evictions": stats.evictions,
            "invalidations": stats.invalidations,
            "total_requests": stats.total_requests,
        }
