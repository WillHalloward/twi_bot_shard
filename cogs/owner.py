import logging
import subprocess
from typing import List

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional

# Import FAISS schema query functions
from query_faiss_schema import query_faiss, build_prompt, generate_sql, extract_sql_from_response, INDEX_FILE, LOOKUP_FILE, TOP_K

cogs = [
    "cogs.summarization",
    "cogs.gallery",
    "cogs.links_tags",
    "cogs.patreon_poll",
    "cogs.twi",
    "cogs.owner",
    "cogs.other",
    "cogs.mods",
    "cogs.stats",
    "cogs.creator_links",
    "cogs.report",
    "cogs.innktober",
]


class OwnerCog(commands.Cog, name="Owner"):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="load")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def load_cog(self, interaction: discord.Interaction, *, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.load_extension(cog)
        except Exception as e:
            await interaction.followup.send(f"**`ERROR:`** {type(e).__name__} - {e}")
            logging.error(f"{type(e).__name__} - {e}")
        else:
            await interaction.followup.send("**`SUCCESS`**")
            await asyncio.sleep(5)
            await interaction.delete_original_response()

    @load_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="unload")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def unload_cog(self, interaction: discord.Interaction, *, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.unload_extension(cog)
        except Exception as e:
            await interaction.followup.send(f"**`ERROR:`** {type(e).__name__} - {e}")
            logging.error(f"{type(e).__name__} - {e}")
        else:
            await interaction.followup.send("**`SUCCESS`**")
            await asyncio.sleep(5)
            await interaction.delete_original_response()

    @unload_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="reload")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.unload_extension(cog)
            await self.bot.load_extension(cog)
        except Exception as e:
            await interaction.followup.send(f"**`ERROR:`** {type(e).__name__} - {e}")
            logging.exception(f"{type(e).__name__} - {e}")
        else:
            await interaction.followup.send("**`SUCCESS`**")
            await asyncio.sleep(5)
            await interaction.delete_original_response()

    @reload_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="cmd")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def cmd(self, interaction: discord.Interaction, args: str):
        args_array = args.split(" ")
        try:
            await interaction.response.send_message(
                subprocess.check_output(args_array, stderr=subprocess.STDOUT).decode(
                    "utf-8"
                )
            )
        except subprocess.CalledProcessError as e:
            await interaction.response.send_message(
                f'Error: {e.output.decode("utf-8")}'
            )

    @app_commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, interaction: discord.Interaction, all_guilds: bool):
        # Defer the response since loading extensions might take time
        await interaction.response.defer()

        # Load all non-loaded extensions before syncing
        loaded_count = 0
        failed_extensions = []

        for extension in self.bot.initial_extensions:
            if not self.bot.loaded_extensions.get(extension, False):
                success = await self.bot.load_extension_if_needed(extension)
                if success:
                    loaded_count += 1
                else:
                    failed_extensions.append(extension)

        # Prepare status message about extension loading
        status_parts = []
        if loaded_count > 0:
            status_parts.append(f"Loaded {loaded_count} additional extension(s)")
        if failed_extensions:
            status_parts.append(f"Failed to load: {', '.join(failed_extensions)}")

        # Perform the sync operation
        if all_guilds:
            try:
                await self.bot.tree.sync()
                sync_message = "Synced Globally"
            except Exception as e:
                logging.error(e)
                sync_message = f"Global sync failed: {str(e)}"
        else:
            try:
                await self.bot.tree.sync(guild=interaction.guild)
                sync_message = "Synced Locally"
            except Exception as e:
                logging.error(e)
                sync_message = f"Local sync failed: {str(e)}"

        # Combine sync result with extension loading status
        final_message = sync_message
        if status_parts:
            final_message += f"\n{' | '.join(status_parts)}"

        await interaction.followup.send(final_message)

    @app_commands.command(name="exit")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def exit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Exiting...")
        await self.bot.close()

    @app_commands.command(name="resources")
    @commands.is_owner()
    async def resources(
        self,
        interaction: discord.Interaction,
        detail_level: Literal["basic", "detailed", "system"] = "basic",
    ):
        """
        Display resource usage statistics.

        Args:
            interaction: The interaction that triggered the command
            detail_level: The level of detail to display (basic, detailed, or system)
        """
        await interaction.response.defer()

        # Get resource statistics
        current_stats = self.bot.resource_monitor.get_resource_stats()
        summary_stats = self.bot.resource_monitor.get_summary_stats()

        # Create embed with basic information
        embed = discord.Embed(
            title="Resource Usage Statistics",
            description=f"Statistics collected over the last {summary_stats.get('history_duration_minutes', 0):.1f} minutes",
            color=discord.Color.blue(),
        )

        # Add current resource usage
        embed.add_field(
            name="Current Usage",
            value=(
                f"Memory: {current_stats['memory_percent']:.1f}%\n"
                f"CPU: {current_stats['cpu_percent']:.1f}%\n"
                f"Threads: {current_stats['thread_count']}\n"
                f"Uptime: {current_stats['uptime'] / 3600:.1f} hours"
            ),
            inline=True,
        )

        # Add summary statistics
        if summary_stats:
            embed.add_field(
                name="Summary Statistics",
                value=(
                    f"Avg Memory: {summary_stats.get('avg_memory_percent', 0):.1f}%\n"
                    f"Max Memory: {summary_stats.get('max_memory_percent', 0):.1f}%\n"
                    f"Avg CPU: {summary_stats.get('avg_cpu_percent', 0):.1f}%\n"
                    f"Max CPU: {summary_stats.get('max_cpu_percent', 0):.1f}%"
                ),
                inline=True,
            )

        # Add HTTP client statistics
        http_stats = self.bot.http_client.get_stats()
        embed.add_field(
            name="HTTP Client Statistics",
            value=(
                f"Requests: {http_stats['requests']}\n"
                f"Errors: {http_stats['errors']}\n"
                f"Timeouts: {http_stats['timeouts']}"
            ),
            inline=True,
        )

        # Add database cache statistics
        db_cache_stats = await self.bot.db.get_cache_stats()
        embed.add_field(
            name="Database Cache Statistics",
            value=(
                f"Hit Rate: {db_cache_stats['hit_rate']:.1f}%\n"
                f"Hits: {db_cache_stats['hits']}\n"
                f"Misses: {db_cache_stats['misses']}\n"
                f"Evictions: {db_cache_stats['evictions']}"
            ),
            inline=True,
        )

        # Add detailed information if requested
        if detail_level == "detailed" or detail_level == "system":
            embed.add_field(
                name="Detailed Memory Usage",
                value=(
                    f"RSS: {current_stats['memory_rss'] / (1024 * 1024):.1f} MB\n"
                    f"VMS: {current_stats['memory_vms'] / (1024 * 1024):.1f} MB\n"
                    f"Open Files: {current_stats['open_files_count']}\n"
                    f"Connections: {current_stats['connection_count']}"
                ),
                inline=True,
            )

        # Add system information if requested
        if detail_level == "system":
            system_info = self.bot.resource_monitor.get_system_info()
            embed.add_field(
                name="System Information",
                value=(
                    f"Platform: {system_info['platform']}\n"
                    f"Python: {system_info['python_version']}\n"
                    f"CPU Count: {system_info['cpu_count']}\n"
                    f"Total Memory: {system_info['total_memory'] / (1024 * 1024 * 1024):.1f} GB\n"
                    f"System Memory Usage: {current_stats['system_memory_percent']:.1f}%\n"
                    f"System CPU Usage: {current_stats['system_cpu_percent']:.1f}%"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="sql")
    @commands.is_owner()
    async def sql_query(self, interaction: discord.Interaction, query: str):
        """
        Execute a SQL query and return the results as a readable table.

        Args:
            interaction: The interaction that triggered the command
            query: The SQL query to execute
        """
        await interaction.response.defer()

        try:
            # Execute the query
            results = await self.bot.db.fetch(query)

            if not results:
                await interaction.followup.send("Query executed successfully but returned no results.")
                return

            # Format results as a table
            if len(results) == 0:
                await interaction.followup.send("Query executed successfully but returned no results.")
                return

            # Get column names from the first row
            columns = list(results[0].keys())

            # Calculate column widths
            col_widths = {}
            for col in columns:
                col_widths[col] = max(len(str(col)), max(len(str(row[col])) for row in results))
                # Limit column width to prevent overly wide tables
                col_widths[col] = min(col_widths[col], 30)

            # Build the table
            table_lines = []

            # Header row
            header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
            table_lines.append(header)

            # Separator row
            separator = "-+-".join("-" * col_widths[col] for col in columns)
            table_lines.append(separator)

            # Data rows (limit to first 20 rows to prevent message being too long)
            for i, row in enumerate(results[:20]):
                row_str = " | ".join(str(row[col])[:col_widths[col]].ljust(col_widths[col]) for col in columns)
                table_lines.append(row_str)

            table_text = "\n".join(table_lines)

            # Check if we need to truncate due to Discord's message limit
            if len(table_text) > 1900:  # Leave room for code block formatting
                table_text = table_text[:1900] + "\n... (truncated)"

            # Add information about total rows
            result_info = f"Query returned {len(results)} row(s)"
            if len(results) > 20:
                result_info += f" (showing first 20)"

            response = f"{result_info}\n```\n{table_text}\n```"
            await interaction.followup.send(response)

        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            logging.error(f"SQL query error: {error_msg}")
            await interaction.followup.send(f"```\n{error_msg}\n```")

    @app_commands.command(name="ask_db")
    @commands.is_owner()
    async def ask_database(self, interaction: discord.Interaction, question: str):
        """
        Ask a natural language question about the database and get SQL results.

        Args:
            interaction: The interaction that triggered the command
            question: The natural language question to ask about the database
        """
        await interaction.response.defer()

        try:
            # Step 1: Search for relevant schema using FAISS
            await interaction.followup.send("🔗 Searching schema for relevant tables...")
            relevant_schema = query_faiss(question, INDEX_FILE, LOOKUP_FILE, TOP_K)

            # Step 2: Build prompt with relevant schema
            await interaction.edit_original_response(content="🧠 Generating SQL query...")
            prompt = build_prompt(question, relevant_schema)

            # Step 3: Generate SQL using OpenAI
            await interaction.edit_original_response(content="🤖 Generating SQL with AI...")
            raw_sql_response = generate_sql(prompt)

            # Step 4: Extract clean SQL from response
            sql_query = extract_sql_from_response(raw_sql_response)

            # Step 4.5: Check for soft error (AI couldn't generate a query)
            if sql_query == "COGNITA_NO_QUERY_POSSIBLE":
                response = f"**Question:** {question}\n\n**Status:** ❌ Unable to generate SQL query\n\n**Explanation:** The AI couldn't determine how to create a database query for your question. This might happen if:\n• The question is too vague or ambiguous\n• The requested data isn't available in the database schema\n• The question requires complex logic that can't be expressed in a single SQL query\n\n**Suggestion:** Try rephrasing your question to be more specific about what Discord data you're looking for (e.g., messages, users, servers, reactions, etc.)."
                await interaction.edit_original_response(content=response)
                return

            # Step 5: Execute the generated SQL
            await interaction.edit_original_response(content="⚡ Executing generated SQL...")
            results = await self.bot.db.fetch(sql_query)

            if not results:
                response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Result:** Query executed successfully but returned no results."
                await interaction.edit_original_response(content=response)
                return

            # Format results as a table (similar to sql_query command)
            columns = list(results[0].keys())

            # Calculate column widths
            col_widths = {}
            for col in columns:
                col_widths[col] = max(len(str(col)), max(len(str(row[col])) for row in results))
                # Limit column width to prevent overly wide tables
                col_widths[col] = min(col_widths[col], 30)

            # Build the table
            table_lines = []

            # Header row
            header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
            table_lines.append(header)

            # Separator row
            separator = "-+-".join("-" * col_widths[col] for col in columns)
            table_lines.append(separator)

            # Data rows (limit to first 20 rows to prevent message being too long)
            for i, row in enumerate(results[:20]):
                row_str = " | ".join(str(row[col])[:col_widths[col]].ljust(col_widths[col]) for col in columns)
                table_lines.append(row_str)

            table_text = "\n".join(table_lines)

            # Check if we need to truncate due to Discord's message limit
            if len(table_text) > 1200:  # Leave more room for question and SQL
                table_text = table_text[:1200] + "\n... (truncated)"

            # Add information about total rows
            result_info = f"Query returned {len(results)} row(s)"
            if len(results) > 20:
                result_info += f" (showing first 20)"

            # Format final response
            response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Results:** {result_info}\n```\n{table_text}\n```"

            # Check total response length and truncate if needed
            if len(response) > 1900:
                # Truncate the table further if needed
                truncated_table = table_text[:800] + "\n... (truncated due to length)"
                response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Results:** {result_info}\n```\n{truncated_table}\n```"

            await interaction.edit_original_response(content=response)

        except Exception as e:
            error_msg = f"Error processing question: {str(e)}"
            logging.error(f"Ask database error: {error_msg}")
            response = f"**Question:** {question}\n\n**Error:** ```\n{error_msg}\n```"
            await interaction.edit_original_response(content=response)


async def setup(bot):
    await bot.add_cog(OwnerCog(bot))
