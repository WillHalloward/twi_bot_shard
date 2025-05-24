import discord
from discord import app_commands
from discord.ext import commands
import config
from openai import OpenAI

client = OpenAI(api_key=config.openai_api_key)


class SummarizationCog(commands.Cog):
    def __init__(self, bot, server_rules):
        self.bot = bot
        self.server_rules = server_rules

    async def summarize_messages(self, messages):
        # Filter out messages from bots and reverse the list
        conversation = "\n".join(
            [f"{msg.author.display_name}: {msg.content}" for msg in reversed(messages) if not msg.author.bot]
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Summarize the following conversation with attention to each user's messages."},
                {"role": "user", "content": conversation}
            ]
        )
        return response.choices[0].message.content

    async def moderate_conversation(self, messages):
        # Filter out messages from bots and reverse the list
        conversation = "\n".join(
            [f"{msg.author.display_name}: {msg.content}" for msg in reversed(messages) if not msg.author.bot]
        )
        rule_check = "\n".join([f"{i + 1}. {rule}" for i, rule in enumerate(self.server_rules)])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Summarize the conversation, checking if any of these rules were broken:\n{rule_check}. "
                               f"Provide examples if you think a message might have broken a rule, even if unsure, so a moderator can decide."
                },
                {"role": "user", "content": conversation}
            ]
        )
        return response.choices[0].message.content

    @app_commands.command(name="summarize")
    async def summarize(self, interaction: discord.Interaction, num_messages: int = 50):
        """Summarizes the last X messages in the channel."""
        await interaction.response.defer()
        messages = [message async for message in interaction.channel.history(limit=num_messages)]
        summary = await self.summarize_messages(messages)
        await interaction.followup.send(f"Summary:\n{summary}")

    @app_commands.command(name="moderate")
    async def moderate(self, interaction: discord.Interaction, num_messages: int = 50):
        """Summarizes the last X messages and checks for rule violations."""
        await interaction.response.defer(ephemeral=True)
        messages = [message async for message in interaction.channel.history(limit=num_messages)]
        report = await self.moderate_conversation(messages)
        await interaction.followup.send(f"Moderation Report:\n{report}")


async def setup(bot):
    # Replace 'your_openai_api_key' and 'server_rules' with actual values or load from config
    server_rules = [
        "Follow the Discord Community Guidelines.",
        "Don't spam or ping excessively, including images, emotes, or gifs.",
        "Don't attack other users.",
        "Don't post personal information.",
        "No bug pictures."
    ]
    await bot.add_cog(SummarizationCog(bot, server_rules))
