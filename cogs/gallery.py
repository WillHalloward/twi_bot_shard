import logging

import discord
from discord import app_commands
from discord.ext import commands
import re
import AO3
from typing import List

ao3_pattern = r'https?://archiveofourown.org/works/\d+'
twitter_pattern = r'https?://twitter.com/[^/]+/status/\d+'
instagram_pattern = r'https?://www.instagram.com/p/[^/]+'


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


class RepostModal(discord.ui.Modal, title="Repost"):
    def __init__(self, mention: str, jump_url: str, title: str) -> None:
        super().__init__()

        self.title_item = discord.ui.TextInput(label="Title", style=discord.TextStyle.short, placeholder="The title of the embed", default=title, required=False)
        self.description_item = discord.ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="The Description of the embed", default=f"Created by: {mention}\nSource: {jump_url}", required=False)
        self.add_item(self.title_item)
        self.add_item(self.description_item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()





class RepostMenu(discord.ui.View):
    def __init__(self, mention: str, jump_url: str, title: str) -> None:
        super().__init__()
        self.message = None
        self.title_item = None
        self.description_item = None
        self.mention = mention
        self.jump_url = jump_url
        self.title = title

        # self.nsfw_toggle = discord.ui.Select(options=[discord.SelectOption(label="True", value="True"), discord.SelectOption(label="False", value="False")], placeholder="NSFW?")
        # self.nsfw_toggle.callback = defer_callback
        # self.add_item(self.nsfw_toggle)

        self.channel_select = discord.ui.Select(placeholder="Where to post?")
        self.channel_select.callback = self.channel_select_callback
        self.add_item(self.channel_select)

        self.submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.primary, emoji="✅", disabled=True)
        self.submit_button.callback = self.submit_callback
        self.add_item(self.submit_button)

        self.modal_button = discord.ui.Button(label="Set Title", style=discord.ButtonStyle.primary, emoji="📝", disabled=True)
        self.modal_button.callback = self.modal_open_callback
        self.add_item(self.modal_button)

    async def channel_select_callback(self, interaction: discord.Interaction) -> None:
        for option in self.channel_select.options:
            if int(option.value) == int(self.channel_select.values[0]):
                self.channel_select.placeholder = option.label
        self.modal_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def modal_open_callback(self, interaction: discord.Interaction) -> None:
        modal = RepostModal(jump_url=self.jump_url, mention=self.mention, title=self.title)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.title_item = modal.title_item.value
        self.description_item = modal.description_item.value
        self.submit_button.disabled = False
        await self.message.edit(view=self)

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.stop()


class GalleryCog(commands.Cog, name="Gallery & Mementos"):
    def __init__(self, bot):
        self.bot = bot
        self.repost = app_commands.ContextMenu(
            name="Repost",
            callback=self.repost,
        )
        self.bot.tree.add_command(self.repost)
        self.repost_cache = None

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.repost.name, type=self.repost.type)

    async def cog_load(self) -> None:
        self.repost_cache = await self.bot.pg_con.fetch("SELECT * FROM gallery_mementos")

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def repost(self, interaction: discord.Interaction, message: discord.Message) -> None:
        if message.attachments:
            # Attachment found
            menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title="")
            for channel in self.repost_cache:
                if channel['guild_id'] == interaction.guild.id:
                    menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
            await interaction.response.send_message("I found an attachment, please select where to repost it", ephemeral=True, view=menu)
            menu.message = await interaction.original_response()
            if not await menu.wait() and menu.channel_select.values:
                await interaction.delete_original_response()
                repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
                x = 1
                embed_list = []
                query_r = await self.bot.pg_con.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC", message.author.id)
                for attachment in message.attachments:
                    embed = discord.Embed(title=menu.title_item, description=menu.description_item, url="https://wanderinginn.com/")
                    embed.set_image(url=attachment.url)
                    if query_r:
                        for query in query_r:
                            if repost_channel.is_nsfw() or not query['nsfw']:
                                embed.add_field(name=f"{query['title']} {' - **NSFW**' if query['nsfw'] else ''}", value=query['link'], inline=False)
                    embed_list.append(embed)
                    if x == 4:
                        await repost_channel.send(embeds=embed_list)
                        embed_list = []
                        x = 1
                    x += 1
                if embed_list:
                    await repost_channel.send(embeds=embed_list)
            else:
                await interaction.delete_original_response()

        elif re.search(ao3_pattern, message.content):
            # AO3 link found
            url = re.search(ao3_pattern, message.content).group(0)
            work = AO3.Work(AO3.utils.workid_from_url(url))
            menu = RepostMenu(jump_url=message.jump_url, mention=message.author.mention, title=work.title)
            for channel in self.repost_cache:
                if channel['guild_id'] == interaction.guild.id:
                    menu.channel_select.append_option(option=discord.SelectOption(label=f"#{channel['channel_name']}", value=channel['channel_id']))
            await interaction.response.send_message("I found an AO3 link, please select where to repost it", ephemeral=True, view=menu)
            menu.message = await interaction.original_response()
            if not await menu.wait() and menu.channel_select.values:
                await interaction.delete_original_response()
                embed = discord.Embed(title=f"{menu.title_item} - **AO3**", description=f"{menu.description_item}\n{work.summary}", url=url)
                repost_channel = interaction.guild.get_channel(int(menu.channel_select.values[0]))
                query_r = await self.bot.pg_con.fetch("SELECT * FROM creator_links WHERE user_id = $1 ORDER BY weight DESC",message.author.id)
                if query_r:
                    for x in query_r:
                        if repost_channel.is_nsfw() or not x['nsfw']:
                            embed.add_field(name=f"{x['title']} {' - **NSFW**' if x['nsfw'] else ''}", value=x['link'], inline=False)
                await repost_channel.send(embed=embed)
        elif re.search(twitter_pattern, message.content):
            # Twitter link found
            await interaction.response.send_message("Twitter links are not supported yet", ephemeral=True)
            pass
        elif re.search(instagram_pattern, message.content):
            # Instagram link found
            await interaction.response.send_message("Instagram links are not supported yet", ephemeral=True)
            pass
        else:
            # No links found and no attachments
            await interaction.response.send_message("I could not find an attachment or link in that message", ephemeral=True)
            pass

    @app_commands.command(
        name="set_repost"
    )
    @commands.check(admin_or_me_check)
    async def set_repost(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if channel.id in [x['channel_id'] for x in self.repost_cache]:
            await self.bot.pg_con.execute("DELETE FROM gallery_mementos WHERE channel_id = $1", channel.id)
            self.repost_cache = await self.bot.pg_con.fetch("SELECT * FROM gallery_mementos")
            await interaction.response.send_message(f"Removed {channel.mention} from repost channels", ephemeral=True)
        else:
            await self.bot.pg_con.execute("INSERT INTO gallery_mementos VALUES ($1, $2, $3)", channel.name, channel.id, channel.guild.id)
            self.repost_cache = await self.bot.pg_con.fetch("SELECT * FROM gallery_mementos")
            await interaction.response.send_message(f"Added {channel.mention} to repost channels", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GalleryCog(bot))
