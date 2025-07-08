"""
Event listeners for the stats system.

This module contains all the Discord event listeners that handle real-time
data collection for messages, reactions, member events, and other Discord events.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.ext.commands import Cog

from .stats_utils import save_message

if TYPE_CHECKING:
    from discord.ext.commands import Bot


class StatsListenersMixin:
    """Mixin class containing all stats-related event listeners."""

    @Cog.listener("on_message")
    async def save_listener(self, message: discord.Message) -> None:
        """
        Listen for new messages and save them to the database.

        Args:
            message: The Discord message object
        """
        if not isinstance(message.channel, discord.channel.DMChannel):
            try:
                await save_message(self.bot, message)
            except Exception as e:
                logging.error(f"Error: {e} on message save")

    @Cog.listener("on_raw_message_edit")
    async def message_edited(self, payload: discord.RawMessageUpdateEvent) -> None:
        """
        Listen for message edits and update the database.

        Args:
            payload: The raw message update event payload
        """
        try:
            if (
                "content" in payload.data
                and "edited_timestamp" in payload.data
                and payload.data["edited_timestamp"] is not None
            ):
                logging.debug(f"message edited {payload}")
                old_content = await self.bot.db.fetchval(
                    "SELECT content FROM messages where message_id = $1 LIMIT 1",
                    int(payload.data["id"]),
                )
                logging.debug(old_content)
                await self.bot.db.execute(
                    "INSERT INTO message_edit(id, old_content, new_content, edit_timestamp) VALUES ($1,$2,$3,$4)",
                    int(payload.data["id"]),
                    old_content,
                    payload.data["content"],
                    datetime.fromisoformat(payload.data["edited_timestamp"]).replace(
                        tzinfo=None
                    ),
                )
                logging.debug("post insert")
                await self.bot.db.execute(
                    "UPDATE messages set content = $1 WHERE message_id = $2",
                    payload.data["content"],
                    int(payload.data["id"]),
                )
                logging.debug("post update")
        except Exception:
            logging.exception(f"message_edited - {payload.data}")

    @Cog.listener("on_raw_message_delete")
    async def message_deleted(self, payload: discord.RawMessageDeleteEvent) -> None:
        """
        Listen for message deletions and mark them as deleted in the database.

        Args:
            payload: The raw message delete event payload
        """
        await self.bot.db.execute(
            "UPDATE public.messages SET deleted = true WHERE message_id = $1",
            payload.message_id,
        )

    @Cog.listener("on_raw_reaction_add")
    async def reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Listen for reaction additions and save them to the database.

        Args:
            payload: The raw reaction action event payload
        """
        try:
            current_time = datetime.now().replace(tzinfo=None)

            # Use transaction for consistency
            async with self.bot.db.pool.acquire() as conn:
                async with conn.transaction():
                    if payload.emoji.is_custom_emoji():
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                            """,
                            None,
                            payload.message_id,
                            payload.user_id,
                            payload.emoji.name,
                            payload.emoji.animated,
                            payload.emoji.id,
                            f"https://cdn.discordapp.com/emojis/{payload.emoji.id}.{'gif' if payload.emoji.animated else 'png'}",
                            current_time,
                            payload.emoji.is_custom_emoji(),
                        )
                    elif isinstance(payload.emoji, str):
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                            """,
                            payload.emoji,
                            payload.message_id,
                            payload.user_id,
                            None,
                            False,
                            None,
                            None,
                            current_time,
                            False,
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                            """,
                            payload.emoji.name,
                            payload.message_id,
                            payload.user_id,
                            payload.emoji.name,
                            None,
                            None,
                            None,
                            current_time,
                            payload.emoji.is_custom_emoji(),
                        )
        except Exception as e:
            logging.exception(f"Error: {e} on reaction add")

    @Cog.listener("on_raw_reaction_remove")
    async def reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Listen for reaction removals and mark them as removed in the database.

        Args:
            payload: The raw reaction action event payload
        """
        try:
            if payload.emoji.is_custom_emoji():
                await self.bot.db.execute(
                    "UPDATE reactions SET removed = TRUE WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3",
                    payload.message_id,
                    payload.user_id,
                    payload.emoji.id,
                )
            else:
                await self.bot.db.execute(
                    "UPDATE reactions SET removed = TRUE WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3",
                    payload.message_id,
                    payload.user_id,
                    str(payload.emoji),
                )
        except Exception as e:
            logging.exception(f"Error: {e} on reaction remove")

    @Cog.listener("on_member_join")
    async def member_join(self, member: discord.Member) -> None:
        """
        Listen for member joins and save the join event to the database.

        Args:
            member: The Discord member who joined
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
                member.id,
                member.guild.id,
                datetime.now().replace(tzinfo=None),
                'join',
                member.guild.name,
                datetime.now().replace(tzinfo=None),
            )
        except Exception as e:
            logging.error(f"Error saving member join: {e}")

    @Cog.listener("on_member_remove")
    async def member_remove(self, member: discord.Member) -> None:
        """
        Listen for member leaves and update the leave date in the database.

        Args:
            member: The Discord member who left
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at) VALUES ($1,$2,$3,$4,$5,$6)",
                member.id,
                member.guild.id,
                datetime.now().replace(tzinfo=None),
                'leave',
                member.guild.name,
                datetime.now().replace(tzinfo=None),
            )
        except Exception as e:
            logging.error(f"Error saving member leave: {e}")

    @Cog.listener("on_member_update")
    async def member_roles_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """
        Listen for member role updates and save role changes to the database.

        Args:
            before: The member state before the update
            after: The member state after the update
        """
        try:
            if before.roles != after.roles:
                # Get added and removed roles
                added_roles = set(after.roles) - set(before.roles)
                removed_roles = set(before.roles) - set(after.roles)

                current_time = datetime.now().replace(tzinfo=None)

                # Save added roles
                for role in added_roles:
                    await self.bot.db.execute(
                        "INSERT INTO role_changes(user_id, server_id, role_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                        after.id,
                        after.guild.id,
                        role.id,
                        "added",
                        current_time,
                    )

                # Save removed roles
                for role in removed_roles:
                    await self.bot.db.execute(
                        "INSERT INTO role_changes(user_id, server_id, role_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                        after.id,
                        after.guild.id,
                        role.id,
                        "removed",
                        current_time,
                    )

                # Log role changes
                if added_roles:
                    logging.info(f"User {after.id} gained roles: {[role.name for role in added_roles]}")
                if removed_roles:
                    logging.info(f"User {after.id} lost roles: {[role.name for role in removed_roles]}")

        except Exception as e:
            logging.error(f"Error processing role changes: {e}")

    @Cog.listener("on_user_update")
    async def user_update(self, before: discord.User, after: discord.User) -> None:
        """
        Listen for user updates and save username changes to the database.

        Args:
            before: The user state before the update
            after: The user state after the update
        """
        try:
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE users SET username = $1 WHERE user_id = $2",
                    after.name,
                    after.id,
                )
        except Exception as e:
            logging.error(f"Error updating username: {e}")

    @Cog.listener("on_guild_channel_create")
    async def guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """
        Listen for channel creation and save new channels to the database.

        Args:
            channel: The newly created channel
        """
        try:
            # Handle all guild channel types
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel)):
                # Get channel-specific attributes with safe defaults
                topic = getattr(channel, 'topic', None)
                is_nsfw = getattr(channel, 'is_nsfw', lambda: False)() if callable(getattr(channel, 'is_nsfw', None)) else False

                await self.bot.db.execute(
                    "INSERT INTO channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    channel.id,
                    channel.name,
                    channel.category_id,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild.id,
                    channel.position,
                    topic,
                    is_nsfw,
                )
        except Exception as e:
            logging.error(f"Error saving new channel: {e}")

    @Cog.listener("on_guild_channel_delete")
    async def guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """
        Listen for channel deletion and mark channels as deleted in the database.

        Args:
            channel: The deleted channel
        """
        try:
            await self.bot.db.execute(
                "UPDATE channels SET deleted = TRUE WHERE id = $1",
                channel.id,
            )
        except Exception as e:
            logging.error(f"Error marking channel as deleted: {e}")


    @Cog.listener("on_thread_create")
    async def thread_created(self, thread: discord.Thread) -> None:
        """
        Listen for thread creation and save new threads to the database.

        Args:
            thread: The newly created thread
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO threads(id, name, parent_id, guild_id, archived, locked) VALUES ($1,$2,$3,$4,$5,$6)",
                thread.id,
                thread.name,
                thread.parent_id,
                thread.guild.id,
                thread.archived,
                thread.locked,
            )
        except Exception as e:
            logging.error(f"Error saving new thread: {e}")

    @Cog.listener("on_thread_delete")
    async def thread_deleted(self, thread: discord.Thread) -> None:
        """
        Listen for thread deletion and mark threads as deleted in the database.

        Args:
            thread: The deleted thread
        """
        try:
            await self.bot.db.execute(
                "UPDATE threads SET deleted = TRUE WHERE id = $1",
                thread.id,
            )
        except Exception as e:
            logging.error(f"Error marking thread as deleted: {e}")


    @Cog.listener("on_guild_emojis_update")
    async def guild_emoji_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ) -> None:
        """
        Listen for emoji updates and save changes to the database.

        Args:
            guild: The guild where emojis were updated
            before: The list of emojis before the update
            after: The list of emojis after the update
        """
        try:
            # Get added and removed emojis
            before_set = {emoji.id for emoji in before}
            after_set = {emoji.id for emoji in after}

            added_emojis = [emoji for emoji in after if emoji.id not in before_set]
            removed_emoji_ids = before_set - after_set

            current_time = datetime.now().replace(tzinfo=None)

            # Save added emojis
            for emoji in added_emojis:
                await self.bot.db.execute(
                    "INSERT INTO emojis(id, name, guild_id, animated, created_at) VALUES ($1,$2,$3,$4,$5)",
                    emoji.id,
                    emoji.name,
                    guild.id,
                    emoji.animated,
                    current_time,
                )

            # Mark removed emojis as deleted
            for emoji_id in removed_emoji_ids:
                await self.bot.db.execute(
                    "UPDATE emojis SET deleted = TRUE WHERE id = $1",
                    emoji_id,
                )
        except Exception as e:
            logging.error(f"Error updating emojis: {e}")

    @Cog.listener("on_guild_role_create")
    async def guild_role_create(self, role: discord.Role) -> None:
        """
        Listen for role creation and save new roles to the database.

        Args:
            role: The newly created role
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO roles(id, name, guild_id, color, position, permissions, created_at) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                role.id,
                role.name,
                role.guild.id,
                role.color.value,
                role.position,
                role.permissions.value,
                role.created_at.replace(tzinfo=None),
            )
        except Exception as e:
            logging.error(f"Error saving new role: {e}")

    @Cog.listener("on_guild_role_delete")
    async def guild_role_delete(self, role: discord.Role) -> None:
        """
        Listen for role deletion and mark roles as deleted in the database.

        Args:
            role: The deleted role
        """
        try:
            await self.bot.db.execute(
                "UPDATE roles SET deleted = TRUE WHERE id = $1",
                role.id,
            )
        except Exception as e:
            logging.error(f"Error marking role as deleted: {e}")

    async def ensure_channel_exists(self, channel: discord.abc.GuildChannel):
        """Ensure a channel exists in the database, inserting it if necessary."""
        try:
            # Check if channel exists
            result = await self.bot.db.fetchval("SELECT id FROM channels WHERE id = $1", channel.id)
            if result is None:
                # Channel doesn't exist, insert it
                topic = getattr(channel, 'topic', None)
                is_nsfw = getattr(channel, 'is_nsfw', lambda: False)() if callable(getattr(channel, 'is_nsfw', None)) else False

                await self.bot.db.execute(
                    "INSERT INTO channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    channel.id,
                    channel.name,
                    channel.category_id,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild.id,
                    channel.position,
                    topic,
                    is_nsfw,
                )
        except Exception as e:
            logging.error(f"Error ensuring channel exists: {e}")

    # ============================================================================
    # MISSING FEATURES FROM ORIGINAL IMPLEMENTATION
    # ============================================================================

    @Cog.listener("on_thread_member_join")
    async def thread_member_join(self, thread_member: discord.ThreadMember) -> None:
        """
        Listen for thread member joins and save them to the database.

        Args:
            thread_member: The thread member who joined
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO thread_membership(user_id, thread_id) VALUES($1,$2)",
                thread_member.id,
                thread_member.thread_id,
            )
            logging.debug(f"User {thread_member.id} joined thread {thread_member.thread_id}")
        except Exception as e:
            logging.error(f"Error saving thread member join: {e}")

    @Cog.listener("on_thread_member_remove")
    async def thread_member_leave(self, thread_member: discord.ThreadMember) -> None:
        """
        Listen for thread member leaves and remove them from the database.

        Args:
            thread_member: The thread member who left
        """
        try:
            await self.bot.db.execute(
                "DELETE FROM thread_membership WHERE user_id = $1 and thread_id = $2",
                thread_member.id,
                thread_member.thread_id,
            )
            logging.debug(f"User {thread_member.id} left thread {thread_member.thread_id}")
        except Exception as e:
            logging.error(f"Error removing thread member: {e}")

    async def log_update(self, table: str, action: str, before_value: str, after_value: str, primary_key: str) -> None:
        """
        Log an update to the updates table for audit trail purposes.

        Args:
            table: The table that was updated
            action: The type of action performed
            before_value: The value before the update
            after_value: The value after the update
            primary_key: The primary key of the updated record
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                table,
                action,
                before_value,
                after_value,
                datetime.now().replace(tzinfo=None),
                primary_key,
            )
        except Exception as e:
            logging.error(f"Error logging update to audit trail: {e}")

    # Enhanced Channel Update Tracking
    @Cog.listener("on_guild_channel_update")
    async def guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        """
        Listen for channel updates and save detailed changes to the database with audit trail.

        Args:
            before: The channel state before the update
            after: The channel state after the update
        """
        try:
            # Track channel name changes
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE channels SET name = $1 WHERE id = $2",
                    after.name,
                    after.id,
                )
                await self.log_update("channels", "UPDATE_CHANNEL_NAME", before.name, after.name, str(after.id))

            # Track category changes
            if before.category_id != after.category_id:
                await self.bot.db.execute(
                    "UPDATE channels SET category_id = $1 WHERE id = $2",
                    after.category_id,
                    after.id,
                )
                await self.log_update("channels", "UPDATE_CHANNEL_CATEGORY_ID", str(before.category_id), str(after.category_id), str(after.id))

            # Track position changes
            if before.position != after.position:
                await self.bot.db.execute(
                    "UPDATE channels SET position = $1 WHERE id = $2",
                    after.position,
                    after.id,
                )
                await self.log_update("channels", "UPDATE_CHANNEL_POSITION", str(before.position), str(after.position), str(after.id))

            # Track topic changes (for text channels)
            if hasattr(before, 'topic') and hasattr(after, 'topic') and before.topic != after.topic:
                await self.bot.db.execute(
                    "UPDATE channels SET topic = $1 WHERE id = $2",
                    after.topic,
                    after.id,
                )
                await self.log_update("channels", "UPDATE_CHANNEL_TOPIC", before.topic, after.topic, str(after.id))

            # Track NSFW status changes (for text channels)
            if hasattr(before, 'is_nsfw') and hasattr(after, 'is_nsfw') and before.is_nsfw() != after.is_nsfw():
                await self.bot.db.execute(
                    "UPDATE channels SET is_nsfw = $1 WHERE id = $2",
                    after.is_nsfw(),
                    after.id,
                )
                await self.log_update("channels", "UPDATE_CHANNEL_IS_NSFW", str(before.is_nsfw()), str(after.is_nsfw()), str(after.id))

        except Exception as e:
            logging.error(f"Error updating channel with audit trail: {e}")

    # Enhanced Thread Update Tracking with Audit Trail
    @Cog.listener("on_thread_update")
    async def enhanced_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        """
        Enhanced thread update listener with comprehensive audit trail.

        Args:
            before: The thread state before the update
            after: The thread state after the update
        """
        try:
            # Track thread name changes
            if before.name != after.name:
                await self.log_update("threads", "THREAD_NAME_UPDATED", before.name, after.name, str(after.id))

            # Track archive status changes
            if before.archived != after.archived:
                await self.log_update("threads", "THREAD_ARCHIVED_UPDATED", str(before.archived), str(after.archived), str(after.id))

            # Track lock status changes
            if before.locked != after.locked:
                await self.log_update("threads", "THREAD_LOCKED_UPDATED", str(before.locked), str(after.locked), str(after.id))

            # Update the threads table
            await self.bot.db.execute(
                "UPDATE threads SET name = $1, archived = $2, locked = $3 WHERE id = $4",
                after.name,
                after.archived,
                after.locked,
                after.id,
            )

        except Exception as e:
            logging.error(f"Error in enhanced thread update tracking: {e}")

    # Enhanced Guild Update Tracking with Audit Trail
    @Cog.listener("on_guild_update")
    async def enhanced_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """
        Enhanced guild update listener with comprehensive audit trail.

        Args:
            before: The guild state before the update
            after: The guild state after the update
        """
        try:
            # Track server name changes
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE servers SET server_name = $1 WHERE server_id = $2",
                    after.name,
                    after.id,
                )
                await self.log_update("servers", "UPDATE_SERVER_NAME", before.name, after.name, str(after.id))

        except Exception as e:
            logging.error(f"Error in enhanced guild update tracking: {e}")

    # Enhanced Role Update Tracking with Audit Trail
    @Cog.listener("on_guild_role_update")
    async def enhanced_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """
        Enhanced role update listener with comprehensive audit trail.

        Args:
            before: The role state before the update
            after: The role state after the update
        """
        try:
            # Track role name changes
            if before.name != after.name:
                await self.log_update("roles", "UPDATE_ROLE_NAME", before.name, after.name, str(after.id))

            # Track role color changes
            if before.color != after.color:
                await self.log_update("roles", "UPDATE_ROLE_COLOR", str(before.color.value), str(after.color.value), str(after.id))

            # Track role position changes
            if before.position != after.position:
                await self.log_update("roles", "UPDATE_ROLE_POSITION", str(before.position), str(after.position), str(after.id))

            # Track role permission changes
            if before.permissions != after.permissions:
                await self.log_update("roles", "UPDATE_ROLE_PERMISSIONS", str(before.permissions.value), str(after.permissions.value), str(after.id))

            # Update the roles table
            await self.bot.db.execute(
                "UPDATE roles SET name = $1, color = $2, position = $3, permissions = $4 WHERE id = $5",
                after.name,
                after.color.value,
                after.position,
                after.permissions.value,
                after.id,
            )

        except Exception as e:
            logging.error(f"Error in enhanced role update tracking: {e}")

    # Enhanced Voice State Tracking with Detailed State Changes
    @Cog.listener("on_voice_state_update")
    async def enhanced_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """
        Enhanced voice state update listener with detailed state change tracking.

        Args:
            member: The member whose voice state changed
            before: The voice state before the update
            after: The voice state after the update
        """
        try:
            # Track mute state changes
            if before.mute != after.mute:
                await self.log_update("voice_state", "UPDATE_VOICE_STATE_MUTE", str(before.mute), str(after.mute), str(member.id))

            # Track deaf state changes
            if before.deaf != after.deaf:
                await self.log_update("voice_state", "UPDATE_VOICE_STATE_DEAF", str(before.deaf), str(after.deaf), str(member.id))

            # Track self-mute state changes
            if before.self_mute != after.self_mute:
                await self.log_update("voice_state", "UPDATE_VOICE_STATE_SELF_MUTE", str(before.self_mute), str(after.self_mute), str(member.id))

            # Track self-deaf state changes
            if before.self_deaf != after.self_deaf:
                await self.log_update("voice_state", "UPDATE_VOICE_STATE_SELF_DEAF", str(before.self_deaf), str(after.self_deaf), str(member.id))

            # Track suppress state changes
            if before.suppress != after.suppress:
                await self.log_update("voice_state", "UPDATE_VOICE_STATE_SUPPRESS", str(before.suppress), str(after.suppress), str(member.id))

            # Handle voice channel join/leave tracking
            current_time = datetime.now().replace(tzinfo=None)

            # User joined a voice channel
            if before.channel is None and after.channel is not None:
                await self.ensure_channel_exists(after.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    after.channel.id,
                    "joined",
                    current_time,
                )

            # User left a voice channel
            elif before.channel is not None and after.channel is None:
                await self.ensure_channel_exists(before.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    before.channel.id,
                    "left",
                    current_time,
                )

            # User moved between voice channels
            elif (
                before.channel != after.channel
                and before.channel is not None
                and after.channel is not None
            ):
                await self.ensure_channel_exists(before.channel)
                await self.ensure_channel_exists(after.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    before.channel.id,
                    "left",
                    current_time,
                )
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    after.channel.id,
                    "joined",
                    current_time,
                )

        except Exception as e:
            logging.error(f"Error in enhanced voice state update tracking: {e}")
