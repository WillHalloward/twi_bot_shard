import json
import logging
from datetime import datetime, timezone
from operator import itemgetter

import aiohttp
import discord
from discord.ext import commands

import secrets


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


async def fetch(session, url):
    async with session.get(url, cookies=secrets.cookies) as respons:
        return await respons.text()


def is_bot_channel(ctx):
    return ctx.channel.id == 361694671631548417


async def get_poll(bot):
    url = "https://www.patreon.com/api/posts?include=Cpoll.choices%2Cpoll.current_user_responses.poll&filter[campaign_id]=568211"
    while True:
        async with aiohttp.ClientSession(cookies=secrets.cookies) as session:
            html = await fetch(session, url)
            json_data = json.loads(html)
            logging.error(json_data)
            logging.error(json_data.text)
        for posts in json_data['data']:
            if posts['relationships']['poll']['data'] is not None:
                poll_id = await bot.pg_con.fetch("SELECT * FROM poll WHERE id = $1",
                                                 int(posts['relationships']['poll']['data']['id']))
                if not poll_id:
                    async with aiohttp.ClientSession() as session:
                        html = await fetch(session, posts['relationships']['poll']['links']['related'])
                        json_data2 = json.loads(html)
                    open_at_converted = datetime.fromisoformat(json_data2['data']['attributes']['created_at'])
                    try:
                        closes_at_converted = datetime.fromisoformat(json_data2['data']['attributes']['closes_at'])
                    except TypeError:
                        closes_at_converted = None
                    title = json_data2['data']['attributes']['question_text']
                    if closes_at_converted is None or closes_at_converted < datetime.now(timezone.utc):
                        await bot.pg_con.execute(
                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, total_votes, "
                            "expired, num_options) "
                            "VALUES ($1,$2,$3,$4,$5,$6,$7, TRUE, $8)",
                            posts['relationships']['poll']['links']['related'],
                            posts['attributes']['patreon_url'],
                            int(posts['relationships']['poll']['data']['id']),
                            open_at_converted,
                            closes_at_converted,
                            title,
                            int(json_data2["data"]["attributes"]["num_responses"]),
                            len(json_data2['data']['relationships']['choices']['data']))
                        for i in range(0, len(json_data2['data']['relationships']['choices']['data'])):
                            await bot.pg_con.execute(
                                "INSERT INTO poll_option(option_text, poll_id, num_votes, option_id)"
                                "VALUES ($1,$2,$3,$4)",
                                json_data2['included'][i]['attributes']['text_content'],
                                int(posts['relationships']['poll']['data']['id']),
                                int(json_data2['included'][i]['attributes']['num_responses']),
                                int(json_data2['data']['relationships']['choices']['data'][i]['id']))
                    else:
                        await bot.pg_con.execute(
                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, expired, "
                            "num_options) "
                            "VALUES ($1,$2,$3,$4,$5,$6, FALSE, $7)",
                            posts['relationships']['poll']['links']['related'],
                            posts['attributes']['patreon_url'],
                            int(posts['relationships']['poll']['data']['id']),
                            open_at_converted,
                            closes_at_converted,
                            title,
                            len(json_data2['data']['relationships']['choices']['data']))
        try:
            url = json_data['links']['next']
        except KeyError:
            break


