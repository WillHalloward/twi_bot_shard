import imghdr
import logging
import os
from datetime import datetime
from logging import PlaceHolder

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import re
import AO3

ao3_pattern = r'https?://archiveofourown\.org/.*'
discord_file_pattern = r'https?://cdn\.discordapp\.com/attachments/\d+/\d+/[^?\s]+(?:\?.*?)?'

def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False

def get_quest_name_from_cache(serial, quest_cache):
    for quest in quest_cache:
        if quest['serial'] == int(serial):
            return quest['quest_name']
    return "Unknown"

class InnktoberModal(discord.ui.Modal, title="Repost"):
    def __init__(self, mention: str, jump_url: str, title: str, extra_description=None) -> None:
        super().__init__()

        self.extra_description = extra_description
        self.title_item = discord.ui.TextInput(label="Title", style=discord.TextStyle.short, placeholder="The title of the submission", default=title, required=True)
        self.add_item(self.title_item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()

class InnktoberCog(commands.Cog, name="Innktober"):
    def __init__(self, bot):
        self.bot = bot
        self.repost = app_commands.ContextMenu(
            name="Submit to Innktober",
            callback=self.repost,
        )
        self.bot.tree.add_command(self.repost)
        self.repost_cache = None

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.repost.name, type=self.repost.type)

    async def cog_load(self) -> None:
        self.repost_cache = await self.bot.pg_con.fetch("SELECT * FROM gallery_mementos")

class InnktoberView(discord.ui.View):
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

    @discord.ui.button(label="Text", style=discord.ButtonStyle.secondary, emoji="📝", disabled=False)
    async def text(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 2
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="Discord File", style=discord.ButtonStyle.secondary, emoji="📁", disabled=True)
    async def discord_file(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 3
            self.stop()
            self.interaction = interaction

    @discord.ui.button(label="AO3", style=discord.ButtonStyle.secondary, emoji="📖", disabled=True)
    async def ao3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id == self.invoker.id:
            self.repost_choice = 4
            self.stop()
            self.interaction = interaction

class Innktobermenu(discord.ui.View):
    def __init__(self, mention: str, jump_url: str, title: str, quest_cache,description_item=None) -> None:
        super().__init__()
        self.message = None
        self.title_item = None
        self.description_item = description_item
        self.mention = mention
        self.jump_url = jump_url
        self.title = title
        self.quest_cache = quest_cache

        self.submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.primary, emoji="✅", disabled=True)
        self.submit_button.callback = self.submit_button_callback
        self.add_item(self.submit_button)

        self.set_title_button = discord.ui.Button(label="Set Title", style=discord.ButtonStyle.primary, emoji="📝", disabled=True)
        self.set_title_button.callback = self.set_title_button_callback
        self.add_item(self.set_title_button)

        self.social_media_consent = discord.ui.Select(placeholder="Do you consent do your art being shared on TWI social medias?")
        self.social_media_consent.callback = self.social_media_consent_callback
        self.social_media_consent.add_option(label=f"Yes", value="Yes")
        self.social_media_consent.add_option(label=f"No", value="No")
        self.add_item(self.social_media_consent)

        self.wiki_booru_consent = discord.ui.Select(placeholder="Do you consent to your art being added to the TWI wiki & TWI Booru?", disabled=True)
        self.wiki_booru_consent.callback = self.wiki_booru_consent_callback
        self.wiki_booru_consent.add_option(label=f"Yes", value="Yes")
        self.wiki_booru_consent.add_option(label=f"No", value="No")
        self.add_item(self.wiki_booru_consent)

        self.quest_select = discord.ui.Select(placeholder="Select which quest to submit this artwork for", disabled=True, max_values=min(len(quest_cache), 25), min_values=1)
        self.quest_select.callback = self.quest_select_callback
        self.add_item(self.quest_select)





    async def social_media_consent_callback(self, interaction: discord.Interaction) -> None:
        self.wiki_booru_consent.disabled = False
        self.social_media_consent.placeholder = interaction.data['values'][0]
        await interaction.response.edit_message(view=self)

    async def wiki_booru_consent_callback(self, interaction: discord.Interaction) -> None:
        self.quest_select.disabled = False
        self.wiki_booru_consent.placeholder = interaction.data['values'][0]
        await interaction.response.edit_message(view=self)

    async def quest_select_callback(self, interaction: discord.Interaction) -> None:
        self.set_title_button.disabled = False
        user_choices_labels = [get_quest_name_from_cache(value, self.quest_cache) for value in interaction.data['values']]
        user_choices_display = ", ".join(user_choices_labels)
        self.quest_select.placeholder = user_choices_display
        await interaction.response.edit_message(view=self)

    async def set_title_button_callback(self, interaction: discord.Interaction) -> None:
        modal = InnktoberModal(jump_url=self.jump_url, mention=self.mention, title=self.title, extra_description=self.description_item)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.title_item = modal.title_item.value
        self.submit_button.disabled = False
        await self.message.edit(view=self)

    async def submit_button_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()

