"""
Mock factories for Discord objects.

This module provides factories for creating mock Discord objects
for testing purposes, such as users, guilds, channels, and interactions.
It uses Faker to generate realistic test data.
"""

import asyncio
import json
import os
import sys
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Faker for generating realistic test data
try:
    from faker import Faker
except ImportError:
    print("Faker is not installed. Please install it with:")
    print("uv pip install faker")
    sys.exit(1)

import discord
from discord import app_commands
from discord.ext import commands

# Create a Faker instance
fake = Faker()


# Set up some Discord-specific generators
def generate_discord_id() -> int:
    """Generate a random Discord snowflake ID."""
    return random.randint(100000000000000000, 999999999999999999)


def generate_discriminator() -> str:
    """Generate a random Discord discriminator."""
    return f"{random.randint(1, 9999):04d}"


class MockUserFactory:
    """Factory for creating mock Discord users."""

    @staticmethod
    def create(
        user_id: int = None,
        name: str = None,
        discriminator: str = None,
        display_name: Optional[str] = None,
        bot: bool = False,
        avatar: Optional[str] = None,
    ) -> discord.User:
        """
        Create a mock Discord user.

        Args:
            user_id: The user ID. If None, generates a random Discord ID.
            name: The username. If None, generates a realistic username.
            discriminator: The user discriminator. If None, generates a random discriminator.
            display_name: The display name. If None, uses the username or generates a nickname.
            bot: Whether the user is a bot.
            avatar: The avatar URL. If None, may generate a random avatar URL.

        Returns:
            A mock Discord user.
        """
        # Generate realistic data if not provided
        if user_id is None:
            user_id = generate_discord_id()

        if name is None:
            name = fake.user_name()

        if discriminator is None:
            discriminator = generate_discriminator()

        if display_name is None:
            # 30% chance to have a different display name
            if random.random() < 0.3:
                display_name = fake.name()
            else:
                display_name = name

        if avatar is None and random.random() < 0.7:  # 70% chance to have an avatar
            avatar = fake.image_url()

        user = MagicMock(spec=discord.User)
        user.id = user_id
        user.name = name
        user.discriminator = discriminator
        user.display_name = display_name
        user.mention = f"<@{user_id}>"
        user.avatar = avatar
        user.bot = bot
        user.dm_channel = None
        user.created_at = fake.date_time_between(start_date="-3y", end_date="now")

        # Add async methods
        user.send = AsyncMock()
        user.create_dm = AsyncMock(return_value=MagicMock(spec=discord.DMChannel))

        return user


