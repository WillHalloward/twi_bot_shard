"""Shared typed base for the Stats cog mixins.

The Stats functionality is split across several mixins (commands, listeners and
queries) that are combined into the concrete :class:`StatsCogs` cog. Every mixin
relies on ``self.bot`` and ``self.logger``, which are assigned on the concrete
cog in its ``__init__``. This base exists purely so static type checkers know
those attributes are present on the mixins; it adds no runtime behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from discord.ext.commands import Bot


class StatsMixinBase:
    """Declares the shared attributes provided by the concrete Stats cog."""

    if TYPE_CHECKING:
        # Set on the concrete StatsCogs in __init__; declared here for typing.
        bot: Bot
        logger: Any
