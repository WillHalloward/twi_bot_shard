from datetime import datetime, timezone
from itertools import cycle

import asyncpg
import discord
from discord.ext import commands, tasks

import gallery
import patreon_poll
import secrets

bot = commands.Bot(
    command_prefix='!',
    description="The wandering inn bot",
    case_insensitive=True, )
bot.remove_command("help")

admin_role_id = 346842813687922689

status = cycle(["Killing the mages of Wistram",
                "Cleaning up a mess",
                "Keeping secrets",
                "Hiding corpses",
                "Mending Pirateaba's broken hands",
                "Longing for Zelkyr",
                "Banishing Chimera to #debates",
                "Hoarding knowledge",
                "Dusting off priceless artifacts"])


@bot.event
async def on_ready():
    status_loop.start()
    print(f'Logged in as {bot.user.name}')
    print('------')


async def create_db_pool():
    bot.pg_con = await asyncpg.create_pool(database="testDB", user="postgres", password=secrets.DB_pass)


@tasks.loop(seconds=10)
async def status_loop():
    await bot.change_presence(activity=discord.Game(next(status)))


@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, "on_error"):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please pass an argument")
    elif isinstance(error, commands.NotOwner):
        await ctx.send(f"Sorry {ctx.author.display_name} only ~~Zelkyr~~ Sara may do that.")
    elif isinstance(error, commands.MissingRole):
        await ctx.send("I'm sorry, you don't seem to have the required role for that")


def admin_or_me_check(ctx):
    if ctx.message.author.id == 268608466690506753:
        return True
    elif ctx.message.author.roles == admin_role_id:
        return True
    else:
        return False


@bot.command(aliases=["gallery"])
@commands.check(admin_or_me_check)
async def g(ctx, msg_id, *, title):
    channel_id = await bot.pg_con.fetchrow("SELECT channel_id FROM gallery_mementos WHERE channel_name = $1", "gallery")
    channel = bot.get_channel(channel_id["channel_id"])
    await gallery.add_to_gallery(ctx, msg_id, title, channel)


@bot.command(aliases=["mementos"])
@commands.check(admin_or_me_check)
async def m(ctx, msg_id, *, title):
    channel_id = await bot.pg_con.fetchrow("SELECT channel_id FROM gallery_mementos WHERE channel_name = $1",
                                           "mementos")
    channel = bot.get_channel(channel_id["channel_id"])
    await gallery.add_to_gallery(ctx, msg_id, title, channel)


@bot.command()
@commands.check(admin_or_me_check)
async def setgallery(ctx, gallery_id: int):
    channel = await bot.pg_con.fetch("SELECT * FROM gallery_mementos WHERE channel_name = $1", "gallery")
    if not channel:
        await bot.pg_con.execute("INSERT INTO gallery_mementos (channel_id, channel_name) VALUES ($1, $2)", gallery_id,
                                 "gallery")
    await bot.pg_con.execute("UPDATE gallery_mementos SET channel_id=$1 WHERE channel_name=$2", gallery_id, "gallery")


@bot.command()
@commands.check(admin_or_me_check)
async def setmementos(ctx, mementos_id: int):
    channel = await bot.pg_con.fetch("SELECT * FROM gallery_mementos WHERE channel_name = $1", "mementos")
    if not channel:
        await bot.pg_con.execute("INSERT INTO gallery_mementos (channel_id, channel_name) VALUES ($1, $2)", mementos_id,
                                 "mementos")
    await bot.pg_con.execute("UPDATE gallery_mementos SET channel_id=$1 WHERE channel_name=$2", mementos_id, "mementos")


@bot.command(aliases=["p"])
async def poll(ctx, x=None):
    active_polls = await bot.pg_con.fetch("SELECT * FROM poll WHERE expire_date > now()")
    if active_polls and x is None:
        await patreon_poll.p_poll(active_polls, ctx, bot)
    else:
        last_poll = await bot.pg_con.fetch("SELECT COUNT (*) FROM poll")
        if x is None:
            x = last_poll[0][0]
        value = await bot.pg_con.fetch("SELECT * FROM poll ORDER BY id OFFSET $1 LIMIT 1", int(x) - 1)
        await patreon_poll.p_poll(value, ctx, bot)


@bot.command(aliases=["pl"])
async def polllist(ctx, year=datetime.now(timezone.utc).year):
    polls_year = await bot.pg_con.fetch(
        "select title, poll_number from (SELECT poll.title, poll.start_date, row_number() OVER (ORDER BY poll.start_date ASC) as poll_number from poll) as numbered_polls where date_part('year', start_date) = $1",
        year)
    if not polls_year:
        await ctx.send("Sorry there were no polls that year that i could find :(")
    else:
        embed = discord.Embed(title="List of polls", color=discord.Color(0x3cd63d),
                              description=f"**{year}**")
        for polls in polls_year:
            embed.add_field(name=f"{polls['title']}", value=polls['poll_number'], inline=False)
        await ctx.send(embed=embed)


@bot.command()
@commands.is_owner()
async def getpoll(ctx):
    await patreon_poll.get_poll(bot)


@bot.command()
async def ping(ctx):
    await ctx.send(f"{round(bot.latency * 1000)} ms")


@bot.command(aliases=["avatar"])
async def av(ctx):
    embed = discord.Embed(title="Avatar", color=discord.Color(0x3cd63d))
    embed.set_image(url=ctx.author.avatar_url)
    await ctx.send(embed=embed)


@bot.command()
async def info(ctx):
    embed = discord.Embed(title=ctx.author.display_name, color=discord.Color(0x3cd63d))
    embed.set_thumbnail(url=ctx.author.avatar_url)
    embed.add_field(name="Account created at", value=ctx.author.created_at.strftime("%d-%m-%Y @ %H:%M:%S"))
    embed.add_field(name="Joined server", value=ctx.author.joined_at.strftime("%d-%m-%Y @ %H:%M:%S"))
    embed.add_field(name="id", value=ctx.author.id)
    embed.add_field(name="Color", value=ctx.author.color)
    roles = ""
    for role in reversed(ctx.message.author.roles):
        if role.is_default():
            pass
        else:
            roles += f"{role.mention}\n"
    if roles is not "":
        embed.add_field(name="Roles", value=roles, inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Help", color=discord.Color(0x3cd63d), description="List of commands")
    embed.add_field(name="!av", value="Posts the full version of your current avatar", inline=False)
    embed.add_field(name="!ping", value="Gives you the latency of the bot", inline=False)
    embed.add_field(name="!info", value="Gives your account information", inline=False)
    embed.add_field(name="!gallery [!g]", value="Use: !gallery [message id] [title]"
                                                "\nEx: !gallery 123123123 a nice image"
                                                "\nPosts the image in the message to a specified channel"
                                                "\nNote: The image needs to be an embed")
    embed.add_field(name="!mementos [!m]", value="Use: !mementos [message id] [title]"
                                                 "\nEx: !mementos 123123123 a good meme"
                                                 "\nPosts the image in the message to a specified channel"
                                                 "\nNote: The image needs to be an embed")
    embed.add_field(name="!setgallery", value="Use: !setgallery [channel id]\n"
                                              "sets which channel !gallery should post in", inline=False)
    embed.add_field(name="!setmementos", value="Use: !setmementos [channel id]\n"
                                               "sets which channel !mementos should post in", inline=False)
    await ctx.send(embed=embed)


bot.loop.run_until_complete(create_db_pool())
bot.run(secrets.bot_token)