class MockMemberFactory:
    """Factory for creating mock Discord guild members."""

    @staticmethod
    def create(
        user_id: int = None,
        name: str = None,
        discriminator: str = None,
        display_name: Optional[str] = None,
        bot: bool = False,
        guild_id: int = None,
        roles: Optional[List[discord.Role]] = None,
        joined_at: Optional[Any] = None,
        nick: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> discord.Member:
        """
        Create a mock Discord guild member.

        Args:
            user_id: The user ID. If None, generates a random Discord ID.
            name: The username. If None, generates a realistic username.
            discriminator: The user discriminator. If None, generates a random discriminator.
            display_name: The display name. If None, uses the nickname or username.
            bot: Whether the user is a bot.
            guild_id: The ID of the guild the member belongs to. If None, generates a random ID.
            roles: The roles the member has.
            joined_at: When the member joined the guild. If None, generates a random date.
            nick: The member's nickname. If None, may generate a random nickname.
            avatar: The avatar URL. If None, may generate a random avatar URL.

        Returns:
            A mock Discord guild member.
        """
        # Generate realistic data if not provided
        if user_id is None:
            user_id = generate_discord_id()

        if name is None:
            name = fake.user_name()

        if discriminator is None:
            discriminator = generate_discriminator()

        if guild_id is None:
            guild_id = generate_discord_id()

        if joined_at is None:
            # Member joined between 2 years ago and now
            joined_at = fake.date_time_between(start_date="-2y", end_date="now")

        if nick is None and random.random() < 0.4:  # 40% chance to have a nickname
            nick = (
                fake.first_name() if random.random() < 0.7 else fake.word().capitalize()
            )

        if display_name is None:
            display_name = nick or name

        if avatar is None and random.random() < 0.7:  # 70% chance to have an avatar
            avatar = fake.image_url()

        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.name = name
        member.discriminator = discriminator
        member.nick = nick
        member.display_name = display_name
        member.mention = f"<@{user_id}>"
        member.bot = bot
        member.guild_id = guild_id
        member.roles = roles or []
        member.joined_at = joined_at
        member.avatar = avatar
        member.created_at = fake.date_time_between(start_date="-3y", end_date=joined_at)
        member.premium_since = (
            fake.date_time_between(start_date=joined_at, end_date="now")
            if random.random() < 0.2
            else None
        )

        # Add async methods
        member.send = AsyncMock()
        member.add_roles = AsyncMock()
        member.remove_roles = AsyncMock()
        member.ban = AsyncMock()
        member.kick = AsyncMock()

        return member


class MockGuildFactory:
    """Factory for creating mock Discord guilds."""

    @staticmethod
    def create(
        guild_id: int = None,
        name: str = None,
        owner_id: int = None,
        roles: Optional[List[discord.Role]] = None,
        members: Optional[List[discord.Member]] = None,
        channels: Optional[List[discord.abc.GuildChannel]] = None,
        emojis: Optional[List[discord.Emoji]] = None,
    ) -> discord.Guild:
        """
        Create a mock Discord guild.

        Args:
            guild_id: The guild ID. If None, generates a random Discord ID.
            name: The guild name. If None, generates a realistic server name.
            owner_id: The ID of the guild owner. If None, generates a random Discord ID.
            roles: The roles in the guild.
            members: The members in the guild.
            channels: The channels in the guild.
            emojis: The emojis in the guild.

        Returns:
            A mock Discord guild.
        """
        # Generate realistic data if not provided
        if guild_id is None:
            guild_id = generate_discord_id()

        if name is None:
            # Generate a realistic server name
            name_types = [
                lambda: f"{fake.word().capitalize()} {fake.word().capitalize()}",  # Two words
                lambda: fake.company(),  # Company name
                lambda: f"The {fake.word().capitalize()} {fake.word().capitalize()}s",  # The X Ys
                lambda: f"{fake.first_name()}'s Server",  # Person's Server
                lambda: f"{fake.word().capitalize()} Community",  # X Community
                lambda: f"{fake.word().capitalize()} Club",  # X Club
                lambda: f"{fake.word().capitalize()} Gaming",  # X Gaming
            ]
            name = random.choice(name_types)()

        if owner_id is None:
            owner_id = generate_discord_id()

        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = name
        guild.owner_id = owner_id
        guild.roles = roles or []
        guild.members = members or []
        guild.channels = channels or []
        guild.emojis = emojis or []
        guild.created_at = fake.date_time_between(start_date="-5y", end_date="-1d")
        guild.description = (
            fake.text(max_nb_chars=100) if random.random() < 0.7 else None
        )
        guild.member_count = len(guild.members) or random.randint(5, 10000)
        guild.premium_tier = random.choices(
            [0, 1, 2, 3], weights=[0.7, 0.2, 0.07, 0.03]
        )[0]
        guild.premium_subscription_count = (
            0
            if guild.premium_tier == 0
            else (
                random.randint(2, 15)
                if guild.premium_tier == 1
                else (
                    random.randint(15, 30)
                    if guild.premium_tier == 2
                    else random.randint(30, 100)
                )
            )
        )
        guild.region = random.choice(
            ["us-west", "us-east", "eu-west", "eu-central", "singapore", "brazil"]
        )
        guild.verification_level = random.choice([0, 1, 2, 3, 4])
        guild.explicit_content_filter = random.choice([0, 1, 2])

        # Add methods for getting objects by ID
        guild.get_channel = lambda channel_id: next(
            (c for c in guild.channels if c.id == channel_id), None
        )
        guild.get_member = lambda member_id: next(
            (m for m in guild.members if m.id == member_id), None
        )
        guild.get_role = lambda role_id: next(
            (r for r in guild.roles if r.id == role_id), None
        )

        # Add async methods
        guild.create_text_channel = AsyncMock()
        guild.create_voice_channel = AsyncMock()
        guild.create_category = AsyncMock()
        guild.create_role = AsyncMock()
        guild.fetch_member = AsyncMock()

        return guild


class MockChannelFactory:
    """Factory for creating mock Discord channels."""

    @staticmethod
    def create_text_channel(
        channel_id: int = None,
        name: str = None,
        guild: Optional[discord.Guild] = None,
        position: int = None,
        topic: Optional[str] = None,
        nsfw: bool = None,
        slowmode_delay: int = None,
        category: Optional[discord.CategoryChannel] = None,
    ) -> discord.TextChannel:
        """
        Create a mock Discord text channel.

        Args:
            channel_id: The channel ID. If None, generates a random Discord ID.
            name: The channel name. If None, generates a realistic channel name.
            guild: The guild the channel belongs to.
            position: The channel position. If None, generates a random position.
            topic: The channel topic. If None, may generate a random topic.
            nsfw: Whether the channel is NSFW. If None, randomly determines.
            slowmode_delay: The slowmode delay in seconds. If None, randomly determines.
            category: The category the channel belongs to.

        Returns:
            A mock Discord text channel.
        """
        # Generate realistic data if not provided
        if channel_id is None:
            channel_id = generate_discord_id()

        if name is None:
            # Generate a realistic channel name
            channel_types = [
                lambda: fake.word().lower(),  # Single word
                lambda: f"{fake.word().lower()}-{fake.word().lower()}",  # Two words with hyphen
                lambda: random.choice(
                    [
                        "general",
                        "chat",
                        "discussion",
                        "lounge",
                        "hangout",
                        "welcome",
                        "announcements",
                        "rules",
                        "introductions",
                        "memes",
                        "media",
                        "bot-commands",
                        "voice-text",
                        "gaming",
                        "music",
                        "art",
                        "food",
                        "pets",
                        "tech",
                        "help",
                        "support",
                    ]
                ),
                lambda: f"{fake.word().lower()}-chat",
                lambda: f"{fake.word().lower()}-discussion",
            ]
            name = random.choice(channel_types)()

        if position is None:
            position = random.randint(0, 50)

        if topic is None and random.random() < 0.6:  # 60% chance to have a topic
            topic = fake.sentence()

        if nsfw is None:
            nsfw = random.random() < 0.1  # 10% chance to be NSFW

        if slowmode_delay is None:
            # Most channels have no slowmode, some have short delays, few have long delays
            slowmode_delay = random.choices(
                [0, 5, 10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 21600],
                weights=[
                    0.8,
                    0.05,
                    0.05,
                    0.02,
                    0.02,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.005,
                    0.005,
                    0.005,
                    0.005,
                ],
            )[0]

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id
        channel.name = name
        channel.guild = guild
        channel.position = position
        channel.topic = topic
        channel.nsfw = nsfw
        channel.slowmode_delay = slowmode_delay
        channel.category = category
        channel.type = discord.ChannelType.text
        channel.mention = f"<#{channel_id}>"
        channel.created_at = fake.date_time_between(start_date="-2y", end_date="now")
        channel.last_message_id = (
            generate_discord_id() if random.random() < 0.9 else None
        )

        # Add async methods
        channel.send = AsyncMock()
        channel.delete = AsyncMock()
        channel.edit = AsyncMock()
        channel.create_webhook = AsyncMock()
        channel.history = AsyncMock(return_value=MagicMock())
        channel.purge = AsyncMock()

        return channel

    @staticmethod
    def create_voice_channel(
        channel_id: int = 444555666,
        name: str = "test-voice",
        guild: Optional[discord.Guild] = None,
        position: int = 0,
        user_limit: int = 0,
        bitrate: int = 64000,
        category: Optional[discord.CategoryChannel] = None,
    ) -> discord.VoiceChannel:
        """
        Create a mock Discord voice channel.

        Args:
            channel_id: The channel ID.
            name: The channel name.
            guild: The guild the channel belongs to.
            position: The channel position.
            user_limit: The user limit.
            bitrate: The bitrate.
            category: The category the channel belongs to.

        Returns:
            A mock Discord voice channel.
        """
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = channel_id
        channel.name = name
        channel.guild = guild
        channel.position = position
        channel.user_limit = user_limit
        channel.bitrate = bitrate
        channel.category = category
        channel.type = discord.ChannelType.voice
        channel.mention = f"<#{channel_id}>"

        # Add async methods
        channel.delete = AsyncMock()
        channel.edit = AsyncMock()

        return channel

    @staticmethod
    def create_category_channel(
        channel_id: int = 777888999,
        name: str = "Test Category",
        guild: Optional[discord.Guild] = None,
        position: int = 0,
    ) -> discord.CategoryChannel:
        """
        Create a mock Discord category channel.

        Args:
            channel_id: The channel ID.
            name: The channel name.
            guild: The guild the channel belongs to.
            position: The channel position.

        Returns:
            A mock Discord category channel.
        """
        channel = MagicMock(spec=discord.CategoryChannel)
        channel.id = channel_id
        channel.name = name
        channel.guild = guild
        channel.position = position
        channel.type = discord.ChannelType.category

        # Add async methods
        channel.delete = AsyncMock()
        channel.edit = AsyncMock()

        return channel


class MockMessageFactory:
    """Factory for creating mock Discord messages."""

    @staticmethod
    def create(
        message_id: int = None,
        content: str = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
        channel: Optional[discord.abc.Messageable] = None,
        guild: Optional[discord.Guild] = None,
        attachments: Optional[List[discord.Attachment]] = None,
        embeds: Optional[List[discord.Embed]] = None,
        reactions: Optional[List[discord.Reaction]] = None,
        mentions: Optional[List[discord.User]] = None,
        mention_everyone: bool = None,
        pinned: bool = None,
        created_at: Optional[Any] = None,
    ) -> discord.Message:
        """
        Create a mock Discord message.

        Args:
            message_id: The message ID. If None, generates a random Discord ID.
            content: The message content. If None, generates realistic message content.
            author: The message author. If None, creates a random user.
            channel: The channel the message was sent in. If None, creates a random channel.
            guild: The guild the message was sent in.
            attachments: The message attachments.
            embeds: The message embeds.
            reactions: The message reactions.
            mentions: The users mentioned in the message.
            mention_everyone: Whether the message mentions everyone. If None, randomly determines.
            pinned: Whether the message is pinned. If None, randomly determines.
            created_at: When the message was created. If None, generates a random date.

        Returns:
            A mock Discord message.
        """
        # Generate realistic data if not provided
        if message_id is None:
            message_id = generate_discord_id()

        if content is None:
            # Generate realistic message content
            content_types = [
                lambda: fake.sentence(),  # Simple sentence
                lambda: fake.paragraph(nb_sentences=1),  # Longer sentence
                lambda: fake.paragraph(
                    nb_sentences=random.randint(1, 3)
                ),  # Multiple sentences
                lambda: random.choice(
                    [
                        "Hello!",
                        "Hi there!",
                        "Hey everyone!",
                        "What's up?",
                        "Good morning!",
                        "Good evening!",
                        "How's it going?",
                        "Anyone online?",
                        "I need help with something",
                        "Check this out!",
                        "This is interesting",
                        "Thoughts?",
                    ]
                ),
                lambda: f"{fake.sentence()} {fake.emoji()}",  # Sentence with emoji
                lambda: f"{fake.emoji()} {fake.sentence()}",  # Emoji with sentence
                lambda: " ".join(
                    [fake.word() for _ in range(random.randint(1, 10))]
                ),  # Random words
            ]
            content = random.choice(content_types)()

        if author is None:
            author = MockUserFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel()

        if mention_everyone is None:
            mention_everyone = random.random() < 0.05  # 5% chance to mention everyone

        if pinned is None:
            pinned = random.random() < 0.02  # 2% chance to be pinned

        if created_at is None:
            created_at = fake.date_time_between(start_date="-30d", end_date="now")

        message = MagicMock(spec=discord.Message)
        message.id = message_id
        message.content = content
        message.author = author
        message.channel = channel
        message.guild = guild
        message.attachments = attachments or []
        message.embeds = embeds or []
        message.reactions = reactions or []
        message.mentions = mentions or []
        message.mention_everyone = mention_everyone
        message.pinned = pinned
        message.created_at = created_at
        message.edited_at = (
            fake.date_time_between(start_date=created_at, end_date="now")
            if random.random() < 0.1
            else None  # 10% chance to be edited
        )
        message.reference = None  # Message reference for replies
        message.flags = MagicMock()  # Message flags
        message.type = discord.MessageType.default

        # Add async methods
        message.delete = AsyncMock()
        message.edit = AsyncMock()
        message.add_reaction = AsyncMock()
        message.remove_reaction = AsyncMock()
        message.pin = AsyncMock()
        message.unpin = AsyncMock()
        message.reply = AsyncMock()

        return message


class MockRoleFactory:
    """Factory for creating mock Discord roles."""

    @staticmethod
    def create(
        role_id: int = None,
        name: str = None,
        color: discord.Color = None,
        hoist: bool = None,
        position: int = None,
        permissions: discord.Permissions = None,
        managed: bool = None,
        mentionable: bool = None,
        guild: Optional[discord.Guild] = None,
    ) -> discord.Role:
        """
        Create a mock Discord role.

        Args:
            role_id: The role ID. If None, generates a random Discord ID.
            name: The role name. If None, generates a realistic role name.
            color: The role color. If None, generates a random color.
            hoist: Whether the role is displayed separately in the member list. If None, randomly determines.
            position: The role position. If None, generates a random position.
            permissions: The role permissions. If None, generates random permissions.
            managed: Whether the role is managed by an integration. If None, randomly determines.
            mentionable: Whether the role is mentionable. If None, randomly determines.
            guild: The guild the role belongs to.

        Returns:
            A mock Discord role.
        """
        # Generate realistic data if not provided
        if role_id is None:
            role_id = generate_discord_id()

        if name is None:
            # Generate a realistic role name
            role_types = [
                lambda: fake.word().capitalize(),  # Single capitalized word
                lambda: f"{fake.word().capitalize()} {fake.word().capitalize()}",  # Two capitalized words
                lambda: random.choice(
                    [
                        "Admin",
                        "Moderator",
                        "Staff",
                        "Helper",
                        "VIP",
                        "Member",
                        "Regular",
                        "Supporter",
                        "Booster",
                        "Bot",
                        "Muted",
                        "Verified",
                        "Trusted",
                        "New Member",
                        "Special Guest",
                        "Partner",
                        "Artist",
                        "Content Creator",
                        "Developer",
                        "Giveaway Winner",
                        "Event Manager",
                    ]
                ),
                lambda: f"Level {random.randint(1, 100)}",  # Level roles
                lambda: f"Tier {random.randint(1, 5)}",  # Tier roles
            ]
            name = random.choice(role_types)()

        if color is None:
            # Generate a random color
            color = discord.Color(random.randint(0, 0xFFFFFF))

        if hoist is None:
            hoist = random.random() < 0.3  # 30% chance to be hoisted

        if position is None:
            position = random.randint(0, 50)

        if permissions is None:
            # Generate random permissions
            permissions = discord.Permissions(
                random.randint(0, discord.Permissions.all().value)
            )

        if managed is None:
            managed = random.random() < 0.1  # 10% chance to be managed

        if mentionable is None:
            mentionable = random.random() < 0.5  # 50% chance to be mentionable

        role = MagicMock(spec=discord.Role)
        role.id = role_id
        role.name = name
        role.color = color
        role.colour = color  # Discord.py uses both spellings
        role.hoist = hoist
        role.position = position
        role.permissions = permissions
        role.managed = managed
        role.mentionable = mentionable
        role.guild = guild
        role.mention = f"<@&{role_id}>"
        role.created_at = fake.date_time_between(start_date="-2y", end_date="now")
        role.tags = None  # Role tags for special roles

        # Add async methods
        role.delete = AsyncMock()
        role.edit = AsyncMock()

        return role


class MockReactionFactory:
    """Factory for creating mock Discord reactions."""

    @staticmethod
    def create(
        emoji: Union[str, discord.Emoji, discord.PartialEmoji] = None,
        count: int = None,
        message: Optional[discord.Message] = None,
        me: bool = None,
        users: Optional[List[Union[discord.User, discord.Member]]] = None,
    ) -> discord.Reaction:
        """
        Create a mock Discord reaction.

        Args:
            emoji: The emoji used for the reaction. If None, generates a random emoji.
            count: The number of users who reacted. If None, generates a random count.
            message: The message the reaction is attached to.
            me: Whether the bot has reacted. If None, randomly determines.
            users: The users who reacted. If None, generates random users.

        Returns:
            A mock Discord reaction.
        """
        # Generate realistic data if not provided
        if emoji is None:
            # Use a simple emoji string
            emoji_options = [
                "👍",
                "👎",
                "❤️",
                "🔥",
                "🎉",
                "😂",
                "😢",
                "🤔",
                "👀",
                "✅",
                "❌",
                "⭐",
                "🌟",
                "💯",
                "🙏",
                "👏",
                "🤣",
                "😍",
                "🥰",
                "😊",
            ]
            emoji = random.choice(emoji_options)

        if count is None:
            # Generate a realistic count (most reactions have few users)
            count_weights = [
                (1, 0.4),  # 40% chance for 1 reaction
                (2, 0.2),  # 20% chance for 2 reactions
                (3, 0.1),  # 10% chance for 3 reactions
                (4, 0.05),  # 5% chance for 4 reactions
                (5, 0.05),  # 5% chance for 5 reactions
                (range(6, 10), 0.1),  # 10% chance for 6-9 reactions
                (range(10, 20), 0.05),  # 5% chance for 10-19 reactions
                (range(20, 50), 0.03),  # 3% chance for 20-49 reactions
                (range(50, 100), 0.02),  # 2% chance for 50-99 reactions
            ]

            count_value = None
            rand_val = random.random()
            cumulative = 0

            for value, weight in count_weights:
                cumulative += weight
                if rand_val <= cumulative:
                    if isinstance(value, range):
                        count_value = random.choice(list(value))
                    else:
                        count_value = value
                    break

            count = count_value or 1  # Default to 1 if something went wrong

        if me is None:
            me = random.random() < 0.2  # 20% chance the bot reacted

        if users is None:
            # Generate random users who reacted
            users = [
                MockUserFactory.create() for _ in range(min(count, 5))
            ]  # Limit to 5 for performance

        if message is None:
            message = MockMessageFactory.create()

        reaction = MagicMock(spec=discord.Reaction)
        reaction.emoji = emoji
        reaction.count = count
        reaction.message = message
        reaction.me = me

        # Add is_custom_emoji method
        reaction.is_custom_emoji = MagicMock(
            return_value=isinstance(emoji, (discord.Emoji, discord.PartialEmoji))
        )

        # Create an async iterator for users who reacted
        class AsyncUserIterator:
            def __init__(self, users_list):
                self.users_list = users_list
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.users_list):
                    raise StopAsyncIteration
                user = self.users_list[self.index]
                self.index += 1
                return user

        def get_users():
            return AsyncUserIterator(users)

        reaction.users = MagicMock(side_effect=get_users)

        # Add async methods
        reaction.remove = AsyncMock()
        reaction.clear = AsyncMock()

        return reaction


