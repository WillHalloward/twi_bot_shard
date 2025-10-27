import discord
import openai
import structlog
from discord import app_commands
from discord.ext import commands
from openai import OpenAI

import config
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    APIError,
    ExternalServiceError,
    ValidationError,
)

client = OpenAI(api_key=config.openai_api_key)


class SummarizationCog(commands.Cog):
    def __init__(self, bot, server_rules) -> None:
        self.bot = bot
        self.server_rules = server_rules
        self.logger = structlog.get_logger("cogs.summarization")

    async def summarize_messages(self, messages):
        """Summarize a list of Discord messages using OpenAI API.

        Args:
            messages: List of Discord message objects to summarize

        Returns:
            str: The summarized content from OpenAI

        Raises:
            ValidationError: If no valid messages are provided
            APIError: If OpenAI API call fails
            ExternalServiceError: If there's an issue with the OpenAI service
        """
        if not messages:
            raise ValidationError(message="No messages provided for summarization")

        # Filter out messages from bots and reverse the list
        valid_messages = [
            msg for msg in messages if not msg.author.bot and msg.content.strip()
        ]

        if not valid_messages:
            raise ValidationError(
                message="No valid messages found to summarize (all messages are from bots or empty)"
            )

        conversation = "\n".join(
            [
                f"{msg.author.display_name}: {msg.content}"
                for msg in reversed(valid_messages)
            ]
        )

        # Limit conversation length to prevent API errors
        max_length = 8000  # Conservative limit for GPT-4o-mini
        if len(conversation) > max_length:
            conversation = (
                conversation[:max_length] + "\n[Conversation truncated due to length]"
            )
            self.logger.warning(
                f"Conversation truncated to {max_length} characters for summarization"
            )

        self.logger.info(
            f"Summarizing conversation with {len(valid_messages)} messages, {len(conversation)} characters"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following conversation with attention to each user's messages. Be concise but comprehensive.",
                    },
                    {"role": "user", "content": conversation},
                ],
                max_tokens=500,  # Limit response length
                temperature=0.3,  # Lower temperature for more consistent summaries
            )

            if not response.choices or not response.choices[0].message.content:
                raise APIError("OpenAI API returned empty response")

            summary = response.choices[0].message.content.strip()
            self.logger.info(
                f"Successfully generated summary of {len(summary)} characters"
            )
            return summary

        except openai.RateLimitError as e:
            self.logger.error(f"OpenAI rate limit exceeded: {e}")
            raise APIError("OpenAI rate limit exceeded. Please try again later.") from e
        except openai.AuthenticationError as e:
            self.logger.error(f"OpenAI authentication failed: {e}")
            raise APIError(
                "OpenAI authentication failed. Please check API configuration."
            ) from e
        except openai.APIError as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise APIError(f"OpenAI API error: {str(e)}") from e
        except openai.OpenAIError as e:
            self.logger.error(f"OpenAI service error: {e}")
            raise ExternalServiceError("OpenAI service is currently unavailable") from e
        except Exception as e:
            self.logger.error(f"Unexpected error during summarization: {e}")
            raise ExternalServiceError(
                "Unexpected error occurred during summarization"
            ) from e

    async def moderate_conversation(self, messages):
        """Moderate a list of Discord messages using OpenAI API to check for rule violations.

        Args:
            messages: List of Discord message objects to moderate

        Returns:
            str: The moderation report from OpenAI

        Raises:
            ValidationError: If no valid messages are provided
            APIError: If OpenAI API call fails
            ExternalServiceError: If there's an issue with the OpenAI service
        """
        if not messages:
            raise ValidationError(message="No messages provided for moderation")

        # Filter out messages from bots and reverse the list
        valid_messages = [
            msg for msg in messages if not msg.author.bot and msg.content.strip()
        ]

        if not valid_messages:
            raise ValidationError(
                message="No valid messages found to moderate (all messages are from bots or empty)"
            )

        conversation = "\n".join(
            [
                f"{msg.author.display_name}: {msg.content}"
                for msg in reversed(valid_messages)
            ]
        )

        # Limit conversation length to prevent API errors
        max_length = 7000  # Conservative limit for GPT-4o-mini (leaving room for rules)
        if len(conversation) > max_length:
            conversation = (
                conversation[:max_length] + "\n[Conversation truncated due to length]"
            )
            self.logger.warning(
                f"Conversation truncated to {max_length} characters for moderation"
            )

        rule_check = "\n".join(
            [f"{i + 1}. {rule}" for i, rule in enumerate(self.server_rules)]
        )

        self.logger.info(
            f"Moderating conversation with {len(valid_messages)} messages, {len(conversation)} characters"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a content moderator. Summarize the conversation and check if any of these rules were broken:\n{rule_check}\n\n"
                        f"Provide specific examples if you think a message might have broken a rule, even if unsure, so a human moderator can decide. "
                        f"Be objective and highlight potential issues clearly. If no violations are found, state that clearly.",
                    },
                    {"role": "user", "content": conversation},
                ],
                max_tokens=600,  # Limit response length
                temperature=0.2,  # Lower temperature for more consistent moderation
            )

            if not response.choices or not response.choices[0].message.content:
                raise APIError("OpenAI API returned empty response")

            report = response.choices[0].message.content.strip()
            self.logger.info(
                f"Successfully generated moderation report of {len(report)} characters"
            )
            return report

        except openai.RateLimitError as e:
            self.logger.error(f"OpenAI rate limit exceeded during moderation: {e}")
            raise APIError("OpenAI rate limit exceeded. Please try again later.") from e
        except openai.AuthenticationError as e:
            self.logger.error(f"OpenAI authentication failed during moderation: {e}")
            raise APIError(
                "OpenAI authentication failed. Please check API configuration."
            ) from e
        except openai.APIError as e:
            self.logger.error(f"OpenAI API error during moderation: {e}")
            raise APIError(f"OpenAI API error: {str(e)}") from e
        except openai.OpenAIError as e:
            self.logger.error(f"OpenAI service error during moderation: {e}")
            raise ExternalServiceError("OpenAI service is currently unavailable") from e
        except Exception as e:
            self.logger.error(f"Unexpected error during moderation: {e}")
            raise ExternalServiceError(
                "Unexpected error occurred during moderation"
            ) from e

    @app_commands.command(name="summarize")
    @handle_interaction_errors
    async def summarize(self, interaction: discord.Interaction, num_messages: int = 50) -> None:
        """Summarizes the last X messages in the channel using AI.

        Args:
            interaction: The Discord interaction object
            num_messages: Number of recent messages to summarize (1-200, default: 50)

        Raises:
            ValidationError: If num_messages is out of valid range
            APIError: If OpenAI API call fails
            ExternalServiceError: If there's an issue with the OpenAI service
        """
        # Validate num_messages parameter
        if num_messages < 1:
            raise ValidationError(
                field="num_messages", message="Number of messages must be at least 1"
            )

        if num_messages > 200:
            raise ValidationError(
                field="num_messages", message="Number of messages cannot exceed 200"
            )

        await interaction.response.defer()

        try:
            # Fetch messages from the channel
            messages = [
                message
                async for message in interaction.channel.history(limit=num_messages)
            ]

            self.logger.info(
                f"Summarize command called by {interaction.user.name} ({interaction.user.id}) for {num_messages} messages in {interaction.channel.name}"
            )

            # Generate summary using the improved method
            summary = await self.summarize_messages(messages)

            # Create a formatted response
            embed = discord.Embed(
                title="📝 Channel Summary",
                description=summary,
                color=discord.Color.blue(),
                timestamp=interaction.created_at,
            )

            embed.add_field(
                name="📊 Summary Details",
                value=f"**Channel:** {interaction.channel.mention}\n"
                f"**Messages Analyzed:** {num_messages}\n"
                f"**Requested by:** {interaction.user.mention}",
                inline=False,
            )

            embed.set_footer(text="Powered by OpenAI GPT-4o-mini")

            await interaction.followup.send(embed=embed)

        except (ValidationError, APIError, ExternalServiceError):
            # Re-raise these exceptions as-is for the error handler
            raise
        except discord.Forbidden:
            raise ValidationError(
                message="I don't have permission to read message history in this channel"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in summarize command: {e}")
            raise ExternalServiceError(
                "An unexpected error occurred while processing the summarization request"
            ) from e

    @app_commands.command(name="moderate")
    @handle_interaction_errors
    async def moderate(self, interaction: discord.Interaction, num_messages: int = 50) -> None:
        """Analyzes the last X messages in the channel for potential rule violations using AI.

        Args:
            interaction: The Discord interaction object
            num_messages: Number of recent messages to analyze (1-200, default: 50)

        Raises:
            ValidationError: If num_messages is out of valid range
            APIError: If OpenAI API call fails
            ExternalServiceError: If there's an issue with the OpenAI service
        """
        # Validate num_messages parameter
        if num_messages < 1:
            raise ValidationError(
                field="num_messages", message="Number of messages must be at least 1"
            )

        if num_messages > 200:
            raise ValidationError(
                field="num_messages", message="Number of messages cannot exceed 200"
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Fetch messages from the channel
            messages = [
                message
                async for message in interaction.channel.history(limit=num_messages)
            ]

            self.logger.info(
                f"Moderate command called by {interaction.user.name} ({interaction.user.id}) for {num_messages} messages in {interaction.channel.name}"
            )

            # Generate moderation report using the improved method
            report = await self.moderate_conversation(messages)

            # Create a formatted response
            embed = discord.Embed(
                title="🛡️ Moderation Report",
                description=report,
                color=discord.Color.orange(),
                timestamp=interaction.created_at,
            )

            embed.add_field(
                name="📊 Analysis Details",
                value=f"**Channel:** {interaction.channel.mention}\n"
                f"**Messages Analyzed:** {num_messages}\n"
                f"**Moderator:** {interaction.user.mention}",
                inline=False,
            )

            embed.add_field(
                name="⚠️ Important Note",
                value="This is an AI-generated analysis. Human moderator review is recommended for any flagged content.",
                inline=False,
            )

            embed.set_footer(text="Powered by OpenAI GPT-4o-mini • Confidential Report")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except (ValidationError, APIError, ExternalServiceError):
            # Re-raise these exceptions as-is for the error handler
            raise
        except discord.Forbidden:
            raise ValidationError(
                message="I don't have permission to read message history in this channel"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in moderate command: {e}")
            raise ExternalServiceError(
                "An unexpected error occurred while processing the moderation request"
            ) from e


async def setup(bot) -> None:
    # Replace 'your_openai_api_key' and 'server_rules' with actual values or load from config
    server_rules = [
        "Follow the Discord Community Guidelines.",
        "Don't spam or ping excessively, including images, emotes, or gifs.",
        "Don't attack other users.",
        "Don't post personal information.",
        "No bug pictures.",
    ]
    await bot.add_cog(SummarizationCog(bot, server_rules))
