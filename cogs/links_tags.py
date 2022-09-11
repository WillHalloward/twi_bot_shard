import logging
import re
from typing import List

import asyncpg
from discord import app_commands
from discord.ext import commands


def numerical_sort(value):
    numbers = re.compile(r'(\d+)')
    parts = numbers.split(value)
    parts[1::2] = map(int, parts[1::2])
    return parts


class LinkTags(commands.Cog, name="Links"):
    def __init__(self, bot):
        self.bot = bot
        self.links_cache = None

    async def cog_load(self) -> None:
        self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")

    @commands.hybrid_group(name="link")
    async def link(self, ctx):
        pass

    # TODO Implement auto complete
    @link.command(
        name="get",
        brief="Posts the link with the given name.",
        usage='[Title]',
        aliases=['map'],
        hidden=False,
    )
    async def link_get(self, ctx, title: str):
        try:
            query_r = await self.bot.pg_con.fetchrow("SELECT content, title FROM links WHERE lower(title) = lower($1)",
                                                     title)
            if query_r:
                await ctx.send(f"{query_r['title']}: {query_r['content']}")
            else:
                await ctx.send(f"I could not find a link with the title **{title}**")
        except:
            logging.exception("Link")

    @link_get.autocomplete('title')
    async def link_get_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        ln = []
        for x in self.links_cache:
            ln.append({"title": x['title'], "content": x['content']})
        return [
                   app_commands.Choice(name=f"{link['title']}: {link['content']}"[0:100], value=link['title'])
                   for link in ln if str(current) in str(link['title']) or current == ""
               ][0:25]

    @link.command(
        name="list",
        brief="View all links.",
        aliases=['maps'],
        hidden=False,
    )
    async def link_list(self, ctx):
        try:
            query_r = await self.bot.pg_con.fetch("SELECT title FROM links ORDER BY title")
            message = ""
            for tags in query_r:
                message = f"{message} `{tags['title']}`"
            await ctx.send(f"Links: {message}")
        except:
            logging.exception("Link")

    @link.command(
        name="add",
        brief="Adds a link with the given name to the given url and tag",
        usage='[url][title][tag]',
        hidden=False,
    )
    async def link_add(self, ctx, content, title: str, tag: str = None):
        try:
            await self.bot.pg_con.execute(
                "INSERT INTO links(content, tag, user_who_added, id_user_who_added, time_added, title) "
                "VALUES ($1,$2,$3,$4,now(),$5)",
                content, tag, ctx.author.display_name, ctx.author.id, title)
            await ctx.send(f"Added Link: {title}\nLink: <{content}>\nTag: {tag}")
            self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")
        except asyncpg.exceptions.UniqueViolationError:
            await ctx.send("That name is already in the list.")

    @link.command(
        name="delete",
        brief="Deletes a link with the given name",
        aliases=['RemoveLink', 'DeleteLink'],
        usage='[Title]',
        hidden=False,
    )
    async def link_delete(self, ctx, title: str):
        result = await self.bot.pg_con.execute("DELETE FROM links WHERE lower(title) = lower($1)", title)
        if result == "DELETE 1":
            await ctx.send(f"Deleted link: **{title}**")
            self.links_cache = await self.bot.pg_con.fetch("SELECT * FROM links")
        else:
            await ctx.send(f"I could not find a link with the title: **{title}**")

    @link_delete.autocomplete('title')
    async def link_delete_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        ln = []
        for x in self.links_cache:
            ln.append({"title": x['title'], "content": x['content']})
        return [
                   app_commands.Choice(name=f"{link['title']}: {link['content']}"[0:100], value=link['title'])
                   for link in ln if str(current) in str(link['title']) or current == ""
               ][0:25]

    @commands.hybrid_command(
        name="tags",
        brief="See all available tags",
        aliases=['ListTags', 'ShowTags'],
        hidden=False,
    )
    async def tags(self, ctx):
        query_r = await self.bot.pg_con.fetch("SELECT DISTINCT tag FROM links ORDER BY tag")
        message = ""
        for tags in query_r:
            message = f"{message} `{tags['tag']}`"
        await ctx.send(f"Tags: {message}")

    @commands.hybrid_command(
        name="tag",
        brief="View all links that got a certain tag",
        aliases=['ShowTag'],
        usage='[Tag]',
        hidden=False,
    )
    async def tag(self, ctx, tag):
        query_r = await self.bot.pg_con.fetch(
            "SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY NULLIF(regexp_replace(title, '\D', '', 'g'), '')::int",
            tag)
        if query_r:
            message = ""
            for tags in query_r:
                message = f"{message}\n`{tags['title']}`"
            await ctx.send(f"links: {message}")
        else:
            await ctx.send(
                f"I could not find a link with the tag **{tag}**. Use !tags to see all available tags. "
                "or !links to see all links.")


async def setup(bot):
    await bot.add_cog(LinkTags(bot))
