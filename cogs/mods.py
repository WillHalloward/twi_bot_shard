import asyncio
import datetime
import logging
import re

import aiohttp
import discord
from discord import app_commands, Webhook
from discord.ext import commands
from discord.ext.commands import Cog

import config


class ModCogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reset",
        description="resets the cooldown of a command"
    )
    @app_commands.default_permissions(ban_members=True)
    async def reset(self, interaction: discord.Interaction, command: str):
        self.bot.get_command(command).reset_cooldown(interaction)
        await interaction.response.send_message(f"Reset the cooldown of {command}")

    @app_commands.command(
        name="state",
        description="Makes Cognita post a mod message"
    )
    @app_commands.default_permissions(ban_members=True)
    async def state(self, interaction: discord.Interaction, message: str):
        embed = discord.Embed(title="**MOD MESSAGE**", color=0xff0000, description=message)
        embed.set_footer(text=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @Cog.listener("on_message")
    async def log_attachment(self, message):
        if message.attachments and not message.author.bot and not isinstance(message.channel, discord.channel.DMChannel):
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(config.webhook, session=session)
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
                        await webhook.send(file=file, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))
                    except Exception as e:
                        logging.exception('Log_attachments')

    @Cog.listener("on_message")
    async def dm_watch(self, message):
        if isinstance(message.channel, discord.channel.DMChannel) and not message.author.bot:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(config.webhook_testing_log, session=session)
                if message.attachments:
                    for attachment in message.attachments:
                        try:
                            embed = discord.Embed(title="New attachment",
                                                  description=f"content: {message.content}")
                            file = await attachment.to_file(spoiler=attachment.is_spoiler())
                            embed.set_image(url=f"attachment://{attachment.filename}")
                            embed.add_field(name="User", value=message.author.mention, inline=True)
                            embed.add_field(name="Username", value=message.author.name, inline=True)
                            await webhook.send(file=file, embed=embed)
                        except Exception as e:
                            logging.exception('DM_watch')
                else:
                    try:
                        embed = discord.Embed(title="New message",
                                              description=f"content: {message.content}")
                        embed.add_field(name="sender", value=message.author.mention, inline=True)
                        embed.add_field(name="Username", value=message.author.name, inline=True)
                        if message.channel.recipient:
                            embed.add_field(name="Recipient", value=message.channel.recipient.mention, inline=True)
                        await webhook.send(embed=embed)
                    except Exception as e:
                        logging.exception('DM_watch')

    @Cog.listener("on_message")
    async def find_links(self, message: discord.Message):
        if not isinstance(message.channel, discord.channel.DMChannel) and not message.author.bot and message.guild.id == 346842016480755724:
            if re.search('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content):
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(config.webhook, session=session)
                    await webhook.send(f"Link detected: {message.content[0:1600]}\n"
                                       f"User: {message.author.name} {message.author.id}\n"
                                       f"Channel: {message.channel.mention}\n"
                                       f"Jump Url: {message.jump_url}",
                                       allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))

    @Cog.listener("on_member_join")
    async def filter_new_users(self, member):
        if member.created_at.replace(tzinfo=None) < datetime.datetime.now() - datetime.timedelta(hours=72):
            verified = member.guild.get_role(945388135355924571)
            await member.add_roles(verified)


async def setup(bot):
    await bot.add_cog(ModCogs(bot))