class MockInteractionFactory:
    """Factory for creating mock Discord interactions."""

    @staticmethod
    def create(
        interaction_id: int = None,
        user: Optional[Union[discord.User, discord.Member]] = None,
        guild: Optional[discord.Guild] = None,
        channel: Optional[discord.abc.Messageable] = None,
        command_name: str = None,
        command_type: int = 1,  # 1 = chat_input (slash command)
    ) -> discord.Interaction:
        """
        Create a mock Discord interaction.

        Args:
            interaction_id: The interaction ID. If None, generates a random Discord ID.
            user: The user who triggered the interaction. If None, creates a random user.
            guild: The guild the interaction was triggered in.
            channel: The channel the interaction was triggered in. If None, creates a random channel.
            command_name: The name of the command. If None, generates a random command name.
            command_type: The type of command. Default is 1 (chat_input/slash command).

        Returns:
            A mock Discord interaction.
        """
        # Generate realistic data if not provided
        if interaction_id is None:
            interaction_id = generate_discord_id()

        if user is None:
            user = MockUserFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel(guild=guild)

        if command_name is None:
            # Generate a realistic command name
            command_types = [
                lambda: fake.word().lower(),  # Single word
                lambda: f"{fake.word().lower()}_{fake.word().lower()}",  # Two words with underscore
                lambda: random.choice(
                    [
                        "help",
                        "info",
                        "stats",
                        "ping",
                        "ban",
                        "kick",
                        "mute",
                        "warn",
                        "clear",
                        "purge",
                        "role",
                        "user",
                        "server",
                        "play",
                        "skip",
                        "queue",
                        "volume",
                        "search",
                        "weather",
                        "define",
                        "translate",
                        "remind",
                        "poll",
                        "avatar",
                    ]
                ),
            ]
            command_name = random.choice(command_types)()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.id = interaction_id
        interaction.user = user
        interaction.guild = guild
        interaction.channel = channel
        interaction.command = MagicMock()
        interaction.command.name = command_name
        interaction.command.type = command_type
        interaction.extras = {}
        interaction.command_failed = False
        interaction.created_at = fake.date_time_between(
            start_date="-1h", end_date="now"
        )
        interaction.locale = random.choice(
            ["en-US", "en-GB", "de", "fr", "es-ES", "pt-BR", "ja"]
        )
        interaction.app_permissions = discord.Permissions(random.randint(0, 8))

        # Create response object
        response = MagicMock()
        response.send_message = AsyncMock()
        response.defer = AsyncMock()
        response.edit_message = AsyncMock()
        response.send_modal = AsyncMock()
        response.is_done = MagicMock(return_value=False)

        interaction.response = response

        # Add followup object
        followup = MagicMock()
        followup.send = AsyncMock()
        followup.edit_message = AsyncMock()
        followup.delete_message = AsyncMock()

        interaction.followup = followup

        return interaction


