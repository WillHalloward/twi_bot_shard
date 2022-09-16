import logging

import discord
from discord import app_commands
from discord.ext import commands


async def repost_image(self, interaction: discord.Interaction, message: discord.message, destination: str):
    if message.attachments:
        modal = MyModal(jump_url=message.jump_url, mention=message.author.mention)
        for channel in self.channel_ids:
            if channel["channel_name"] == destination and channel['guild_id'] == interaction.guild.id:
                try:
                    channel = self.bot.get_channel(channel["channel_id"])
                except:
                    await interaction.response.send_message("This command has not been properly setup", ephemeral=True)
                    logging.error(f"Could not get channel via id {channel['channel_id']} via /{destination}")
                    return
                await interaction.response.send_modal(modal)
                for attachment in message.attachments:
                    await modal.wait()
                    embed = discord.Embed(title=modal.title_item.value, description=modal.description_item.value)
                    embed.set_image(url=attachment.url)
                    await channel.send(embed=embed)
                    return
        channel = self.channel_ids = await self.bot.pg_con.fetchrow("SELECT channel_id FROM gallery_mementos WHERE channel_name  = $2 and gallery_mementos.guild_id = $1", interaction.guild.id, destination)
        try:
            channel = self.bot.get_channel(channel["channel_id"])
        except:
            await interaction.response.send_message("The channel for this command has not been configured.", ephemeral=True)
            return
        for attachment in message.attachments:
            await modal.wait()
            embed = discord.Embed(title=modal.title_item.value, description=modal.description_item.value)
            embed.set_image(url=attachment.url)
            await channel.send(embed=embed)
            return
    else:
        logging.warning(f"Could not find image on id {message.id} {message.attachments}")
        await interaction.response.send_message("I could not find an attachment with that message id", ephemeral=True)


async def set_channel(self, ctx, channel: discord.TextChannel, channel_name: str):
    await self.bot.pg_con.execute("INSERT INTO gallery_mementos (channel_id, channel_name) "
                                  "VALUES ($1, $2) "
                                  "ON CONFLICT (channel_name) "
                                  "DO UPDATE "
                                  "SET channel_id = excluded.channel_id",
                                  channel.id, channel_name)
    self.channel_ids = await self.bot.pg_con.fetch("SELECT channel_id, channel_name, guild_id FROM gallery_mementos")


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
        await interaction.response.defer()


class GalleryCog(commands.Cog, name="Gallery & Mementos"):
    def __init__(self, bot):
        self.channel_ids = None
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
        self.bot.tree.remove_command(self.pt_mementos.name, type=self.pt_mementos.type)
        self.bot.tree.remove_command(self.pt_tobeadded.name, type=self.pt_tobeadded.type)

    async def cog_load(self) -> None:
        self.channel_ids = await self.bot.pg_con.fetch("SELECT channel_id, channel_name, guild_id FROM gallery_mementos")

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_gallery(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await repost_image(self, interaction, message, "gallery")

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_mementos(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await repost_image(self, interaction, message, "mementos")

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def post_to_toBeAdded(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await repost_image(self, interaction, message, "to_be_added")

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
