import logging
import os
import ssl
import sys
import traceback
from itertools import cycle

import asyncpg
import discord
from discord.ext import commands, tasks

import secrets

context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
home = os.path.expanduser('~')
context.load_verify_locations(f"{home}/ssl-cert/server-ca.pem")
context.load_cert_chain(f"{home}/ssl-cert/client-cert.pem", f"{home}/ssl-cert/client-key.pem")
logging.basicConfig(filename=f'{home}/twi_bot_shard/cognita.log',
                    format='%(asctime)s :: %(levelname)-8s :: %(filename)s :: %(message)s',
                    level=logging.WARNING)
logging.info("Cognita starting")
intents = discord.Intents.default()  # All but the two privileged ones
intents.members = True  # Subscribe to the Members intent
bot = commands.Bot(
    command_prefix='!',
    description="The Wandering Inn helper",
    case_insensitive=True,
    intents=intents)

cogs = ['cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods',
        'cogs.stats']


@bot.event
async def on_ready():
    logging.info("Loading in Cogs")
    for extension in cogs:
        try:
            bot.load_extension(extension)
        except Exception as e:
            logging.error(f"Failed to load cog {extension} - {e}")
            print(f'Failed to load extension {extension}.', file=sys.stderr)
            traceback.print_exc()
    logging.info("Cogs loaded")
    stats_cog = bot.get_cog("stats")
    bot.remove_listener(stats_cog.save_listener, name="on_message")
    bot.remove_listener(stats_cog.message_deleted, name="on_raw_message_delete")
    bot.remove_listener(stats_cog.message_edited, name="on_raw_message_edit")
    # bot.remove_listener(stats_cog.reaction_add, name="on_raw_reaction_add")
    # bot.remove_listener(stats_cog.reaction_remove, name="on_raw_reaction_remove")
    status_loop.start()
    logging.info(f'Logged in as: {bot.user.name}\nVersion: {discord.__version__}\n')


async def create_db_pool():
    try:
        bot.pg_con = await asyncpg.create_pool(database=secrets.database, user=secrets.DB_user,
                                               password=secrets.DB_password,
                                               host=secrets.host, ssl=context)
    except Exception as e:
        logging.critical(f"{type(e).__name__} - {e}")
        sys.exit("Failed to connect to database")

    logging.info("created database connection")


status = cycle(["Killing the mages of Wistram",
                "Cleaning up a mess",
                "Keeping secrets",
                "Hiding corpses",
                "Mending Pirateaba's broken hands",
                "Longing for answers",
                "Hoarding knowledge",
                "Dusting off priceless artifacts",
                "Praying for Mating Rituals 4",
                "Plotting demise of nosy half-elfs"])


@tasks.loop(seconds=10)
async def status_loop():
    await bot.change_presence(activity=discord.Game(next(status)))


@bot.event
async def on_command_error(ctx, error):
    logging.warning(f"{type(error).__name__} - {error}")
    if hasattr(ctx.command, "on_error"):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(error)
    elif isinstance(error, commands.NotOwner):
        await ctx.send(f"Sorry {ctx.author.display_name} only ~~Zelkyr~~ Sara may do that.")
    elif isinstance(error, commands.MissingRole):
        await ctx.send("I'm sorry, you don't seem to have the required role for that")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"That command is on cooldown, please wait a bit.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Error: {error}")
    elif isinstance(error, discord.NotFound):
        await ctx.send(f"I could not find that message - {error}")
    elif isinstance(error, discord.Forbidden):
        await ctx.send(f"Error: I don't have the right permissions for that. - {error}")


@bot.event
async def on_command(ctx):
    logging.info(
        f"{ctx.author.name} invoked {ctx.command} with arguments {ctx.kwargs} in channel {ctx.channel.name} from guild {ctx.guild.name}")


bot.loop.run_until_complete(create_db_pool())
bot.run(secrets.bot_token)
