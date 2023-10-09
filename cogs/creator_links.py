import logging
from typing import List

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands


class CreatorLinks(commands.Cog, name="Creator"):
    def __init__(self, bot):
        self.links_cache = None
        self.bot = bot

    async def cog_load(self) -> None:
        self.links_cache = await self.bot.pg_con.fetch("SELECT title, user_id FROM creator_links")

    @commands.hybrid_group(name="creator_link")
    async def creator_link(self, ctx):
        pass

    @creator_link.command(
        name="get",
        brief="Posts the creators links.",
        usage='@Creator'
    )
    async def creator_link_get(self, ctx, *, creator: discord.User = None):
        if creator is None:
            creator = ctx.author
        try:
            query_r = await self.bot.pg_con.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC",
                                                  creator.id)
            if query_r:
                embed = discord.Embed(title=f"{creator.display_name}'s links", color=0x00ff00)
                embed.set_thumbnail(url=creator.display_avatar.url)
                for x in query_r:
                    if ctx.channel.is_nsfw() or not x['nsfw']:
                        embed.add_field(name=f"{x['title']} {' - NSFW' if x['nsfw'] else ''}", value=x['link'], inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"I could not find any links for **{creator.display_name}**")

        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="add",
        brief="Adds a link to your creator links.",
        usage='[Title] [Link]'
    )
    async def creator_link_add(self, ctx, title: str, link: str, nsfw: bool = False, weight: int = 0, feature: bool = True):
        try:
            await self.bot.pg_con.execute("INSERT INTO creator_links (user_id, title, link, nsfw, weight, feature) VALUES ($1, $2, $3,$4, $5, $6)",
                                          ctx.author.id, title, link, nsfw, weight, feature)
            await ctx.send(f"Added link **{title}** to your links.")
        except asyncpg.UniqueViolationError:
            await ctx.send(f"You already have a link with the title **{title}**")
        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="remove",
        brief="Removes a link from your creator links.",
        usage='[Title]'
    )
    async def creator_link_remove(self, ctx, title: str):
        try:
            await self.bot.pg_con.execute("DELETE FROM creator_links WHERE user_id = $1 AND lower(title) = lower($2)",
                                          ctx.author.id, title)
            await ctx.send(f"Removed link **{title}** from your links.")
        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="edit",
        brief="Edits a link from your creator links.",
        usage='[Title] [Link]'
    )
    async def creator_link_edit(self, ctx, title: str, link: str, nsfw: bool = False, weight: int = 0, feature: bool = True):
        try:
            await self.bot.pg_con.execute("UPDATE creator_links SET link = $1, nsfw = $2, weight = $5, feature = $6, last_changed = now() WHERE user_id = $3 AND lower(title) = lower($4)",
                                          link, nsfw, ctx.author.id, title, weight, feature)
            await ctx.send(f"Edited link **{title}** in your links.")
        except Exception as e:
            logging.exception(f"Creator Link {e}")


async def setup(bot):
    await bot.add_cog(CreatorLinks(bot))
