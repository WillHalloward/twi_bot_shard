import logging

import discord
from discord import app_commands
from discord.ext import commands


async def add_to_gallery(self, ctx, msg_id, title, channel_name):
    channel_id = await self.bot.pg_con.fetchrow(
        "SELECT channel_id FROM gallery_mementos WHERE channel_name = $1", channel_name)
    try:
        channel = self.bot.get_channel(channel_id["channel_id"])
    except KeyError:
        await ctx.send("The channel for this command has not been configured.")
        logging.warning(f"{ctx.command} channel was not configured.")
        return
    msg = await ctx.fetch_message(msg_id)
    attach = msg.attachments
    if not attach:
        logging.warning(f"Could not find image on id {msg_id}")
        await ctx.send("I could not find an attachment with that message id")
        return
    embed = discord.Embed(title=title, description=f"Created by: {msg.author.mention}\nSource: {msg.jump_url}")
    embed.set_image(url=attach[0].url)
    await channel.send(embed=embed)
    try:
        await ctx.message.delete()
    except discord.NotFound:
        logging.warning(f"The message {ctx.message} was already deleted")
    except discord.Forbidden:
        logging.warning(f"Missing delete message permissions in server {ctx.guild.name}.")


async def set_channel(self, ctx, channel: discord.TextChannel, channel_name: str):
    await self.bot.pg_con.execute("INSERT INTO gallery_mementos (channel_id, channel_name) "
                                  "VALUES ($1, $2) "
                                  "ON CONFLICT (channel_name) "
                                  "DO UPDATE "
                                  "SET channel_id = excluded.channel_id",
                                  channel.id, channel_name)


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


