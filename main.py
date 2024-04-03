import asyncio
import logging
import logging.handlers
import ssl
from itertools import cycle
from typing import List, Optional

import asyncpg
import discord
from aiohttp import ClientSession
from discord.ext import commands

import secrets
from cogs.twi import PersistentView

status = cycle(["Killing the mages of Wistram",
                "Cleaning up a mess",
                "Hiding corpses",
                "Mending Pirateaba's broken hands",
                "Hoarding knowledge",
                "Dusting off priceless artifacts",
                "Praying for Mating Rituals 4",
                "Plotting demise of nosy half-elfs",
                "Humming while dusting the graves",
                "Harmonizing the tombstones",
                "Writing songs to ward off the departed"])
class Cognita(commands.Bot):
    def __init__(
            self,
            *args,
            initial_extensions: List[str],
            db_pool: asyncpg.Pool,
            web_client: ClientSession,
            testing_guild_id: Optional[int] = None,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.pg_con = db_pool
        self.web_client = web_client
        self.testing_guild_id = testing_guild_id
        self.testing_guild = 297916314239107072

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.start_status_loop())
        self.add_view(PersistentView(self))
        await self.load_extensions()
        if self.testing_guild_id:
            guild = discord.Object(self.testing_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        self.unsubscribe_stats_listeners()

    async def load_extensions(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                logging.exception(f"Failed to load cog {extension} - {e}")

    def unsubscribe_stats_listeners(self):
        stats_cog = self.get_cog("stats")
        self.remove_listener(stats_cog.save_listener, "on_message")
        self.remove_listener(stats_cog.message_deleted, "on_raw_message_delete")
        self.remove_listener(stats_cog.message_edited, "on_raw_message_edit")
        self.remove_listener(stats_cog.reaction_add, "on_raw_reaction_add")
        self.remove_listener(stats_cog.reaction_remove, "on_raw_reaction_remove")

    async def on_ready(self):
        logging.info(f"Logged in as {self}")

    async def on_command_completion(self, ctx: discord.ext.commands.Context):
        logging.info(f"{ctx.author.name} invoked {ctx.command} with arguments {ctx.kwargs} in channel {ctx.channel.name} from guild {ctx.guild.name}")

    async def start_status_loop(self):
        await self.wait_until_ready()
        if secrets.logfile != 'test':
            await self.change_presence(activity=discord.Game(next(status)))
            await asyncio.sleep(10)

async def main():

    logger = logging.getLogger('discord')
    logger.setLevel(secrets.logging_level)

    handler = logging.handlers.RotatingFileHandler(
        filename=f'{secrets.logfile}.log',
        encoding='utf-8',
        maxBytes=32*1024*1024,
        backupCount=10
    )
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("Logging started...")

    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_verify_locations(f"ssl-cert/server-ca.pem")
    context.load_cert_chain(f"ssl-cert/client-cert.pem", f"ssl-cert/client-key.pem")

    async with ClientSession() as our_client, asyncpg.create_pool(database=secrets.database, user=secrets.DB_user, password=secrets.DB_password, host=secrets.host, ssl=context, command_timeout=300) as pool:
        exts = ['cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods', 'cogs.stats', 'cogs.creator_links', 'cogs.report']
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        async with Cognita(
            commands.when_mentioned_or("!"),
            db_pool=pool,
            web_client=our_client,
            initial_extensions=exts,
            intents=intents
        ) as bot:
            await bot.start(secrets.bot_token)

asyncio.run(main())