import imghdr
import logging
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
from utils.permissions import admin_or_me_check, admin_or_me_check_wrapper, app_admin_or_me_check

ao3_pattern = r'https?://archiveofourown\.org/.*'
twitter_pattern = r"((?:https?://)?(?:www\.|mobile\.)?(?:(?:[fv]x)?twitter|x)\.com/[^/]+/status/\d+)"
instagram_pattern = r'https?://www.instagram.com/p/[^/]+'
discord_file_pattern = r'https?://cdn\.discordapp\.com/attachments/\d+/\d+/[^?\s]+(?:\?.*?)?'


class RepostModal(discord.ui.Modal, title="Repost"):
    def __init__(self, mention: str, jump_url: str, title: str, extra_description=None) -> None:
        super().__init__()

        self.extra_description = extra_description
        self.title_item = discord.ui.TextInput(label="Title", style=discord.TextStyle.short, placeholder="The title of the embed", default=title, required=False)
        self.add_item(self.title_item)
        if extra_description is None:
            self.description_item = discord.ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="The Description of the embed", default=f"Created by: {mention}\nSource: {jump_url}", required=False)
        else:
            self.description_item = discord.ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="The Description of the embed", default=f"Created by: {mention}\nSource: {jump_url}\n{extra_description}", required=False)
        self.add_item(self.description_item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()


class RepostMenu(discord.ui.View):
    def __init__(self, mention: str, jump_url: str, title: str, description_item=None) -> None:
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

        self.submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.primary, emoji="✅", disabled=True)
        self.submit_button.callback = self.submit_callback
        self.add_item(self.submit_button)

        self.title_button = discord.ui.Button(label="Set Title", style=discord.ButtonStyle.primary, emoji="📝", disabled=True)
        self.title_button.callback = self.modal_open_callback
        self.add_item(self.title_button)

    async def channel_select_callback(self, interaction: discord.Interaction) -> None:
        for option in self.channel_select.options:
            if int(option.value) == int(self.channel_select.values[0]):
                self.channel_select.placeholder = option.label
        self.title_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def modal_open_callback(self, interaction: discord.Interaction) -> None:
        modal = RepostModal(jump_url=self.jump_url, mention=self.mention, title=self.title, extra_description=self.description_item)
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

    @discord.ui.button(label="Attachment", style=discord.ButtonStyle.secondary, emoji="📎", disabled=True)
    async def attachment(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 1
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="AO3", style=discord.ButtonStyle.secondary, emoji="📖", disabled=True)
    async def ao3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 2
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="Twitter", style=discord.ButtonStyle.secondary, emoji="🐦", disabled=True)
    async def twitter(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 3
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="Instagram", style=discord.ButtonStyle.secondary, emoji="📸", disabled=True)
    async def instagram(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 4
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="Text", style=discord.ButtonStyle.secondary, emoji="📝", disabled=False)
    async def text(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 5
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="Discord File", style=discord.ButtonStyle.secondary, emoji="📁", disabled=True)
    async def discord_file(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
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

        # Create database services
        self.gallery_service = DatabaseService(GalleryMementos)
        self.creator_links_service = DatabaseService(CreatorLink)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.repost.name, type=self.repost.type)

    async def cog_load(self) -> None:
        # Use SQLAlchemy to load gallery mementos
        async with await self.bot.get_db_session() as session:
            # Query gallery mementos
            stmt = select(GalleryMementos)
            result = await session.execute(stmt)
            self.repost_cache = result.scalars().all()

        # Keep the old method as a fallback
        if not self.repost_cache:
            self.repost_cache = await self.bot.db.fetch("SELECT * FROM gallery_mementos")

    @app_commands.default_permissions(ban_members=True)
    async def repost(self, interaction: discord.Interaction, message: discord.Message) -> None:
        repost_type = []
        if message.attachments:
            repost_type.append(1)
        if re.search(ao3_pattern, message.content):
            repost_type.append(2)
        if re.search(twitter_pattern, message.content):
            repost_type.append(3)
        if re.search(instagram_pattern, message.content):
            repost_type.append(4)
        if re.search(discord_file_pattern, message.content):
            repost_type.append(6)
        if not repost_type:
            repost_type.append(5)


        if repost_type:
            view = ButtonView(invoker=interaction.user)

            embed = discord.Embed(title="Repost", description="I found the following repostable content in that message", color=discord.Color.green())
            if 1 in repost_type:
                embed.add_field(name="Attachment", value=f"I found {len(message.attachments)} attachments", inline=False)
                view.attachment.disabled = False
            if 2 in repost_type:
                embed.add_field(name="AO3 Link", value=f"I found an AO3 link: {re.search(ao3_pattern, message.content).group(0)}", inline=False)
                view.ao3.disabled = False
            if 3 in repost_type:
                embed.add_field(name="Twitter Link", value=f"I found a Twitter link: {re.search(twitter_pattern, message.content).group(0)}", inline=False)
                view.twitter.disabled = False
            if 4 in repost_type:
                embed.add_field(name="Instagram Link", value=f"I found an Instagram link: {re.search(instagram_pattern, message.content).group(0)}", inline=False)
                view.instagram.disabled = False
            if 5 in repost_type:
                embed.add_field(name="Text", value="I can also repost the text in the message.", inline=False)
            if 6 in repost_type:
                embed.add_field(name="Discord File", value=f"I found a discord file: {re.search(discord_file_pattern, message.content).group(0)}", inline=False)
                view.discord_file.disabled = False
            embed.add_field(name="Please select the type of repost you want to do", value="If you want to repost multiple types, you will have to do it one by one", inline=False)
            await interaction.response.send_message(embed=embed, view=view)
            if not await view.wait():
                await interaction.delete_original_response()
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
                        try:
                            await self.repost_discord_file(view.interaction, message)
                        except Exception as e:
                            logging.exception(e)
                    case _:  # default
                        await interaction.response.send_message("Something appears to have gone wrong", ephemeral=True)
            else:
                try:
                    await interaction.delete_original_response()
                except discord.errors.NotFound:
                    pass

    async def repost_attachment(self, interaction: discord.Interaction, message: discord.Message) -> None:
        supported = any(attachment.content_type.startswith(media_type) for attachment in message.attachments for media_type in ["image", "video", "audio", "text", "application"])
        if supported:
            menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title="")
            for channel in self.repost_cache:
                if channel['guild_id'] == interaction.guild_id:
                    menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
            await interaction.response.send_message("I found an attachment, please select where to repost it", ephemeral=True, view=menu)
            menu.message = await interaction.original_response()
            if not await menu.wait() and menu.channel_select.values:
                await interaction.delete_original_response()
                x = 1
                embed_list = []
                files_list = []

                repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
                query_r = await self.bot.db.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
                if type(repost_channel) != discord.channel.ForumChannel:
                    logging.info(type(repost_channel))
                    for attachment in message.attachments:
                        embed = discord.Embed(title=menu.title_item, description=menu.description_item, url=message.jump_url)
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                        if query_r:
                            for query in query_r:
                                if repost_channel.is_nsfw() or not query['nsfw']:
                                    embed.add_field(name=f"{query['title']} {' - **NSFW**' if query['nsfw'] else ''}", value=query['link'], inline=False)
                        if attachment.content_type.startswith("image"):
                            embed.set_image(url=attachment.url)
                            embed_list.append(embed)
                            if x == 4:
                                try:
                                    await repost_channel.send(embeds=embed_list)
                                except discord.Forbidden:
                                    await interaction.response.send_message("I do not have permission to send messages to that channel", ephemeral=True)
                                except discord.HTTPException:
                                    await interaction.response.send_message("I could not send the embeds to that channel", ephemeral=True)
                                except ValueError:
                                    await interaction.response.send_message("The files or embeds list is not of the appropriate size", ephemeral=True)
                                embed_list = []
                                x = 1
                            x += 1
                        else:
                            files_list.append(await attachment.to_file())
                    if embed_list and files_list:
                        await repost_channel.send(embeds=embed_list, files=files_list)
                    elif embed_list and not files_list:
                        await repost_channel.send(embeds=embed_list)
                    elif files_list and not embed_list:
                        await repost_channel.send(files=files_list, embed=embed)
                else:
                    list_of_files = []
                    for attachment in message.attachments:
                        file = await attachment.to_file()
                        list_of_files.append(file)
                    embed = discord.Embed(title=menu.title_item, description=menu.description_item, url=message.jump_url, color=0x00ff00)
                    # embed.set_thumbnail(url=message.author.display_avatar.url)
                    if query_r:
                        for x in query_r:
                            if interaction.channel.is_nsfw() or not x['nsfw']:
                                embed.add_field(name=f"{x['title']} {' - NSFW' if x['nsfw'] else ''}", value=x['link'], inline=False)
                    await repost_channel.create_thread(name=menu.title_item, embed=embed, files=list_of_files)
            else:
                await interaction.delete_original_response()
        else:
            print("Unsupported attachment")
            await interaction.response.send_message(f"I could not find a supported attachment in that message. Attachment types: {', '.join([attachment.content_type for attachment in message.attachments])}", ephemeral=True)

    async def repost_ao3(self, interaction: discord.Interaction, message: discord.Message) -> None:
        logging.error(message.content)
        url = re.search(ao3_pattern, message.content).group(0)
        logging.error(url)
        work = AO3.Work(AO3.utils.workid_from_url(url))
        menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title=f"{work.title} - **AO3**")
        for channel in self.repost_cache:
            if channel['guild_id'] == interaction.guild_id:
                menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
        await interaction.response.send_message("I found an AO3 link, please select where to repost it", ephemeral=True, view=menu)
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            embed = discord.Embed(title=f"{menu.title_item}", description=f"{menu.description_item}\n{work.summary}", url=url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="Rating", value=work.rating, inline=True)
            embed.add_field(name="Warnings", value="\n".join(work.warnings), inline=True)
            embed.add_field(name="Categories", value=','.join(work.categories))
            embed.add_field(name="Chapters", value=f"{work.nchapters}/{work.expected_chapters if work.expected_chapters is not None else '?'}", inline=True)
            embed.add_field(name="Words", value=f"{int(work.words):,}", inline=True)
            embed.add_field(name="Status", value=work.status, inline=True)
            repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
            query_r = await self.bot.db.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
            if query_r:
                for x in query_r:
                    if repost_channel.is_nsfw() or not x['nsfw']:
                        embed.add_field(name=f"{x['title']} {' - **NSFW**' if x['nsfw'] else ''}", value=x['link'], inline=False)
            await repost_channel.send(embed=embed)

    async def repost_twitter(self, interaction: discord.Interaction, message: discord.Message) -> None:
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
            content = tweet_content['content']
            tweet_id = tweet_content['tweet_id']
            author = tweet_content['author']
            menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title=f"{author['name']} - **Twitter**")
            for channel in self.repost_cache:
                if channel['guild_id'] == interaction.guild_id:
                    menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
            await interaction.response.send_message("I found an Tweet, please select where to repost it", ephemeral=True, view=menu)
            menu.message = await interaction.original_response()
            tweet.run()
            if not await menu.wait() and menu.channel_select.values:
                embed_list = []
                files_list = []
                await interaction.delete_original_response()
                repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
                query_r = await self.bot.db.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
                for image in sorted(os.listdir(f"temp_files")):
                    if image.startswith(str(tweet_id)) and not image.endswith(".mp4"):
                        file = discord.File(f"temp_files/{image}")
                        embed = discord.Embed(title=menu.title_item, description=f"{menu.description_item}\n{content}", url=url)
                        embed.set_image(url=f"attachment://{image}")
                        if query_r:
                            for x in query_r:
                                if repost_channel.is_nsfw() or not x['nsfw']:
                                    embed.add_field(name=f"{x['title']} {' - **NSFW**' if x['nsfw'] else ''}", value=x['link'], inline=False)
                        embed.set_thumbnail(url=author['profile_image'])
                        embed_list.append(embed)
                        files_list.append(file)
                    elif image.startswith(str(tweet_id)) and image.endswith(".mp4"):
                        embed = discord.Embed(title=menu.title_item, description=f"{menu.description_item}\n{content}", url=url)
                        if query_r:
                            for x in query_r:
                                if repost_channel.is_nsfw() or not x['nsfw']:
                                    embed.add_field(name=f"{x['title']} {' - **NSFW**' if x['nsfw'] else ''}", value=x['link'], inline=False)
                        embed.set_thumbnail(url=author['profile_image'])
                        file = discord.File(f"temp_files/{image}")
                        files_list.append(file)
                if embed_list and files_list:
                    await repost_channel.send(embeds=embed_list, files=files_list)
                elif embed_list and not files_list:
                    await repost_channel.send(embeds=embed_list)
                elif files_list and not embed_list:
                    await repost_channel.send(files=files_list, embed=embed)
                else:
                    await interaction.response.send_message("I could not find any images to repost", ephemeral=True)
                for file in os.listdir(f"temp_files"):
                    os.remove(f"temp_files/{file}")
            else:
                await interaction.delete_original_response()
        else:
            await interaction.response.send_message("I could not read that twitter url", ephemeral=True)

    async def repost_instagram(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.send_message("Instagram links are not supported yet", ephemeral=True)

    async def repost_text(self, interaction: discord.Interaction, message: discord.Message) -> None:
        menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title=f"", description_item=message.content)
        for channel in self.repost_cache:
            if channel['guild_id'] == interaction.guild_id:
                menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
        await interaction.response.send_message("I found a text message, please select where to repost it", ephemeral=True, view=menu)
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
            query_r = await self.bot.db.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
            embed = discord.Embed(title=menu.title_item, description=menu.description_item, url=message.jump_url)
            if query_r:
                for x in query_r:
                    if repost_channel.is_nsfw() or not x['nsfw']:
                        embed.add_field(name=f"{x['title']} {' - **NSFW**' if x['nsfw'] else ''}", value=x['link'], inline=False)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await repost_channel.send(embed=embed)

    async def repost_discord_file(self, interaction: discord.Interaction, message: discord.Message) -> None:
        boost_level = interaction.guild.premium_tier
        if boost_level >= 2:
            max_file_size = 50 * 1024 * 1024  # 50 MB
        else:
            max_file_size = 8 * 1024 * 1024  # 8 MB
        menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title=f"Discord File")
        for channel in self.repost_cache:
            if channel['guild_id'] == interaction.guild_id:
                menu.channel_select.add_option(label=f"#{channel['channel_name']}", value=channel['channel_id'])
        await interaction.response.send_message("I found a discord file, please select where to repost it", ephemeral=True, view=menu)
        os.makedirs(f"{interaction.guild_id}_temp_files", exist_ok=True)
        urls = re.findall(discord_file_pattern, message.content)
        async with aiohttp.ClientSession() as session:
            for counter, url in enumerate(urls, start=1):
                async with session.get(url) as response:
                    if response.status != 200:
                        logging.error(f"Failed to download {url}")
                        continue
                    data = await response.read()
                    filename = f"{message.id}_{counter}.{url.split('.')[-1]}"
                    with open(f"{interaction.guild_id}_temp_files/{filename}", "wb") as file:
                        file.write(data)

        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.channel_select.values:
            await interaction.delete_original_response()
            counter = 1
            embed_list = []
            files_list = []
            current_size = 0
            repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
            query_r = await self.bot.db.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
            for image in sorted(os.listdir(f"{interaction.guild_id}_temp_files")):
                file = discord.File(f"{interaction.guild_id}_temp_files/{image}")
                embed = discord.Embed(title=menu.title_item, description=f"{menu.description_item}", url=url)
                if query_r:
                    for credit in query_r:
                        if repost_channel.is_nsfw() or not credit['nsfw']:
                            embed.add_field(name=f"{credit['title']} {' - **NSFW**' if credit['nsfw'] else ''}", value=credit['link'], inline=False)
                embed.set_thumbnail(url=message.author.display_avatar.url)
                if imghdr.what(f"{interaction.guild_id}_temp_files/{image}"):
                    embed.set_image(url=f"attachment://{image}")
                    embed_list.append(embed)
                    counter += 1
                    if counter == 5:
                        try:
                            await repost_channel.send(embeds=embed_list)
                        except (discord.HTTPException, discord.Forbidden, ValueError) as e:
                            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                            raise
                        embed_list.clear()
                        counter = 1
                files_list.append(file)
                current_size += os.path.getsize(f"{interaction.guild_id}_temp_files/{image}")
                if current_size >= max_file_size:
                    try:
                        await repost_channel.send(files=files_list, embed=embed)
                    except (discord.HTTPException, discord.Forbidden, ValueError) as e:
                        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
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
                await interaction.response.send_message("I could not find any images to repost", ephemeral=True)
            for file in os.listdir(f"{interaction.guild_id}_temp_files"):
                os.remove(f"{interaction.guild_id}_temp_files/{file}")
        else:
            await interaction.delete_original_response()

    @app_commands.command(
        name="set_repost"
    )
    @app_commands.check(app_admin_or_me_check)
    async def set_repost(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with self.bot.get_db_session() as session:
            # Check if channel exists in database
            stmt = select(GalleryMementos).where(GalleryMementos.channel_id == channel.id)
            result = await session.execute(stmt)
            existing = result.scalars().first()

            if existing:
                # Delete existing channel
                await session.delete(existing)
                await session.commit()
                await interaction.response.send_message(f"Removed {channel.mention} from repost channels", ephemeral=True)
            else:
                # Add new channel
                new_channel = GalleryMementos(
                    channel_name=channel.name,
                    channel_id=channel.id,
                    guild_id=channel.guild.id
                )
                session.add(new_channel)
                await session.commit()
                await interaction.response.send_message(f"Added {channel.mention} to repost channels", ephemeral=True)

            # Refresh cache
            stmt = select(GalleryMementos)
            result = await session.execute(stmt)
            self.repost_cache = result.scalars().all()

        # Keep the old method as a fallback
        if not self.repost_cache:
            self.repost_cache = await self.bot.db.fetch("SELECT * FROM gallery_mementos")


async def setup(bot):
    await bot.add_cog(GalleryCog(bot))
