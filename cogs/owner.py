import logging
import subprocess

from discord.ext import commands


class OwnerCog(commands.Cog, name="Owner"):

    def __init__(self, bot):
        self.bot = bot

    # Hidden means it won't show up on the default help.
    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def load_cog(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    async def unload_cog(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.unload_extension(cog)
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
            logging.error(f'{type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='cmd')
    @commands.is_owner()
    async def cmd(self, ctx, *, args):
        args_array = args.split(" ")
        try:
            await ctx.send(subprocess.check_output(args_array, stderr=subprocess.STDOUT).decode("utf-8"))
        except subprocess.CalledProcessError as e:
            await ctx.send(f'Error: {e.output.decode("utf-8")}')

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx):
        try:
            await self.bot.tree.sync()
        except Exception as e:
            logging.error(e)
        logging.debug("Synced")


async def setup(bot):
    await bot.add_cog(OwnerCog(bot))
