import logging
import re
from typing import List

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands


class LinkTags(commands.Cog, name="Links"):
    def __init__(self, bot):
        self.bot = bot
        self.links_cache = None

    async def cog_load(self) -> None:
        self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")

    async def link_autocomplete(self, interaction: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        ln = []
        for x in self.links_cache:
            ln.append({"title": x['title'], "content": x['content']})
        return [
                   app_commands.Choice(name=f"{link['title']}: {link['content']}"[0:100], value=link['title'])
                   for link in ln if current.lower() in link['title'].lower() or current == ""
               ][0:25]

    link = app_commands.Group(name="link", description="Link commands")

    @link.command(
        name="get",
        description="Gets a link with the given name"
    )
    @app_commands.autocomplete(title=link_autocomplete)
    async def link_get(self, interaction: discord.Interaction, title: str):
        try:
            query_r = await self.bot.pg_con.fetchrow("SELECT content, title, embed FROM links WHERE lower(title) = lower($1)",
                                                     title)
            if query_r:
                if query_r['embed']:
                    await interaction.response.send_message(f"[{query_r['title']}]({query_r['content']})")
                else:
                    await interaction.response.send_message(f"{query_r['title']}: {query_r['content']}")
            else:
                await interaction.response.send_message(f"I could not find a link with the title **{title}**")
        except Exception as e:
            logging.exception("Link")

    @link.command(
        name="list",
        description="View all links."
    )
    async def link_list(self, interaction: discord.Interaction):
        try:
            query_r = await self.bot.pg_con.fetch("SELECT title FROM links ORDER BY title")
            message = ""
            for tags in query_r:
                message = f"{message} `{tags['title']}`"
            await interaction.response.send_message(f"Links: {message[0:1990]}")
        except:
            logging.exception("Link")

    @link.command(
        name="add",
        description="Adds a link with the given name to the given url and tag"
    )
    async def link_add(self, interaction: discord.Interaction, content: str, title: str, tag: str = None, embed: bool = True):
        try:
            await self.bot.pg_con.execute(
                "INSERT INTO links(content, tag, user_who_added, id_user_who_added, time_added, title, embed) "
                "VALUES ($1,$2,$3,$4,now(),$5, $6)",
                content, tag, interaction.user.display_name, interaction.user.id, title, embed)
            await interaction.response.send_message(f"Added Link: {title}\nLink: <{content}>\nTag: {tag}")
            self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")
        except asyncpg.exceptions.UniqueViolationError:
            await interaction.response.send_message("That name is already in the list.")

    @link.command(
        name="delete",
        description="Deletes a link with the given name"
    )
    @app_commands.autocomplete(title=link_autocomplete)
    async def link_delete(self, interaction: discord.Interaction, title: str):
        result = await self.bot.pg_con.execute("DELETE FROM links WHERE lower(title) = lower($1)", title)
        if result == "DELETE 1":
            await interaction.response.send_message(f"Deleted link: **{title}**")
            self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")
        else:
            await interaction.response.send_message(f"I could not find a link with the title: **{title}**")

    @link.command(
        name="edit",
        description="Edits a link with the given name",
    )
    async def link_edit(self, interaction: discord.Interaction, title: str, content: str):
        check = await self.bot.pg_con.fetchrow("SELECT * FROM links WHERE lower(title) = lower($1) and guild_id = $2", title, interaction.guild.id)
        if check:
            if check['id_user_who_added'] == interaction.user.id or interaction.user.guild_permissions.administrator:
                await self.bot.pg_con.execute("UPDATE links SET content = $1 WHERE lower(title) = lower($2)",
                                              content, title)
                await interaction.response.send_message(f"Edited link: **{title}**")
                self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")
            else:
                await interaction.response.send_message("You can only edit links you added yourself.")
        else:
            await interaction.response.send_message(f"I could not find a link with the title: **{title}**")

    @app_commands.command(
        name="tags",
        description="See all available tags"
    )
    async def tags(self, interaction: discord.Interaction):
        query_r = await self.bot.pg_con.fetch("SELECT DISTINCT tag FROM links ORDER BY tag")
        message = ""
        for tags in query_r:
            message = f"{message} `{tags['tag']}`"
        await interaction.response.send_message(f"Tags: {message}")

    @app_commands.command(
        name="tag",
        description="View all links that got a certain tag"
    )
    async def tag(self, interaction: discord.Interaction, tag: str):
        query_r = await self.bot.pg_con.fetch(
            "SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY NULLIF(regexp_replace(title, '\D', '', 'g'), '')::int", tag)
        if query_r:
            message = ""
            for tags in query_r:
                message = f"{message}\n`{tags['title']}`"
            await interaction.response.send_message(f"links: {message}")
        else:
            await interaction.response.send_message(
                f"I could not find a link with the tag **{tag}**. Use /tags to see all available tags. "
                "or /links to see all links.")


async def setup(bot):
    await bot.add_cog(LinkTags(bot))
