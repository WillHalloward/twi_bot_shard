"""
Content functionality for The Wandering Inn cog.

This module handles invisible text retrieval and colored text display
for The Wandering Inn web serial.
"""

import datetime
import logging
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.twi_utils import log_command_usage, log_command_error, truncate_text
from utils.error_handling import handle_interaction_errors
from utils.exceptions import ValidationError, DatabaseError


class ContentMixin:
    """Mixin class providing content-related commands for The Wandering Inn cog."""

    def __init__(self):
        """Initialize the content mixin."""
        self.invis_text_cache = None

    async def load_invis_text_cache(self):
        """Load invisible text cache for autocomplete functionality."""
        try:
            self.invis_text_cache = await self.bot.db.fetch(
                "SELECT DISTINCT title FROM invisible_text_twi"
            )
        except Exception as e:
            logging.error(f"TWI CONTENT: Failed to load invisible text cache: {e}")
            self.invis_text_cache = []

    @app_commands.command(
        name="invistext", description="Gives a list of all the invisible text in TWI."
    )
    @handle_interaction_errors
    async def invis_text(self, interaction: discord.Interaction, chapter: str = None):
        """
        Retrieve invisible text from The Wandering Inn chapters.

        This command either lists all chapters containing invisible text
        or provides the specific invisible text from a requested chapter.
        Invisible text is special content that's hidden in the web serial
        by making the text color match the background.

        Args:
            interaction: The interaction that triggered the command
            chapter: Optional chapter name to get specific invisible text

        Raises:
            ValidationError: If chapter parameter is invalid
            DatabaseError: If database operations fail
        """
        try:
            log_command_usage(
                "INVISTEXT",
                interaction.user.id,
                interaction.user.display_name,
                f"requesting invisible text{f' for chapter: {truncate_text(chapter, 50)}' if chapter else ' list'}",
            )

            if chapter is None:
                await self._handle_invis_text_list(interaction)
            else:
                await self._handle_specific_invis_text(interaction, chapter)

        except (ValidationError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Invisible Text Command Failed**\nUnexpected error while retrieving invisible text: {str(e)}"
            log_command_error("INVISTEXT", interaction.user.id, e)
            raise DatabaseError(message=error_msg) from e

    async def _handle_invis_text_list(self, interaction: discord.Interaction):
        """Handle listing all chapters with invisible text."""
        try:
            invis_text_chapters = await self.bot.db.fetch(
                "SELECT title, COUNT(*) FROM invisible_text_twi GROUP BY title, date ORDER BY date"
            )
        except Exception as e:
            log_command_error(
                "INVISTEXT", interaction.user.id, e, "Database query failed"
            )
            raise DatabaseError(
                message="❌ **Database Error**\nFailed to retrieve invisible text chapters from database"
            ) from e

        if not invis_text_chapters:
            embed = discord.Embed(
                title="👻 Invisible Text",
                description="No chapters with invisible text found in the database.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(),
            )

            embed.add_field(
                name="ℹ️ Information",
                value="Invisible text is special content hidden in chapters by making the text color match the background.",
                inline=False,
            )

            await interaction.response.send_message(embed=embed)
            logging.info(
                f"TWI INVISTEXT: No chapters found for user {interaction.user.id}"
            )
            return

        # Create chapters list embed
        embed = discord.Embed(
            title="👻 Chapters with Invisible Text",
            description=f"Found **{len(invis_text_chapters)}** chapter{'s' if len(invis_text_chapters) != 1 else ''} containing invisible text",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(),
        )

        # Add chapters (limit to prevent embed size issues)
        max_chapters = 20
        chapters_to_show = invis_text_chapters[:max_chapters]

        for chapter_data in chapters_to_show:
            try:
                title = chapter_data.get("title", "Unknown Chapter")
                count = chapter_data.get("count", 0)

                # Truncate long titles
                display_title = truncate_text(title, 60)

                embed.add_field(
                    name=f"📖 {display_title}",
                    value=f"**{count}** invisible text{'s' if count != 1 else ''}",
                    inline=False,
                )
            except Exception as e:
                logging.warning(
                    f"TWI INVISTEXT WARNING: Failed to process chapter for user {interaction.user.id}: {e}"
                )
                continue

        # Add note if there are more chapters
        if len(invis_text_chapters) > max_chapters:
            embed.add_field(
                name="ℹ️ Note",
                value=f"Showing first {max_chapters} of {len(invis_text_chapters)} chapters. Use the chapter parameter to search for specific chapters.",
                inline=False,
            )

        embed.add_field(
            name="💡 Tip",
            value="Use `/invistext chapter:<chapter_name>` to see invisible text from a specific chapter.",
            inline=False,
        )

        embed.set_footer(text="Invisible text data from The Wandering Inn")

        await interaction.response.send_message(embed=embed)
        logging.info(
            f"TWI INVISTEXT: Successfully listed {len(chapters_to_show)} chapters for user {interaction.user.id}"
        )

    async def _handle_specific_invis_text(
        self, interaction: discord.Interaction, chapter: str
    ):
        """Handle retrieving invisible text for a specific chapter."""
        # Input validation
        if not chapter or len(chapter.strip()) < 2:
            raise ValidationError(
                message="❌ **Invalid Chapter Name**\nChapter name must be at least 2 characters long."
            )

        chapter = chapter.strip()
        if len(chapter) > 200:
            raise ValidationError(
                message="❌ **Chapter Name Too Long**\nChapter name must be 200 characters or less."
            )

        try:
            invis_text_data = await self.bot.db.fetch(
                "SELECT text, date FROM invisible_text_twi WHERE title ILIKE $1 ORDER BY date",
                f"%{chapter}%",
            )
        except Exception as e:
            log_command_error(
                "INVISTEXT",
                interaction.user.id,
                e,
                f"Database query failed for chapter: {chapter}",
            )
            raise DatabaseError(
                message="❌ **Database Error**\nFailed to retrieve invisible text from database"
            ) from e

        if not invis_text_data:
            embed = discord.Embed(
                title="👻 Invisible Text",
                description=f"No invisible text found for chapters matching **{chapter}**",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(),
            )

            embed.add_field(
                name="💡 Search Tips",
                value="• Try different keywords\n• Check spelling\n• Use partial chapter names\n• Try using `/invistext` without parameters to see all available chapters",
                inline=False,
            )

            embed.set_footer(text="Invisible text data from The Wandering Inn")

            await interaction.response.send_message(embed=embed)
            logging.info(
                f"TWI INVISTEXT: No invisible text found for user {interaction.user.id} chapter: '{chapter}'"
            )
            return

        # Create invisible text embed
        embed = discord.Embed(
            title="👻 Invisible Text",
            description=f"Found **{len(invis_text_data)}** invisible text{'s' if len(invis_text_data) != 1 else ''} for chapters matching **{chapter}**",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(),
        )

        # Add invisible text entries (limit to prevent embed size issues)
        max_entries = 10
        entries_to_show = invis_text_data[:max_entries]

        for i, entry in enumerate(entries_to_show, 1):
            try:
                text = entry.get("text", "No text available")
                date = entry.get("date", "Unknown date")

                # Truncate long text
                display_text = truncate_text(text, 800)

                embed.add_field(
                    name=f"📝 Entry {i}",
                    value=f"**Date:** {date}\n**Text:** {display_text}",
                    inline=False,
                )
            except Exception as e:
                logging.warning(
                    f"TWI INVISTEXT WARNING: Failed to process entry for user {interaction.user.id}: {e}"
                )
                continue

        # Add note if there are more entries
        if len(invis_text_data) > max_entries:
            embed.add_field(
                name="ℹ️ Note",
                value=f"Showing first {max_entries} of {len(invis_text_data)} entries. Try more specific search terms for better results.",
                inline=False,
            )

        embed.set_footer(text="Invisible text data from The Wandering Inn")

        await interaction.response.send_message(embed=embed)
        logging.info(
            f"TWI INVISTEXT: Successfully found {len(entries_to_show)} entries for user {interaction.user.id}"
        )

    @invis_text.autocomplete("chapter")
    async def invis_text_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete suggestions for chapter names.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current input from the user

        Returns:
            List of autocomplete choices
        """
        if not self.invis_text_cache:
            return []

        try:
            titles = [x["title"] for x in self.invis_text_cache]
            return [
                app_commands.Choice(name=title, value=title)
                for title in titles
                if current.lower() in title.lower() or current == ""
            ][
                :25
            ]  # Discord limits to 25 choices
        except Exception as e:
            logging.warning(
                f"TWI INVISTEXT AUTOCOMPLETE WARNING: Failed to generate autocomplete for user {interaction.user.id}: {e}"
            )
            return []

    @app_commands.command(
        name="coloredtext", description="List of all the different colored texts in twi"
    )
    @handle_interaction_errors
    async def colored_text(self, interaction: discord.Interaction):
        """
        Display a comprehensive list of colored text used in The Wandering Inn.

        This command creates an embed with information about all the different
        colored text used in the web serial, including their hex codes, visual
        representation, and the chapters where they first appeared. The colors
        are used for various special elements like skills, classes, and character
        speech.

        Args:
            interaction: The interaction that triggered the command
        """
        log_command_usage(
            "COLOREDTEXT", interaction.user.id, interaction.user.display_name
        )

        embed = discord.Embed(
            title="🎨 The Wandering Inn's Colored Text",
            description="A comprehensive guide to all the different colored text used in the web serial",
            color=discord.Color.from_rgb(255, 204, 0),  # Golden color
            timestamp=datetime.datetime.now(),
        )

        # Skills and Classes
        embed.add_field(
            name="🔴 Red Skills and Classes",
            value="#FF0000\n"
            f"{'<:FF0000:666429504834633789>' * 4}"
            "\n[3.17T](https://wanderinginn.com/2017/09/27/3-17-t/)",
            inline=True,
        )

        embed.add_field(
            name="⚔️ Ser Raim Skill",
            value="#EB0E0E\n"
            f"{'<:EB0E0E:666429505019183144>' * 4}"
            "\n[6.43E](https://wanderinginn.com/2019/09/10/6-43-e/)",
            inline=True,
        )

        embed.add_field(
            name="🔥 Ivolethe Summoning Fire",
            value="#E01D1D\n"
            f"{'<:E01D1D:666429504863993908>' * 4}"
            "\n[Interlude 4](https://wanderinginn.com/2017/12/30/interlude-4/)",
            inline=True,
        )

        embed.add_field(
            name="✨ Unique Skills",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[2.19](https://wanderinginn.com/2017/05/03/2-19/)",
            inline=True,
        )

        embed.add_field(
            name="🏛️ Erin's Landmark Skill",
            value="#FF9900\n"
            f"{'<:FF9900:666435308480364554>' * 4}"
            "\n[5.44](https://wanderinginn.com/2018/12/08/5-44/)",
            inline=True,
        )

        embed.add_field(
            name="⚡ Divine/Temporary Skills",
            value="#FFD700\n"
            f"{'<:FFD700:666429505031897107>' * 4}"
            "\n[4.23E](https://wanderinginn.com/2018/03/27/4-23-e/)",
            inline=True,
        )

        embed.add_field(
            name="🔄 Class Restoration/Conviction Skill",
            value="#99CCFF\n"
            f"{'<:99CCFF:667886770679054357>' * 4}"
            "\n[3.20T](https://wanderinginn.com/2017/10/03/3-20-t/)",
            inline=True,
        )

        # Fae Speech
        embed.add_field(
            name="❄️ Winter Fae Talking",
            value="#8AE8FF\n"
            f"{'<:8AE8FF:666429505015119922>' * 4}"
            "\n[2.06](https://wanderinginn.com/2017/03/28/2-06/)",
            inline=True,
        )

        embed.add_field(
            name="🌸 Spring Fae Talking",
            value="#96BE50\n"
            f"{'<:96BE50:666429505014857728>' * 4}"
            "\n[5.11E](https://wanderinginn.com/2018/08/14/5-11-e/)",
            inline=True,
        )

        # Antinium Queens
        embed.add_field(
            name="👑 Grand Queen Talking",
            value="#FFCC00\n"
            f"{'<:FFCC00:674267820678316052>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
            inline=True,
        )

        embed.add_field(
            name="🤫 Silent Queen Talking and Purple Skills",
            value="#CC99FF\n"
            f"{'<:CC99FF:674267820732841984>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
            inline=True,
        )

        embed.add_field(
            name="🛡️ Armored Queen Talking",
            value="#999999\n"
            f"{'<:999999:674267820820791306>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
            inline=True,
        )

        embed.add_field(
            name="🌀 Twisted Queen Talking",
            value="#993300\n"
            f"{'<:993300:674267820694962186>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
            inline=True,
        )

        embed.add_field(
            name="🦋 Flying Queen Talking",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
            inline=True,
        )

        # Special Skills
        embed.add_field(
            name="💖 Magnolia Charm Skill",
            value="#FDDBFF, #FFB8FD,\n#FD78FF, #FB00FF\n"
            "<:FDDBFF:674370583412080670><:FFB8FD:674385325572751371><:FD78FF:674385325208109088><:FB00FF:674385325522681857>"
            "\n[2.31](https://wanderinginn.com/2017/06/21/2-31/)",
            inline=True,
        )

        embed.add_field(
            name="🧊 Ceria Cold Skill",
            value="#CCFFFF, #99CCFF,\n#3366FF\n"
            "<:CCFFFF:674385325522681857><:99CCFF:667886770679054357><:3366FF:674385325522681857>"
            "\n[Various chapters](https://wanderinginn.com/)",
            inline=True,
        )

        embed.add_field(
            name="ℹ️ About Colored Text",
            value="Colored text in The Wandering Inn represents different types of magical effects, character speech patterns, and special abilities. Each color has specific meaning and significance in the story.",
            inline=False,
        )

        embed.set_footer(text="Color data compiled from The Wandering Inn web serial")

        await interaction.response.send_message(embed=embed)
        logging.info(
            f"TWI COLOREDTEXT: Successfully displayed colored text guide for user {interaction.user.id}"
        )

    @app_commands.command(
        name="connect_discord",
        description="Provides instructions on how to connect Discord and Patreon accounts.",
    )
    @handle_interaction_errors
    async def connect_discord(self, interaction: discord.Interaction):
        """
        Provide instructions for connecting Discord and Patreon accounts.

        This command sends a link to Patreon's official documentation on
        how to link Discord and Patreon accounts to receive role benefits.

        Args:
            interaction: The interaction that triggered the command
        """
        log_command_usage(
            "CONNECT_DISCORD", interaction.user.id, interaction.user.display_name
        )

        embed = discord.Embed(
            title="🔗 Connect Discord and Patreon",
            description="Learn how to link your Discord and Patreon accounts to receive supporter benefits!",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(),
        )

        embed.add_field(
            name="📋 Instructions",
            value="Follow Patreon's official guide to connect your accounts and automatically receive Discord roles based on your support level.",
            inline=False,
        )

        embed.add_field(
            name="🔗 Official Guide",
            value="[How do I receive my Discord role?](https://support.patreon.com/hc/en-us/articles/212052266-How-do-I-receive-my-Discord-role)",
            inline=False,
        )

        embed.add_field(
            name="💡 Benefits",
            value="• Automatic role assignment\n• Access to supporter channels\n• Early chapter access\n• Community recognition",
            inline=False,
        )

        embed.set_footer(text="Thank you for supporting The Wandering Inn!")

        await interaction.response.send_message(embed=embed)
        logging.info(
            f"TWI CONNECT_DISCORD: Provided connection instructions to user {interaction.user.id}"
        )