class MockContextFactory:
    """Factory for creating mock Discord command contexts."""

    @staticmethod
    def create(
        message: Optional[discord.Message] = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
        guild: Optional[discord.Guild] = None,
        channel: Optional[discord.abc.Messageable] = None,
        bot: Optional[commands.Bot] = None,
        prefix: str = None,
        command_name: str = None,
    ) -> commands.Context:
        """
        Create a mock Discord command context.

        Args:
            message: The message that triggered the command. If None, creates a random message.
            author: The author of the message. If None, creates a random user.
            guild: The guild the message was sent in.
            channel: The channel the message was sent in. If None, creates a random channel.
            bot: The bot instance. If None, creates a TestBot instance.
            prefix: The command prefix. If None, uses a random common prefix.
            command_name: The name of the command. If None, generates a random command name.

        Returns:
            A mock Discord command context.
        """
        # Generate realistic data if not provided
        if prefix is None:
            prefix = random.choice(
                ["!", ".", "?", "$", "%", "&", "/", "-", ">", "+", "~"]
            )

        if command_name is None:
            # Generate a realistic command name (similar to interaction commands)
            command_types = [
                lambda: fake.word().lower(),  # Single word
                lambda: f"{fake.word().lower()}_{fake.word().lower()}",  # Two words with underscore
                lambda: random.choice(
                    [
                        "help",
                        "info",
                        "stats",
                        "ping",
                        "ban",
                        "kick",
                        "mute",
                        "warn",
                        "clear",
                        "purge",
                        "role",
                        "user",
                        "server",
                        "play",
                        "skip",
                        "queue",
                        "volume",
                        "search",
                        "weather",
                        "define",
                        "translate",
                        "remind",
                        "poll",
                        "avatar",
                    ]
                ),
            ]
            command_name = random.choice(command_types)()

        # Create default objects if not provided
        if author is None:
            author = MockUserFactory.create()

        if guild is None:
            guild = MockGuildFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel(guild=guild)

        if message is None:
            message = MockMessageFactory.create(
                content=f"{prefix}{command_name}",
                author=author,
                channel=channel,
                guild=guild,
            )

        if bot is None:
            # Create a simple mock Bot instead of importing TestBot
            bot = MagicMock(spec=commands.Bot)
            bot.user = MockUserFactory.create(bot=True, name="TestBot")
            bot.command_prefix = prefix
            bot.get_cog = MagicMock(return_value=None)
            bot.get_command = MagicMock(return_value=None)
            bot.get_context = AsyncMock()
            bot.wait_for = AsyncMock()
            bot.is_owner = AsyncMock(return_value=False)

        # Create the context
        ctx = MagicMock(spec=commands.Context)
        ctx.message = message
        ctx.author = author
        ctx.guild = guild
        ctx.channel = channel
        ctx.bot = bot
        ctx.prefix = prefix
        ctx.command = MagicMock()
        ctx.command.name = command_name
        ctx.invoked_with = command_name
        ctx.command_failed = False
        ctx.subcommand_passed = None
        ctx.invoked_subcommand = None
        ctx.invoked_parents = []

        # Add async methods
        ctx.send = AsyncMock()
        ctx.reply = AsyncMock()
        ctx.typing = AsyncMock().__aenter__.return_value = None
        ctx.trigger_typing = AsyncMock()

        return ctx


