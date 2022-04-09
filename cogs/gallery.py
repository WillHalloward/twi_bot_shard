import logging

import discord
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


async def set_channel(self, ctx, channel_id: int, channel_name: str):
        await self.bot.pg_con.execute("INSERT INTO gallery_mementos (channel_id, channel_name) "
                                      "VALUES ($1, $2) "
                                      "ON CONFLICT (channel_name) "
                                      "DO UPDATE "
                                      "SET channel_id = excluded.channel_id",
                                      channel_id, channel_name)

def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


class GalleryCog(commands.Cog, name="Gallery & Mementos"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="Gallery",
        brief="Adds a image to #gallery",
        help="'!gallery 123123123 a nice image A nice image' will add a image with the id '123123123' called 'A nice "
             "image' to #gallery\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' **Note you need to use the command "
             "in the same channel as the image**",
        aliases=['g'],
        usage='[Msg Id][Title]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def g(self, ctx, msg_id, *, title):
        await add_to_gallery(self, ctx, msg_id, title, 'gallery')

    @commands.command(
        name="Mementos",
        brief="Adds an image to #mementos",
        help="'!Mementos 123123123 a nice image A nice image' will add a image with the id '123123123' called 'A nice "
             "image' to #mementos\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' **Note you need to use the command "
             "in the same channel as the image**",
        aliases=['m'],
        usage='[message Id] [title]\nEx: !mementos 123123123 A nice meme',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def m(self, ctx, msg_id, *, title):
        await add_to_gallery(self, ctx, msg_id, title, 'mementos')

    @commands.command(
        name="ToBeAdded",
        brief="Adds a image to the channel <#697663359444713482>",
        help="'!ToBeAdded 123123123 nice image' will add a image with the id '123123123' called 'A nice image' to "
             "#To-be-added\n "
             "Get the id of the image by right clicking it and selecting 'Copy id' "
             "\nNote you need to use the command in the same channel as the image",
        aliases=['tba'],
        usage="[Message id] [Title]"
    )
    @commands.check(admin_or_me_check)
    async def to_be_added(self, ctx, msg_id, *, title):
        await add_to_gallery(self, ctx, msg_id, title, 'to_be_added')

    @commands.command(
        name="setGallery",
        brief="Set what channel !gallery posts to",
        aliases=['sg'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_gallery(self, ctx, gallery_id: int):
        await set_channel(self, ctx, gallery_id, "gallery")

    @commands.command(
        name="SetMementos",
        brief="Set what channel !mementos posts to",
        aliases=['sm'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_mementos(self, ctx, mementos_id: int):
        await set_channel(self, ctx, mementos_id, "mementos")

    @commands.command(
        name="SetToBeAdded",
        brief="Set what channel !ToBeAdded posts to",
        aliases=['stba'],
        usage='[Channel id]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    async def set_to_be_added(self, ctx, to_be_added: int):
        await set_channel(self, ctx, to_be_added, "to_be_added")

    @commands.command(
        name="editEmbed",
        brief="Edits the title a of embed by its message id.",
        help="Ex: '!EditEmbed 704581082808320060 New title' will give a new title to the embed with the id "
             "704581082808320060\n "
             "Needs to be used in the same channel as the embed",
        aliases=['ee'],
        usage='[message id] [New title]'
    )
    @commands.check(admin_or_me_check)
    async def editembed(self, ctx, embed_id: int, *, title):
        msg = await ctx.fetch_message(embed_id)
        new_embed = msg.embeds
        new_embed[0].title = title
        await msg.edit(embed=new_embed[0])
        await ctx.message.delete()


def setup(bot):
    bot.add_cog(GalleryCog(bot))
