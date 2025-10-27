"""Example cog demonstrating best practices for database operations.

This cog shows how to use the Database utility class for various database operations,
including error handling, transactions, and query optimization.
"""

import discord
import structlog
from discord import app_commands
from discord.ext import commands


class ExampleCog(commands.Cog, name="Example"):
    """Example cog demonstrating best practices for database operations."""

    def __init__(self, bot) -> None:
        """Initialize the cog with a reference to the bot."""
        self.bot = bot
        self.logger = structlog.get_logger("cogs.example")

    @commands.command(name="example_transaction")
    @commands.is_owner()
    async def example_transaction(self, ctx) -> None:
        """Example command demonstrating transaction usage."""
        # Define the queries to execute in a transaction
        queries = [
            (
                "INSERT INTO example_table(name, value) VALUES($1, $2)",
                ("example1", 100),
            ),
            (
                "UPDATE example_table SET value = value + $1 WHERE name = $2",
                (50, "example1"),
            ),
            (
                "INSERT INTO example_log(action, timestamp) VALUES($1, NOW())",
                ("example_transaction",),
            ),
        ]

        try:
            # Execute all queries in a single transaction
            await self.bot.db.execute_in_transaction(queries)
            await ctx.send("Transaction completed successfully!")
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            await ctx.send(f"Transaction failed: {e}")

    @app_commands.command(name="example_fetch")
    async def example_fetch(self, interaction: discord.Interaction, limit: int = 10) -> None:
        """Example command demonstrating fetch operations with error handling."""
        try:
            # Fetch data with retry logic built in
            results = await self.bot.db.fetch(
                "SELECT * FROM example_table ORDER BY value DESC LIMIT $1", limit
            )

            if not results:
                await interaction.response.send_message("No results found.")
                return

            # Process the results
            response = "Results:\n"
            for row in results:
                response += f"- {row['name']}: {row['value']}\n"

            await interaction.response.send_message(response)
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            await interaction.response.send_message(
                "An error occurred while fetching data. Please try again later.",
                ephemeral=True,
            )

    @app_commands.command(name="example_update")
    async def example_update(
        self, interaction: discord.Interaction, name: str, value: int
    ) -> None:
        """Example command demonstrating update operations with error handling."""
        try:
            # First, check if the record exists
            exists = await self.bot.db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM example_table WHERE name = $1)", name
            )

            if exists:
                # Update existing record
                await self.bot.db.execute(
                    "UPDATE example_table SET value = $1 WHERE name = $2", value, name
                )
                await interaction.response.send_message(f"Updated {name} to {value}.")
            else:
                # Insert new record
                await self.bot.db.execute(
                    "INSERT INTO example_table(name, value) VALUES($1, $2)", name, value
                )
                await interaction.response.send_message(
                    f"Created new record {name} with value {value}."
                )
        except Exception as e:
            self.logger.error(f"Error updating data: {e}")
            await interaction.response.send_message(
                "An error occurred while updating data. Please try again later.",
                ephemeral=True,
            )

    @commands.Cog.listener("on_message")
    async def example_listener(self, message) -> None:
        """Example event listener demonstrating database operations in event handlers."""
        # Skip bot messages
        if message.author.bot:
            return

        # Example of a complex operation that should use a transaction
        if "!example" in message.content:
            try:
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.transaction():
                        # Multiple related operations that should be atomic
                        await conn.execute(
                            "INSERT INTO example_messages(message_id, content, author_id) VALUES($1, $2, $3)",
                            message.id,
                            message.content,
                            message.author.id,
                        )

                        await conn.execute(
                            "UPDATE example_user_stats SET message_count = message_count + 1 WHERE user_id = $1",
                            message.author.id,
                        )

                        # This could fail if the user doesn't exist in the stats table
                        rows_updated = await conn.fetchval(
                            "SELECT COUNT(*) FROM example_user_stats WHERE user_id = $1",
                            message.author.id,
                        )

                        if rows_updated == 0:
                            # Insert a new record if the user doesn't exist
                            await conn.execute(
                                "INSERT INTO example_user_stats(user_id, message_count) VALUES($1, 1)",
                                message.author.id,
                            )
            except Exception as e:
                # Log the error but don't disrupt the bot's operation
                self.logger.error(f"Error processing message in example_listener: {e}")


async def setup(bot) -> None:
    """Add the cog to the bot."""
    await bot.add_cog(ExampleCog(bot))
