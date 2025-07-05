import logging
import mimetypes
import os

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import re
import gallery_dl
from sqlalchemy import select
import AO3

from models.tables.gallery import GalleryMementos
from models.tables.creator_links import CreatorLink
from utils.db_service import DatabaseService
from utils.permissions import (
    admin_or_me_check,
    admin_or_me_check_wrapper,
    app_admin_or_me_check,
)
from utils.error_handling import handle_interaction_errors
from utils.decorators import log_command
from utils.validation import validate_interaction_params, validate_string

ao3_pattern = r"https?://archiveofourown\.org/.*"
twitter_pattern = (
    r"((?:https?://)?(?:www\.|mobile\.)?(?:(?:[fv]x)?twitter|x)\.com/[^/]+/status/\d+)"
)
instagram_pattern = r"https?://www.instagram.com/p/[^/]+"
discord_file_pattern = (
    r"https?://cdn\.discordapp\.com/attachments/\d+/\d+/[^?\s]+(?:\?.*?)?"
)


class RepostModal(discord.ui.Modal, title="Repost"):
    def __init__(
        self, mention: str, jump_url: str, title: str, extra_description=None
    ) -> None:
        super().__init__()

        self.extra_description = extra_description
        self.title_item = discord.ui.TextInput(
            label="Title",
            style=discord.TextStyle.short,
            placeholder="The title of the embed",
            default=title,
            required=False,
        )
        self.add_item(self.title_item)
        if extra_description is None:
            self.description_item = discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.long,
                placeholder="The Description of the embed",
                default=f"Created by: {mention}\nSource: {jump_url}",
                required=False,
            )
        else:
            self.description_item = discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.long,
                placeholder="The Description of the embed",
                default=f"Created by: {mention}\nSource: {jump_url}\n{extra_description}",
                required=False,
            )
        self.add_item(self.description_item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()


class RepostMenu(discord.ui.View):
    def __init__(
        self, mention: str, jump_url: str, title: str, description_item=None
    ) -> None:
        super().__init__()
        self.message = None
        self.title_item = None
        self.description_item = description_item
        self.mention = mention
        self.jump_url = jump_url
        self.title = title

        self.channel_select = discord.ui.Select(placeholder="Where to post?")
        self.channel_select.callback = self.channel_select_callback
        self.add_item(self.channel_select)

        self.submit_button = discord.ui.Button(
            label="Submit", style=discord.ButtonStyle.primary, emoji="✅", disabled=True
        )
        self.submit_button.callback = self.submit_callback
        self.add_item(self.submit_button)

        self.title_button = discord.ui.Button(
            label="Set Title",
            style=discord.ButtonStyle.primary,
            emoji="📝",
            disabled=True,
        )
        self.title_button.callback = self.modal_open_callback
        self.add_item(self.title_button)

    async def channel_select_callback(self, interaction: discord.Interaction) -> None:
        for option in self.channel_select.options:
            if int(option.value) == int(self.channel_select.values[0]):
                self.channel_select.placeholder = option.label
        self.title_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def modal_open_callback(self, interaction: discord.Interaction) -> None:
        modal = RepostModal(
            jump_url=self.jump_url,
            mention=self.mention,
            title=self.title,
            extra_description=self.description_item,
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.title_item = modal.title_item.value
        self.description_item = modal.description_item.value
        self.submit_button.disabled = False
        await self.message.edit(view=self)

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()


class ButtonView(discord.ui.View):
    def __init__(self, invoker) -> None:
        super().__init__()
        self.repost_choice = None
        self.invoker = invoker
        self.interaction = None

    @discord.ui.button(
        label="Attachment",
        style=discord.ButtonStyle.secondary,
        emoji="📎",
        disabled=True,
    )
    async def attachment(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 1
            self.stop()
            self.interaction = interaction

    @discord.ui.button(
        label="AO3", style=discord.ButtonStyle.secondary, emoji="📖", disabled=True
    )
    async def ao3(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 2
            self.stop()
            self.interaction = interaction

    @discord.ui.button(
        label="Twitter", style=discord.ButtonStyle.secondary, emoji="🐦", disabled=True
    )
    async def twitter(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 3
            self.stop()
            self.interaction = interaction

    @discord.ui.button(
        label="Instagram",
        style=discord.ButtonStyle.secondary,
        emoji="📸",
        disabled=True,
    )
    async def instagram(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 4
            self.stop()
            self.interaction = interaction

    @discord.ui.button(
        label="Text", style=discord.ButtonStyle.secondary, emoji="📝", disabled=False
    )
    async def text(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 5
            self.stop()
            self.interaction = interaction

    @discord.ui.button(
        label="Discord File",
        style=discord.ButtonStyle.secondary,
        emoji="📁",
        disabled=True,
    )
    async def discord_file(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 6
            self.stop()
            self.interaction = interaction


class GalleryCog(commands.Cog, name="Gallery & Mementos"):
    def __init__(self, bot):
        self.bot = bot
        self.repost = app_commands.ContextMenu(
            name="Repost",
            callback=self.repost,
        )
        self.bot.tree.add_command(self.repost)
        self.repost_cache = None

        # Get repositories from the repository factory
        self.gallery_repo = bot.repo_factory.get_repository(GalleryMementos)
        self.creator_links_repo = bot.repo_factory.get_repository(CreatorLink)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.repost.name, type=self.repost.type)

    async def cog_load(self) -> None:
        # Use repository to load gallery mementos
        self.repost_cache = await self.gallery_repo.get_all()

        # Keep the old method as a fallback
        if not self.repost_cache:
            self.repost_cache = await self.bot.db.fetch(
                "SELECT * FROM gallery_mementos"
            )

    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    @log_command("repost")
    @validate_interaction_params(
        message=lambda x: x if isinstance(x, discord.Message) else None
    )
    async def repost(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Analyze a message and provide options to repost its content to configured channels.

        Args:
            interaction: The Discord interaction
            message: The message to analyze for repostable content
        """
        repost_type = []

        # Check for attachments
        if message.attachments:
            repost_type.append(1)

        # Check for various URL patterns with error handling
        try:
            if message.content and re.search(ao3_pattern, message.content):
                repost_type.append(2)
            if message.content and re.search(twitter_pattern, message.content):
                repost_type.append(3)
            if message.content and re.search(instagram_pattern, message.content):
                repost_type.append(4)
            if message.content and re.search(discord_file_pattern, message.content):
                repost_type.append(6)
        except re.error as e:
            self.logger.error(
                f"Regex error in repost command: {e}",
                extra={
                    "command": "repost",
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "message_id": message.id,
                },
            )
            await interaction.response.send_message(
                "❌ Error analyzing message content. Please try again.", ephemeral=True
            )
            return

        # If no specific content found, default to text repost
        if not repost_type:
            repost_type.append(5)

        if repost_type:
            view = ButtonView(invoker=interaction.user)

            embed = discord.Embed(
                title="Repost",
                description="I found the following repostable content in that message",
                color=discord.Color.green(),
            )
            if 1 in repost_type:
                attachment_count = len(message.attachments)
                embed.add_field(
                    name="📎 Attachments",
                    value=f"Found {attachment_count} attachment{'s' if attachment_count != 1 else ''}",
                    inline=False,
                )
                view.attachment.disabled = False
            if 2 in repost_type:
                try:
                    ao3_match = re.search(ao3_pattern, message.content)
                    ao3_url = ao3_match.group(0) if ao3_match else "Unknown AO3 link"
                    embed.add_field(
                        name="📚 AO3 Link",
                        value=f"Found AO3 link: {ao3_url}",
                        inline=False,
                    )
                    view.ao3.disabled = False
                except (AttributeError, IndexError):
                    self.logger.warning(
                        "Failed to extract AO3 URL from message",
                        extra={
                            "command": "repost",
                            "user_id": interaction.user.id,
                            "message_id": message.id,
                        },
                    )
            if 3 in repost_type:
                try:
                    twitter_match = re.search(twitter_pattern, message.content)
                    twitter_url = (
                        twitter_match.group(0)
                        if twitter_match
                        else "Unknown Twitter link"
                    )
                    embed.add_field(
                        name="🐦 Twitter/X Link",
                        value=f"Found Twitter/X link: {twitter_url}",
                        inline=False,
                    )
                    view.twitter.disabled = False
                except (AttributeError, IndexError):
                    self.logger.warning(
                        "Failed to extract Twitter URL from message",
                        extra={
                            "command": "repost",
                            "user_id": interaction.user.id,
                            "message_id": message.id,
                        },
                    )
            if 4 in repost_type:
                try:
                    instagram_match = re.search(instagram_pattern, message.content)
                    instagram_url = (
                        instagram_match.group(0)
                        if instagram_match
                        else "Unknown Instagram link"
                    )
                    embed.add_field(
                        name="📷 Instagram Link",
                        value=f"Found Instagram link: {instagram_url}",
                        inline=False,
                    )
                    view.instagram.disabled = False
                except (AttributeError, IndexError):
                    self.logger.warning(
                        "Failed to extract Instagram URL from message",
                        extra={
                            "command": "repost",
                            "user_id": interaction.user.id,
                            "message_id": message.id,
                        },
                    )
            if 5 in repost_type:
                embed.add_field(
                    name="📝 Text Content",
                    value="Repost the text content from this message.",
                    inline=False,
                )
            if 6 in repost_type:
                try:
                    discord_file_match = re.search(
                        discord_file_pattern, message.content
                    )
                    discord_file_url = (
                        discord_file_match.group(0)
                        if discord_file_match
                        else "Unknown Discord file"
                    )
                    embed.add_field(
                        name="🔗 Discord File",
                        value=f"Found Discord file: {discord_file_url}",
                        inline=False,
                    )
                    view.discord_file.disabled = False
                except (AttributeError, IndexError):
                    self.logger.warning(
                        "Failed to extract Discord file URL from message",
                        extra={
                            "command": "repost",
                            "user_id": interaction.user.id,
                            "message_id": message.id,
                        },
                    )
            embed.add_field(
                name="📋 Instructions",
                value="Please select the type of repost you want to perform.\n"
                "💡 **Note:** For multiple types, you'll need to run the command again.",
                inline=False,
            )

            try:
                await interaction.response.send_message(embed=embed, view=view)
            except discord.HTTPException as e:
                self.logger.error(
                    f"Failed to send repost menu: {e}",
                    extra={
                        "command": "repost",
                        "user_id": interaction.user.id,
                        "guild_id": interaction.guild_id,
                    },
                )
                await interaction.response.send_message(
                    "❌ Failed to display repost options. Please try again.",
                    ephemeral=True,
                )
                return

            if not await view.wait():
                try:
                    await interaction.delete_original_response()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.HTTPException as e:
                    self.logger.warning(
                        f"Failed to delete original response: {e}",
                        extra={"command": "repost", "user_id": interaction.user.id},
                    )

                # Handle repost choice with comprehensive error handling
                try:
                    match view.repost_choice:
                        case 1:
                            await self.repost_attachment(view.interaction, message)
                        case 2:
                            await self.repost_ao3(view.interaction, message)
                        case 3:
                            await self.repost_twitter(view.interaction, message)
                        case 4:
                            await self.repost_instagram(view.interaction, message)
                        case 5:
                            await self.repost_text(view.interaction, message)
                        case 6:
                            await self.repost_discord_file(view.interaction, message)
                        case _:  # default
                            await view.interaction.response.send_message(
                                "❌ Invalid repost option selected. Please try again.",
                                ephemeral=True,
                            )
                except Exception as e:
                    self.logger.error(
                        f"Error during repost operation: {e}",
                        extra={
                            "command": "repost",
                            "user_id": interaction.user.id,
                            "repost_choice": getattr(view, "repost_choice", "unknown"),
                            "message_id": message.id,
                        },
                    )
                    try:
                        await view.interaction.response.send_message(
                            "❌ An error occurred during the repost operation. Please try again.",
                            ephemeral=True,
                        )
                    except discord.InteractionResponded:
                        await view.interaction.followup.send(
                            "❌ An error occurred during the repost operation. Please try again.",
                            ephemeral=True,
                        )
            else:
                # User didn't make a selection in time
                try:
                    await interaction.delete_original_response()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.HTTPException as e:
                    self.logger.warning(
                        f"Failed to delete timed-out response: {e}",
                        extra={"command": "repost", "user_id": interaction.user.id},
                    )

    @handle_interaction_errors
    @log_command("repost_attachment")
    async def repost_attachment(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Repost message attachments to a selected channel.

        Args:
            interaction: The Discord interaction
            message: The message containing attachments to repost
        """
        # Validate attachments and check for supported content types
        if not message.attachments:
            await interaction.response.send_message(
                "❌ No attachments found in the message.", ephemeral=True
            )
            return

        try:
            supported = any(
                attachment.content_type
                and attachment.content_type.startswith(media_type)
                for attachment in message.attachments
                for media_type in ["image", "video", "audio", "text", "application"]
                if attachment.content_type  # Ensure content_type exists
            )
        except AttributeError as e:
            self.logger.error(
                f"Error checking attachment content types: {e}",
                extra={
                    "command": "repost_attachment",
                    "user_id": interaction.user.id,
                    "message_id": message.id,
                },
            )
            await interaction.response.send_message(
                "❌ Error analyzing attachments. Please try again.", ephemeral=True
            )
            return

        if not supported:
            await interaction.response.send_message(
                "❌ No supported attachment types found. Supported types: images, videos, audio, text, and application files.",
                ephemeral=True,
            )
            return

        if supported:
            menu = RepostMenu(
                jump_url=message.jump_url, mention=message.author.mention, title=""
            )
            # Populate channel options for the current guild
            available_channels = [
                channel
                for channel in self.repost_cache
                if channel.guild_id == interaction.guild_id
            ]

            if not available_channels:
                await interaction.response.send_message(
                    "❌ No repost channels configured for this server. Please ask an admin to set up repost channels first.",
                    ephemeral=True,
                )
                return

            for channel in available_channels:
                menu.channel_select.append_option(
                    option=discord.SelectOption(
                        label=f"#{channel.channel_name}", value=str(channel.channel_id)
                    )
                )

            try:
                await interaction.response.send_message(
                    "📎 Found attachments! Please select where to repost them:",
                    ephemeral=True,
                    view=menu,
                )
            except discord.HTTPException as e:
                self.logger.error(
                    f"Failed to send attachment repost menu: {e}",
                    extra={
                        "command": "repost_attachment",
                        "user_id": interaction.user.id,
                        "guild_id": interaction.guild_id,
                    },
                )
                await interaction.response.send_message(
                    "❌ Failed to display repost options. Please try again.",
                    ephemeral=True,
                )
                return
            try:
                menu.message = await interaction.original_response()
            except discord.HTTPException as e:
                self.logger.error(
                    f"Failed to get original response: {e}",
                    extra={
                        "command": "repost_attachment",
                        "user_id": interaction.user.id,
                    },
                )
                return

            if not await menu.wait() and menu.channel_select.values:
                try:
                    await interaction.delete_original_response()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.HTTPException as e:
                    self.logger.warning(
                        f"Failed to delete original response: {e}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                        },
                    )

                x = 1
                embed_list = []
                files_list = []

                # Get the selected repost channel
                try:
                    repost_channel = interaction.guild.get_channel(
                        int(menu.channel_select.values[0])
                    )
                    if not repost_channel:
                        await interaction.followup.send(
                            "❌ Selected channel not found. It may have been deleted.",
                            ephemeral=True,
                        )
                        return
                except (ValueError, IndexError) as e:
                    self.logger.error(
                        f"Invalid channel selection: {e}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                            "selected_value": (
                                menu.channel_select.values[0]
                                if menu.channel_select.values
                                else "None"
                            ),
                        },
                    )
                    await interaction.followup.send(
                        "❌ Invalid channel selection. Please try again.",
                        ephemeral=True,
                    )
                    return

                # Get creator links for the message author
                try:
                    query_r = await self.creator_links_repo.get_by_user_id(
                        message.author.id
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to fetch creator links: {e}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                            "author_id": message.author.id,
                        },
                    )
                    query_r = []  # Continue without creator links
                # Handle regular channels (non-forum)
                if not isinstance(repost_channel, discord.ForumChannel):
                    self.logger.info(
                        f"Reposting attachments to regular channel: {repost_channel.name}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                            "channel_type": type(repost_channel).__name__,
                            "channel_id": repost_channel.id,
                        },
                    )

                    try:
                        for attachment in message.attachments:
                            # Create embed for each attachment
                            embed = discord.Embed(
                                title=menu.title_item or "Reposted Content",
                                description=menu.description_item
                                or f"Reposted from {message.author.mention}",
                                url=message.jump_url,
                                color=discord.Color.blue(),
                            )
                            embed.set_thumbnail(url=message.author.display_avatar.url)

                            # Add creator links if available
                            if query_r:
                                for query in query_r:
                                    if repost_channel.is_nsfw() or not query.nsfw:
                                        embed.add_field(
                                            name=f"{query.title} {' - **NSFW**' if query.nsfw else ''}",
                                            value=query.link,
                                            inline=False,
                                        )

                            # Handle different attachment types
                            if (
                                attachment.content_type
                                and attachment.content_type.startswith("image")
                            ):
                                embed.set_image(url=attachment.url)
                                embed_list.append(embed)
                                if x == 4:  # Send in batches of 4 embeds
                                    try:
                                        await repost_channel.send(embeds=embed_list)
                                        self.logger.info(
                                            f"Successfully sent {len(embed_list)} image embeds",
                                            extra={
                                                "command": "repost_attachment",
                                                "user_id": interaction.user.id,
                                                "channel_id": repost_channel.id,
                                            },
                                        )
                                    except discord.Forbidden:
                                        await interaction.followup.send(
                                            "❌ I don't have permission to send messages to that channel.",
                                            ephemeral=True,
                                        )
                                        return
                                    except discord.HTTPException as e:
                                        self.logger.error(
                                            f"Failed to send embeds: {e}",
                                            extra={
                                                "command": "repost_attachment",
                                                "user_id": interaction.user.id,
                                                "channel_id": repost_channel.id,
                                            },
                                        )
                                        await interaction.followup.send(
                                            "❌ Failed to send embeds to that channel. Please try again.",
                                            ephemeral=True,
                                        )
                                        return
                                    embed_list = []
                                    x = 1
                                x += 1
                            else:
                                # For non-image attachments, convert to file
                                try:
                                    file = await attachment.to_file()
                                    files_list.append(file)
                                except discord.HTTPException as e:
                                    self.logger.error(
                                        f"Failed to convert attachment to file: {e}",
                                        extra={
                                            "command": "repost_attachment",
                                            "user_id": interaction.user.id,
                                            "attachment_url": attachment.url,
                                        },
                                    )
                                    continue

                        # Send remaining embeds and files
                        try:
                            if embed_list and files_list:
                                await repost_channel.send(
                                    embeds=embed_list, files=files_list
                                )
                            elif embed_list and not files_list:
                                await repost_channel.send(embeds=embed_list)
                            elif files_list and not embed_list:
                                # Create a simple embed for files
                                simple_embed = discord.Embed(
                                    title=menu.title_item or "Reposted Files",
                                    description=menu.description_item
                                    or f"Reposted from {message.author.mention}",
                                    url=message.jump_url,
                                    color=discord.Color.blue(),
                                )
                                await repost_channel.send(
                                    files=files_list, embed=simple_embed
                                )

                            await interaction.followup.send(
                                f"✅ Successfully reposted {len(message.attachments)} attachment(s) to {repost_channel.mention}!",
                                ephemeral=True,
                            )

                        except discord.Forbidden:
                            await interaction.followup.send(
                                "❌ I don't have permission to send messages to that channel.",
                                ephemeral=True,
                            )
                        except discord.HTTPException as e:
                            self.logger.error(
                                f"Failed to send final attachments: {e}",
                                extra={
                                    "command": "repost_attachment",
                                    "user_id": interaction.user.id,
                                    "channel_id": repost_channel.id,
                                },
                            )
                            await interaction.followup.send(
                                "❌ Failed to send attachments to that channel. Please try again.",
                                ephemeral=True,
                            )

                    except Exception as e:
                        self.logger.error(
                            f"Unexpected error during attachment repost: {e}",
                            extra={
                                "command": "repost_attachment",
                                "user_id": interaction.user.id,
                                "channel_id": repost_channel.id,
                            },
                        )
                        await interaction.followup.send(
                            "❌ An unexpected error occurred. Please try again.",
                            ephemeral=True,
                        )
                else:
                    # Handle forum channels
                    self.logger.info(
                        f"Reposting attachments to forum channel: {repost_channel.name}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                            "channel_id": repost_channel.id,
                        },
                    )

                    try:
                        list_of_files = []
                        for attachment in message.attachments:
                            try:
                                file = await attachment.to_file()
                                list_of_files.append(file)
                            except discord.HTTPException as e:
                                self.logger.error(
                                    f"Failed to convert attachment to file: {e}",
                                    extra={
                                        "command": "repost_attachment",
                                        "user_id": interaction.user.id,
                                        "attachment_url": attachment.url,
                                    },
                                )
                                continue

                        if not list_of_files:
                            await interaction.followup.send(
                                "❌ Failed to process any attachments for forum thread.",
                                ephemeral=True,
                            )
                            return

                        embed = discord.Embed(
                            title=menu.title_item or "Reposted Content",
                            description=menu.description_item
                            or f"Reposted from {message.author.mention}",
                            url=message.jump_url,
                            color=discord.Color.green(),
                        )
                        embed.set_thumbnail(url=message.author.display_avatar.url)

                        # Add creator links if available
                        if query_r:
                            for query in query_r:
                                if repost_channel.is_nsfw() or not query.nsfw:
                                    embed.add_field(
                                        name=f"{query.title} {' - **NSFW**' if query.nsfw else ''}",
                                        value=query.link,
                                        inline=False,
                                    )

                        try:
                            thread = await repost_channel.create_thread(
                                name=menu.title_item or "Reposted Content",
                                embed=embed,
                                files=list_of_files,
                            )
                            await interaction.followup.send(
                                f"✅ Successfully created forum thread with {len(list_of_files)} attachment(s): {thread.mention}",
                                ephemeral=True,
                            )

                        except discord.Forbidden:
                            await interaction.followup.send(
                                "❌ I don't have permission to create threads in that forum channel.",
                                ephemeral=True,
                            )
                        except discord.HTTPException as e:
                            self.logger.error(
                                f"Failed to create forum thread: {e}",
                                extra={
                                    "command": "repost_attachment",
                                    "user_id": interaction.user.id,
                                    "channel_id": repost_channel.id,
                                },
                            )
                            await interaction.followup.send(
                                "❌ Failed to create forum thread. Please try again.",
                                ephemeral=True,
                            )

                    except Exception as e:
                        self.logger.error(
                            f"Unexpected error during forum thread creation: {e}",
                            extra={
                                "command": "repost_attachment",
                                "user_id": interaction.user.id,
                                "channel_id": repost_channel.id,
                            },
                        )
                        await interaction.followup.send(
                            "❌ An unexpected error occurred while creating the forum thread.",
                            ephemeral=True,
                        )
            else:
                # User didn't make a selection in time
                try:
                    await interaction.delete_original_response()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.HTTPException as e:
                    self.logger.warning(
                        f"Failed to delete timed-out response: {e}",
                        extra={
                            "command": "repost_attachment",
                            "user_id": interaction.user.id,
                        },
                    )

    async def repost_ao3(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        logging.error(message.content)
        url = re.search(ao3_pattern, message.content).group(0)
        logging.error(url)
        work = AO3.Work(AO3.utils.workid_from_url(url))
        menu = RepostMenu(
            jump_url=message.jump_url,
            mention=message.author.mention,
            title=f"{work.title} - **AO3**",
        )
        for channel in self.repost_cache:
            if channel.guild_id == interaction.guild_id:
                menu.channel_select.append_option(
                    option=discord.SelectOption(
                        label=f"#{channel.channel_name}", value=channel.channel_id
                    )
                )
        await interaction.response.send_message(
            "I found an AO3 link, please select where to repost it",
            ephemeral=True,
            view=menu,
        )
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            embed = discord.Embed(
                title=f"{menu.title_item}",
                description=f"{menu.description_item}\n{work.summary}",
                url=url,
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="Rating", value=work.rating, inline=True)
            embed.add_field(
                name="Warnings", value="\n".join(work.warnings), inline=True
            )
            embed.add_field(name="Categories", value=",".join(work.categories))
            embed.add_field(
                name="Chapters",
                value=f"{work.nchapters}/{work.expected_chapters if work.expected_chapters is not None else '?'}",
                inline=True,
            )
            embed.add_field(name="Words", value=f"{int(work.words):,}", inline=True)
            embed.add_field(name="Status", value=work.status, inline=True)
            repost_channel = interaction.guild.get_channel(
                int(menu.channel_select.values[0])
            )
            query_r = await self.creator_links_repo.get_by_user_id(message.author.id)
            if query_r:
                for x in query_r:
                    if repost_channel.is_nsfw() or not x.nsfw:
                        embed.add_field(
                            name=f"{x.title} {' - **NSFW**' if x.nsfw else ''}",
                            value=x.link,
                            inline=False,
                        )
            await repost_channel.send(embed=embed)

    async def repost_twitter(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        url = re.search(twitter_pattern, message.content).group(0)
        gallery_dl.config.load()
        tweet = gallery_dl.job.DownloadJob(url)
        tweet_content = None
        for x in tweet.extractor:
            if x[0] == 2:
                if x[1] is not None:
                    tweet_content = x[1]
                    break
        if tweet_content is not None:
            content = tweet_content["content"]
            tweet_id = tweet_content["tweet_id"]
            author = tweet_content["author"]
            menu = RepostMenu(
                jump_url=message.jump_url,
                mention=message.author.mention,
                title=f"{author['name']} - **Twitter**",
            )
            for channel in self.repost_cache:
                if channel.guild_id == interaction.guild_id:
                    menu.channel_select.append_option(
                        option=discord.SelectOption(
                            label=f"#{channel.channel_name}", value=channel.channel_id
                        )
                    )
            await interaction.response.send_message(
                "I found an Tweet, please select where to repost it",
                ephemeral=True,
                view=menu,
            )
            menu.message = await interaction.original_response()
            tweet.run()
            if not await menu.wait() and menu.channel_select.values:
                embed_list = []
                files_list = []
                await interaction.delete_original_response()
                repost_channel = interaction.guild.get_channel(
                    int(menu.channel_select.values[0])
                )
                query_r = await self.creator_links_repo.get_by_user_id(
                    message.author.id
                )
                for image in sorted(os.listdir(f"temp_files")):
                    if image.startswith(str(tweet_id)) and not image.endswith(".mp4"):
                        file = discord.File(f"temp_files/{image}")
                        embed = discord.Embed(
                            title=menu.title_item,
                            description=f"{menu.description_item}\n{content}",
                            url=url,
                        )
                        embed.set_image(url=f"attachment://{image}")
                        if query_r:
                            for x in query_r:
                                if repost_channel.is_nsfw() or not x.nsfw:
                                    embed.add_field(
                                        name=f"{x.title} {' - **NSFW**' if x.nsfw else ''}",
                                        value=x.link,
                                        inline=False,
                                    )
                        embed.set_thumbnail(url=author["profile_image"])
                        embed_list.append(embed)
                        files_list.append(file)
                    elif image.startswith(str(tweet_id)) and image.endswith(".mp4"):
                        embed = discord.Embed(
                            title=menu.title_item,
                            description=f"{menu.description_item}\n{content}",
                            url=url,
                        )
                        if query_r:
                            for x in query_r:
                                if repost_channel.is_nsfw() or not x.nsfw:
                                    embed.add_field(
                                        name=f"{x.title} {' - **NSFW**' if x.nsfw else ''}",
                                        value=x.link,
                                        inline=False,
                                    )
                        embed.set_thumbnail(url=author["profile_image"])
                        file = discord.File(f"temp_files/{image}")
                        files_list.append(file)
                if embed_list and files_list:
                    await repost_channel.send(embeds=embed_list, files=files_list)
                elif embed_list and not files_list:
                    await repost_channel.send(embeds=embed_list)
                elif files_list and not embed_list:
                    await repost_channel.send(files=files_list, embed=embed)
                else:
                    await interaction.response.send_message(
                        "I could not find any images to repost", ephemeral=True
                    )
                for file in os.listdir(f"temp_files"):
                    os.remove(f"temp_files/{file}")
            else:
                await interaction.delete_original_response()
        else:
            await interaction.response.send_message(
                "I could not read that twitter url", ephemeral=True
            )

    async def repost_instagram(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_message(
            "Instagram links are not supported yet", ephemeral=True
        )

    async def repost_text(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        menu = RepostMenu(
            jump_url=message.jump_url,
            mention=message.author.mention,
            title=f"",
            description_item=message.content,
        )
        for channel in self.repost_cache:
            if channel.guild_id == interaction.guild_id:
                menu.channel_select.append_option(
                    option=discord.SelectOption(
                        label=f"#{channel.channel_name}", value=channel.channel_id
                    )
                )
        await interaction.response.send_message(
            "I found a text message, please select where to repost it",
            ephemeral=True,
            view=menu,
        )
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            repost_channel = interaction.guild.get_channel(
                int(menu.channel_select.values[0])
            )
            query_r = await self.creator_links_repo.get_by_user_id(message.author.id)
            embed = discord.Embed(
                title=menu.title_item,
                description=menu.description_item,
                url=message.jump_url,
            )
            if query_r:
                for x in query_r:
                    if repost_channel.is_nsfw() or not x.nsfw:
                        embed.add_field(
                            name=f"{x.title} {' - **NSFW**' if x.nsfw else ''}",
                            value=x.link,
                            inline=False,
                        )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await repost_channel.send(embed=embed)

    async def repost_discord_file(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        boost_level = interaction.guild.premium_tier
        if boost_level >= 2:
            max_file_size = 50 * 1024 * 1024  # 50 MB
        else:
            max_file_size = 8 * 1024 * 1024  # 8 MB
        menu = RepostMenu(
            jump_url=message.jump_url,
            mention=message.author.mention,
            title=f"Discord File",
        )
        for channel in self.repost_cache:
            if channel.guild_id == interaction.guild_id:
                menu.channel_select.add_option(
                    label=f"#{channel.channel_name}", value=channel.channel_id
                )
        await interaction.response.send_message(
            "I found a discord file, please select where to repost it",
            ephemeral=True,
            view=menu,
        )
        os.makedirs(f"{interaction.guild_id}_temp_files", exist_ok=True)
        urls = re.findall(discord_file_pattern, message.content)

        # Use the bot's HTTP client for connection pooling
        for counter, url in enumerate(urls, start=1):
            # Download the file using the HTTP client
            filename = f"{message.id}_{counter}.{url.split('.')[-1]}"
            file_path = f"{interaction.guild_id}_temp_files/{filename}"

            success = await self.bot.http_client.download_file(url, file_path)
            if not success:
                logging.error(f"Failed to download {url}")
                continue

        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            counter = 1
            embed_list = []
            files_list = []
            current_size = 0
            repost_channel = interaction.guild.get_channel(
                int(menu.channel_select.values[0])
            )
            query_r = await self.creator_links_repo.get_by_user_id(message.author.id)
            for image in sorted(os.listdir(f"{interaction.guild_id}_temp_files")):
                file = discord.File(f"{interaction.guild_id}_temp_files/{image}")
                embed = discord.Embed(
                    title=menu.title_item,
                    description=f"{menu.description_item}",
                    url=url,
                )
                if query_r:
                    for credit in query_r:
                        if repost_channel.is_nsfw() or not credit.nsfw:
                            embed.add_field(
                                name=f"{credit.title} {' - **NSFW**' if credit.nsfw else ''}",
                                value=credit.link,
                                inline=False,
                            )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                # Check if file is an image using mimetypes
                mime_type, _ = mimetypes.guess_type(
                    f"{interaction.guild_id}_temp_files/{image}"
                )
                if mime_type and mime_type.startswith("image/"):
                    embed.set_image(url=f"attachment://{image}")
                    embed_list.append(embed)
                    counter += 1
                    if counter == 5:
                        try:
                            await repost_channel.send(embeds=embed_list)
                        except (
                            discord.HTTPException,
                            discord.Forbidden,
                            ValueError,
                        ) as e:
                            await interaction.response.send_message(
                                f"Error: {str(e)}", ephemeral=True
                            )
                            raise
                        embed_list.clear()
                        counter = 1
                files_list.append(file)
                current_size += os.path.getsize(
                    f"{interaction.guild_id}_temp_files/{image}"
                )
                if current_size >= max_file_size:
                    try:
                        await repost_channel.send(files=files_list, embed=embed)
                    except (discord.HTTPException, discord.Forbidden, ValueError) as e:
                        await interaction.response.send_message(
                            f"Error: {str(e)}", ephemeral=True
                        )
                        raise
                    files_list.clear()
                    current_size = 0
            if embed_list and files_list:
                await repost_channel.send(embeds=embed_list, files=files_list)
            elif embed_list and not files_list:
                await repost_channel.send(embeds=embed_list)
            elif files_list and not embed_list:
                await repost_channel.send(files=files_list, embed=embed)
            else:
                await interaction.response.send_message(
                    "I could not find any images to repost", ephemeral=True
                )
            for file in os.listdir(f"{interaction.guild_id}_temp_files"):
                os.remove(f"{interaction.guild_id}_temp_files/{file}")
        else:
            await interaction.delete_original_response()

    @app_commands.command(name="set_repost")
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    @log_command("set_repost")
    @validate_interaction_params(
        channel=lambda x: x if isinstance(x, discord.TextChannel) else None
    )
    async def set_repost(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Add or remove a channel from the repost channels list.

        Args:
            interaction: The Discord interaction
            channel: The text channel to add or remove from repost channels
        """
        # Validate channel permissions
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}. "
                "Please ensure I have the 'Send Messages' permission in that channel.",
                ephemeral=True,
            )
            return

        try:
            # Check if channel exists in database
            existing = await self.gallery_repo.get_by_field("channel_id", channel.id)

            if existing:
                # Remove existing channel
                try:
                    await self.gallery_repo.delete(existing[0].channel_name)

                    embed = discord.Embed(
                        title="🗑️ Repost Channel Removed",
                        description=f"Successfully removed {channel.mention} from repost channels.",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="Channel Info",
                        value=f"**Name:** {channel.name}\n**ID:** {channel.id}",
                        inline=False,
                    )

                    self.logger.info(
                        f"Removed repost channel: {channel.name} ({channel.id})",
                        extra={
                            "command": "set_repost",
                            "user_id": interaction.user.id,
                            "guild_id": interaction.guild_id,
                            "channel_id": channel.id,
                            "action": "remove",
                        },
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to remove repost channel: {e}",
                        extra={
                            "command": "set_repost",
                            "user_id": interaction.user.id,
                            "channel_id": channel.id,
                            "action": "remove",
                        },
                    )
                    await interaction.response.send_message(
                        f"❌ Failed to remove {channel.mention} from repost channels. Please try again.",
                        ephemeral=True,
                    )
                    return

            else:
                # Add new channel
                try:
                    await self.gallery_repo.create(
                        channel_name=channel.name,
                        channel_id=channel.id,
                        guild_id=channel.guild.id,
                    )

                    embed = discord.Embed(
                        title="✅ Repost Channel Added",
                        description=f"Successfully added {channel.mention} to repost channels.",
                        color=discord.Color.green(),
                    )
                    embed.add_field(
                        name="Channel Info",
                        value=f"**Name:** {channel.name}\n**ID:** {channel.id}",
                        inline=False,
                    )
                    embed.add_field(
                        name="Usage",
                        value="Users can now select this channel when reposting content.",
                        inline=False,
                    )

                    self.logger.info(
                        f"Added repost channel: {channel.name} ({channel.id})",
                        extra={
                            "command": "set_repost",
                            "user_id": interaction.user.id,
                            "guild_id": interaction.guild_id,
                            "channel_id": channel.id,
                            "action": "add",
                        },
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to add repost channel: {e}",
                        extra={
                            "command": "set_repost",
                            "user_id": interaction.user.id,
                            "channel_id": channel.id,
                            "action": "add",
                        },
                    )
                    await interaction.response.send_message(
                        f"❌ Failed to add {channel.mention} to repost channels. Please try again.",
                        ephemeral=True,
                    )
                    return

            # Send response with embed
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Refresh cache
            try:
                self.repost_cache = await self.gallery_repo.get_all()

                # Keep the old method as a fallback
                if not self.repost_cache:
                    self.repost_cache = await self.bot.db.fetch(
                        "SELECT * FROM gallery_mementos"
                    )

                self.logger.info(
                    f"Refreshed repost cache, now contains {len(self.repost_cache)} channels",
                    extra={
                        "command": "set_repost",
                        "user_id": interaction.user.id,
                        "cache_size": len(self.repost_cache),
                    },
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to refresh repost cache: {e}",
                    extra={"command": "set_repost", "user_id": interaction.user.id},
                )
                # Don't fail the command for cache refresh issues
                await interaction.followup.send(
                    "⚠️ Channel updated successfully, but cache refresh failed. "
                    "Changes may not be immediately visible.",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(
                f"Database error in set_repost: {e}",
                extra={
                    "command": "set_repost",
                    "user_id": interaction.user.id,
                    "channel_id": channel.id,
                },
            )
            await interaction.response.send_message(
                "❌ A database error occurred. Please try again later.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(GalleryCog(bot))