class MyModal(discord.ui.Modal, title="Embed generator"):
    def __init__(self, mention: str, jump_url: str) -> None:
        super().__init__()

        self.title_item = discord.ui.TextInput(label="Title", style=discord.TextStyle.short, placeholder="The title of the embed", default=None, required=False)
        self.description_item = discord.ui.TextInput(label="Title", style=discord.TextStyle.long, placeholder="The Description of the embed", default=f"Created by: {mention}\nSource: {jump_url}", required=False)
        self.add_item(self.title_item)
        self.add_item(self.description_item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Posted!", ephemeral=True)


class GalleryCog(commands.Cog, name="Gallery & Mementos"):
    def __init__(self, bot):
        self.bot = bot
        self.pt_gallery = app_commands.ContextMenu(
            name="Post to #Gallery",
            callback=self.post_to_gallery,
        )
        self.pt_mementos = app_commands.ContextMenu(
            name="Post to #Mementos",
            callback=self.post_to_mementos,
        )
        self.pt_tobeadded = app_commands.ContextMenu(
            name="Post to #To-Be-Added",
            callback=self.post_to_toBeAdded,
        )
        self.bot.tree.add_command(self.pt_gallery)
        self.bot.tree.add_command(self.pt_mementos)
        self.bot.tree.add_command(self.pt_tobeadded)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.pt_gallery.name, type=self.pt_gallery.type)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_gallery(self, interaction: discord.Interaction, message: discord.Message) -> None:
        modal = MyModal(jump_url=message.jump_url, mention=message.author.mention)
        await interaction.response.send_modal(modal)
        channel_id = await self.bot.pg_con.fetchrow(
            "SELECT channel_id FROM gallery_mementos WHERE channel_name = $1", 'gallery')
        try:
            channel = self.bot.get_channel(channel_id["channel_id"])
        except KeyError:
            await interaction.response.send_message("The channel for this command has not been configured.", ephemeral=True)
            return
        attach = message.attachments
        if not attach:
            logging.warning(f"Could not find image on id {message.id}")
            await interaction.response.send_message("I could not find an attachment with that message id", ephemeral=True)
            return
        await modal.wait()
        embed = discord.Embed(title=modal.title_item.value, description=modal.description_item.value)
        embed.set_image(url=attach[0].url)
        await channel.send(embed=embed)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_mementos(self, interaction: discord.Interaction, message: discord.Message) -> None:
        modal = MyModal(jump_url=message.jump_url, mention=message.author.mention)
        await interaction.response.send_modal(modal)
        channel_id = await self.bot.pg_con.fetchrow(
            "SELECT channel_id FROM gallery_mementos WHERE channel_name = $1", 'mementos')
        try:
            channel = self.bot.get_channel(channel_id["channel_id"])
        except KeyError:
            await interaction.response.send_message("The channel for this command has not been configured.", ephemeral=True)
            return
        attach = message.attachments
        if not attach:
            logging.warning(f"Could not find image on id {message.id}")
            await interaction.response.send_message("I could not find an attachment with that message id", ephemeral=True)
            return
        await modal.wait()
        embed = discord.Embed(title=None, description=f"Created by: {message.author.mention}\nSource: {message.jump_url}")
        embed.set_image(url=attach[0].url)
        await channel.send(embed=embed)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_toBeAdded(self, interaction: discord.Interaction, message: discord.Message) -> None:
        modal = MyModal(jump_url=message.jump_url, mention=message.author.mention)
        await interaction.response.send_modal(modal)
        channel_id = await self.bot.pg_con.fetchrow(
            "SELECT channel_id FROM gallery_mementos WHERE channel_name = $1", 'to_be_added')
        try:
            channel = self.bot.get_channel(channel_id["channel_id"])
        except KeyError:
            await interaction.response.send_message("The channel for this command has not been configured.", ephemeral=True)
            return
        attach = message.attachments
        if not attach:
            logging.warning(f"Could not find image on id {message.id}")
            await interaction.response.send_message("I could not find an attachment with that message id", ephemeral=True)
            return
        await modal.wait()
        embed = discord.Embed(title=None, description=f"Created by: {message.author.mention}\nSource: {message.jump_url}")
        embed.set_image(url=attach[0].url)
        await channel.send(embed=embed)

    # TODO Bake all into a single context action
    @commands.hybrid_command(
        name="gallery",
        brief="Adds a image to #gallery",
        help="'!gallery 123123123 a nice image A nice image' will add a image with the id '123123123' called 'A nice "
             "image' to #gallery\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' **Note you need to use the command "
             "in the same channel as the image**",
        aliases=['g'],
        usage='[Msg Id][Title]',
        hidden=False,
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(manage_messages=True)
    async def g(self, ctx, message_id: str, *, title: str):
        await add_to_gallery(self, ctx, int(message_id), title, 'gallery')

    @commands.hybrid_command(
        name="mementos",
        brief="Adds an image to #mementos",
        help="'!Mementos 123123123 a nice image A nice image' will add a image with the id '123123123' called 'A nice "
             "image' to #mementos\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' **Note you need to use the command "
             "in the same channel as the image**",
        aliases=['m'],
        usage='[message Id] [title]\nEx: !mementos 123123123 A nice meme',
        hidden=False,
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(manage_messages=True)
    async def m(self, ctx, message_id: str, *, title: str):
        await add_to_gallery(self, ctx, int(message_id), title, 'mementos')

    @commands.hybrid_command(
        name="tobeadded",
        brief="Adds a image to the channel <#697663359444713482>",
        help="'!ToBeAdded 123123123 nice image' will add a image with the id '123123123' called 'A nice image' to "
             "#To-be-added\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' "
             "\nNote you need to use the command in the same channel as the image",
        aliases=['tba'],
        usage="[Message id] [Title]"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(manage_messages=True)
    async def to_be_added(self, ctx, message_id: str, *, title: str):
        await add_to_gallery(self, ctx, int(message_id), title, 'to_be_added')

    @commands.hybrid_group(name="set")
    @app_commands.default_permissions(manage_messages=True)
    async def set(self, ctx):
        pass

    @set.command(
        name="gallery",
        brief="Set what channel !gallery posts to",
        aliases=['sg'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_gallery(self, ctx, channel: discord.TextChannel):
        await set_channel(self, ctx, channel, "gallery")

    @set.command(
        name="mementos",
        brief="Set what channel !mementos posts to",
        aliases=['sm'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_mementos(self, ctx, channel: discord.TextChannel):
        await set_channel(self, ctx, channel, "mementos")

    @set.command(
        name="tobeadded",
        brief="Set what channel !ToBeAdded posts to",
        aliases=['stba'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_to_be_added(self, ctx, channel: discord.TextChannel):
        await set_channel(self, ctx, channel, "to_be_added")

    @commands.hybrid_command(
        name="editembed",
        brief="Edits the title a of embed by its message id.",
        help="Ex: '!EditEmbed 704581082808320060 New title' will give a new title to the embed with the id "
             "704581082808320060\n "
             "Needs to be used in the same channel as the embed",
        aliases=['ee'],
        usage='[message id] [New title]'
    )
    @commands.check(admin_or_me_check)
    @app_commands.default_permissions(manage_messages=True)
    async def editembed(self, ctx, embed_id: int, *, title):
        msg = await ctx.fetch_message(embed_id)
        new_embed = msg.embeds
        new_embed[0].test_title = title
        await msg.edit(embed=new_embed[0])
        await ctx.message.delete()


async def setup(bot):
    await bot.add_cog(GalleryCog(bot))
