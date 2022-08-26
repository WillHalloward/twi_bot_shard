import logging
from itertools import groupby

import discord
from discord import app_commands
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
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @commands.hybrid_command(
        name="ping",
        brief="Gives the latency of the bot",
        aliases=['latency', 'delay'],
        hidden=False,
    )
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f"{round(self.bot.latency * 1000)} ms")

    @commands.hybrid_command(
        name="avatar",
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

    @commands.hybrid_group(name="info")
    async def info(self, ctx):
        pass

    @info.command(
        name="user",
        brief="Gives the account information of a user.",
        aliases=['Stats', 'Information'],
        usage='[@user]',
        hidden=False,
    )
    async def info_user(self, ctx, *, member: discord.Member = None):
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

    @info.command(name="server")
    async def info_server(self, ctx):
        print()
        # TODO Implement !info server

    @info.command(name="role")
    async def info_role(self, ctx, role: discord.Role):
        print()
        # TODO Implement !info role

    @commands.command(
        name="say",
        brief="Makes Cognita repeat whatever was said",
        aliases=['repeat'],
        usage='[message]'
    )
    @commands.is_owner()
    async def say(self, ctx, *, say):
        await ctx.send(say)

    @commands.command(
        name="saychannel",
        brief="Makes Cognita repeat whatever was said in a specific channel",
        aliases=['sayc', 'repeatc', 'sc', 'repeatchannel'],
        usage='[Channel_id][message]'
    )
    @commands.is_owner()
    async def say_channel(self, ctx, channel_id, *, say):
        channel = ctx.guild.get_channel_or_thread(int(channel_id))
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

    @commands.hybrid_group(name="quote")
    async def quote(self, ctx):
        pass

    @quote.command(
        name="add",
        aliases=['aq']
    )
    async def quote_add(self, ctx, *, quote):
        await self.bot.pg_con.execute(
            "INSERT INTO quotes(quote, author, author_id, time, tokens) VALUES ($1,$2,$3,now(),to_tsvector($4))",
            quote, ctx.author.display_name, ctx.author.id, quote)
        row_number = await self.bot.pg_con.fetchrow("SELECT COUNT(*) FROM quotes")
        await ctx.send(f"Added quote `{quote}` at index {row_number['count']}")

    @quote.command(
        name="find",
        aliases=['fq']
    )
    async def quote_find(self, ctx, *, search):
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

    @quote.command(
        name="delete",
        aliases=['dq', 'removequote', 'rq']
    )
    async def quote_delete(self, ctx, *, delete: int):
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

    @quote.command(
        name="get",
        aliases=['q']
    )
    async def quote_get(self, ctx, index: int = None):
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

    @quote.command(
        name="who",
        aliases=['infoquote', 'iq', 'wq']
    )
    async def quote_who(self, ctx, index: int):
        u_quote = await self.bot.pg_con.fetchrow(
            "SELECT author, author_id, time, row_number FROM (SELECT author, author_id, time, ROW_NUMBER () OVER () FROM quotes) x WHERE ROW_NUMBER = $1",
            index)
        if u_quote:
            await ctx.send(
                f"Quote {u_quote['row_number']} was added by: {u_quote['author']} ({u_quote['author_id']}) at {u_quote['time']}")
        else:
            await ctx.send("Im sorry, i could not find a quote with that index value.")

    @commands.hybrid_command(
        name="roles",
        aliases=['rolelist', 'listroles', 'rl', 'lr']
    )
    async def role_list(self, ctx):
        list_r = list()
        for role in ctx.author.roles:
            list_r.append(role.id)
        roles = await self.bot.pg_con.fetch(
            "SELECT id, name, required_roles, weight, alias, category "
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
                                  description="Request the role by doing !role [Rolename]",
                                  color=0x00fcff)
            embed.set_thumbnail(url=ctx.guild.icon)
            roles = sorted(roles, key=key_func)
            for key, value in groupby(roles, key_func):
                foobar = ""
                x = 1
                for row in sorted(value, key=key_func2):
                    temp_str = f"`{row['alias']}` `{'-' * (length - len(row['alias']) + 5)}` {ctx.guild.get_role(row['id']).mention}\n"
                    if len(temp_str + foobar) > 1024:
                        embed.add_field(name=f"**{key.capitalize()}**", value=foobar.strip(), inline=False)
                        foobar = ""
                        key = key + " " + str(x + 1)
                    foobar = foobar + temp_str
                embed.add_field(name=f"**{key.capitalize()}**", value=foobar.strip(), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Doesn't look like any roles has been setup to be self assignable on this server."
                           "The moderators can do that by using: "
                           "`!addrole [Role]`")

    @commands.hybrid_group(name="admin_role")
    @app_commands.default_permissions(manage_roles=True)
    async def admin_role(self, ctx):
        pass

    @admin_role.command(
        name="weight"
    )
    @commands.check(admin_or_me_check)
    async def update_role_weight(self, ctx, role: discord.role.Role, new_weight: int):
        await self.bot.pg_con.execute("UPDATE roles set weight = $1 WHERE id = $2 AND guild_id = $3",
                                      new_weight, role.id, ctx.guild.id)

    @admin_role.command(
        name="add"
    )
    @commands.check(admin_or_me_check)
    async def role_add(self, ctx, role: discord.role.Role, alias: str, category: str = 'Uncategorized',
                       auto_replace: bool = False, *, required_roles=None):
        try:
            if required_roles is not None:
                list_of_roles = list()
                required_roles = required_roles.split(" ")
                for user_role in required_roles:
                    temp = await commands.RoleConverter().convert(ctx, user_role)
                    list_of_roles.append(temp.id)
                await self.bot.pg_con.execute(
                    "UPDATE roles SET self_assignable = TRUE, required_roles = $1, alias = $2, category=$5, auto_replace = $6 "
                    "where id = $3 "
                    "and guild_id = $4",
                    list_of_roles, alias, role.id, ctx.guild.id, category.lower(), auto_replace)
            else:
                await self.bot.pg_con.execute(
                    "UPDATE roles SET self_assignable = TRUE, required_roles = NULL, alias = $1, category=$4, auto_replace = $5 "
                    "where id = $2 "
                    "and guild_id = $3",
                    alias, role.id, ctx.guild.id, category.lower(), auto_replace)
        except Exception as e:
            logging.error(e)
            await ctx.send(f"Error: {e}")

    @admin_role.command(
        name="remove",
        description="removes a role from the self assign list"
    )
    @commands.check(admin_or_me_check)
    async def role_remove(self, ctx, role):
        await self.bot.pg_con.execute(
            "UPDATE roles SET self_assignable = FALSE, weight = 0, alias = NULL, category = NULL, required_role = NULL, auto_replace = FALSE "
            "where id = $1 "
            "AND guild_id = $2",
            role, ctx.guild.id)

    @commands.hybrid_command(
        name="role",
        aliases=['r', 'iam', 'iamnot', 'giverole']
    )
    async def role(self, ctx, *, role: discord.Role):
        if type(role) == discord.Role:
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
                        if await self.bot.pg_con.fetchval("SELECT auto_replace FROM roles WHERE id = $1", role.id):
                            list_r = list()
                            for r in ctx.author.roles:
                                list_r.append(r.id)
                            r_loop = self.bot.pg_con.fetch("SELECT id FROM roles WHERE id = ANY($1::bigint[]) "
                                                           "AND category = "
                                                           "(SELECT category FROM roles where id = $2)",
                                                           list_r, role.id)
                            for r in await r_loop:
                                await ctx.author.remove_roles(await commands.RoleConverter().convert(ctx, str(r['id'])))
                        await ctx.author.add_roles(role)
                        await ctx.send(f"I added {role}")
                else:
                    await ctx.send("You do not have the required role for that.")
            else:
                await ctx.send(
                    "The requested role is not self assignable")
        else:
            await ctx.send("Failed to find the role. Try again with the id of the role or its alias")

    @commands.hybrid_command(
        name="pin"
    )
    @commands.has_role(870298484484485190)
    async def pin(self, ctx, message_id: str):
        try:
            message = await ctx.channel.fetch_message(int(message_id))
            await message.pin()
        except Exception as e:
            await ctx.send(f"Error: - {e}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OtherCogs(bot))
