"""Single source of truth for the bot's cog registry.

This module is THE registry of loadable cog extensions. ``main.py`` (startup
loading), ``cogs/owner.py`` (``/admin load``/``loadall`` and their
autocompletes), and ``tests/test_cogs.py`` all consume these tuples — do not
hand-maintain copies of this list anywhere else.

To add a new cog: append its module path to :data:`COGS` (and to
:data:`BASE_CRITICAL_COGS` only if it must be loaded at startup in
development/testing).

Note: this module must stay import-light and must never import ``main`` —
importing ``main`` runs the bot.
"""

#: All loadable cog extensions, in load order.
COGS: tuple[str, ...] = (
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
    "cogs.settings",
    "cogs.message_log",
    "cogs.interactive_help",
    "cogs.heartbeat",
)

#: Cogs that must be loaded at startup even in development/testing (all cogs
#: load at startup in production/staging regardless — slash commands must be
#: registered before the command tree is synced).
BASE_CRITICAL_COGS: tuple[str, ...] = (
    "cogs.owner",  # Owner commands for bot management
    "cogs.mods",  # Moderation commands
    "cogs.stats",  # Core statistics tracking
    "cogs.settings",  # Bot settings management
    "cogs.interactive_help",  # Interactive help system
)
