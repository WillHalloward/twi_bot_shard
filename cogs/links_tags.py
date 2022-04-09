import logging
import re

import asyncpg
from discord.ext import commands


def numerical_sort(value):
    numbers = re.compile(r'(\d+)')
    parts = numbers.split(value)
    parts[1::2] = map(int, parts[1::2])
    return parts


class LinkTags(commands.Cog, name="Links"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="Link",
        brief="Posts the link with the given name.",
        usage='[Title]',
        aliases=['map'],
        hidden=False,
    )
    async def link(self, ctx, user_input):
        try:
            query_r = await self.bot.pg_con.fetchrow("SELECT content, title FROM links WHERE lower(title) = lower($1)",
                                                     user_input)
            if query_r:
                await ctx.send(f"{query_r['title']}: {query_r['content']}")
            else:
                await ctx.send(f"I could not find a link with the title **{user_input}**")
        except:
            logging.exception("Link")

    @commands.command(
        name="Links",
        brief="View all links.",
        aliases=['maps'],
        hidden=False,
    )
    async def links(self, ctx):
        try:
            query_r = await self.bot.pg_con.fetch("SELECT title FROM links ORDER BY title")
            message = ""
            for tags in query_r:
                message = f"{message} `{tags['title']}`"
            await ctx.send(f"Links: {message}")
        except:
            logging.exception("Link")

    @commands.command(
        name="AddLink",
        brief="Adds a link with the given name to the given url and tag",
        usage='[url][title][tag]',
        hidden=False,
    )
    async def add_link(self, ctx, content, title, tag=None):
        try:
            await self.bot.pg_con.execute(
                "INSERT INTO links(content, tag, user_who_added, id_user_who_added, time_added, title) "
                "VALUES ($1,$2,$3,$4,now(),$5)",
                content, tag, ctx.author.display_name, ctx.author.id, title)
            await ctx.send(f"Added Link: {title}\nLink: <{content}>\nTag: {tag}")
        except asyncpg.exceptions.UniqueViolationError:
            await ctx.send("That name is already in the list.")

    @commands.command(
        name="Delink",
        brief="Deletes a link with the given name",
        aliases=['RemoveLink', 'DeleteLink'],
        usage='[Title]',
        hidden=False,
    )
    async def delete_link(self, ctx, title):
        result = await self.bot.pg_con.execute("DELETE FROM links WHERE lower(title) = lower($1)", title)
        if result == "DELETE 1":
            await ctx.send(f"Deleted link: **{title}**")
        else:
            await ctx.send(f"I could not find a link with the title: **{title}**")

    @commands.command(
        name="Tags",
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

    @commands.command(
        name="Tag",
        brief="View all links that got a certain tag",
        aliases=['ShowTag'],
        usage='[Tag]',
        hidden=False,
    )
    async def tag(self, ctx, user_input):
        query_r = await self.bot.pg_con.fetch("SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY title",
                                              user_input)
        logging.error(query_r)
        logging.error(type(query_r))
        if query_r:
            message = ""
            for tags in sorted(query_r, key=numerical_sort):
                message = f"{message}\n`{tags['title']}`"
            await ctx.send(f"links: {message}")
        else:
            await ctx.send(
                f"I could not find a link with the tag **{user_input}**. Use !tags to see all available tags. "
                "or !links to see all links.")


def setup(bot):
    bot.add_cog(LinkTags(bot))
