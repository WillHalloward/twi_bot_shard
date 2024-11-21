import asyncio
import json
import logging
import logging.handlers
import ssl
from itertools import cycle
from pprint import pprint
from typing import List, Optional, Union
import datetime
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
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.pg_con = db_pool
        self.web_client = web_client

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.start_status_loop())
        self.add_view(PersistentView(self))
        await self.load_extensions()
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

    async def on_app_command_completion(self, interaction: discord.Interaction, command: Union[discord.app_commands.Command, discord.app_commands.ContextMenu]):
        end_date = datetime.datetime.now()
        if 'start_time' in interaction.extras:
            run_time = end_date - interaction.extras['start_time']
            await self.pg_con.execute("""
                UPDATE command_history 
                SET 
                    run_time=$1, 
                    finished_successfully=TRUE,
                    end_date=$2 
                WHERE serial=$3
                """, run_time, end_date, interaction.extras['id'])
        else:
            logging.error(f"No start time in extra dict {interaction=}")


    async def on_interaction(self, interaction: discord.Interaction):
        user_id = interaction.user.id  # get id of the user who performed the command
        guild_id = interaction.guild.id if interaction.guild else None  # get the id of the guild
        if interaction.command is not None:
            command_name = interaction.command.name   # get the name of the command
        else:
            command_name = None
        #check if channel is a thread or channel:
        if interaction.channel.type == discord.ChannelType.text:
            channel_id = interaction.channel.id # get the id of the channel
        else:
            channel_id = None
        slash_command = isinstance(interaction.command, discord.app_commands.Command)
        started_successfully = not interaction.command_failed
        command_args = json.dumps(interaction.data.get('options', []))  # Convert options to JSON string
        start_date = datetime.datetime.now()

        sql_query = """
            INSERT INTO command_history(
                start_date, 
                user_id, 
                command_name, 
                channel_id, 
                guild_id, 
                slash_command, 
                args, 
                started_successfully
            )
            VALUES($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING serial
            """
        serial = await self.pg_con.fetchval(sql_query,
                                            start_date,
                                            user_id,
                                            command_name,
                                            channel_id,
                                            guild_id,
                                            slash_command,
                                            command_args,
                                            started_successfully)

        interaction.extras['id'] = serial
        interaction.extras['start_time'] = start_date

    async def start_status_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.change_presence(activity=discord.Game(next(status)))
            await asyncio.sleep(10)


async def main():
    logger = logging.getLogger('discord')
    logger.setLevel(secrets.logging_level)

    handler = logging.handlers.RotatingFileHandler(
        filename=f'{secrets.logfile}.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,
        backupCount=10
    )
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message} :{lineno}', datefmt='%Y-%m-%d %H:%M:%S', style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("Logging started...")

    context = ssl.create_default_context()
    context.check_hostname = False
    context.load_verify_locations(f"ssl-cert/server-ca.pem")
    context.load_cert_chain(f"ssl-cert/client-cert.pem", f"ssl-cert/client-key.pem")

    async with ClientSession() as our_client, asyncpg.create_pool(database=secrets.database, user=secrets.DB_user, password=secrets.DB_password, host=secrets.host, ssl=context, command_timeout=300) as pool:
        cogs = ['cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods', 'cogs.stats', 'cogs.creator_links', 'cogs.report', 'cogs.innktober', 'cogs.summarization']
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        async with Cognita(
                commands.when_mentioned_or("!"),
                db_pool=pool,
                web_client=our_client,
                initial_extensions=cogs,
                intents=intents
        ) as bot:
            await bot.start(secrets.bot_token)


asyncio.run(main())