class GalleryCog(commands.Cog, name="Innktober"):
    def __init__(self, bot):
        self.bot = bot
        self.repost = app_commands.ContextMenu(
            name="Submit to Innktober",
            callback=self.repost,
        )
        self.bot.tree.add_command(self.repost)
        self.repost_cache = None
        self.quest_cache = None

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.repost.name, type=self.repost.type)

    async def cog_load(self) -> None:
        self.repost_cache = await self.bot.pg_con.fetch("SELECT * FROM gallery_mementos")
        self.quest_cache = await self.bot.pg_con.fetch("SELECT * FROM innktober_quests")

    @app_commands.default_permissions(ban_members=True)
    async def repost(self, interaction: discord.Interaction, message: discord.Message) -> None:
        is_moderator = any(role.id == 346842813687922689 for role in interaction.user.roles)
        if message.author.id != interaction.user.id and not is_moderator:
            await interaction.response.send_message("You can only submit your own posts to innktober", ephemeral=True)
            return
        repost_type = []
        if message.attachments:
            repost_type.append(1)
        if re.search(discord_file_pattern, message.content):
            repost_type.append(3)
        if re.search(ao3_pattern, message.content):
            repost_type.append(4)
        if not repost_type:
            repost_type.append(2)


        if repost_type:
            view = InnktoberView(invoker=interaction.user)
            embed = discord.Embed(title="Repost", description="I found the following submittable content in that message", color=discord.Color.green())
            if 1 in repost_type:
                embed.add_field(name="Attachment", value=f"I found {len(message.attachments)} attachments", inline=False)
                view.attachment.disabled = False
            if 3 in repost_type:
                embed.add_field(name="Discord File", value=f"I found a discord file: {re.search(discord_file_pattern, message.content).group(0)}", inline=False)
                view.discord_file.disabled = False
            if 2 in repost_type:
                embed.add_field(name="Text", value="I can also submit the text in the message.", inline=False)
            embed.add_field(name="Please select the type of submission you want to do", value="If you want to submit multiple types, you will have to do it one by one", inline=False)
            if 4 in repost_type:
                embed.add_field(name="AO3 Link", value=f"I found an AO3 link: {re.search(ao3_pattern, message.content).group(0)}", inline=False)
                view.ao3.disabled = False
            await interaction.response.send_message(embed=embed, view=view)
            if not await view.wait():
                await interaction.delete_original_response()
                match view.repost_choice:
                    case 1:
                        await self.repost_attachment(view.interaction, message)
                    case 2:
                        await self.repost_text(view.interaction, message)
                    case 3:
                        try:
                            await self.repost_discord_file(view.interaction, message)
                        except Exception as e:
                            logging.exception(e)
                    case 4:
                        await self.repost_ao3(view.interaction, message)
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
            menu = Innktobermenu(jump_url=message.jump_url, mention=message.author.mention, quest_cache=self.quest_cache,title="")
            for i, quest in enumerate(self.quest_cache):
                if i >= 25:
                    break
                menu.quest_select.add_option(label=quest['quest_name'], value=quest['serial'])
            await interaction.response.send_message(ephemeral=True, view=menu)
            menu.message = await interaction.original_response()
            if not await menu.wait() and menu.social_media_consent.values:
                await interaction.delete_original_response()
                x = 1
                embed_list = []
                files_list = []

                repost_channel = interaction.guild.get_channel_or_thread(1290379677499654165)
                if type(repost_channel) != discord.channel.ForumChannel:
                    for attachment in message.attachments:
                        embed = discord.Embed(title=menu.title_item, description=menu.description_item, url=message.jump_url)
                        embed.set_thumbnail(url=message.author.display_avatar.url)
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
                    embed.set_thumbnail(url=message.author.display_avatar.url)
                    await repost_channel.create_thread(name=menu.title_item, embed=embed, files=list_of_files)
            else:
                await interaction.delete_original_response()
        else:
            logging.warning(f"Unsupported attachment, {', '.join([attachment.content_type for attachment in message.attachments])}")
            await interaction.response.send_message(f"I could not find a supported attachment in that message. Attachment types: {', '.join([attachment.content_type for attachment in message.attachments])}", ephemeral=True)


    async def repost_text(self, interaction: discord.Interaction, message: discord.Message) -> None:
        menu = Innktobermenu(jump_url=message.jump_url, mention=message.author.mention, title=f"", description_item=message.content, quest_cache=self.quest_cache)
        for i, quest in enumerate(self.quest_cache):
            if i >= 25:
                break
            menu.quest_select.add_option(label=quest['quest_name'], value=quest['serial'])
        await interaction.response.send_message(ephemeral=True, view=menu)
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.social_media_consent.values:
            await interaction.delete_original_response()
            embed = discord.Embed(title=menu.title_item, url=message.jump_url, description=message.content)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="Submitter", value=message.author.mention)
            user_choices_labels = [get_quest_name_from_cache(value, self.quest_cache) for value in menu.quest_select.values]
            user_choices_display = "\n".join(user_choices_labels)
            embed.add_field(name="Quests", value=user_choices_display)
            if interaction.guild.id == 297916314239107072:
                repost_channel = interaction.guild.get_channel_or_thread(964519175320125490)
            else:
                repost_channel = interaction.guild.get_channel_or_thread(1290379677499654165)
            list_of_quest_id = ",".join(menu.quest_select.values) if menu.quest_select.values else ""
            repost_message = await repost_channel.send(embed=embed)
            if menu.social_media_consent.values[0] == "Yes" and interaction.guild.id != 297916314239107072:
                social_media_consent_channel = interaction.guild.get_channel_or_thread(1290389187329003580)
                await social_media_consent_channel.send(embed=embed)
            await self.bot.pg_con.execute("INSERT INTO innktober_submission (user_id, date, message_id, quest_id, repost_message_id, social_media_consent, wiki_booru_consent, submission_type) VALUES ($1,$2,$3,$4,$5,$6,$7,'text')",
                                          message.author.id,
                                          datetime.now(),
                                          message.id,
                                          list_of_quest_id,
                                          repost_message.id,
                                          menu.social_media_consent.values[0] == "Yes",
                                          menu.wiki_booru_consent.values[0] == "Yes",
                                          )
    async def repost_ao3(self, interaction: discord.Interaction, message: discord.Message) -> None:
        url = re.search(ao3_pattern, message.content).group(0)
        work = AO3.Work(AO3.utils.workid_from_url(url))

        menu = Innktobermenu(jump_url=message.jump_url, mention=message.author.mention, title=f"{work.title} - **AO3**", quest_cache=self.quest_cache)
        for quest in self.quest_cache[:25]:
            menu.quest_select.add_option(label=quest['quest_name'], value=quest['serial'])
        await interaction.response.send_message(ephemeral=True, view=menu)
        menu.message = await interaction.original_response()
        if not await menu.wait() and menu.social_media_consent.values:
            await interaction.delete_original_response()
            embed = discord.Embed(title=f"{menu.title_item}", description=f"{menu.description_item}\n{work.summary}", url=url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="Rating", value=work.rating, inline=True)
            embed.add_field(name="Chapters", value=f"{work.nchapters}/{work.expected_chapters if work.expected_chapters is not None else '?'}", inline=True)
            embed.add_field(name="Words", value=f"{int(work.words):,}", inline=True)
            user_choices_labels = [get_quest_name_from_cache(value, self.quest_cache) for value in menu.quest_select.values]
            user_choices_display = "\n".join(user_choices_labels)
            embed.add_field(name="Quests", value=user_choices_display)
            if interaction.guild.id == 297916314239107072:
                repost_channel = interaction.guild.get_channel_or_thread(964519175320125490)
            else:
                repost_channel = interaction.guild.get_channel_or_thread(1290379677499654165)
            repost_message = await repost_channel.send(embed=embed)
            list_of_quest_id = ",".join(menu.quest_select.values) if menu.quest_select.values else ""
            await self.bot.pg_con.execute("INSERT INTO innktober_submission (user_id, date, message_id, quest_id, repost_message_id, social_media_consent, wiki_booru_consent, submission_type) VALUES ($1,$2,$3,$4,$5,$6,$7,'text')",
                                          message.author.id,
                                          datetime.now(),
                                          message.id,
                                          list_of_quest_id,
                                          repost_message.id,
                                          menu.social_media_consent.values[0] == "Yes",
                                          menu.wiki_booru_consent.values[0] == "Yes",
                                          )

    async def repost_discord_file(self, interaction: discord.Interaction, message: discord.Message) -> None:
        boost_level = interaction.guild.premium_tier

        if boost_level >= 2:
            max_file_size = 50 * 1024 * 1024  # 50 MB
        else:
            max_file_size = 8 * 1024 * 1024  # 8 MB
        menu = Innktobermenu(jump_url=message.jump_url, mention=message.author.mention, title=f"Discord File", quest_cache=self.quest_cache)
        for i, quest in enumerate(self.quest_cache):
            if i >= 25:
                break
            menu.quest_select.add_option(label=quest['quest_name'], value=quest['serial'])
        await interaction.response.send_message(ephemeral=True, view=menu)
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
        if not await menu.wait() and menu.social_media_consent.values:
            await interaction.delete_original_response()
            counter = 1
            embed_list = []
            files_list = []
            current_size = 0
            if interaction.guild.id == 297916314239107072:
                repost_channel = interaction.guild.get_channel_or_thread(964519175320125490)
            else:
                repost_channel = interaction.guild.get_channel_or_thread(1290379677499654165)
            for image in sorted(os.listdir(f"{interaction.guild_id}_temp_files")):
                file = discord.File(f"{interaction.guild_id}_temp_files/{image}")
                embed = discord.Embed(title=menu.title_item, description=f"{menu.description_item}", url=url)
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
                repost_message = await repost_channel.send(embeds=embed_list, files=files_list)
            elif embed_list and not files_list:
                repost_message = await repost_channel.send(embeds=embed_list)
            elif files_list and not embed_list:
                repost_message = await repost_channel.send(files=files_list, embed=embed)
            else:
                await interaction.response.send_message("I could not find any images to repost", ephemeral=True)
            for file in os.listdir(f"{interaction.guild_id}_temp_files"):
                os.remove(f"{interaction.guild_id}_temp_files/{file}")
            list_of_quest_id = ",".join(menu.quest_select.values) if menu.quest_select.values else ""
            await self.bot.pg_con.execute("INSERT INTO innktober_submission (user_id, date, message_id, quest_id, repost_message_id, social_media_consent, wiki_booru_consent, submission_type) VALUES ($1,$2,$3,$4,$5,$6,$7,'text')",
                                          message.author.id,
                                          datetime.now(),
                                          message.id,
                                          list_of_quest_id,
                                          repost_message.id,
                                          menu.social_media_consent.values[0] == "Yes",
                                          menu.wiki_booru_consent.values[0] == "Yes",
                                          )
        else:
            await interaction.delete_original_response()


async def setup(bot):
    await bot.add_cog(GalleryCog(bot))
