import logging
from itertools import groupby
import discord
from discord.ext import commands


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


class OtherCogs(commands.Cog, name="Other"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="Ping",
        brief="Gives the latency of the bot",
        aliases=['latency', 'delay'],
        hidden=False,
    )
    async def ping(self, ctx):
        await ctx.send(f"{round(self.bot.latency * 1000)} ms")

    @commands.command(
        name="Avatar",
        brief="Posts the full version of a avatar",
        aliases=['Av'],
        usage='[@User]',
        hidden=False,
    )
    async def av(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author
        embed = discord.Embed(title="Avatar", color=discord.Color(0x3cd63d))
        logging.debug(f"Avatar url: {member.avatar.url}")
        embed.set_image(url=member.avatar.url)
        await ctx.send(embed=embed)

    @commands.command(
        name="Info",
        brief="Gives the account information of a user.",
        aliases=['Stats', 'Information'],
        usage='[@user]',
        hidden=False,
    )
    async def info(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(title=member.display_name, color=discord.Color(0x3cd63d))
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="Account created at", value=member.created_at.strftime("%d-%m-%Y @ %H:%M:%S"))
        embed.add_field(name="Joined server", value=member.joined_at.strftime("%d-%m-%Y @ %H:%M:%S"))
        embed.add_field(name="Id", value=member.id)
        embed.add_field(name="Color", value=member.color)
        roles = ""
        for role in reversed(member.roles):
            if role.is_default():
                pass
            else:
                roles += f"{role.mention}\n"
        if roles != "":
            embed.add_field(name="Roles", value=roles, inline=False)
        await ctx.send(embed=embed)

    @commands.command(
        name="Say",
        brief="Makes Cognita repeat whatever was said",
        aliases=['repeat'],
        usage='[message]'
    )
    @commands.is_owner()
    async def say(self, ctx, *, say):
        await ctx.message.delete()
        await ctx.send(say)

    @commands.command(
        name="SayChannel",
        brief="Makes Cognita repeat whatever was said in a specific channel",
        aliases=['sayc', 'repeatc', 'sc', 'repeatchannel'],
        usage='[Channel_id][message]'
    )
    @commands.is_owner()
    async def say_channel(self, ctx, channel_id, *, say):
        channel = self.bot.get_channel_or_thread(int(channel_id))
        await channel.send(say)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Acid jars, Acid Flies, Frying Pans, Enchanted Soup, Barefoot Clients.
        # Green, Purple, Orange, Blue, Red
        list_of_ids = [346842555448557568, 346842589984718848, 346842629633343490, 416001891970056192,
                       416002473032024086]
        gained = set(after.roles) - set(before.roles)
        if gained:
            gained = gained.pop()
            if gained.id in list_of_ids:
                channel = self.bot.get_channel(346842161704075265)
                # Acid jar
                if gained.id == 346842555448557568:
                    embed = discord.Embed(title=f"Hey be careful over there!",
                                          description=f"Those {gained.mention} will melt your hands off {after.mention}!")
                # Acid Flies
                elif gained.id == 346842589984718848:
                    embed = discord.Embed(title=f"Make some room at the tables!",
                                          description=f"{after.mention} just ordered a bowl of {gained.mention}!")
                # Frying Pans
                elif gained.id == 346842629633343490:
                    embed = discord.Embed(title=f"Someone ordered a frying pan!",
                                          description=f"Hope {after.mention} can dodge!")
                # Enchanted Soup
                elif gained.id == 416001891970056192:
                    embed = discord.Embed(title=f"Hey get down from there Mrsha!",
                                          description=f"Looks like {after.mention} will have to order a new serving of {gained.mention} because Mrsha just ate theirs!")
                # Barefoot Clients
                elif gained.id == 416002473032024086:
                    embed = discord.Embed(title=f"Make way!",
                                          description=f"{gained.mention} {after.mention} coming through!")
                else:
                    embed = discord.Embed(title=f"Make some room in the inn!",
                                          description=f"{after.mention} just joined the ranks of {gained.mention}!")
                embed.set_thumbnail(url=after.avatar.url)
                await channel.send(embed=embed, content=f"{after.mention}")

    @commands.command(
        name="addQuote",
        aliases=['aq']
    )
    async def addquote(self, ctx, *, quote):
        await self.bot.pg_con.execute(
            "INSERT INTO quotes(quote, author, author_id, time, tokens) VALUES ($1,$2,$3,now(),to_tsvector($4))",
            quote, ctx.author.display_name, ctx.author.id, quote)
        row_number = await self.bot.pg_con.fetchrow("SELECT COUNT(*) FROM quotes")
        await ctx.send(f"Added quote `{quote}` at index {row_number['count']}")

    @commands.command(
        name="findQuote",
        aliases=['fq']
    )
    async def findquote(self, ctx, *, search):
        results = await self.bot.pg_con.fetch(
            "SELECT quote, ROW_NUMBER () OVER (ORDER BY time) FROM quotes WHERE tokens @@ to_tsquery($1);", search)
        if len(results) > 1:
            index_res = "["
            iterres = iter(results)
            next(iterres)
            for result in iterres:
                index_res = f"{index_res}{str(result['row_number'])}, "
            index_res = index_res[:-2]
            index_res = f"{index_res}]"
            await ctx.send(
                f"Quote {results[0]['row_number']}: {results[0]['quote']}\nThere is also results at {index_res}")
        elif len(results) == 1:
            await ctx.send(f"Quote {results[0]['row_number']}: {results[0]['quote']}")
        elif len(results) < 1:
            await ctx.send("I found no results")
        else:
            await ctx.send("How the fuck?")

    @commands.command(
        name="deleteQuote",
        aliases=['dq', 'removequote', 'rq']
    )
    async def deletequote(self, ctx, *, delete: int):
        u_quote = await self.bot.pg_con.fetchrow(
            "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x WHERE ROW_NUMBER = $1",
            delete)
        if u_quote:
            await self.bot.pg_con.execute(
                "DELETE FROM quotes WHERE serial_id in (SELECT serial_id FROM QUOTES ORDER BY TIME LIMIT 1 OFFSET $1)",
                delete - 1)
            await ctx.send(f"Deleted quote `{u_quote['quote']}` from position {u_quote['row_number']}")
        else:
            await ctx.send("Im sorry. I could not find a quote on that index")

    @commands.command(
        name="Quote",
        aliases=['q']
    )
    async def quote(self, ctx, index: int = None):
        if index is None:
            u_quote = await self.bot.pg_con.fetchrow(
                "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x  ORDER BY random() LIMIT 1")
        else:
            u_quote = await self.bot.pg_con.fetchrow(
                "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x WHERE ROW_NUMBER = $1",
                index)
        if u_quote:
            await ctx.send(f"Quote {u_quote['row_number']}: `{u_quote['quote']}`")
        else:
            await ctx.send("Im sorry, i could not find a quote with that index value.")

    @commands.command(
        name="whoQuote",
        aliases=['infoquote', 'iq', 'wq']
    )
    async def whoquote(self, ctx, index: int):
        u_quote = await self.bot.pg_con.fetchrow(
            "SELECT author, author_id, time, row_number FROM (SELECT author, author_id, time, ROW_NUMBER () OVER () FROM quotes) x WHERE ROW_NUMBER = $1",
            index)
        if u_quote:
            await ctx.send(
                f"Quote {u_quote['row_number']} was added by: {u_quote['author']} ({u_quote['author_id']}) at {u_quote['time']}")
        else:
            await ctx.send("Im sorry, i could not find a quote with that index value.")

    @commands.command(
        name="pink",
        aliases=['nitro']
    )
    @commands.has_role(585789843368574997)
    async def pink(self, ctx):
        pink_role = ctx.guild.get_role(690373096099545168)
        if pink_role in ctx.author.roles:
            await ctx.author.remove_roles(pink_role)
            await ctx.send(f"I removed {pink_role.name}")
        else:
            await ctx.author.add_roles(pink_role)
            await ctx.send(f"I added {pink_role.name}")

    @commands.command(
        name="artistColor",
        aliases=['artcolor', 'artcolour', 'artistcolour']
    )
    @commands.has_role(730704163792748625)
    async def artistcolor(self, ctx):
        artist_role = ctx.guild.get_role(740611013556043887)
        if artist_role in ctx.author.roles:
            await ctx.author.remove_roles(artist_role)
            await ctx.send(f"I removed {artist_role.name}")
        else:
            await ctx.author.add_roles(artist_role)
            await ctx.send(f"I added {artist_role.name}")

    @commands.command(
        name="roles",
        aliases=['rolelist', 'listroles', 'rl', 'lr']
    )
    async def role_list(self, ctx):
        list_r = list()
        for role in ctx.author.roles:
            list_r.append(role.id)
        roles = await self.bot.pg_con.fetch(
            "SELECT id, name, required_role, weight, alias, category "
            "FROM roles "
            "WHERE (required_roles && $2::bigint[] OR required_roles is NULL)"
            "AND guild_id = $1 "
            "AND self_assignable = TRUE "
            "order by weight, name desc",
            ctx.guild.id, list_r)
        length = 0
        for name in roles:
            if len(name['alias']) > length:
                length = len(name['alias'])

        def key_func(k):
            return k['category']

        def key_func2(k):
            return k['weight']

        if len(roles) != 0:
            embed = discord.Embed(title="List of all the roles in the server",
                                  description="Explanation of the roles command",
                                  color=0x00fcff)
            embed.set_thumbnail(url=ctx.guild.icon)
            roles = sorted(roles, key=key_func)
            for key, value in groupby(roles, key_func):
                foobar = ""
                for row in sorted(value, key=key_func2):
                    foobar = foobar + f"`{row['alias']}` `{'-' * (length - len(row['alias']) + 5)}` {ctx.guild.get_role(row['id']).mention}\n"
                embed.add_field(name=f"**{key.capitalize()}**",
                                value=foobar.strip(),
                                inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Doesn't look like any roles has been setup to be self assignable on this server."
                           "The moderators can do that by using: "
                           "`!addrole [Role]`")

    @commands.command(
        name="update_role_weight",
        aliases=['urw', 'role_weight', 'weight']
    )
    @commands.check(admin_or_me_check)
    async def update_role_weight(self, ctx, role: discord.role.Role, new_weight: int):
        await self.bot.pg_con.execute("UPDATE roles set weight = $1 WHERE id = $2 AND guild_id = $3",
                                      new_weight, role['id'], ctx.guild.id)

    @commands.command(
        name="add_role",
        aliases=['ar', 'addrole']
    )
    @commands.check(admin_or_me_check)
    async def add_role(self, ctx, role: discord.role.Role, alias: str, category: str, *, required_role=None):
        list_of_roles = list()
        required_role = required_role.split(" ")
        for user_role in required_role:
            temp = await commands.RoleConverter().convert(ctx, user_role)
            list_of_roles.append(temp.id)
        try:
            if required_role is not None:
                await self.bot.pg_con.execute(
                    "UPDATE roles SET self_assignable = TRUE, required_roles = $1, alias = $2, category=$5 "
                    "where id = $3 "
                    "and guild_id = $4",
                    list_of_roles, alias, role.id, ctx.guild.id, category.lower())
            else:
                await self.bot.pg_con.execute(
                    "UPDATE roles SET self_assignable = TRUE, required_roles = NULL, alias = $1, category=$4 "
                    "where id = $2 "
                    "and guild_id = $3",
                    alias, role.id, ctx.guild.id, category.lower())
        except Exception as e:
            logging.error(e)
            await ctx.send(f"Error: {e}")

    @commands.command(
        name="remove_roll",
        aliases=['rr', 'removeroll'],
        brief="removes a role from self assign list",
        description="removes a role from the self assign list",
        enable=True,
        help="role",
        hidden=False,
        usage="!remove_roll [roll]",
    )
    @commands.check(admin_or_me_check)
    async def remove_roll(self, ctx, role):
        await self.bot.pg_con.execute("UPDATE roles SET self_assignable = FALSE where id = $1 AND guild_id = $2",
                                      role, ctx.guild.id)

    @commands.command(
        name="role",
        aliases=['requestrole', 'needrole', 'plzrole', 'r', 'takerole']
    )
    async def toggle_role(self, ctx, *, role):
        try:
            role = await commands.RoleConverter().convert(ctx, role)
        except discord.ext.commands.RoleNotFound:
            role = ctx.guild.get_role(await self.bot.pg_con.fetchval("SELECT id FROM roles "
                                                                     "WHERE lower(alias) = lower($1) "
                                                                     "and guild_id = $2",
                                                                     role, ctx.guild.id))
        if type(role) == discord.role.Role:
            s_role = await self.bot.pg_con.fetchrow("SELECT * FROM roles WHERE id = $1", role.id)
            if s_role['self_assignable']:
                b_role = list()
                for a_role in ctx.author.roles:
                    b_role.append(a_role.id)
                if s_role['required_roles'] is None or [i for i in s_role['required_roles'] if i in b_role] != []:
                    if role in ctx.author.roles:
                        await ctx.author.remove_roles(role)
                        await ctx.send(f"I removed {role}")
                    else:
                        await ctx.author.add_roles(role)
                        await ctx.send(f"I added {role}")
                else:
                    await ctx.send("You do not have the required role for that.")
            else:
                await ctx.send(
                    "Either the role requested is not self assignable or you don't have the required role for it")
        else:
            await ctx.send("Failed to find the role. Try again with the id of the role")

    @toggle_role.error
    async def isError(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            print()

    @commands.command(
        name="pin",
        aliases=['pinn'],
        brief="pins a selected message",
        description="",
        enable=True,
        help="",
        hidden=False,
        usage="[message_id]",
    )
    @commands.has_role(870298484484485190)
    async def pin(self, ctx, message_id):
        try:
            message = await ctx.channel.fetch_message(message_id)
            await message.pin()
        except Exception as e:
            await ctx.send(f"Error: - {e}")


def setup(bot):
    bot.add_cog(OtherCogs(bot))