async def p_poll(polls, ctx, bot):
    for poll in polls:
        if not poll['expired']:
            async with aiohttp.ClientSession(cookies=secrets.cookies) as session:
                html = await fetch(session, poll["api_url"])
                json_data = json.loads(html)
            options = []
            for i in range(0, len(json_data['data']['relationships']['choices']['data'])):
                data = (json_data['included'][i]['attributes']['text_content'],
                        json_data['included'][i]['attributes']['num_responses'])
                options.append(data)
            options = sorted(options, key=itemgetter(1), reverse=True)
        else:
            options = await bot.pg_con.fetch(
                "SELECT option_text, num_votes FROM poll_option WHERE poll_id = $1 ORDER BY num_votes DESC",
                poll['id'])
        embed = discord.Embed(title="Poll", color=discord.Color(0x3cd63d),
                              description=f"**[{poll['title']}]({poll['poll_url']})**")
        if poll['expire_date'] is not None:
            time_left = poll["expire_date"] - datetime.now(timezone.utc)
            hours = int(((time_left.total_seconds() // 3600) % 24))
            embed.set_footer(
                text=f"Poll started at {poll['start_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                     f"and {'closed' if poll['expired'] else 'closes'} at "
                     f"{poll['expire_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                     f"({time_left.days} days and {hours} hours {'ago' if poll['expired'] else 'left'})")
        else:
            embed.set_footer(
                text=f"Poll started at {poll['start_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                     f"and does not have a close date")

        for option in options:
            embed.add_field(name=option[0], value=option[1], inline=False)
        await ctx.send(embed=embed)


async def search_poll(bot, query):
    test = await bot.pg_con.fetch(
        "SELECT poll_id, option_text FROM poll_option WHERE tokens @@ plainto_tsquery($1)",
        query)
    embed = discord.Embed(title="Poll search results", color=discord.Color(0x3cd63d),
                          description=f"Query: **{query}**")
    for results in test:
        polls_year = await bot.pg_con.fetchrow(
            "select title, index_serial from poll where id = $1",
            results['poll_id'])
        embed.add_field(name=polls_year['title'], value=f"{polls_year['index_serial']} - {results['option_text']}",
                        inline=False)
    return embed


class PollCog(commands.Cog, name="Poll"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="Poll",
        brief="Posts the latest poll or a specific poll",
        description="Returns a poll by it's given id.",
        aliases=['p'],
        usage='[Id]',
        help="Shows the current active polls if no id is given. If there is no active poll, the latest poll is shown."
             "\nFind the poll id via !PollList or !FindPoll",
        hidden=False
    )
    # @commands.check(is_bot_channel)
    @commands.cooldown(1, 300, commands.BucketType.channel)
    async def poll(self, ctx, id=None):
        if is_bot_channel(ctx):
            self.poll.reset_cooldown(ctx)
        active_polls = await self.bot.pg_con.fetch("SELECT * FROM poll WHERE expire_date > now()")
        if active_polls and id is None:
            await p_poll(active_polls, ctx, self.bot)
        else:
            last_poll = await self.bot.pg_con.fetch("SELECT COUNT (*) FROM poll")
            if id is None:
                id = last_poll[0][0]
            value = await self.bot.pg_con.fetch("SELECT * FROM poll ORDER BY id OFFSET $1 LIMIT 1", int(id) - 1)
            await p_poll(value, ctx, self.bot)

    @poll.error
    async def isError(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Please use this command in <#361694671631548417> only. It takes up quite a bit of space.")

    @commands.command(
        name="PollList",
        brief="Shows the list of poll ids sorted by year.",
        description="",
        aliases=['pl', 'ListPolls'],
        usage='[Year]',
        hidden=False
    )
    @commands.check(is_bot_channel)
    async def poll_list(self, ctx, year=datetime.now(timezone.utc).year):
        polls_years = await self.bot.pg_con.fetch(
            "SELECT title, index_serial FROM poll WHERE date_part('year', start_date) = $1 ORDER BY start_date",
            year)
        if not polls_years:
            await ctx.send("Sorry there were no polls that year that i could find :(")
        else:
            embed = discord.Embed(title="List of polls", color=discord.Color(0x3cd63d),
                                  description=f"**{year}**")
            for polls in polls_years:
                embed.add_field(name=f"{polls['title']}", value=polls['index_serial'], inline=False)
            await ctx.send(embed=embed)

    @poll_list.error
    async def isError(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Please use this command in <#361694671631548417> only. It takes up quite a bit of space.")

    @commands.command(
        name="GetPoll"
    )
    @commands.check(admin_or_me_check)
    async def getpoll(self, ctx):
        await get_poll(self.bot)
        await ctx.send("Done!")

    @commands.command(
        name="FindPoll",
        aliases=['fp', 'SearchPoll'],
        brief="Searches poll questions for a given query",
        usage='[Query]',
        hidden=False
    )
    async def findpoll(self, ctx, *, query):
        await ctx.send(embed=await search_poll(self.bot, query))


def setup(bot):
    bot.add_cog(PollCog(bot))
