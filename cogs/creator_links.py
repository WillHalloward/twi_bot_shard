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

    creator_link = app_commands.Group(name="creator_link", description="Creator Link commands")

    @creator_link.command(
        name="get",
        description="Posts the creators links.",
    )
    async def creator_link_get(self, interaction: discord.Interaction, creator: discord.User = None):
        if creator is None:
            creator = interaction.user
        try:
            query_r = await self.bot.pg_con.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC",creator.id)
            if query_r:
                embed = discord.Embed(title=f"{creator.display_name}'s links", color=0x00ff00)
                embed.set_thumbnail(url=creator.display_avatar.url)
                for x in query_r:
                    if interaction.channel.is_nsfw() or not x['nsfw']:
                        embed.add_field(name=f"{x['title']} {' - NSFW' if x['nsfw'] else ''}", value=x['link'], inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"I could not find any links for **{creator.display_name}**")

        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="add",
        description="Adds a link to your creator links.",
    )
    async def creator_link_add(self, interaction: discord.Interaction, title: str, link: str, nsfw: bool = False, weight: int = 0, feature: bool = True):
        try:
            await self.bot.pg_con.execute("INSERT INTO creator_links (user_id, title, link, nsfw, weight, feature) VALUES ($1, $2, $3,$4, $5, $6)",
                                          interaction.user.id, title, link, nsfw, weight, feature)
            await interaction.response.send_message(f"Added link **{title}** to your links.")
        except asyncpg.UniqueViolationError:
            await interaction.response.send_message(f"You already have a link with the title **{title}**")
        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="remove",
        description="Removes a link from your creator links.",
    )
    async def creator_link_remove(self, interaction: discord.Interaction, title: str):
        try:
            await self.bot.pg_con.execute("DELETE FROM creator_links WHERE user_id = $1 AND lower(title) = lower($2)",
                                          interaction.user.id, title)
            await interaction.response.send_message(f"Removed link **{title}** from your links.")
        except Exception as e:
            logging.exception(f"Creator Link {e}")

    @creator_link.command(
        name="edit",
        description="Edits a link from your creator links.",
    )
    async def creator_link_edit(self, interaction: discord.Interaction, title: str, link: str, nsfw: bool = False, weight: int = 0, feature: bool = True):
        try:
            await self.bot.pg_con.execute("UPDATE creator_links SET link = $1, nsfw = $2, weight = $5, feature = $6, last_changed = now() WHERE user_id = $3 AND lower(title) = lower($4)",
                                          link, nsfw, interaction.user.id, title, weight, feature)
            await interaction.response.send_message(f"Edited link **{title}** in your links.")
        except Exception as e:
            logging.exception(f"Creator Link {e}")


async def setup(bot):
    await bot.add_cog(CreatorLinks(bot))
