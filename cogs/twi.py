"""
The Wandering Inn cog for the Twi Bot Shard.

This module provides commands related to The Wandering Inn web serial, including
password retrieval for Patreon supporters, wiki searches, invisible text lookup,
and other TWI-specific functionality.
"""

import datetime
import json
import logging
import os
from typing import List
from PIL import Image, ImageSequence
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from googleapiclient.discovery import build
from os import remove
import config
from cogs.patreon_poll import fetch
from utils.permissions import (
    admin_or_me_check,
    admin_or_me_check_wrapper,
    app_admin_or_me_check,
    is_bot_channel,
    is_bot_channel_wrapper,
    app_is_bot_channel,
)
from utils.error_handling import handle_command_errors, handle_interaction_errors
from utils.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    ExternalServiceError,
)


def google_search(search_term, api_key, cse_id, **kwargs):
    """
    Perform a Google Custom Search using the provided API credentials.

    Args:
        search_term (str): The search query to execute
        api_key (str): Google API key for authentication
        cse_id (str): Custom Search Engine ID
        **kwargs: Additional parameters to pass to the search API

    Returns:
        dict: The search results as returned by the Google API
    """
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, num=9, **kwargs).execute()
    return res


class TwiCog(commands.Cog, name="The Wandering Inn"):
    """
    Cog providing commands related to The Wandering Inn web serial.

    This cog includes commands for retrieving Patreon passwords, searching the TWI wiki,
    finding content within the story, and accessing special text features like invisible text
    and colored text used in the serial.

    Attributes:
        bot: The bot instance
        invis_text_cache: Cache of invisible text chapter titles for autocomplete
        last_run: Timestamp of the last time the password command was run publicly
    """

    def __init__(self, bot):
        """
        Initialize the TwiCog.

        Args:
            bot: The bot instance to which this cog is attached
        """
        self.bot = bot
        self.invis_text_cache = None
        self.last_run = datetime.datetime.now() - datetime.timedelta(minutes=10)

    async def cog_load(self) -> None:
        """
        Load initial data when the cog is added to the bot.

        This method is called automatically when the cog is loaded.
        It populates the invisible text cache for use in autocomplete.
        """
        self.invis_text_cache = await self.bot.db.fetch(
            "SELECT DISTINCT title FROM invisible_text_twi"
        )

    # button class for linking people to the chapter
    class Button(discord.ui.Button):
        """
        A simple link button for directing users to a chapter.

        This button is used in various commands to provide a direct link
        to the relevant chapter on The Wandering Inn website.
        """

        def __init__(self, url):
            """
            Initialize the button with a URL.

            Args:
                url (str): The URL to link to
            """
            super().__init__(style=discord.ButtonStyle.link, url=url, label="Chapter")

    @app_commands.command(
        name="password",
        description="Gives the password for the latest chapter for patreons or instructions for non patreons.",
    )
    @handle_interaction_errors
    async def password(self, interaction: discord.Interaction):
        """
        Provide the current Patreon password or instructions on how to get it.

        If used in an allowed channel, this command provides the current password
        for accessing Patreon-exclusive content. If used elsewhere, it provides
        instructions on how to obtain the password through various methods.

        Args:
            interaction: The interaction that triggered the command
        """
        if interaction.channel.id in config.password_allowed_channel_ids:
            password = await self.bot.db.fetchrow(
                "SELECT password, link "
                "FROM password_link "
                "WHERE password IS NOT NULL "
                "ORDER BY serial_id DESC "
                "LIMIT 1"
            )
            if self.last_run < datetime.datetime.now() - datetime.timedelta(minutes=10):
                await interaction.response.send_message(
                    f"{password['password']}",
                    view=discord.ui.View().add_item(self.Button(password["link"])),
                )
                self.last_run = datetime.datetime.now()
            else:
                await interaction.response.send_message(
                    f"{password['password']}",
                    ephemeral=True,
                    view=discord.ui.View().add_item(self.Button(password["link"])),
                )
        else:
            await interaction.response.send_message(
                "There are 3 ways to get the patreon password.\n"
                f"1. Link discord to patreon and go to <#{config.inn_general_channel_id}> and check pins or use /password inside it.\n"
                "If you don't know how to connect discord to patreon use the command /connectdiscord\n"
                "2. You will get an email with the password every time pirate posts it.\n"
                "3. go to <https://www.patreon.com/pirateaba> and check the latest posts. It has the password.\n"
            )

    @app_commands.command(
        name="connectdiscord",
        description="Information for patreons on how to connect their patreon account to discord.",
    )
    @handle_interaction_errors
    async def connect_discord(self, interaction: discord.Interaction):
        """
        Provide instructions on connecting Patreon and Discord accounts.

        This command sends a link to Patreon's official documentation on
        how to link Discord and Patreon accounts to receive role benefits.

        Args:
            interaction: The interaction that triggered the command
        """
        await interaction.response.send_message(
            "Check this link https://support.patreon.com/hc/en-us/articles/212052266-How-do-I-receive-my-Discord-role"
        )

    @app_commands.command(
        name="wiki",
        description="Searches the The Wandering Inn wiki for a matching article.",
    )
    @handle_interaction_errors
    async def wiki(self, interaction: discord.Interaction, query: str):
        """
        Search The Wandering Inn wiki for articles matching the query.

        This command queries the TWI wiki API and returns matching articles
        with links. If available, it also includes a thumbnail image from
        the first result.

        Args:
            interaction: The interaction that triggered the command
            query: The search term to look for on the wiki
        """
        embed = discord.Embed(title=f"Wiki results search **{query}**")
        # Use the bot's shared HTTP client session for connection pooling
        session = await self.bot.http_client.get_session()
        html = await fetch(
            session,
            f"https://thewanderinginn.fandom.com/api.php?action=query&generator=search&gsrsearch={query}&format=json&prop=info|images&inprop=url",
        )
        try:
            sorted_json_data = sorted(
                json.loads(html)["query"]["pages"].values(), key=lambda k: k["index"]
            )
        except KeyError:
            await interaction.response.send_message(
                f"I'm sorry, I could not find a article matching **{query}**."
            )
            return
        for results in sorted_json_data:
            embed.add_field(
                name="\u200b",
                value=f"[{results['title']}]({results['fullurl']})",
                inline=False,
            )
        try:
            # Use the same session for the second request
            image_json = await fetch(
                session,
                f"https://thewanderinginn.fandom.com/api.php?action=query&format=json&titles={sorted_json_data[0]['images'][0]['title']}&prop=imageinfo&iiprop=url",
            )
            image_urls = next(iter(json.loads(image_json)["query"]["pages"].values()))
            embed.set_thumbnail(url=image_urls["imageinfo"][0]["url"])
        except KeyError:
            pass
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="find",
        description="Does a google search on 'Wanderinginn.com' and returns the results",
    )
    @app_commands.check(app_is_bot_channel)
    @handle_interaction_errors
    async def find(self, interaction: discord.Interaction, query: str):
        """
        Search wanderinginn.com using Google Custom Search.

        This command performs a Google search restricted to the Wandering Inn
        website and returns the results with snippets and links. Due to the
        potentially large response, this command is restricted to bot channels.

        Args:
            interaction: The interaction that triggered the command
            query: The search term to look for on wanderinginn.com
        """
        results = google_search(query, config.google_api_key, config.google_cse_id)
        if results["searchInformation"]["totalResults"] == "0":
            await interaction.response.send_message(
                "I could not find anything that matches your search."
            )
        else:
            embed = discord.Embed(title="Search", description=f"**{query}**")
            for result in results["items"]:
                embed.add_field(
                    name=result["title"], value=f"{result['snippet']}\n{result['link']}"
                )
            await interaction.response.send_message(embed=embed)

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
        """
        if chapter is None:
            invis_text_chapters = await self.bot.db.fetch(
                "SELECT title, COUNT(*) FROM invisible_text_twi GROUP BY title, date ORDER BY date"
            )
            embed = discord.Embed(title="Chapters with invisible text")
            for posts in invis_text_chapters:
                embed.add_field(
                    name=f"Chapter: {posts['title']}",
                    value=f"{posts['count']}",
                    inline=False,
                )
            await interaction.response.send_message(embed=embed)
        else:
            texts = await self.bot.db.fetch(
                "SELECT title, content FROM invisible_text_twi WHERE lower(title) similar to lower($1)",
                chapter,
            )
            if texts:
                embed = discord.Embed(title=f"Search for: **{chapter}** invisible text")
                for text in texts:
                    embed.add_field(
                        name=f"{text['title']}", value=text["content"], inline=False
                    )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    "Sorry i could not find any invisible text on that chapter.\n"
                    "Please give me the chapters exact title."
                )

    @invis_text.autocomplete("chapter")
    async def invis_text_autocomplete(
        self,
        interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete suggestions for chapter names with invisible text.

        This method filters the cached chapter titles based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current text input by the user

        Returns:
            A list of up to 25 matching chapter name choices
        """
        ln = []
        for x in self.invis_text_cache:
            ln.append(x["title"])
        return [
            app_commands.Choice(name=title, value=title)
            for title in ln
            if current.lower() in title.lower() or current == ""
        ][0:25]

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
        embed = discord.Embed(title="Twi's different colored text")
        embed.add_field(
            name="Red skills and classes",
            value="#FF0000\n"
            f"{'<:FF0000:666429504834633789>' * 4}"
            "\n[3.17T](https://wanderinginn.com/2017/09/27/3-17-t/)",
        )
        embed.add_field(
            name="Ser Raim skill",
            value="#EB0E0E\n"
            f"{'<:EB0E0E:666429505019183144>' * 4}"
            "\n[6.43E](https://wanderinginn.com/2019/09/10/6-43-e/)",
        )
        embed.add_field(
            name="Ivolethe summoning fire",
            value="#E01D1D\n"
            f"{'<:E01D1D:666429504863993908>' * 4}"
            "\n[Interlude 4](https://wanderinginn.com/2017/12/30/interlude-4/)",
        )
        embed.add_field(
            name="Unique Skills",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[2.19](https://wanderinginn.com/2017/05/03/2-19/)",
        )
        embed.add_field(
            name="Erin's landmark skill",
            value="#FF9900\n"
            f"{'<:FF9900:666435308480364554>' * 4}"
            "\n[5.44](https://wanderinginn.com/2018/12/08/5-44/)",
        )
        embed.add_field(
            name="Divine/Temporary skills",
            value="#FFD700\n"
            f"{'<:FFD700:666429505031897107>' * 4}"
            "\n[4.23E](https://wanderinginn.com/2018/03/27/4-23-e/)",
        )
        embed.add_field(
            name="Class restoration / Conviction skill",
            value="#99CCFF\n"
            f"{'<:99CCFF:667886770679054357>' * 4}"
            "\n[3.20T](https://wanderinginn.com/2017/10/03/3-20-t/)",
        )
        embed.add_field(
            name="Winter fae talking",
            value="#8AE8FF\n"
            f"{'<:8AE8FF:666429505015119922>' * 4}"
            "\n[2.06](https://wanderinginn.com/2017/03/28/2-06/)",
        )
        embed.add_field(
            name="Spring fae talking",
            value="#96BE50\n"
            f"{'<:96BE50:666429505014857728>' * 4}"
            "\n[5.11E](https://wanderinginn.com/2018/08/14/5-11-e/)",
        )
        embed.add_field(
            name="Grand Queen talking",
            value="#FFCC00\n"
            f"{'<:FFCC00:674267820678316052>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Silent Queen talking and purple skills",
            value="#CC99FF\n"
            f"{'<:CC99FF:674267820732841984>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Armored Queen talking",
            value="#999999\n"
            f"{'<:999999:674267820820791306>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Twisted Queen talking",
            value="#993300\n"
            f"{'<:993300:674267820694962186>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Flying Queen talking",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Magnolia charm skill",
            value="#FDDBFF, #FFB8FD,\n#FD78FF, #FB00FF\n"
            "<:FDDBFF:674370583412080670><:FFB8FD:674385325572751371><:FD78FF:674385325208109088><:FB00FF:674385325522681857>"
            "\n[2.31](https://wanderinginn.com/2017/06/21/2-31/)",
        )
        embed.add_field(
            name="Ceria cold skill",
            value="#CCFFFF, #99CCFF,\n#3366FF\n"
            "<:CCFFFF:962498665317011527><:99CCFF:667886770679054357><:3366FF:962498751086338088>"
            "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)",
        )
        embed.add_field(
            name="Siren water skill",
            value="#00CCFF\n"
            f"{'<:00CCFF:962498765879656498>' * 4}"
            "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)",
        )
        embed.add_field(
            name="Invisible Skills/Text",
            value="#0C0E0E,\n"
            f"{'<:0C0E0E:666452140994330624>' * 4}\n"
            "[1.08 R](https://wanderinginn.com/2016/12/18/1-08-r//)",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="update_password",
        description="Updates the password and link from /password",
    )
    @app_commands.check(app_admin_or_me_check)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def update_password(
        self, interaction: discord.Interaction, password: str, link: str
    ):
        """
        Update the Patreon password and chapter link in the database.

        This admin-only command updates the password and link that are provided
        by the /password command. It records the user who made the update and
        the current timestamp.

        Args:
            interaction: The interaction that triggered the command
            password: The new Patreon password to store
            link: The URL to the chapter that requires the password
        """
        await self.bot.db.execute(
            "INSERT INTO password_link(password, link, user_id, date) VALUES ($1, $2, $3, now())",
            password,
            link,
            interaction.user.id,
        )
        await interaction.response.send_message(
            "Updated password and link", ephemeral=True
        )

    # Reddit verification functionality has been removed or disabled
    # This feature previously allowed users to link their Discord and Reddit accounts
    # for access to the TWI_Patreon subreddit


async def setup(bot):
    """
    Set up the TwiCog.

    This function is called automatically by the bot when loading the extension.

    Args:
        bot: The bot instance to attach the cog to
    """
    await bot.add_cog(TwiCog(bot))
