import asyncio
import datetime
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Cog

import secrets


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


class ModCogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="reset",
        brief="resets the cooldown of a command",
        help="resets the cooldown of a command",
        aliases=['removecooldown', 'cooldown'],
        usage='[Command]',
        hidden=False,
    )
    @commands.check(admin_or_me_check)
    @app_commands.default_permissions(manage_messages=True)
    async def reset(self, ctx, command):
        self.bot.get_command(command).reset_cooldown(ctx)
        await ctx.send("reset!")

    @commands.hybrid_command(
        name="state",
        brief="Makes Cognita post a mod message",
        help="",
        aliases=['modState'],
        usage="[message]"
    )
    @commands.check(admin_or_me_check)
    @app_commands.default_permissions(manage_messages=True)
    async def state(self, ctx, *, message):
        embed = discord.Embed(title="**MOD MESSAGE**", color=0xff0000)
        # embed.set_thumbnail(
        #     url="https://cdn.discordapp.com/attachments/359864559361851392/715698476813385788/Exclamation-Mark-Symbol-PNG.png")
        embed.add_field(name="\u200b", value=message, inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # @commands.command(
    #     name="deletealluser",
    #     alias=['dau']
    # )
    # @commands.is_owner()
    # async def delete_all_user(self, ctx, user: discord.User):
    #     result = await self.bot.pg_con.fetchrow(
    #         "SELECT COUNT(*) message_count FROM messages WHERE user_id = $1 AND deleted = False AND server_id = $2",
    #         user.id, ctx.guild.id)
    #     confirm = await ctx.send(
    #         f"Are you sure you want do delete {result['message_count']} messages from user {user.mention}",
    #         allowed_mentions=None)
    #     await confirm.add_reaction('✅')
    #     await confirm.add_reaction('❌')
    #     logging.info(
    #         f"requestion confirmation to delete: {result['message_count']} messages from user id {user.id} "
    #         f"and user name {user.name}")
    #
    #     def check(reaction, author):
    #         return str(reaction.emoji) in ['✅', '❌'] and author == ctx.author
    #
    #     try:
    #         reaction, author = await self.bot.wait_for(
    #             'reaction_add', timeout=60,
    #             check=check)
    #
    #     except asyncio.TimeoutError:
    #         await ctx.send("No reaction within 60 seconds")
    #
    #     else:
    #         if str(reaction.emoji) == '✅':
    #             await ctx.send("Confirmed")
    #             all_messages = await self.bot.pg_con.fetch(
    #                 "SELECT message_id from messages where user_id = $1 AND deleted = False AND server_id = $2",
    #                 user.id, ctx.guild.id)
    #             total_del = 0
    #             for message in all_messages:
    #                 try:
    #                     msg = await ctx.fetch_message(message['message_id'])
    #                     await msg.delete()
    #                     total_del += 1
    #                 except discord.Forbidden as e:
    #                     logging.error(f"Forbidden {e} - {message['message_id']}")
    #                 except discord.NotFound as e:
    #                     logging.error(f"NotFound {e} - {message['message_id']}")
    #                 except discord.HTTPException as e:
    #                     logging.error(f"HTTPException {e} - {message['message_id']}")
    #                 await asyncio.sleep(1)
    #             await ctx.send(f"I succeeded in deleting {total_del} messages out of {result['message_count']}")
    #
    #         if str(reaction.emoji) == '❌':
    #             await ctx.send("Denied")

    # @Cog.listener("on_message")
    # async def mention_pirate(self, message):
    #     for mention in message.mentions:
    #         if mention.id == 230442779803648000:
    #             webhook = discord.SyncWebhook.from_url(secrets.webhook)
    #             webhook.send(f"User {message.author.name} @ Pirate at {message.jump_url} <@&346842813687922689>")

    # @Cog.listener("on_message")
    # async def password_leak(self, message):
    #     banned_words = {'warAnts', "Iwalkedameadowweary"}
    #     allowed_channel_ids = [620021401516113940, 346842161704075265, 521403093892726785, 362248294849576960,
    #                            359864559361851392, 668721870488469514, 930596086547116112, 871486325692432464]
    #     if any(x in message.content for x in banned_words) and message.channel.id not in allowed_channel_ids:
    #         webhook = discord.SyncWebhook.from_url(secrets.webhook)
    #         try:
    #             await message.delete()
    #         except discord.Forbidden:
    #             logging.error(f"Failed to delete message from {message.author.id} due to Forbidden")
    #             webhook.send(f"Failed to delete message from {message.author.id} due to Forbidden")
    #         except Exception as e:
    #             logging.error(f"Failed to delete message from {message.author.id} due to {e}")
    #             webhook.send(f"Failed to delete message from {message.author.id} due to {e}")
    #         muted = message.guild.get_role(542078638741520404)
    #         try:
    #             await message.author.add_roles(muted)
    #         except discord.Forbidden:
    #             logging.error(f"Failed to add Muted role to {message.author.id} due to Forbidden")
    #             webhook.send(f"Failed to add Muted role to {message.author.id} due to Forbidden")
    #         except Exception as e:
    #             logging.error(f"Failed to add mute role to {message.author.id} due to {e}")
    #             webhook.send(f"Failed to add Muted role to {message.author.id} due to {e}")
    #         webhook.send(f"Deleted `{message.content}` and muted user {message.author.name} for posting gravesong "
    #                      f"password outside of patreon channels <@268608466690506753>")

    @Cog.listener("on_message")
    async def log_attachment(self, message):
        if message.attachments and message.author.bot is False and not isinstance(message.channel, discord.channel.DMChannel):
            logging.debug(message.attachments)
            webhook = discord.SyncWebhook.from_url(secrets.webhook)
            for attachment in message.attachments:
                try:
                    embed = discord.Embed(title="New attachment", url=message.jump_url,
                                          description=f"content: {message.content}")
                    file = await attachment.to_file(spoiler=attachment.is_spoiler())
                    embed.set_image(url=f"attachment://{attachment.filename}")
                    embed.add_field(name="User", value=message.author.mention, inline=True)
                    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                    if message.author.avatar is not None:
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                    webhook.send(file=file, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))
                except Exception as e:
                    logging.exception('Log_attachments')

    @Cog.listener("on_message")
    async def dm_watch(self, message):
        if isinstance(message.channel, discord.channel.DMChannel) and not message.author.bot:
            webhook = discord.SyncWebhook.from_url(secrets.webhook_testing_log)
            if message.attachments:
                for attachment in message.attachments:
                    try:
                        embed = discord.Embed(title="New attachment",
                                              description=f"content: {message.content}")
                        file = await attachment.to_file(spoiler=attachment.is_spoiler())
                        embed.set_image(url=f"attachment://{attachment.filename}")
                        embed.add_field(name="User", value=message.author.mention, inline=True)
                        webhook.send(file=file, embed=embed)
                    except Exception as e:
                        logging.exception('Log_attachments')
            else:
                try:
                    embed = discord.Embed(title="New message",
                                          description=f"content: {message.content}")
                    embed.add_field(name="sender", value=message.author.mention, inline=True)
                    if message.channel.recipient:
                        embed.add_field(name="Recipient", value=message.channel.recipient.mention, inline=True)
                    webhook.send(embed=embed)
                except Exception as e:
                    logging.exception('Log_attachments')

    @Cog.listener("on_message")
    async def find_links(self, message):
        if re.search('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content) \
                and message.author.bot is False:
            webhook = discord.SyncWebhook.from_url(secrets.webhook)
            webhook.send(f"Link detected: {message.content}\n"
                         f"User: {message.author.name} {message.author.id}\n"
                         f"Channel: {message.channel.mention}\n"
                         f"Date: {message.created_at}\n"
                         f"Jump Url: {message.jump_url}",
                         allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))

    # @Cog.listener("on_message")
    # async def on_message_mass_ping(self, message):
    #     if len(message.mentions) >= 10:
    #         webhook = discord.SyncWebhook.from_url(secrets.webhook)
    #         try:
    #             muted = message.guild.get_role(542078638741520404)
    #         except Exception as e:
    #             webhook.send(e)
    #             return
    #         try:
    #             await message.author.add_roles(muted)
    #         except discord.Forbidden:
    #             logging.warning(f"I don't have the required permissions to mute {message.author.mention}")
    #         else:
    #             await webhook.send(
    #                 f"{message.author.mention} has been muted for pining more than 10 users in one message"
    #                 f"<@268608466690506753>")

    # @Cog.listener("on_message")
    # async def on_message_pirate_ping_new_account(self, message):
    #     if message.author.created_at.replace(tzinfo=None) > datetime.datetime.now() - datetime.timedelta(hours=24):
    #         for mention in message.mentions:
    #             if mention.id == 230442779803648000:
    #                 webhook = discord.SyncWebhook.from_url(secrets.webhook)
    #                 try:
    #                     muted = message.guild.get_role(542078638741520404)
    #                 except Exception as e:
    #                     webhook.send(e)
    #                     return
    #                 try:
    #                     await message.author.add_roles(muted)
    #                 except discord.Forbidden:
    #                     logging.warning(f"I don't have the required permissions to mute {message.author.mention}")
    #                 else:
    #                     await webhook.send(
    #                         f"{message.author.mention} has been muted for pinging pirate on a young account"
    #                         f"<@268608466690506753>")
    #
    # @Cog.listener("on_member_join")
    # async def suspected_spammer(self, member):
    #     if member.created_at.replace(tzinfo=None) > datetime.datetime.now() - datetime.timedelta(hours=24):
    #         webhook = discord.SyncWebhook.from_url(secrets.webhook)
    #         await webhook.send(f"{member.mention} joined and has a account younger than 24 hours <@268608466690506753>")

    @commands.command(
        name="add_role_to_all",
        aliases=['arta', 'roleall'],
        brief="Adds a role to all users on the server",
        usage='@Role',
        hidden=True
    )
    @commands.is_owner()
    async def add_role_to_all(self, ctx, role: discord.Role):
        for member in ctx.guild.members:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                logging.error(f"Can't add role 'verified' to user {member.name}")
            except discord.HTTPException:
                logging.error(f"Failed to add role 'verified' to user {member.name}")
            except Exception as e:
                logging.error(e)
            await asyncio.sleep(0.5)

    @Cog.listener("on_member_join")
    async def filter_new_users(self, member):
        if member.created_at.replace(tzinfo=None) < datetime.datetime.now() - datetime.timedelta(hours=72):
            verified = member.guild.get_role(945388135355924571)
            await member.add_roles(verified)

    @commands.command("populate_forum")
    @commands.is_owner()
    async def populate_forum(self, ctx):
        chapters = [
            "1.00",
            "1.01",
            "1.02",
            "1.03",
            "1.04",
            "1.05",
            "1.06",
            "1.07",
            "1.08",
            "1.09",
            "1.10",
            "1.11",
            "Interlude",
            "1.12",
            "1.13",
            "1.14",
            "1.15",
            "1.16",
            "1.17",
            "1.18",
            "1.19",
            "1.20",
            "Interlude – 1.00 R",
            "1.01 R",
            "1.21",
            "1.22",
            "1.23",
            "Interlude: King Edition",
            "1.24",
            "1.02 R",
            "1.03 R",
            "1.25",
            "1.26",
            "1.27",
            "1.04 R",
            "1.05 R",
            "1.28",
            "1.06 R",
            "1.29",
            "1.30",
            "1.31",
            "1.07 R",
            "1.08 R",
            "1.32",
            "1.33",
            "1.09 R",
            "1.10 R",
            "1.34",
            "1.35",
            "1.11 R",
            "1.12 R",
            "1.36",
            "1.37",
            "1.38",
            "1.39",
            "1.40",
            "1.13 R",
            "1.41",
            "1.00 H",
            "1.01 H",
            "1.02 H",
            "1.42",
            "1.43",
            "1.44",
            "1.45",
            "Interlude",
            "2.00",
            "2.01",
            "2.02",
            "2.03",
            "2.04",
            "2.05",
            "2.06",
            "2.07",
            "2.08",
            "2.09",
            "2.10 T",
            "2.11",
            "2.12",
            "2.13",
            "2.14 G",
            "S01 – Mating Rituals",
            "2.15",
            "2.16",
            "2.17",
            "2.18",
            "2.19 G",
            "2.20",
            "2.21",
            "2.22 K",
            "2.23",
            "2.24 T",
            "2.25",
            "2.26",
            "1.00 C",
            "1.01 C",
            "2.27 G",
            "2.28",
            "2.29",
            "2.30",
            "2.31",
            "2.32 H",
            "2.33",
            "2.34",
            "2.35",
            "2.36 G",
            "2.37",
            "2.38",
            "Interlude",
            "S02 – The Antinium Wars (Pt.1)",
            "S02 – The Antinium Wars (Pt.2)",
            "2.39",
            "2.40",
            "2.41",
            "2.42",
            "2.43",
            "2.44",
            "2.45",
            "S03 – Wistram Days (Pt. 1)",
            "2.46",
            "2.47",
            "2.48",
            "3.00 E",
            "3.01 E",
            "3.02 H",
            "3.03",
            "3.04",
            "3.05 L",
            "1.00 D",
            "1.01 D",
            "3.06 L",
            "3.07 H",
            "3.08 H",
            "3.09",
            "3.10",
            "3.11 E",
            "3.12 E",
            "3.13",
            "3.14",
            "3.15",
            "3.16",
            "S03 – Wistram Days (Pt. 2)",
            "3.17 T",
            "3.18 T",
            "3.19 T",
            "3.20 T",
            "3.21 L",
            "3.22 L",
            "3.23 L",
            "3.24",
            "3.25",
            "3.26 G",
            "3.27 M",
            "3.28 G",
            "3.29 G",
            "3.30",
            "3.31 G",
            "S03 – Wistram Days (Pt. 3)",
            "S03 – Wistram Days (Pt. 4)",
            "S03 – Wistram Days (Pt. 5)",
            "S03 – Wistram Days (Pt. 6)",
            "S03 – Wistram Days (Pt. 7)",
            "3.32",
            "3.33",
            "3.34",
            "3.35",
            "3.36",
            "3.37",
            "3.38",
            "3.39",
            "3.40",
            "3.41",
            "3.42",
            "Interlude",
            "4.00 K",
            "4.01 K",
            "4.02 K",
            "4.03 K",
            "4.04 K",
            "4.05 K",
            "4.06 KM",
            "4.07",
            "4.08 T",
            "4.09",
            "4.10",
            "4.11",
            "4.12",
            "4.13 L",
            "4.14 L",
            "4.15 L",
            "4.16",
            "4.17",
            "1.02 D",
            "1.03 D",
            "1.04 D",
            "1.05 D",
            "1.06 D",
            "4.18",
            "4.19",
            "4.20 E",
            "4.21 E",
            "4.22 E",
            "4.23 E",
            "4.24",
            "4.25 N",
            "4.26 M",
            "4.27 H",
            "4.28",
            "4.29",
            "4.30",
            "4.31",
            "4.32 G",
            "1.02 C",
            "1.03 C",
            "1.04 C",
            "1.05 C",
            "4.33",
            "4.34",
            "4.35 E",
            "4.36 O",
            "4.37 O",
            "4.38 B",
            "4.39 G",
            "4.40 L",
            "4.41 L",
            "4.42 L",
            "4.43",
            "4.44 M",
            "4.45",
            "4.46",
            "4.47",
            "S02 – The Antinium Wars (Pt.3)",
            "S02 – The Antinium Wars (Pt.4)",
            "S02 – The Antinium Wars (Pt.5)",
            "4.48",
            "4.49",
            "The Depthless Doctor",
            "Glossary",
            "5.00",
            "5.01",
            "5.02",
            "5.03",
            "5.04",
            "5.05",
            "5.06 M",
            "5.07",
            "5.08",
            "Interlude – Flos",
            "5.09 E",
            "5.10 E",
            "5.11 E",
            "5.12",
            "5.13",
            "5.14",
            "5.15",
            "5.16 S",
            "5.17 S",
            "5.18 S",
            "5.19 G",
            "5.20 G",
            "5.21 E",
            "5.22 G",
            "5.23 G",
            "5.24 L",
            "5.25 L",
            "5.26 L",
            "5.27",
            "5.28",
            "5.29",
            "5.30 G",
            "5.31 G",
            "5.32 G",
            "5.33 B",
            "Interlude – Blackmage",
            "5.34",
            "5.35 H",
            "5.36",
            "5.37 G",
            "5.38",
            "5.39",
            "5.40",
            "5.41",
            "5.42",
            "5.43",
            "Interlude – Niers",
            "5.44",
            "5.45",
            "5.46",
            "5.47 G",
            "5.48 G",
            "5.49",
            "5.50 G",
            "Interlude – Bird",
            "5.51 G",
            "5.52",
            "5.53",
            "5.54 (Non-Canon)",
            "5.54",
            "Interlude – Krshia",
            "5.55 G",
            "5.56 G",
            "5.57",
            "5.58",
            "5.59",
            "Interlude – Pebblesnatch and Garry",
            "5.60",
            "5.61",
            "5.62",
            "Interlude",
            "6.00",
            "6.01",
            "6.02",
            "6.03",
            "6.04 D",
            "6.05 D",
            "6.06 D",
            "6.07 D",
            "6.08",
            "6.09",
            "6.10",
            "6.11",
            "6.12 K",
            "6.13 K",
            "6.14 K",
            "6.15 K",
            "6.16",
            "6.17 S",
            "6.18 H",
            "6.19 H",
            "6.20 D",
            "6.21 D",
            "6.22 D",
            "6.23 D",
            "6.24 D",
            "6.25",
            "6.26",
            "6.27 M",
            "6.28",
            "6.29",
            "Interlude – Embria",
            "6.30",
            "6.31",
            "6.32",
            "6.33 E",
            "6.34 E",
            "Interlude – Numbtongue (Pt.1)",
            "Interlude – Numbtongue (Pt.2)",
            "6.35",
            "6.36 E",
            "6.37 E",
            "6.38",
            "6.39",
            "6.40 E",
            "6.41 E",
            "Interlude – Two Rats",
            "Interlude – Rufelt",
            "6.42 E",
            "6.43 E",
            "6.44 E",
            "6.45 E",
            "6.46 E",
            "6.47 E",
            "6.48 T",
            "6.49",
            "6.50 I",
            "6.51 A",
            "6.52 K",
            "6.53 K",
            "6.54 K",
            "6.55 K",
            "Interlude – The Titan’s Question",
            "6.56",
            "6.57",
            "6.58",
            "6.59",
            "6.60",
            "Interlude – Talia",
            "6.61 L",
            "6.62 L",
            "Interlude – Foliana",
            "6.63 P",
            "6.64",
            "6.65",
            "6.66 H",
            "6.67",
            "6.68",
            "7.00",
            "7.01",
            "7.02",
            "7.03",
            "Mini Chapter #1",
            "7.04",
            "Interlude – Queens and Dragons",
            "7.05 P",
            "7.06",
            "7.07",
            "7.08 K",
            "7.09 K",
            "7.10 K",
            "7.11",
            "Interlude – Dancing and Brawling",
            "Interlude – Chocolate Gold",
            "Interlude – Chess and Ships",
            "Interlude – Chocolate Alchemy",
            "Interlude – Lifting Ants",
            "Interlude – Burning Alcohol",
            "Interlude – The Hangover After",
            "7.12 G",
            "7.13 K",
            "Mating Rituals Pt.2",
            "7.14 T",
            "7.15 R",
            "7.16 L",
            "7.17 S",
            "7.18 M",
            "Interlude – Strategists at Sea (Pt. 1)",
            "Interlude – Strategists at Sea (Pt. 2)",
            "7.19",
            "7.20",
            "Interlude – A Night in the Inn",
            "7.21 KQ",
            "7.22 D",
            "7.23 LM",
            "7.24",
            "7.25",
            "7.26",
            "7.27",
            "Interlude – The Gecko of Illusions",
            "7.28",
            "7.29 B",
            "7.30",
            "7.31",
            "Interlude – A Meeting of [Druids]",
            "7.32 D",
            "7.33 I",
            "7.34 C",
            "7.35 C",
            "7.36 C",
            "7.37",
            "7.38",
            "7.39 A",
            "Interlude – Carriages and Conversations",
            "Interlude – Meetings and Friendships",
            "Interlude – Sand and Notes",
            "7.40 ER",
            "Interlude – Food and Growth",
            "7.41",
            "7.42 M",
            "7.43 G",
            "7.44",
            "7.45",
            "7.46 K",
            "7.47 K",
            "7.48 K",
            "7.49",
            "Interlude – Experiments in Golems",
            "7.50",
            "7.51",
            "7.52",
            "7.53",
            "7.54",
            "7.55 E",
            "Interlude – Saliss the Adventurer",
            "7.56",
            "7.57",
            "7.58",
            "7.59",
            "7.60",
            "Interlude – The Tribes of Izril",
            "Interlude – The Innkeeper’s [Knight]",
            "7.61",
            "7.62",
            "Solstice (Pt. 1)",
            "Solstice (Pt. 2)",
            "Solstice (Pt. 3)",
            "Solstice (Pt. 4)",
            "Solstice (Pt. 5)",
            "Solstice (Pt. 6)",
            "Solstice (Pt. 7)",
            "Solstice (Pt. 8)",
            "Solstice (Pt. 9)",
            "8.00",
            "8.01",
            "8.02",
            "8.03",
            "Interlude – The Revenant and the Naga",
            "8.04 T",
            "8.05 I",
            "8.06 RT",
            "8.07 L",
            "8.08 J",
            "8.09",
            "8.10",
            "8.11 E",
            "8.12 T",
            "Interlude – The [Rower] and the [Bartender]",
            "8.13 F",
            "8.14 N",
            "8.15",
            "Interlude – Paradigm Shift (Pt. 1)",
            "Interlude – Paradigm Shift (Pt. 2)",
            "8.16",
            "8.17 H",
            "8.18 H",
            "8.19 H",
            "8.20",
            "8.21 L",
            "8.22 HE",
            "Interlude – Senior Guardsman Relc",
            "8.23",
            "8.24",
            "8.25 KH",
            "8.26 FK",
            "Interlude – Luan the Giant",
            "8.27",
            "8.28",
            "8.29",
            "Interlude – The Pets of Innworld",
            "8.30",
            "8.31",
            "Interlude – Pisces (Revised)",
            "8.32",
            "8.33 R",
            "8.34 R",
            "8.35",
            "8.36 H",
            "8.37 H",
            "8.38 H",
            "8.39",
            "8.40 CTV",
            "Interlude – Of Vampires and Fraerlings",
            "8.41",
            "Interlude – Songs and Stories",
            "8.42",
            "8.43",
            "8.44 O",
            "8.45 O",
            "8.46 G",
            "Interlude – Perspective and Past",
            "8.47 H",
            "8.48 H",
            "8.49 M – Revised",
            "8.50",
            "Interlude – Conversations",
            "8.51 D",
            "8.52 MN",
            "8.53 FH",
            "8.54 H",
            "8.55 L",
            "8.56",
            "8.57 H",
            "8.58 PFH",
            "8.59 H",
            "8.60",
            "8.61",
            "8.62 K",
            "8.63 K",
            "8.64 K",
            "8.65",
            "Interlude – Hectval (Pt. 1)",
            "Interlude – Hectval (Pt. 2)",
            "Interlude – Hectval (Pt. 3)",
            "Interlude – Satar (Revised)",
            "8.66",
            "8.67",
            "8.68",
            "8.69 T",
            "8.70 E",
            "8.71",
            "8.72",
            "8.73 R",
            "8.74 DR",
            "8.75",
            "8.76 B",
            "8.77 B",
            "8.78 F",
            "8.79",
            "8.80",
            "8.81",
            "8.82 (Pt. 1)",
            "8.82 (Pt. 2)",
            "8.82 (Pt. 3)",
            "8.83",
            "8.84",
            "8.85",
            "Epilogue",
            "9.00",
            "9.01",
            "9.02",
            "Interlude – Singing Ships",
            "9.03",
            "9.04",
            "Interlude – The Isles of Goblin and Minos",
            "9.05 NPR",
            "9.06",
            "9.07",
            "9.08",
            "Interlude – Mundanity and Memorials",
            "Interlude – The Competition",
            "9.09 P",
            "9.10 W",
            "9.11 W",
            "9.12",
            "9.13",
            "9.14 VM",
            "9.15 VM 🐀"
        ]
        for channel in ctx.guild.channels:
            if channel.type == discord.ChannelType.forum and channel.id == 1020273330160414750:
                for chapter in chapters:
                    logging.error(f"Creating {chapter}")
                    try:
                        await channel.create_thread(name=chapter, content="Chapter " + chapter)
                    except Exception as e:
                        await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
                    await asyncio.sleep(1)


async def setup(bot):
    await bot.add_cog(ModCogs(bot))
