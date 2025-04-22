import json
import logging
from datetime import datetime, timezone
from operator import itemgetter

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import secrets


async def fetch(session, url):
    async with session.get(url, cookies=secrets.cookies) as respons:
        return await respons.text()


def is_bot_channel(interaction: discord.Interaction):
    return interaction.channel.id == 361694671631548417


async def get_poll(bot):
    url = "https://www.patreon.com/api/posts?include=Cpoll.choices%2Cpoll.current_user_responses.poll&filter[campaign_id]=568211"
    poll_ids = await bot.db.fetch("SELECT id FROM poll")
    while True:
        async with aiohttp.ClientSession(cookies=secrets.cookies, headers=secrets.headers) as session:
            html = await fetch(session, url)
            try:
                json_data = json.loads(html)
            except Exception as e:
                logging.error(e)
        for posts in json_data['data']:
            if posts['relationships']['poll']['data'] is not None:

                poll_id = await bot.db.fetch("SELECT * FROM poll WHERE id = $1",
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
                        await bot.db.execute(
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
                            await bot.db.execute(
                                "INSERT INTO poll_option(option_text, poll_id, num_votes, option_id)"
                                "VALUES ($1,$2,$3,$4)",
                                json_data2['included'][i]['attributes']['text_content'],
                                int(posts['relationships']['poll']['data']['id']),
                                int(json_data2['included'][i]['attributes']['num_responses']),
                                int(json_data2['data']['relationships']['choices']['data'][i]['id']))
                    else:
                        await bot.db.execute(
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
            logging.error("going to next page")
        except KeyError:
            logging.error("found no more pages")
            break


async def p_poll(polls, interaction, bot):
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
            options = await bot.db.fetch(
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
        await interaction.response.send_message(embed=embed)


async def search_poll(bot, query: str):
    test = await bot.db.fetch(
        "SELECT poll_id, option_text FROM poll_option WHERE tokens @@ plainto_tsquery($1)",
        query)
    embed = discord.Embed(title="Poll search results", color=discord.Color(0x3cd63d),
                          description=f"Query: **{query}**")
    for results in test:
        polls_year = await bot.db.fetchrow(
            "select title, index_serial from poll where id = $1",
            results['poll_id'])
        embed.add_field(name=polls_year['title'], value=f"{polls_year['index_serial']} - {results['option_text']}",
                        inline=False)
    return embed


class PollCog(commands.Cog, name="Poll"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="poll",
        description="Posts the latest poll or a specific poll",
    )
    # @commands.check(is_bot_channel)
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.user.id, i.channel.id))
    async def poll(self, interaction: discord.Interaction, poll_id: int = None):
        active_polls = await self.bot.db.fetch("SELECT * FROM poll WHERE expire_date > now()")
        if active_polls and poll_id is None:
            await p_poll(active_polls, interaction, self.bot)
        else:
            last_poll = await self.bot.db.fetch("SELECT COUNT (*) FROM poll")
            if poll_id is None:
                poll_id = last_poll[0][0]
            value = await self.bot.db.fetch("SELECT * FROM poll ORDER BY id OFFSET $1 LIMIT 1", int(poll_id) - 1)
            await p_poll(value, interaction, self.bot)

    @poll.error
    async def on_poll_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
            print(error.retry_after)
            await interaction.response.send_message(f"Please wait {round(error.retry_after, 2)} seconds before using this command again.", ephemeral=True)
        else:
            logging.exception(error)

    @app_commands.command(
        name="polllist",
        description="Shows the list of poll ids sorted by year.",
    )
    @commands.check(is_bot_channel)
    async def poll_list(self, interaction: discord.Interaction, year: int = datetime.now(timezone.utc).year):
        polls_years = await self.bot.db.fetch(
            "SELECT title, index_serial FROM poll WHERE date_part('year', start_date) = $1 ORDER BY start_date",
            year)
        if not polls_years:
            await interaction.response.send_message("Sorry there were no polls that year that i could find :(")
        else:
            embed = discord.Embed(title="List of polls", color=discord.Color(0x3cd63d),
                                  description=f"**{year}**")
            for polls in polls_years:
                embed.add_field(name=f"{polls['title']}", value=polls['index_serial'], inline=False)
            await interaction.response.send_message(embed=embed)

    @poll_list.error
    async def isError(self, interaction: discord.Interaction, error):
        if isinstance(error, commands.CheckFailure):
            await interaction.response.send_message("Please use this command in <#361694671631548417> only. It takes up quite a bit of space.", ephemeral=True)

    @app_commands.command(
        name="getpoll"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def getpoll(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await get_poll(self.bot)
        await interaction.followup.send("Done!",ephemeral=True)

    @app_commands.command(
        name="findpoll",
        description="Searches poll questions for a given query",
    )
    async def findpoll(self, interaction: discord.Interaction,  query: str):
        await interaction.response.send_message(embed=await search_poll(self.bot, query))


async def setup(bot):
    await bot.add_cog(PollCog(bot))
