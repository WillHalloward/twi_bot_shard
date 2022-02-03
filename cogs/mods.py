import asyncio
import logging
import re

import discord
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
        hidden=False, )
    @commands.check(admin_or_me_check)
    async def reset(self, ctx, command):
        self.bot.get_command(command).reset_cooldown(ctx)

    @commands.command(
        name="state",
        brief="Makes Cognita post a mod message",
        help="",
        aliases=['modState'],
        usage="[message]"
    )
    @commands.check(admin_or_me_check)
    async def state(self, ctx, *, message):
        embed = discord.Embed(title="**MOD MESSAGE**", color=0xff0000)
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/359864559361851392/715698476813385788/Exclamation-Mark-Symbol-PNG.png")
        embed.add_field(name="\u200b", value=message, inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @commands.command(
        name="deletealluser",
        alias=['dau']
    )
    @commands.is_owner()
    async def delete_all_user(self, ctx, user: discord.User):
        result = await self.bot.pg_con.fetchrow(
            "SELECT COUNT(*) message_count FROM messages WHERE user_id = $1 AND deleted = False AND server_id = $2",
            user.id, ctx.guild.id)
        confirm = await ctx.send(
            f"Are you sure you want do delete {result['message_count']} messages from user {user.mention}",
            allowed_mentions=None)
        await confirm.add_reaction('✅')
        await confirm.add_reaction('❌')
        logging.info(
            f"requestion confirmation to delete: {result['message_count']} messages from user id {user.id} "
            f"and user name {user.name}")

        def check(reaction, author):
            return str(reaction.emoji) in ['✅', '❌'] and author == ctx.author

        try:
            reaction, author = await self.bot.wait_for(
                'reaction_add', timeout=60,
                check=check)

        except asyncio.TimeoutError:
            await ctx.send("No reaction within 60 seconds")

        else:
            if str(reaction.emoji) == '✅':
                await ctx.send("Confirmed")
                all_messages = await self.bot.pg_con.fetch(
                    "SELECT message_id from messages where user_id = $1 AND deleted = False AND server_id = $2",
                    user.id, ctx.guild.id)
                total_del = 0
                for message in all_messages:
                    try:
                        msg = await ctx.fetch_message(message['message_id'])
                        await msg.delete()
                        total_del += 1
                    except discord.Forbidden as e:
                        logging.error(f"Forbidden {e} - {message['message_id']}")
                    except discord.NotFound as e:
                        logging.error(f"NotFound {e} - {message['message_id']}")
                    except discord.HTTPException as e:
                        logging.error(f"HTTPException {e} - {message['message_id']}")
                    await asyncio.sleep(1)
                await ctx.send(f"I succeeded in deleting {total_del} messages out of {result['message_count']}")

            if str(reaction.emoji) == '❌':
                await ctx.send("Denied")

    @Cog.listener("on_message")
    async def mention_pirate(self, message):
        for mention in message.mentions:
            if mention.id == 230442779803648000:
                webhook = discord.SyncWebhook.from_url(secrets.webhook)
                webhook.send(f"User {message.author.name} @ Pirate at {message.jump_url} <@&346842813687922689>")

    @Cog.listener("on_message")
    async def password_leak(self, message):
        allowed_channel_ids = [620021401516113940, 346842161704075265, 521403093892726785, 362248294849576960,
                               359864559361851392, 668721870488469514]
        if "Iwalkedameadowweary" in message.content and message.channel.id not in allowed_channel_ids:
            muted = message.guild.get_role(542078638741520404)
            try:
                message.author.add_roles(muted)
            except discord.Forbidden:
                logging.error(f"Failed to add Muted role to {message.author.id}")
            message.delete()
            webhook = discord.SyncWebhook.from_url(secrets.webhook)
            webhook.send("Gravesong password leaked <@&346842813687922689>")

    @Cog.listener("on_message")
    async def log_attachment(self, message):
        if message.attachments and message.author.bot is False:
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
                    embed.set_thumbnail(url=message.author.avatar.url)
                    webhook.send(file=file, embed=embed,
                                       allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))
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


def setup(bot):
    bot.add_cog(ModCogs(bot))
