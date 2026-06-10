"""Message Log Cog.

Logs message edits, deletes, and bulk deletes to a configured Discord channel.
Layers on top of the existing stats_listeners DB tracking — this cog handles
the user-visible log output, not the database writes.

Commands:
- /set_log_channel: Configure which channel receives log embeds
- /clear_log_channel: Disable logging for this server
"""

from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.base_cog import BaseCog
from utils.error_handling import handle_interaction_errors

# Truncation limit for embed field values (Discord limit is 1024)
CONTENT_MAX = 900


def _truncate(text: str | None, limit: int = CONTENT_MAX) -> str:
    """Truncate text for embed fields, preserving meaning."""
    if not text:
        return "*empty*"
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _channel_context(channel: discord.abc.GuildChannel | discord.Thread) -> str:
    """Build a human-readable channel context string including thread/forum info."""
    if isinstance(channel, discord.Thread):
        parent = channel.parent
        if isinstance(parent, discord.ForumChannel):
            return f"Forum: #{parent.name} > Thread: {channel.name}"
        return (
            f"#{parent.name} > Thread: {channel.name}"
            if parent
            else f"Thread: {channel.name}"
        )
    return f"#{channel.name}"


class MessageLogCog(BaseCog):
    """Logs message edits, deletes, and bulk deletes to a configured channel."""

    def __init__(self, bot) -> None:
        super().__init__(bot, name="message_log")
        self._log_channel_cache: dict[int, int | None] = {}

    async def _get_log_channel(self, guild_id: int) -> discord.TextChannel | None:
        """Get the log channel for a guild, using a cache to avoid repeated DB hits."""
        if guild_id not in self._log_channel_cache:
            row = await self.bot.db.fetchrow(
                "SELECT log_channel_id FROM server_settings WHERE guild_id = $1",
                guild_id,
            )
            self._log_channel_cache[guild_id] = row["log_channel_id"] if row else None

        channel_id = self._log_channel_cache.get(guild_id)
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    # ── Commands ──────────────────────────────────────────────────────

    @app_commands.command(
        name="set_log_channel",
        description="Set the channel where message edits/deletes are logged",
    )
    @app_commands.describe(channel="The text channel to send log messages to")
    @app_commands.default_permissions(manage_guild=True)
    @handle_interaction_errors
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """Configure the log channel for this server."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        # Defer before DB work so the 3s interaction window can't be missed.
        await interaction.response.defer(ephemeral=True)

        # Upsert into server_settings
        existing = await self.bot.db.fetchrow(
            "SELECT guild_id FROM server_settings WHERE guild_id = $1", guild_id
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        if existing:
            await self.bot.db.execute(
                "UPDATE server_settings "
                "SET log_channel_id = $1, updated_at = $2 "
                "WHERE guild_id = $3",
                channel.id,
                now,
                guild_id,
            )
        else:
            await self.bot.db.execute(
                "INSERT INTO server_settings"
                "(guild_id, log_channel_id, created_at, updated_at) "
                "VALUES ($1, $2, $3, $3)",
                guild_id,
                channel.id,
                now,
            )

        self._log_channel_cache[guild_id] = channel.id
        self.logger.info(
            "log_channel_set",
            guild_id=guild_id,
            channel_id=channel.id,
            user_id=interaction.user.id,
        )
        await interaction.followup.send(
            f"Log channel set to {channel.mention}.", ephemeral=True
        )

    @app_commands.command(
        name="clear_log_channel",
        description="Disable message edit/delete logging for this server",
    )
    @app_commands.default_permissions(manage_guild=True)
    @handle_interaction_errors
    async def clear_log_channel(self, interaction: discord.Interaction) -> None:
        """Disable message logging for this server."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        # Defer before DB work so the 3s interaction window can't be missed.
        await interaction.response.defer(ephemeral=True)
        await self.bot.db.execute(
            "UPDATE server_settings "
            "SET log_channel_id = NULL, updated_at = $1 "
            "WHERE guild_id = $2",
            datetime.now(UTC).replace(tzinfo=None),
            guild_id,
        )
        self._log_channel_cache[guild_id] = None
        self.logger.info("log_channel_cleared", guild_id=guild_id)
        await interaction.followup.send("Message logging disabled.", ephemeral=True)

    # ── Edit Listener ────────────────────────────────────────────────

    @commands.Cog.listener("on_message_edit")
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Log message edits to the configured log channel."""
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return

        log_channel = await self._get_log_channel(before.guild.id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Message Edited",
            color=discord.Color.gold(),
            timestamp=datetime.now(UTC),
        )
        embed.set_author(
            name=str(before.author),
            icon_url=before.author.display_avatar.url,
        )
        embed.add_field(
            name="Before",
            value=_truncate(before.content),
            inline=False,
        )
        embed.add_field(
            name="After",
            value=_truncate(after.content),
            inline=False,
        )
        embed.add_field(
            name="Channel",
            value=_channel_context(before.channel),
            inline=True,
        )
        embed.add_field(
            name="Jump",
            value=f"[Go to message]({after.jump_url})",
            inline=True,
        )
        embed.set_footer(text=f"Message ID: {before.id} | User ID: {before.author.id}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            self.logger.warning(
                "log_channel_forbidden",
                guild_id=before.guild.id,
                channel_id=log_channel.id,
            )

    # ── Delete Listener ──────────────────────────────────────────────

    @commands.Cog.listener("on_message_delete")
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletions to the configured log channel."""
        if message.author.bot or not message.guild:
            return

        log_channel = await self._get_log_channel(message.guild.id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(UTC),
        )
        embed.set_author(
            name=str(message.author),
            icon_url=message.author.display_avatar.url,
        )
        embed.add_field(
            name="Content",
            value=_truncate(message.content),
            inline=False,
        )

        # Show attachments if any
        if message.attachments:
            att_text = "\n".join(a.filename for a in message.attachments)
            embed.add_field(
                name=f"Attachments ({len(message.attachments)})",
                value=_truncate(att_text, 256),
                inline=False,
            )

        embed.add_field(
            name="Channel",
            value=_channel_context(message.channel),
            inline=True,
        )
        embed.add_field(
            name="Sent At",
            value=discord.utils.format_dt(message.created_at, style="R"),
            inline=True,
        )
        embed.set_footer(
            text=f"Message ID: {message.id} | User ID: {message.author.id}"
        )

        # Try to find who deleted the message from the audit log
        try:
            async for entry in message.guild.audit_logs(
                action=discord.AuditLogAction.message_delete, limit=5
            ):
                if (
                    entry.target
                    and entry.target.id == message.author.id
                    and entry.extra
                    and entry.extra.channel.id == message.channel.id
                ):
                    embed.add_field(
                        name="Deleted By",
                        value=str(entry.user),
                        inline=True,
                    )
                    break
        except discord.Forbidden:
            pass  # No audit log permission — that's fine

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            self.logger.warning(
                "log_channel_forbidden",
                guild_id=message.guild.id,
                channel_id=log_channel.id,
            )

    # ── Bulk Delete Listener ─────────────────────────────────────────

    @commands.Cog.listener("on_bulk_message_delete")
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        """Log bulk message deletions to the configured log channel."""
        if not messages:
            return
        guild = messages[0].guild
        if not guild:
            return

        log_channel = await self._get_log_channel(guild.id)
        if not log_channel:
            return

        # Group by channel for clarity
        channel = messages[0].channel
        authors = {m.author for m in messages if not m.author.bot}
        author_names = ", ".join(str(a) for a in list(authors)[:10])
        if len(authors) > 10:
            author_names += f" (+{len(authors) - 10} more)"

        embed = discord.Embed(
            title="Bulk Message Delete",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(
            name="Messages Deleted",
            value=str(len(messages)),
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=_channel_context(channel),
            inline=True,
        )
        embed.add_field(
            name="Authors",
            value=author_names or "*unknown*",
            inline=False,
        )

        # Show a sample of deleted content
        sample_lines = []
        for msg in messages[:5]:
            content = _truncate(msg.content, 80)
            sample_lines.append(f"**{msg.author.display_name}:** {content}")
        if len(messages) > 5:
            sample_lines.append(f"*...and {len(messages) - 5} more*")
        embed.add_field(
            name="Sample",
            value="\n".join(sample_lines) or "*no text content*",
            inline=False,
        )

        embed.set_footer(text=f"Channel ID: {channel.id}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            self.logger.warning(
                "log_channel_forbidden",
                guild_id=guild.id,
                channel_id=log_channel.id,
            )


async def setup(bot) -> None:
    """Required entry point for cog loading."""
    await bot.add_cog(MessageLogCog(bot))
