"""Utility commands cog for the Twi Bot Shard.

This module provides utility commands like ping, dice rolling, and fun interactions.
"""

import logging
import random
import re
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    ExternalServiceError,
    PermissionError,
    ValidationError,
)


class Utility(commands.Cog, name="Utility"):
    """Utility commands for bot interaction and fun."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Gives the latency of the bot",
    )
    @handle_interaction_errors
    async def ping(self, interaction: discord.Interaction) -> None:
        """Display the bot's current latency to Discord."""
        try:
            start_time = time.time()

            ws_latency = self.bot.latency
            if ws_latency < 0:
                raise ValidationError(message="Invalid latency measurement received")

            ws_latency_ms = round(ws_latency * 1000, 2)

            await interaction.response.defer()

            response_time = round((time.time() - start_time) * 1000, 2)

            if ws_latency_ms < 100:
                status_emoji = "🟢"
                status_text = "Excellent"
            elif ws_latency_ms < 200:
                status_emoji = "🟡"
                status_text = "Good"
            elif ws_latency_ms < 500:
                status_emoji = "🟠"
                status_text = "Fair"
            else:
                status_emoji = "🔴"
                status_text = "Poor"

            embed = discord.Embed(
                title="🏓 Bot Latency Information",
                color=(
                    discord.Color.green()
                    if ws_latency_ms < 200
                    else (
                        discord.Color.orange()
                        if ws_latency_ms < 500
                        else discord.Color.red()
                    )
                ),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="WebSocket Latency",
                value=f"{status_emoji} **{ws_latency_ms}ms**\n*{status_text}*",
                inline=True,
            )

            embed.add_field(
                name="Response Time",
                value=f"⚡ **{response_time}ms**\n*API Response*",
                inline=True,
            )

            embed.add_field(
                name="Bot Status", value="🤖 **Online**\n*Ready to serve*", inline=True
            )

            embed.set_footer(text="Latency measured to Discord's servers")

            logging.info(
                f"UTILITY PING: Latency check by user {interaction.user.id} - "
                f"WS: {ws_latency_ms}ms, Response: {response_time}ms"
            )
            await interaction.followup.send(embed=embed)

        except (ValidationError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(f"UTILITY PING ERROR: {e}")
            raise ExternalServiceError(message=f"Unable to measure latency: {e}") from e

    @app_commands.command(name="roll", description="Rolls a dice")
    @handle_interaction_errors
    async def roll(
        self,
        interaction: discord.Interaction,
        dice: int = 20,
        amount: int = 1,
        modifier: int = 0,
    ) -> None:
        """Roll dice and display the results."""
        try:
            if dice < 2:
                raise ValidationError(message="Dice must have at least 2 sides")

            if dice > 1000:
                raise ValidationError(message="Dice cannot have more than 1000 sides")

            if amount < 1:
                raise ValidationError(message="You must roll at least 1 die")

            if amount > 100:
                raise ValidationError(message="Cannot roll more than 100 dice at once")

            if modifier < -1000 or modifier > 1000:
                raise ValidationError(message="Modifier must be between -1000 and 1000")

            logging.info(
                f"UTILITY ROLL: User {interaction.user.id} rolling {amount}d{dice}+{modifier}"
            )

            try:
                rolls = [random.randint(1, dice) for _ in range(amount)]
            except Exception as e:
                logging.error(f"UTILITY ROLL ERROR: Random generation failed: {e}")
                raise ExternalServiceError(
                    message="Failed to generate random numbers"
                ) from e

            total_before_modifier = sum(rolls)
            final_total = total_before_modifier + modifier

            embed = discord.Embed(
                title="🎲 Dice Roll Results",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            dice_notation = f"{amount}d{dice}"
            if modifier != 0:
                modifier_sign = "+" if modifier >= 0 else ""
                dice_notation += f" {modifier_sign}{modifier}"

            embed.add_field(name="🎯 Roll", value=f"**{dice_notation}**", inline=True)
            embed.add_field(name="🎲 Total", value=f"**{final_total}**", inline=True)

            if amount > 1 or modifier != 0:
                breakdown_parts = []

                if amount > 1:
                    if len(rolls) <= 20:
                        rolls_str = ", ".join(map(str, rolls))
                    else:
                        rolls_str = (
                            ", ".join(map(str, rolls[:20]))
                            + f"... (+{len(rolls) - 20} more)"
                        )
                    breakdown_parts.append(f"Rolls: [{rolls_str}]")
                    breakdown_parts.append(f"Sum: {total_before_modifier}")

                if modifier != 0:
                    modifier_sign = "+" if modifier >= 0 else ""
                    breakdown_parts.append(f"Modifier: {modifier_sign}{modifier}")

                embed.add_field(
                    name="📊 Breakdown", value="\n".join(breakdown_parts), inline=False
                )

            if amount > 1:
                min_roll = min(rolls)
                max_roll = max(rolls)
                avg_roll = round(total_before_modifier / amount, 2)

                embed.add_field(
                    name="📈 Statistics",
                    value=f"**Min:** {min_roll} | **Max:** {max_roll} | **Avg:** {avg_roll}",
                    inline=False,
                )

            if amount == 1:
                if rolls[0] == 1:
                    embed.set_footer(text="💀 Critical failure!")
                elif rolls[0] == dice:
                    embed.set_footer(text="⭐ Critical success!")
                else:
                    embed.set_footer(text="🎲 Good luck!")
            else:
                if all(roll == dice for roll in rolls):
                    embed.set_footer(text="🌟 All maximum rolls! Incredible luck!")
                elif all(roll == 1 for roll in rolls):
                    embed.set_footer(text="💀 All minimum rolls! What are the odds?")
                else:
                    embed.set_footer(text=f"🎲 Rolled {amount} dice")

            logging.info(
                f"UTILITY ROLL: {dice_notation} = {final_total} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(f"UTILITY ROLL ERROR: {e}")
            raise ExternalServiceError(
                message=f"Unexpected error while rolling dice: {e}"
            ) from e

    @app_commands.command(
        name="say",
        description="Makes Cognita repeat whatever was said",
    )
    @commands.is_owner()
    @handle_interaction_errors
    async def say(
        self,
        interaction: discord.Interaction,
        say: str,
        channel: discord.TextChannel = None,
    ) -> None:
        """Make the bot repeat a message (owner only)."""
        try:
            if not say or len(say.strip()) == 0:
                raise ValidationError(message="Message content cannot be empty")

            say = say.strip()
            target_channel = channel if channel else interaction.channel

            if len(say) > 2000:
                raise ValidationError(
                    message="Message too long (maximum 2000 characters)"
                )

            prohibited_patterns = [
                r"@everyone",
                r"@here",
                r"<@&\d+>",
                r"discord\.gg/",
                r"https?://discord\.com/invite/",
            ]

            for pattern in prohibited_patterns:
                if re.search(pattern, say, re.IGNORECASE):
                    logging.warning(
                        f"UTILITY SAY SECURITY: Prohibited content by {interaction.user.id}"
                    )
                    raise ValidationError(
                        message=f"Message contains prohibited content: {pattern}"
                    )

            if say.count("@") > 5:
                raise ValidationError(
                    message="Too many mentions in message (maximum 5)"
                )

            if len(say.split("\n")) > 20:
                raise ValidationError(
                    message="Too many line breaks in message (maximum 20)"
                )

            if channel:
                if not isinstance(channel, discord.TextChannel):
                    raise ValidationError(message="Target must be a text channel")

                if interaction.guild and channel.guild != interaction.guild:
                    raise PermissionError(
                        message="Cannot send messages to channels in other servers"
                    )

            logging.info(
                f"UTILITY SAY: Owner {interaction.user.id} sending to "
                f"{target_channel.id}: '{say[:100]}...'"
            )

            if target_channel.guild:
                bot_member = target_channel.guild.get_member(interaction.client.user.id)
                if not bot_member:
                    raise PermissionError(message="Bot not found in guild")

                channel_perms = target_channel.permissions_for(bot_member)
                if not channel_perms.send_messages:
                    raise PermissionError(
                        message=f"Bot lacks permission to send messages in {target_channel.mention}"
                    )

            try:
                sent_message = await target_channel.send(say)
                display_message = say if len(say) <= 100 else say[:100] + "..."

                if channel:
                    jump_url = (
                        f"https://discord.com/channels/"
                        f"{target_channel.guild.id if target_channel.guild else '@me'}/"
                        f"{target_channel.id}/{sent_message.id}"
                    )
                    await interaction.response.send_message(
                        f"✅ **Message Sent**\n**Channel:** {target_channel.mention}\n"
                        f"**Message:** {display_message}\n**Link:** {jump_url}",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ **Message Sent**\n**Message:** {display_message}",
                        ephemeral=True,
                    )

            except discord.HTTPException as e:
                logging.error(f"UTILITY SAY ERROR: Discord HTTP error: {e}")
                raise ExternalServiceError(
                    message=f"Failed to send message: {e}"
                ) from e

        except (ValidationError, PermissionError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(f"UTILITY SAY ERROR: {e}")
            raise ExternalServiceError(message=f"Say command failed: {e}") from e

    @app_commands.command(
        name="pat", description="Give Cognita a pat for a job well done!"
    )
    async def pat(self, interaction: discord.Interaction) -> None:
        """Pat the bot to show appreciation."""
        responses = [
            "...Your gesture is acknowledged.",
            "*The stone is cool to the touch, but not unwelcoming.*",
            "I have endured the spells of Archmages. A pat is... acceptable.",
            "You are either very brave or very foolish. I appreciate both qualities.",
            "*Her emerald eyes blink once.* Thank you.",
            "I have stood for centuries. This is the first pat in quite some time.",
            "Zelkyr never patted me. I am uncertain how to process this.",
            "*Her expression remains impassive, but something shifts in those emerald eyes.*",
            "Your appreciation is noted and... welcome.",
            "I could crush you with a single hand. Instead, I shall accept this gesture.",
            "*The faintest hint of warmth emanates from the Truestone.* ...Acknowledged.",
            "You would pat a being who has slain Archmages? Bold.",
            "I am made of stone. And yet... that was not unpleasant.",
        ]
        response = random.choice(responses)
        logging.info(f"UTILITY PAT: User {interaction.user.id} patted the bot")
        await interaction.response.send_message(response)


async def setup(bot: commands.Bot) -> None:
    """Set up the Utility cog."""
    await bot.add_cog(Utility(bot))
