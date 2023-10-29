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

    @app_commands.command(name='load')
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def load_cog(self, interaction: discord.Interaction, *, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.load_extension(cog)
        except Exception as e:
            await interaction.response.send_message(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await interaction.response.send_message('**`SUCCESS`**', delete_after=5)

    @load_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, interaction: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @app_commands.command(name='unload')
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def unload_cog(self, interaction: discord.Interaction, *, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.unload_extension(cog)
        except Exception as e:
            await interaction.response.send_message(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await interaction.response.send_message('**`SUCCESS`**', delete_after=5)

    @unload_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, interaction: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @app_commands.command(name='reload')
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        await interaction.response.defer()
        try:
            await self.bot.unload_extension(cog)
            await self.bot.load_extension(cog)
        except Exception as e:
            await interaction.response.send_message(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.exception(f'{type(e).__name__} - {e}')
        else:
            await interaction.response.send_message('**`SUCCESS`**', delete_after=5)

    @reload_cog.autocomplete('cog')
    async def reload_cog_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs if current.lower() in cog.lower()
        ]

    @app_commands.command(name='cmd')
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def cmd(self, interaction: discord.Interaction, args: str):
        args_array = args.split(" ")
        try:
            await interaction.response.send_message(subprocess.check_output(args_array, stderr=subprocess.STDOUT).decode("utf-8"))
        except subprocess.CalledProcessError as e:
            await interaction.response.send_message(f'Error: {e.output.decode("utf-8")}')

    @app_commands.command(name="sync")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def sync(self, interaction: discord.Interaction, all_guilds: bool):
        if all_guilds:
            try:
                await self.bot.tree.sync()
            except Exception as e:
                logging.error(e)
            await interaction.response.send_message("Synced Globally")
        else:
            try:
                await self.bot.tree.sync(guild=interaction.guild)
            except Exception as e:
                logging.error(e)
            await interaction.response.send_message("Synced Locally")

    @app_commands.command(name="exit")
    @commands.is_owner()
    @app_commands.guilds(297916314239107072)
    async def exit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Exiting...")
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(OwnerCog(bot), guilds=[discord.Object(id=297916314239107072)])
