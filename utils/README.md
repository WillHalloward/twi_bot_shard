# Database Utility Module

This module provides a robust and efficient way to interact with the PostgreSQL database in the Cognita bot.

## Features

- **Error handling with retries**: Automatically retries failed database operations with exponential backoff
- **Transaction management**: Easily execute multiple queries in a single transaction
- **Connection pooling**: Efficiently manages database connections to prevent leaks and improve performance
- **Parameterized queries**: Prevents SQL injection by using parameterized queries
- **Comprehensive logging**: Detailed logging of database operations and errors

## Usage

### Basic Queries

```python
# Execute a query that doesn't return rows
await bot.db.execute(
    "INSERT INTO example_table(name, value) VALUES($1, $2)",
    "example", 100
)

# Fetch multiple rows
results = await bot.db.fetch(
    "SELECT * FROM example_table WHERE value > $1",
    50
)

# Fetch a single row
row = await bot.db.fetchrow(
    "SELECT * FROM example_table WHERE name = $1",
    "example"
)

# Fetch a single value
value = await bot.db.fetchval(
    "SELECT value FROM example_table WHERE name = $1",
    "example"
)
```

### Transactions

```python
# Execute multiple queries in a transaction
queries = [
    ("INSERT INTO example_table(name, value) VALUES($1, $2)", ("example1", 100)),
    ("UPDATE example_table SET value = value + $1 WHERE name = $2", (50, "example1")),
    ("INSERT INTO example_log(action, timestamp) VALUES($1, NOW())", ("example_transaction",))
]

await bot.db.execute_in_transaction(queries)

# Or use a transaction context manager
async with bot.db.pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("INSERT INTO example_table(name, value) VALUES($1, $2)", "example2", 200)
        await conn.execute("UPDATE example_stats SET count = count + 1")
```

### Error Handling

The Database class automatically handles retries for transient errors, but you should still wrap your code in try/except blocks to handle other errors:

```python
try:
    await bot.db.execute(
        "INSERT INTO example_table(name, value) VALUES($1, $2)",
        "example", 100
    )
except Exception as e:
    logging.error(f"Error inserting data: {e}")
    # Handle the error appropriately
```

## Best Practices

1. **Use transactions for related operations**: When performing multiple related database operations, use transactions to ensure they are executed atomically.

2. **Handle errors appropriately**: Always wrap database operations in try/except blocks and handle errors appropriately.

3. **Use parameterized queries**: Always use parameterized queries to prevent SQL injection.

4. **Limit result sets**: When fetching data, use LIMIT clauses to prevent fetching too much data.

5. **Use appropriate methods**: Use the appropriate method for your query:
   - `execute` for queries that don't return rows (INSERT, UPDATE, DELETE)
   - `fetch` for queries that return multiple rows
   - `fetchrow` for queries that return a single row
   - `fetchval` for queries that return a single value

6. **Avoid long-running transactions**: Keep transactions as short as possible to avoid locking tables for too long.

7. **Use indexes**: Ensure your database tables have appropriate indexes for your queries.

## Example Cog

See the `example_cog.py` file for a complete example of how to use the Database utility class in a cog.

## Migration Guide

To migrate existing code to use the new Database utility:

1. Replace `bot.db.execute()` with `bot.db.execute()`
2. Replace `bot.db.fetch()` with `bot.db.fetch()`
3. Replace `bot.db.fetchrow()` with `bot.db.fetchrow()`
4. Replace `bot.db.fetchval()` with `bot.db.fetchval()`
5. Add appropriate error handling with try/except blocks
6. Use transactions for related operations

## Configuration

The database connection pool is configured in `main.py` with the following settings:

```python
asyncpg.create_pool(
    database=secrets.database,
    user=secrets.DB_user,
    password=secrets.DB_password,
    host=secrets.host,
    ssl=context,
    command_timeout=300,
    min_size=5,           # Minimum number of connections
    max_size=20,          # Maximum number of connections
    max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 minutes
    timeout=10.0          # Connection timeout
)
```

These settings can be adjusted based on the specific needs of your application.