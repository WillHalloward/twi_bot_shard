"""
Database utility module for Cognita bot.

This module provides utility functions and classes for database operations,
including transaction management, error handling, and connection management.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

import asyncpg

T = TypeVar('T')

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass

class RetryableError(DatabaseError):
    """Exception for errors that can be retried."""
    pass

class Database:
    """Database utility class for managing database operations."""
    
    def __init__(self, pool: asyncpg.Pool):
        """Initialize the database utility with a connection pool.
        
        Args:
            pool: The asyncpg connection pool to use for database operations.
        """
        self.pool = pool
        self.logger = logging.getLogger('database')
    
    async def execute(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5
    ) -> str:
        """Execute a query that doesn't return rows.
        
        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            
        Returns:
            The command tag for the query.
            
        Raises:
            DatabaseError: If the query fails after all retries.
        """
        for attempt in range(retries):
            try:
                return await self.pool.execute(query, *args, timeout=timeout)
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e
    
    async def fetch(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5
    ) -> List[asyncpg.Record]:
        """Execute a query and return all results.
        
        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            
        Returns:
            A list of records from the query.
            
        Raises:
            DatabaseError: If the query fails after all retries.
        """
        for attempt in range(retries):
            try:
                return await self.pool.fetch(query, *args, timeout=timeout)
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e
    
    async def fetchrow(
        self, 
        query: str, 
        *args, 
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5
    ) -> Optional[asyncpg.Record]:
        """Execute a query and return the first row.
        
        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            
        Returns:
            The first record from the query, or None if no records.
            
        Raises:
            DatabaseError: If the query fails after all retries.
        """
        for attempt in range(retries):
            try:
                return await self.pool.fetchrow(query, *args, timeout=timeout)
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                self.logger.error(f"Database error: {e}")
                raise DatabaseError(f"Failed to execute query: {e}") from e
    
    async def fetchval(
        self, 
        query: str, 
        *args, 
        column: int = 0,
        timeout: Optional[float] = None,
        retries: int = 3,
        retry_delay: float = 0.5
    ) -> Any:
        """Execute a query and return a single value.
        
        Args:
            query: The SQL query to execute.
            *args: Parameters for the query.
            column: The column index to return.
            timeout: Optional timeout for the query.
            retries: Number of retries for transient errors.
            retry_delay: Delay between retries in seconds.
            
        Returns:
            The value from the specified column of the first row.
            
        Raises:
            DatabaseError: If the query fails after all retries.
        """
        for attempt in range(retries):
            try:
                return await self.pool.fetchval(query, *args, column=column, timeout=timeout)
            except (asyncpg.PostgresConnectionError, asyncpg.PostgresError) as e:
                if isinstance(e, asyncpg.DeadlockDetectedError) or isinstance(e, asyncpg.ConnectionDoesNotExistError):
                    # These errors are retryable
                    if attempt < retries - 1:
                        self.logger.warning(f"Retryable error on attempt {attempt + 1}/{retries}: {e}")
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
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
        queries: List[Tuple[str, Tuple]],
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