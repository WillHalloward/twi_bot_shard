import logging
import subprocess
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

cogs = ['cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods', 'cogs.stats', 'cogs.creator_links']


class OwnerCog(commands.Cog, name="Owner"):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='load', hidden=True)
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def load_cog(self, ctx, *, cog: str):
        try:
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @load_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @commands.hybrid_command(name='unload', hidden=True)
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def unload_cog(self, ctx, *, cog: str):
        try:
            await self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @unload_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @commands.hybrid_command(name='reload', hidden=True)
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def reload_cog(self, ctx, cog: str):
        try:
            await self.bot.unload_extension(cog)
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**', delete_after=5)
            await ctx.message.delete()

    @reload_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @commands.hybrid_command(name='cmd')
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def cmd(self, ctx, *, args):
        args_array = args.split(" ")
        try:
            await ctx.send(subprocess.check_output(args_array, stderr=subprocess.STDOUT).decode("utf-8"))
        except subprocess.CalledProcessError as e:
            await ctx.send(f'Error: {e.output.decode("utf-8")}')

    @commands.hybrid_command(name="sync")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def sync(self, ctx, *, all_guilds: bool):
        if all_guilds:
            try:
                await self.bot.tree.sync()
            except Exception as e:
                logging.error(e)
            await ctx.send("Synced Globally")
        else:
            try:
                await self.bot.tree.sync(guild=ctx.guild)
            except Exception as e:
                logging.error(e)
            await ctx.send("Synced Locally")

    @commands.command(name="exit")
    @commands.is_owner()
    async def exit(self, ctx):
        await ctx.send("Exiting...")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(OwnerCog(bot), guilds=[discord.Object(id=297916314239107072)])