# Example usage
async def example_usage():
    """Example of how to use the mock factories."""
    print("\n=== Basic Usage with Default Values ===")

    # Create a mock user with default values (Faker generated)
    user = MockUserFactory.create()
    print(f"Created mock user: {user.name}#{user.discriminator} (ID: {user.id})")
    print(
        f"Display name: {user.display_name}, Bot: {user.bot}, Created at: {user.created_at}"
    )

    # Create another user with specific values
    custom_user = MockUserFactory.create(user_id=123456789, name="CustomUser")
    print(
        f"Created custom user: {custom_user.name}#{custom_user.discriminator} (ID: {custom_user.id})"
    )

    # Create a mock guild with default values
    guild = MockGuildFactory.create()
    print(f"Created mock guild: {guild.name} (ID: {guild.id})")
    print(f"Owner ID: {guild.owner_id}, Member count: {guild.member_count}")
    print(f"Premium tier: {guild.premium_tier}, Created at: {guild.created_at}")

    # Create a mock text channel with default values
    channel = MockChannelFactory.create_text_channel(guild=guild)
    print(f"Created mock channel: #{channel.name} (ID: {channel.id})")
    print(
        f"Topic: {channel.topic}, NSFW: {channel.nsfw}, Slowmode: {channel.slowmode_delay}s"
    )

    # Create a mock message with default values
    message = MockMessageFactory.create(author=user, channel=channel, guild=guild)
    print(f"Created mock message: '{message.content}' by {message.author.name}")
    print(f"Created at: {message.created_at}, Edited: {message.edited_at is not None}")

    print("\n=== Creating Multiple Random Objects ===")

    # Create multiple random users
    users = [MockUserFactory.create() for _ in range(3)]
    for i, u in enumerate(users):
        print(f"Random user {i+1}: {u.name}#{u.discriminator}")

    # Create multiple random channels
    channels = [MockChannelFactory.create_text_channel(guild=guild) for _ in range(3)]
    for i, c in enumerate(channels):
        print(f"Random channel {i+1}: #{c.name}")

    # Create multiple random messages
    messages = [
        MockMessageFactory.create(
            author=random.choice(users), channel=random.choice(channels)
        )
        for _ in range(3)
    ]
    for i, m in enumerate(messages):
        print(
            f"Random message {i+1}: '{m.content}' by {m.author.name} in #{m.channel.name}"
        )

    print("\n=== Testing Mock Methods ===")

    # Create a mock interaction
    interaction = MockInteractionFactory.create(user=user, guild=guild, channel=channel)
    print(f"Created mock interaction for command: {interaction.command.name}")

    # Create a mock context
    ctx = MockContextFactory.create(
        author=user, guild=guild, channel=channel, command_name="test_command"
    )
    print(f"Created mock context for command: {ctx.command.name}")

    # Test sending a message with the mock channel
    await channel.send("Test message")
    channel.send.assert_called_once_with("Test message")
    print("Successfully called channel.send()")

    # Test responding to the mock interaction
    await interaction.response.send_message("Test response")
    interaction.response.send_message.assert_called_once_with("Test response")
    print("Successfully called interaction.response.send_message()")

    print("\n=== Example Complete ===")


if __name__ == "__main__":
    # Run the example usage
    asyncio.run(example_usage())
