"""Quick script to sync slash commands to Discord.
This script mirrors the main bot setup so cogs that require the database can load.
Run this locally with the bot token and database env vars configured.
"""

import asyncio
import logging
import os
import platform
import ssl

import asyncpg
import discord
from discord.ext import commands
from dotenv import load_dotenv
from utils.repository_factory import RepositoryFactory

import config
from utils.command_groups import admin, gallery_admin, mod
from utils.db import Database
from utils.http_client import HTTPClient
from utils.repositories import register_repositories
from utils.resource_monitor import ResourceMonitor
from utils.service_container import ServiceContainer
from utils.sqlalchemy_db import async_session_maker

load_dotenv()

COGS = [
    "cogs.gallery",
    "cogs.links_tags",
    "cogs.patreon_poll",
    "cogs.twi",
    "cogs.owner",
    "cogs.utility",
    "cogs.info",
    "cogs.pins",
    "cogs.quotes",
    "cogs.external_services",
    "cogs.roles",
    "cogs.mods",
    "cogs.stats",
    "cogs.creator_links",
    "cogs.report",
    "cogs.summarization",
    "cogs.settings",
    "cogs.interactive_help",
]


def _get_git_sha() -> str | None:
    env_keys = [
        "RAILWAY_GIT_COMMIT_SHA",
        "RAILWAY_GIT_COMMIT",
        "GIT_SHA",
        "COMMIT_SHA",
        "SOURCE_COMMIT",
    ]
    for key in env_keys:
        value = os.getenv(key)
        if value:
            return value

    try:
        with open(os.path.join(".git", "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()
        if head.startswith("ref: "):
            ref_path = os.path.join(".git", head.split(" ", 1)[1])
            with open(ref_path, encoding="utf-8") as handle:
                return handle.read().strip()
        return head
    except OSError:
        return None


def _format_sha(sha: str | None) -> str:
    if not sha:
        return "unknown"
    return sha[:12]


def get_build_info() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "discord": discord.__version__,
        "git": _format_sha(_get_git_sha()),
    }


def _parse_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _should_dump(name: str, filters: set[str]) -> bool:
    return not filters or name.lower() in filters


def _format_option(option, indent: str = "  ") -> list[str]:
    option_type = getattr(option, "type", "unknown")
    required = getattr(option, "required", None)
    choices = getattr(option, "choices", None)
    required_suffix = f", required={required}" if required is not None else ""
    lines = [f"{indent}- {option.name} (type={option_type}{required_suffix})"]
    if choices:
        choice_items = ", ".join(f"{choice.name}={choice.value}" for choice in choices)
        lines.append(f"{indent}  choices: {choice_items}")
    if getattr(option, "options", None):
        for sub in option.options:
            lines.extend(_format_option(sub, indent=indent + "  "))
    return lines


def _format_local_command(command, indent: str = "") -> list[str]:
    is_group = bool(getattr(command, "commands", None))
    command_type = "group" if is_group else getattr(command, "type", "command")
    lines = [f"{indent}- {command.name} (type={command_type})"]

    parameters = getattr(command, "parameters", None)
    if parameters:
        for param in parameters:
            lines.extend(_format_option(param, indent=indent + "  "))

    if is_group:
        for sub in command.commands:
            lines.extend(_format_local_command(sub, indent=indent + "  "))

    return lines


async def dump_remote_commands(
    bot: commands.Bot, guild: discord.Object | None, filters: set[str]
) -> None:
    scope = f"guild {guild.id}" if guild else "global"
    try:
        remote = await bot.tree.fetch_commands(guild=guild)
    except Exception as exc:
        print(f"[FAIL] Failed to fetch remote commands ({scope}): {exc}")
        return

    print(f"Remote commands ({scope}):")
    for cmd in remote:
        if not _should_dump(cmd.name, filters):
            continue
        cmd_type = getattr(cmd, "type", "unknown")
        cmd_id = getattr(cmd, "id", None)
        id_suffix = f", id={cmd_id}" if cmd_id else ""
        print(f"- {cmd.name} (type={cmd_type}{id_suffix})")
        if getattr(cmd, "options", None):
            for option in cmd.options:
                for line in _format_option(option):
                    print(line)


def dump_local_commands(
    bot: commands.Bot, filters: set[str], label: str = "local"
) -> None:
    print(f"Local commands ({label}):")
    for cmd in bot.tree.get_commands():
        if not _should_dump(cmd.name, filters):
            continue
        for line in _format_local_command(cmd):
            print(line)


class SyncBot(commands.Bot):
    def __init__(
        self,
        *args,
        initial_extensions: list[str],
        db_pool: asyncpg.Pool,
        http_client: HTTPClient,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.loaded_extensions = dict.fromkeys(initial_extensions, False)

        self.db = Database(db_pool)
        self.http_client = http_client
        self.web_client = None
        self.session_maker = async_session_maker
        self.startup_times = {}
        self.logger = logging.getLogger("sync_bot")
        self.resource_monitor = ResourceMonitor(
            check_interval=300,
            memory_threshold=85.0,
            cpu_threshold=80.0,
            memory_leak_threshold=52428800,
            enable_memory_leak_detection=False,
            logger=self.logger.getChild("resource_monitor"),
        )

        self.container = ServiceContainer()
        self.container.register("bot", self)
        self.container.register("db", self.db)
        self.container.register("http_client", http_client)
        self.container.register("resource_monitor", self.resource_monitor)
        self.container.register_factory("db_session", self.get_db_session)

        self.repo_factory = RepositoryFactory(self.container, self.get_db_session)

    async def get_db_session(self):
        return self.session_maker()

    async def setup_hook(self) -> None:
        self.web_client = await self.http_client.get_session()
        register_repositories(self.repo_factory)

        self.tree.add_command(admin)
        self.tree.add_command(mod)
        self.tree.add_command(gallery_admin)

        print("Loading cogs...")
        for cog in self.initial_extensions:
            try:
                await self.load_extension(cog)
                self.loaded_extensions[cog] = True
                print(f"  [OK] Loaded {cog}")
            except Exception as exc:
                print(f"  [FAIL] Failed to load {cog}: {exc}")

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.close()
        await super().close()


def build_ssl_config():
    if os.getenv("DATABASE_URL"):
        return "require"

    context = ssl.create_default_context()
    context.check_hostname = False
    context.load_verify_locations("ssl-cert/server-ca.pem")
    context.load_cert_chain("ssl-cert/client-cert.pem", "ssl-cert/client-key.pem")
    return context


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    build = get_build_info()
    print(
        "Build info: "
        f"python={build['python']} "
        f"discord={build['discord']} "
        f"git={build['git']}"
    )

    token = config.bot_token
    guild_id = os.getenv("SYNC_GUILD_ID")
    copy_globals = os.getenv("COPY_GLOBAL_TO_GUILD", "1") != "0"
    clear_global = os.getenv("CLEAR_GLOBAL_COMMANDS") == "1"
    dump_filters = _parse_filter(os.getenv("DUMP_COMMAND_FILTER"))
    dump_commands = os.getenv("DUMP_REMOTE_COMMANDS") == "1"
    dump_local = os.getenv("DUMP_LOCAL_COMMANDS") == "1"
    delete_command_id = os.getenv("DELETE_COMMAND_ID")
    delete_command_scope = os.getenv("DELETE_COMMAND_SCOPE", "global").lower()
    http_client = HTTPClient(
        timeout=30,
        max_connections=25,
        max_keepalive_connections=5,
        keepalive_timeout=30,
        logger=logging.getLogger("http_client"),
    )

    async with asyncpg.create_pool(
        database=config.database,
        user=config.DB_user,
        password=config.DB_password,
        host=config.host,
        port=config.port,
        ssl=build_ssl_config(),
        command_timeout=300,
        min_size=1,
        max_size=5,
        max_inactive_connection_lifetime=180.0,
        timeout=30.0,
    ) as pool:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        async with SyncBot(
            commands.when_mentioned_or("!"),
            initial_extensions=COGS,
            db_pool=pool,
            http_client=http_client,
            intents=intents,
            help_command=None,
        ) as bot:

            @bot.event
            async def on_ready() -> None:
                print(f"Logged in as {bot.user} (ID: {bot.user.id})")
                guild = None
                if guild_id:
                    try:
                        guild = discord.Object(id=int(guild_id))
                    except ValueError:
                        print(f"[FAIL] Invalid SYNC_GUILD_ID: {guild_id}")
                        await bot.close()
                        return

                if guild:
                    if copy_globals:
                        print(f"Syncing commands to guild {guild_id}...")
                    else:
                        print(
                            f"Syncing guild {guild_id} without copying global commands..."
                        )
                else:
                    if clear_global:
                        print("Clearing global commands...")
                    else:
                        print("Syncing commands globally...")

                try:
                    if delete_command_id:
                        application_id = bot.user.id
                        if delete_command_scope == "guild":
                            if not guild:
                                print(
                                    "[FAIL] DELETE_COMMAND_SCOPE=guild requires SYNC_GUILD_ID"
                                )
                                await bot.close()
                                return
                            await bot.http.delete_guild_command(
                                application_id, guild.id, int(delete_command_id)
                            )
                            print(f"[OK] Deleted guild command id={delete_command_id}")
                        else:
                            await bot.http.delete_global_command(
                                application_id, int(delete_command_id)
                            )
                            print(f"[OK] Deleted global command id={delete_command_id}")

                    if guild:
                        if os.getenv("CLEAR_GUILD_COMMANDS") == "1":
                            bot.tree.clear_commands(guild=guild)
                            await bot.tree.sync(guild=guild)
                        if copy_globals:
                            bot.tree.copy_global_to(guild=guild)
                        if dump_local:
                            try:
                                dump_local_commands(
                                    bot, dump_filters, label=f"guild {guild_id}"
                                )
                            except Exception as exc:
                                print(f"[WARN] Failed to dump local commands: {exc}")
                        synced = await bot.tree.sync(guild=guild)
                        print(f"[OK] Synced {len(synced)} commands to guild {guild_id}")
                        if dump_commands:
                            await dump_remote_commands(bot, guild, dump_filters)
                    else:
                        if clear_global:
                            bot.tree.clear_commands(guild=None)
                            synced = await bot.tree.sync()
                            print(
                                f"[OK] Cleared global commands (synced {len(synced)})"
                            )
                            if dump_local:
                                try:
                                    dump_local_commands(bot, dump_filters)
                                except Exception as exc:
                                    print(
                                        f"[WARN] Failed to dump local commands: {exc}"
                                    )
                            if dump_commands:
                                await dump_remote_commands(bot, None, dump_filters)
                            return
                        if dump_local:
                            try:
                                dump_local_commands(bot, dump_filters)
                            except Exception as exc:
                                print(f"[WARN] Failed to dump local commands: {exc}")
                        synced = await bot.tree.sync()
                        print(f"[OK] Synced {len(synced)} commands globally")
                        if dump_commands:
                            await dump_remote_commands(bot, None, dump_filters)
                except Exception as exc:
                    print(f"[FAIL] Failed to sync: {exc}")
                finally:
                    print("Closing bot...")
                    await bot.close()

            try:
                await bot.start(token)
            except Exception as exc:
                print(f"ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
