"""Quote management cog for the Twi Bot Shard.

This module provides commands for managing and retrieving quotes from the database.
"""

import logging
import re
from datetime import UTC

import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ExternalServiceError,
    PermissionError,
    ValidationError,
)


class Quotes(commands.Cog, name="Quotes"):
    """Quote management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.quote_cache = None

    async def cog_load(self) -> None:
        """Load quote cache on cog load."""
        try:
            self.quote_cache = await self.bot.db.fetch(
                "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
            )
            logging.info(
                f"QUOTES: Successfully loaded quote cache with {len(self.quote_cache)} quotes"
            )
        except Exception as e:
            logging.error(f"QUOTES: Failed to load quote cache: {e}")
            self.quote_cache = []

    quote = app_commands.Group(name="quote", description="Quote commands")

    @quote.command(name="add", description="Adds a quote to the list of quotes")
    @handle_interaction_errors
    async def quote_add(self, interaction: discord.Interaction, quote: str) -> None:
        """Add a new quote to the database."""
        try:
            if not quote or len(quote.strip()) == 0:
                raise ValidationError(message="Quote cannot be empty")

            quote = quote.strip()

            if len(quote) > 2000:
                raise ValidationError(
                    message="Quote too long (maximum 2000 characters)"
                )

            if len(quote) < 3:
                raise ValidationError(message="Quote too short (minimum 3 characters)")

            if quote.count("\n") > 10:
                raise ValidationError(
                    message="Too many line breaks in quote (maximum 10)"
                )

            logging.info(
                f"QUOTES ADD: Quote add request by user {interaction.user.id} "
                f"({interaction.user.display_name}): '{quote[:100]}{'...' if len(quote) > 100 else ''}'"
            )

            try:
                await self.bot.db.execute(
                    "INSERT INTO quotes(quote, author, author_id, time, tokens) VALUES ($1,$2,$3,now(),to_tsvector($4))",
                    quote,
                    interaction.user.display_name,
                    interaction.user.id,
                    quote,
                )
            except Exception as e:
                logging.error(
                    f"QUOTES ADD ERROR: Database insert failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to add quote to database: {e}"
                ) from e

            try:
                row_number = await self.bot.db.fetchrow("SELECT COUNT(*) FROM quotes")
                quote_index = row_number["count"] if row_number else "Unknown"
            except Exception as e:
                logging.warning(f"QUOTES ADD WARNING: Could not get quote count: {e}")
                quote_index = "Unknown"

            try:
                self.quote_cache = await self.bot.db.fetch(
                    "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
                )
            except Exception as e:
                logging.warning(
                    f"QUOTES ADD WARNING: Failed to update quote cache: {e}"
                )

            embed = discord.Embed(
                title="Quote Added Successfully",
                description=f"**Quote #{quote_index}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            display_quote = quote if len(quote) <= 200 else quote[:200] + "..."
            embed.add_field(
                name="Quote Content", value=f"```{display_quote}```", inline=False
            )

            embed.add_field(
                name="Added By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="Quote Stats",
                value=f"**Index:** {quote_index}\n**Length:** {len(quote)} characters",
                inline=True,
            )

            embed.set_footer(text="Use /quote get to retrieve quotes")

            logging.info(
                f"QUOTES ADD: Successfully added quote #{quote_index} by user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"QUOTES ADD ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while adding quote: {e}"
            ) from e

    @quote.command(name="find", description="Searches for a quote")
    @handle_interaction_errors
    async def quote_find(self, interaction: discord.Interaction, search: str) -> None:
        """Search for quotes containing specific words."""
        try:
            if not search or len(search.strip()) == 0:
                raise ValidationError(message="Search terms cannot be empty")

            search = search.strip()

            if len(search) > 100:
                raise ValidationError(
                    message="Search terms too long (maximum 100 characters)"
                )

            if len(search) < 2:
                raise ValidationError(
                    message="Search terms too short (minimum 2 characters)"
                )

            logging.info(
                f"QUOTES FIND: Quote search request by user {interaction.user.id} for terms: '{search}'"
            )

            try:
                formatted_search = search.replace(" ", " & ")
                formatted_search = re.sub(r"[^\w\s&|!()]", "", formatted_search)
            except Exception as e:
                logging.error(f"QUOTES FIND ERROR: Search formatting failed: {e}")
                raise ValidationError(message="Invalid search terms format") from e

            try:
                results = await self.bot.db.fetch(
                    "SELECT quote, x.row_number FROM (SELECT tokens, quote, ROW_NUMBER() OVER () as row_number FROM quotes) x WHERE x.tokens @@ to_tsquery($1);",
                    formatted_search,
                )
            except Exception as e:
                logging.error(
                    f"QUOTES FIND ERROR: Database search failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to search quotes database: {e}"
                ) from e

            if not results or len(results) == 0:
                embed = discord.Embed(
                    title="Quote Search Results",
                    description=f"**Search Terms:** `{search}`",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="No Results Found",
                    value="No quotes found matching your search terms.\n\n**Suggestions:**\n- Try different keywords\n- Use fewer search terms\n- Check spelling",
                    inline=False,
                )
                embed.set_footer(text="Use /quote add to add new quotes")

                logging.info(
                    f"QUOTES FIND: No results found for search '{search}' by user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            first_result = results[0]
            result_count = len(results)

            embed = discord.Embed(
                title="Quote Search Results",
                description=f"**Search Terms:** `{search}`\n**Found:** {result_count} quote{'s' if result_count != 1 else ''}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            quote_text = first_result["quote"]
            display_quote = (
                quote_text if len(quote_text) <= 300 else quote_text[:300] + "..."
            )

            embed.add_field(
                name=f"Quote #{first_result['row_number']}",
                value=f"```{display_quote}```",
                inline=False,
            )

            if result_count > 1:
                additional_indices = [
                    str(result["row_number"]) for result in results[1:]
                ]

                if len(additional_indices) > 20:
                    displayed_indices = additional_indices[:20]
                    indices_text = (
                        ", ".join(displayed_indices)
                        + f" ... and {len(additional_indices) - 20} more"
                    )
                else:
                    indices_text = ", ".join(additional_indices)

                embed.add_field(
                    name="Additional Results",
                    value=f"**Quote indices:** {indices_text}\n\n*Use `/quote get <index>` to view specific quotes*",
                    inline=False,
                )

            embed.set_footer(text=f"Showing result 1 of {result_count}")

            logging.info(
                f"QUOTES FIND: Found {result_count} results for search '{search}' by user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"QUOTES FIND ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while searching quotes: {e}"
            ) from e

    @quote.command(name="delete", description="Delete a quote")
    @handle_interaction_errors
    async def quote_delete(self, interaction: discord.Interaction, delete: int) -> None:
        """Delete a quote from the database by its index."""
        try:
            if delete is None or delete < 1:
                raise ValidationError(message="Quote index must be a positive number")

            if delete > 10000:
                raise ValidationError(message="Quote index too high (maximum 10000)")

            logging.info(
                f"QUOTES DELETE: Quote delete request by user {interaction.user.id} for index {delete}"
            )

            try:
                u_quote = await self.bot.db.fetchrow(
                    "SELECT quote, row_number, author_id FROM (SELECT quote, author_id, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                    delete,
                )
            except Exception as e:
                logging.error(
                    f"QUOTES DELETE ERROR: Database lookup failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(message=f"Failed to lookup quote: {e}") from e

            if not u_quote:
                embed = discord.Embed(
                    title="Quote Not Found",
                    description=f"**Index:** {delete}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="No Quote Found",
                    value=f"No quote exists at index {delete}.\n\n**Suggestions:**\n- Use `/quote get` to see available quotes\n- Check the quote index number",
                    inline=False,
                )
                embed.set_footer(text="Use /quote find to search for quotes")

                logging.info(
                    f"QUOTES DELETE: Quote not found at index {delete} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            quote_author_id = u_quote.get("author_id")
            is_quote_author = quote_author_id == interaction.user.id
            is_admin = False

            if interaction.guild:
                try:
                    is_admin = (
                        interaction.user.guild_permissions.administrator
                        or interaction.user.guild_permissions.manage_messages
                    )
                except Exception as e:
                    logging.warning(
                        f"QUOTES DELETE WARNING: Could not check permissions for user {interaction.user.id}: {e}"
                    )

            if not is_quote_author and not is_admin:
                logging.warning(
                    f"QUOTES DELETE SECURITY: Permission denied for user {interaction.user.id} "
                    f"to delete quote {delete} (author: {quote_author_id})"
                )
                raise PermissionError(
                    message="You don't have permission to delete this quote"
                )

            quote_text = u_quote["quote"]
            quote_row = u_quote["row_number"]

            try:
                await self.bot.db.execute(
                    "DELETE FROM quotes WHERE serial_id in (SELECT serial_id FROM quotes ORDER BY time LIMIT 1 OFFSET $1)",
                    delete - 1,
                )
                logging.info(
                    f"QUOTES DELETE: Successfully deleted quote #{delete} by user {interaction.user.id}"
                )
            except Exception as e:
                logging.error(
                    f"QUOTES DELETE ERROR: Database deletion failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to delete quote from database: {e}"
                ) from e

            try:
                self.quote_cache = await self.bot.db.fetch(
                    "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
                )
            except Exception as e:
                logging.warning(
                    f"QUOTES DELETE WARNING: Failed to update quote cache: {e}"
                )

            embed = discord.Embed(
                title="Quote Deleted Successfully",
                description=f"**Quote #{quote_row}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            display_quote = (
                quote_text if len(quote_text) <= 200 else quote_text[:200] + "..."
            )
            embed.add_field(
                name="Deleted Quote", value=f"```{display_quote}```", inline=False
            )

            embed.add_field(
                name="Deleted By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="Action Info",
                value=f"**Original Index:** {quote_row}\n**Permission:** {'Author' if is_quote_author else 'Admin'}",
                inline=True,
            )

            embed.set_footer(text="Quote indices may have shifted after deletion")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"QUOTES DELETE ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while deleting quote: {e}"
            ) from e

    @quote_delete.autocomplete("delete")
    async def quote_delete_autocomplete(
        self, interaction: discord.Interaction, current: int
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote delete command."""
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]

    @quote.command(
        name="get",
        description="Posts a quote a random quote or a quote with the given index",
    )
    @handle_interaction_errors
    async def quote_get(
        self, interaction: discord.Interaction, index: int = None
    ) -> None:
        """Retrieve and display a quote from the database."""
        try:
            if index is not None:
                if index < 1:
                    raise ValidationError(
                        message="Quote index must be a positive number"
                    )

                if index > 10000:
                    raise ValidationError(
                        message="Quote index too high (maximum 10000)"
                    )

            is_random = index is None
            logging.info(
                f"QUOTES GET: Quote get request by user {interaction.user.id} for "
                f"{'random quote' if is_random else f'index {index}'}"
            )

            try:
                if is_random:
                    u_quote = await self.bot.db.fetchrow(
                        "SELECT quote, row_number, author, author_id, time FROM (SELECT quote, author, author_id, time, ROW_NUMBER () OVER () as row_number FROM quotes) x ORDER BY random() LIMIT 1"
                    )
                else:
                    u_quote = await self.bot.db.fetchrow(
                        "SELECT quote, row_number, author, author_id, time FROM (SELECT quote, author, author_id, time, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                        index,
                    )
            except Exception as e:
                logging.error(
                    f"QUOTES GET ERROR: Database query failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to retrieve quote from database: {e}"
                ) from e

            if not u_quote:
                if is_random:
                    embed = discord.Embed(
                        title="No Quotes Available",
                        description="The quote database appears to be empty.",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(
                        name="Suggestion",
                        value="Be the first to add a quote using `/quote add`!",
                        inline=False,
                    )
                    embed.set_footer(text="Help build the quote collection")
                else:
                    embed = discord.Embed(
                        title="Quote Not Found",
                        description=f"**Index:** {index}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(
                        name="No Quote Found",
                        value=f"No quote exists at index {index}.\n\n**Suggestions:**\n- Try a different index number\n- Use `/quote get` without an index for a random quote\n- Use `/quote find` to search for quotes",
                        inline=False,
                    )
                    embed.set_footer(text="Quote indices start from 1")

                await interaction.response.send_message(embed=embed)
                return

            quote_text = u_quote["quote"]
            quote_number = u_quote["row_number"]
            quote_author = u_quote.get("author", "Unknown")
            quote_author_id = u_quote.get("author_id")
            quote_time = u_quote.get("time")

            embed = discord.Embed(
                title=f"Quote #{quote_number}" + (" (Random)" if is_random else ""),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            display_quote = (
                quote_text if len(quote_text) <= 1000 else quote_text[:1000] + "..."
            )
            embed.add_field(name="Quote", value=f"```{display_quote}```", inline=False)

            if quote_author and quote_author != "Unknown":
                author_info = f"**Added by:** {quote_author}"
                if quote_author_id:
                    author_info += f"\n**ID:** {quote_author_id}"
                if quote_time:
                    try:
                        formatted_time = quote_time.strftime("%Y-%m-%d %H:%M:%S")
                        author_info += f"\n**Added:** {formatted_time}"
                    except Exception:
                        pass

                embed.add_field(name="Author Info", value=author_info, inline=True)

            stats_info = (
                f"**Index:** {quote_number}\n**Length:** {len(quote_text)} characters"
            )
            if is_random:
                stats_info += "\n**Type:** Random selection"

            embed.add_field(name="Quote Stats", value=stats_info, inline=True)

            if is_random:
                embed.set_footer(text="Use /quote get <index> for a specific quote")
            else:
                embed.set_footer(text="Use /quote get for a random quote")

            logging.info(
                f"QUOTES GET: Successfully retrieved quote #{quote_number} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"QUOTES GET ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while retrieving quote: {e}"
            ) from e

    @quote_get.autocomplete("index")
    async def quote_get_autocomplete(
        self,
        interaction: discord.Interaction,
        current: int,
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote get command."""
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]

    @quote.command(name="who", description="Posts who added a quote")
    @handle_interaction_errors
    async def quote_who(self, interaction: discord.Interaction, index: int) -> None:
        """Display information about who added a specific quote."""
        try:
            if index is None or index < 1:
                raise ValidationError(message="Quote index must be a positive number")

            if index > 10000:
                raise ValidationError(message="Quote index too high (maximum 10000)")

            logging.info(
                f"QUOTES WHO: Quote who request by user {interaction.user.id} for index {index}"
            )

            try:
                u_quote = await self.bot.db.fetchrow(
                    "SELECT author, author_id, time, row_number, quote FROM (SELECT author, author_id, time, quote, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                    index,
                )
            except Exception as e:
                logging.error(
                    f"QUOTES WHO ERROR: Database query failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to retrieve quote information: {e}"
                ) from e

            if not u_quote:
                embed = discord.Embed(
                    title="Quote Not Found",
                    description=f"**Index:** {index}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="No Quote Found",
                    value=f"No quote exists at index {index}.\n\n**Suggestions:**\n- Check the quote index number\n- Use `/quote get` to see available quotes\n- Use `/quote find` to search for quotes",
                    inline=False,
                )
                embed.set_footer(text="Quote indices start from 1")

                logging.info(
                    f"QUOTES WHO: Quote not found at index {index} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            quote_author = u_quote.get("author", "Unknown")
            quote_author_id = u_quote.get("author_id")
            quote_time = u_quote.get("time")
            quote_number = u_quote["row_number"]
            quote_text = u_quote.get("quote", "")

            embed = discord.Embed(
                title=f"Quote #{quote_number} - Author Information",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            if quote_text:
                preview_text = (
                    quote_text if len(quote_text) <= 150 else quote_text[:150] + "..."
                )
                embed.add_field(
                    name="Quote Preview", value=f"```{preview_text}```", inline=False
                )

            author_info = ""
            if quote_author and quote_author != "Unknown":
                author_info += f"**Username:** {quote_author}\n"
            else:
                author_info += "**Username:** *Unknown*\n"

            if quote_author_id:
                author_info += f"**User ID:** {quote_author_id}\n"
                try:
                    if interaction.guild:
                        member = interaction.guild.get_member(quote_author_id)
                        if member:
                            author_info += f"**Current Name:** {member.display_name}\n"
                            author_info += "**Status:** Active member\n"
                        else:
                            author_info += "**Status:** No longer in server\n"
                except Exception:
                    pass
            else:
                author_info += "**User ID:** *Unknown*\n"

            embed.add_field(
                name="Author Details", value=author_info.strip(), inline=True
            )

            time_info = ""
            if quote_time:
                try:
                    from datetime import datetime

                    formatted_time = quote_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                    time_info += f"**Added:** {formatted_time}\n"

                    now = datetime.now(UTC)
                    if quote_time.tzinfo is None:
                        quote_time = quote_time.replace(tzinfo=UTC)

                    time_diff = now - quote_time
                    days = time_diff.days

                    if days == 0:
                        time_info += "**Age:** Today\n"
                    elif days == 1:
                        time_info += "**Age:** 1 day ago\n"
                    elif days < 30:
                        time_info += f"**Age:** {days} days ago\n"
                    elif days < 365:
                        months = days // 30
                        time_info += (
                            f"**Age:** {months} month{'s' if months != 1 else ''} ago\n"
                        )
                    else:
                        years = days // 365
                        time_info += (
                            f"**Age:** {years} year{'s' if years != 1 else ''} ago\n"
                        )

                except Exception as e:
                    logging.warning(
                        f"QUOTES WHO WARNING: Could not format time for quote {index}: {e}"
                    )
                    time_info += f"**Added:** {quote_time}\n"
            else:
                time_info += "**Added:** *Unknown*\n"

            embed.add_field(name="Timestamp Info", value=time_info.strip(), inline=True)

            stats_info = f"**Quote Index:** {quote_number}\n"
            if quote_text:
                stats_info += f"**Length:** {len(quote_text)} characters\n"

            embed.add_field(name="Quote Stats", value=stats_info.strip(), inline=True)

            embed.set_footer(text="Use /quote get to view the full quote")

            logging.info(
                f"QUOTES WHO: Successfully retrieved author info for quote #{quote_number} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"QUOTES WHO ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while retrieving quote info: {e}"
            ) from e

    @quote_who.autocomplete("index")
    async def quote_who_autocomplete(
        self,
        interaction: discord.Interaction,
        current: int,
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote who command."""
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]


async def setup(bot: commands.Bot) -> None:
    """Set up the Quotes cog."""
    await bot.add_cog(Quotes(bot))
