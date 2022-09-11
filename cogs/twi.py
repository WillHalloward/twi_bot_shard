import json
import logging
from typing import List

import aiohttp
import discord
import praw
from discord import app_commands
from discord.ext import commands
from googleapiclient.discovery import build

import secrets
from cogs.patreon_poll import fetch


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, num=9, **kwargs).execute()
    return res


async def is_bot_channel(ctx):
    return ctx.channel.id == 361694671631548417


reddit = praw.Reddit(client_id=secrets.client_id,
                     client_secret=secrets.client_secret,
                     user_agent=secrets.user_agent,
                     username=secrets.username,
                     password=secrets.password)


class TwiCog(commands.Cog, name="The Wandering Inn"):
    def __init__(self, bot):
        self.bot = bot
        self.invis_text_cache = None

    async def cog_load(self) -> None:
        self.invis_text_cache = await self.bot.pg_con.fetch("SELECT DISTINCT title FROM invisible_text_twi")

    @commands.hybrid_command(
        name="password",
        brief="Information for patreons on how to get the chapter password",
        aliases=['pw'],
        hidden=False,
    )
    async def password(self, ctx):
        allowed_channel_ids = [620021401516113940, 346842161704075265, 521403093892726785, 362248294849576960,
                               359864559361851392, 668721870488469514]
        if ctx.message.channel.id in allowed_channel_ids:
            password = await self.bot.pg_con.fetchrow("SELECT password, link "
                                                      "FROM password_link "
                                                      "WHERE password IS NOT NULL "
                                                      "ORDER BY serial_id DESC "
                                                      "LIMIT 1")
            await ctx.send(password['password'])
            await ctx.send(f"<{password['link']}>")
        else:
            await ctx.send(
                "3 ways.\n"
                "1. Link discord to patreon and go to <#346842161704075265> and check pins or use !pw inside it.\n"
                "If you don't know how to connect discord to patreon use the command !cd\n"
                "2. You will get an email with the password every time pirate posts it.\n"
                "3. go to <https://www.patreon.com/pirateaba> and check the latest posts. It has the password.\n"
            )

    @commands.hybrid_command(
        name="connectdiscord",
        brief="Information for patreons on how to connect their patreon account to discord.",
        aliases=['cd', 'connectpatreon', 'patreon', 'connect'],
        hidden=False,
    )
    async def connect_discord(self, ctx):
        await ctx.send(
            "Check this link https://support.patreon.com/hc/en-us/articles/212052266-How-do-I-receive-my-Discord-role")

    @commands.hybrid_command(
        name="wiki",
        brief="Searches the The Wandering Inn wiki for a matching article.",
        aliases=['w'],
        usage='[Query]',
        hidden=False,
    )
    async def wiki(self, ctx, *, query):
        embed = discord.Embed(title=f"Wiki results search **{query}**")
        async with aiohttp.ClientSession() as session:
            html = await fetch(session,
                               f"https://thewanderinginn.fandom.com/api.php?action=query&generator=search&gsrsearch={query}&format=json&prop=info|images&inprop=url")
        try:
            sorted_json_data = sorted(json.loads(html)['query']['pages'].values(), key=lambda k: k['index'])
        except KeyError:
            await ctx.send(f"I'm sorry, I could not find a article matching **{query}**.")
            return
        for results in sorted_json_data:
            embed.add_field(name="\u200b", value=f"[{results['title']}]({results['fullurl']})", inline=False)
        try:
            async with aiohttp.ClientSession() as session:
                image_json = await fetch(session,
                                         f"https://thewanderinginn.fandom.com/api.php?action=query&format=json&titles={sorted_json_data[0]['images'][0]['title']}&prop=imageinfo&iiprop=url")
            image_urls = next(iter(json.loads(image_json)['query']['pages'].values()))
            embed.set_thumbnail(url=image_urls['imageinfo'][0]['url'])
        except KeyError:
            pass
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="find",
        brief="Does a google search on 'Wanderinginn.com' and returns the results",
        aliases=['F', 'search'],
        usage='[Query]',
        hidden=False,
    )
    @commands.check(is_bot_channel)
    async def find(self, ctx, *, query):
        results = google_search(query, secrets.google_api_key, secrets.google_cse_id)
        if results['searchInformation']['totalResults'] == "0":
            await ctx.send("I could not find anything that matches your search.")
        else:
            embed = discord.Embed(title="Search", description=f"**{query}**")
            for result in results['items']:
                embed.add_field(name=result['title'],
                                value=f"{result['snippet']}\n{result['link']}")
            await ctx.send(embed=embed)

    @find.error
    async def isError(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Please use this command in <#361694671631548417> only. It takes up quite a bit of space.")

    @commands.hybrid_command(
        name="invistext",
        brief="Gives a list of all the invisible text in TWI.",
        aliases=['ht', 'hiddentext', 'hidden_text', 'invisbletext', 'invisible_text', 'it', 'invisitext']
    )
    async def invis_text(self, ctx, *, chapter=None):
        if chapter is None:
            invis_text_chapters = await self.bot.pg_con.fetch(
                "SELECT title, COUNT(*) FROM invisible_text_twi GROUP BY title, date ORDER BY date"
            )
            embed = discord.Embed(title="Chapters with invisible text")
            for posts in invis_text_chapters:
                embed.add_field(name=f"Chapter: {posts['title']}", value=f"{posts['count']}", inline=False)
            await ctx.send(embed=embed)
        else:
            texts = await self.bot.pg_con.fetch(
                "SELECT title, content FROM invisible_text_twi WHERE lower(title) similar to lower($1)",
                chapter)
            if texts:
                embed = discord.Embed(title=f"Search for: **{chapter}** invisible text")
                for text in texts:
                    embed.add_field(name=f"{text['title']}", value=text['content'], inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send("Sorry i could not find any invisible text on that chapter.\n"
                               "Please give me the chapters exact title.")

    @invis_text.autocomplete('chapter')
    async def invis_text_autocomplete(self, ctx, current: str, ) -> List[app_commands.Choice[str]]:
        ln = []
        for x in self.invis_text_cache:
            ln.append(x['title'])
        return [
                   app_commands.Choice(name=title, value=title)
                   for title in ln if current.lower() in title.lower() or current == ""
               ][0:25]

    @commands.hybrid_command(
        name="coloredtext",
        brief="List of all the different colored texts in twi",
        aliases=['ct', 'textcolor', 'tc', 'color', 'colour']
    )
    async def colored_text(self, ctx):
        embed = discord.Embed(title="Twi's different colored text")
        embed.add_field(name="Red skills and classes",
                        value="#FF0000\n"
                              f"{'<:FF0000:666429504834633789>' * 4}"
                              "\n[3.17T](https://wanderinginn.com/2017/09/27/3-17-t/)")
        embed.add_field(name="Ser Raim skill",
                        value="#EB0E0E\n"
                              f"{'<:EB0E0E:666429505019183144>' * 4}"
                              "\n[6.43E](https://wanderinginn.com/2019/09/10/6-43-e/)")
        embed.add_field(name="Ivolethe summoning fire",
                        value="#E01D1D\n"
                              f"{'<:E01D1D:666429504863993908>' * 4}"
                              "\n[Interlude 4](https://wanderinginn.com/2017/12/30/interlude-4/)")
        embed.add_field(name="Unique Skills",
                        value="#99CC00\n"
                              f"{'<:99CC00:666429504998211594>' * 4}"
                              "\n[2.19](https://wanderinginn.com/2017/05/03/2-19/)")
        embed.add_field(name="Erin's landmark skill",
                        value="#FF9900\n"
                              f"{'<:FF9900:666435308480364554>' * 4}"
                              "\n[5.44](https://wanderinginn.com/2018/12/08/5-44/)")
        embed.add_field(name="Divine/Temporary skills",
                        value="#FFD700\n"
                              f"{'<:FFD700:666429505031897107>' * 4}"
                              "\n[4.23E](https://wanderinginn.com/2018/03/27/4-23-e/)")
        embed.add_field(name="Class restoration / Conviction skill",
                        value="#99CCFF\n"
                              f"{'<:99CCFF:667886770679054357>' * 4}"
                              "\n[3.20T](https://wanderinginn.com/2017/10/03/3-20-t/)")
        embed.add_field(name="Winter fae talking",
                        value="#8AE8FF\n"
                              f"{'<:8AE8FF:666429505015119922>' * 4}"
                              "\n[2.06](https://wanderinginn.com/2017/03/28/2-06/)")
        embed.add_field(name="Spring fae talking",
                        value="#96BE50\n"
                              f"{'<:96BE50:666429505014857728>' * 4}"
                              "\n[5.11E](https://wanderinginn.com/2018/08/14/5-11-e/)")
        embed.add_field(name="Grand Queen talking",
                        value="#FFCC00\n"
                              f"{'<:FFCC00:674267820678316052>' * 4}"
                              "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)")
        embed.add_field(name="Silent Queen talking and purple skills",
                        value="#CC99FF\n"
                              f"{'<:CC99FF:674267820732841984>' * 4}"
                              "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)")
        embed.add_field(name="Armored Queen talking",
                        value="#999999\n"
                              f"{'<:999999:674267820820791306>' * 4}"
                              "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)")
        embed.add_field(name="Twisted Queen talking",
                        value="#993300\n"
                              f"{'<:993300:674267820694962186>' * 4}"
                              "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)")
        embed.add_field(name="Flying Queen talking",
                        value="#99CC00\n"
                              f"{'<:99CC00:666429504998211594>' * 4}"
                              "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)")
        embed.add_field(name="Magnolia charm skill",
                        value="#FDDBFF, #FFB8FD,\n#FD78FF, #FB00FF\n"
                              "<:FDDBFF:674370583412080670><:FFB8FD:674385325572751371><:FD78FF:674385325208109088><:FB00FF:674385325522681857>"
                              "\n[2.31](https://wanderinginn.com/2017/06/21/2-31/)")
        embed.add_field(name="Ceria cold skill",
                        value="#CCFFFF, #99CCFF,\n#3366FF\n"
                              "<:CCFFFF:962498665317011527><:99CCFF:667886770679054357><:3366FF:962498751086338088>"
                              "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)")
        embed.add_field(name="Siren water skill",
                        value="#00CCFF\n"
                              f"{'<:00CCFF:962498765879656498>' * 4}"
                              "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)")
        embed.add_field(name="Invisible Skills/Text",
                        value="#0C0E0E,\n"
                              f"{'<:0C0E0E:666452140994330624>' * 4}\n"
                              "[1.08 R](https://wanderinginn.com/2016/12/18/1-08-r//)")
        await ctx.send(embed=embed)

    # @commands.Cog.listener()
    # async def on_message(self, message):
    #     if message.author.id in {579061805335183370, 579060950867640332}:
    #         old_pin = await self.bot.pg_con.fetchrow("SELECT * FROM webhook_pins_twi WHERE webhook_id = $1",
    #                                                  message.webhook_id)
    #         if old_pin:
    #             await self.bot.pg_con.execute(
    #                 "UPDATE webhook_pins_twi set message_id = $1, posted_date = $2 WHERE webhook_id = $3",
    #                 message.id, message.created_at.replace(tzinfo=None), message.webhook_id)
    #             for pin in await message.channel.pins():
    #                 if pin.id == old_pin['message_id']:
    #                     await pin.unpin()
    #                     break
    #         else:
    #             await self.bot.pg_con.execute(
    #                 "INSERT INTO webhook_pins_twi(message_id, webhook_id, posted_date) VALUES ($1,$2,$3)",
    #                 message.id, message.webhook_id, message.created_at.replace(tzinfo=None))
    #         await message.pin()

    @commands.hybrid_command(
        name="updatepassword",
        brief="Updates the password and link from !password",
        aliases=['up', 'update', 'upp'],
        usage='[Password] [Link]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    @app_commands.default_permissions(manage_messages=True)
    async def update_password(self, ctx, password: str, link: str):
        await self.bot.pg_con.execute(
            "INSERT INTO password_link(password, link, user_id, date) VALUES ($1, $2, $3, $4)",
            password, link, ctx.author.id, ctx.message.created_at.replace(tzinfo=None)
        )

    @commands.hybrid_command(name="getrules")
    @commands.is_owner()
    async def get_rules(self, ctx):
        rules_list = await ctx.guild.fetch_automod_rules()
        for rule in rules_list:
            logging.error(f"{rule}, {rule.id}, {rule.name}, {rule.type}, {rule.enabled}, {rule.created_at}, {rule.updated_at}")

    # @commands.command(name="reddit")
    # async def reddit_verification(self, ctx, username):
    #     if username.startswith("/"):
    #         logging.info("Removing first /")
    #         username = username[1:]
    #     if username.startswith("u/"):
    #         logging.info("Removing u/")
    #         username = username[2:]
    #     logging.info(f"Trying to find user {username}")
    #     try:
    #         reddit.subreddit("TWI_Patreon").contributor.add(username)
    #     except RedditAPIException as exception:
    #         for subexception in exception.items:
    #             logging.error(subexception)
    #     try:
    #         await self.bot.pg_con.execute(
    #             """INSERT INTO twi_reddit(
    #             time_added, discord_username, discord_id, reddit_username, currant_patreon, subreddit
    #             )
    #             VALUES (NOW(), $1, $2, $3, True, 'TWI_patreon')""",
    #             ctx.author.name, ctx.author.id, username
    #         )
    #     except asyncpg.UniqueViolationError as e:
    #         logging.exception(f'{e}')
    #         dup_user = await self.bot.pg_con.fetchrow("SELECT reddit_username FROM twi_reddit WHERE discord_id = $1",
    #                                                   ctx.author.id)
    #         await ctx.send(f"You are already in the list with username {dup_user['reddit_username']}")


async def setup(bot):
    await bot.add_cog(TwiCog(bot))
