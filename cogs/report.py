import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ValidationError,
    PermissionError,
)


class ReportModal(discord.ui.Modal):
    def __init__(self, report_view: "ReportView"):
        super().__init__(title="Additional Information")
        self.report_view = report_view
        self.logger = logging.getLogger("report_modal")

        self.additional_info = discord.ui.TextInput(
            label="Additional Information",
            placeholder="Please provide any additional details about this report...",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=2000,
            required=False,
        )
        self.add_item(self.additional_info)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission."""
        try:
            self.report_view.additional_info_text = self.additional_info.value or ""
            self.logger.info(
                f"Additional info collected for report by user {interaction.user.id}"
            )
            await interaction.response.send_message(
                "✅ Additional information saved.", ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error handling additional info submission: {e}")
            await interaction.response.send_message(
                "❌ Failed to save additional information.", ephemeral=True
            )


class ReportView(discord.ui.View):
    def __init__(self, message: discord.Message, bot):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.message = message
        self.bot = bot
        self.logger = logging.getLogger("report_view")

        # Store user selections
        self.selected_reason: Optional[str] = None
        self.is_anonymous: Optional[bool] = None
        self.additional_info_text: str = ""

        self.reason_select = discord.ui.Select(
            placeholder="Select a reason for reporting",
            options=[
                discord.SelectOption(
                    label="Spam",
                    value="spam",
                    description="Unwanted repetitive content",
                ),
                discord.SelectOption(
                    label="NSFW", value="nsfw", description="Not safe for work content"
                ),
                discord.SelectOption(
                    label="Harassment",
                    value="harassment",
                    description="Bullying or harassment",
                ),
                discord.SelectOption(
                    label="Other", value="other", description="Other rule violation"
                ),
                discord.SelectOption(
                    label="Wrong Channel",
                    value="wrong_channel",
                    description="Content in wrong channel",
                ),
                discord.SelectOption(
                    label="Spoiler", value="spoiler", description="Unmarked spoilers"
                ),
            ],
        )
        self.reason_select.callback = self.reason_select_callback
        self.add_item(self.reason_select)

        self.anonymous = discord.ui.Select(
            placeholder="Report anonymously?",
            options=[
                discord.SelectOption(
                    label="Yes - Anonymous",
                    value="yes",
                    description="Hide my identity from moderators",
                ),
                discord.SelectOption(
                    label="No - Include my name",
                    value="no",
                    description="Show my identity to moderators",
                ),
            ],
        )
        self.anonymous.callback = self.anonymous_callback
        self.add_item(self.anonymous)

        self.additional_info = discord.ui.Button(
            label="Add Details", style=discord.ButtonStyle.secondary, emoji="📝"
        )
        self.additional_info.callback = self.additional_info_callback
        self.add_item(self.additional_info)

        self.submit = discord.ui.Button(
            label="Submit Report", style=discord.ButtonStyle.danger, emoji="🚨"
        )
        self.submit.callback = self.submit_callback
        self.add_item(self.submit)

    async def reason_select_callback(self, interaction: discord.Interaction) -> None:
        """Handle reason selection."""
        try:
            self.selected_reason = interaction.data["values"][0]
            self.logger.info(
                f"User {interaction.user.id} selected reason: {self.selected_reason}"
            )
            await interaction.response.send_message(
                f"✅ Reason selected: **{self.selected_reason.replace('_', ' ').title()}**",
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error handling reason selection: {e}")
            await interaction.response.send_message(
                "❌ Failed to select reason.", ephemeral=True
            )

    async def anonymous_callback(self, interaction: discord.Interaction) -> None:
        """Handle anonymous selection."""
        try:
            self.is_anonymous = interaction.data["values"][0] == "yes"
            anonymous_text = "anonymous" if self.is_anonymous else "with your identity"
            self.logger.info(
                f"User {interaction.user.id} chose to report {anonymous_text}"
            )
            await interaction.response.send_message(
                f"✅ Report will be submitted **{anonymous_text}**", ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error handling anonymous selection: {e}")
            await interaction.response.send_message(
                "❌ Failed to set anonymity preference.", ephemeral=True
            )

    async def additional_info_callback(self, interaction: discord.Interaction) -> None:
        """Handle additional info button click."""
        try:
            modal = ReportModal(self)
            await interaction.response.send_modal(modal)
            self.logger.info(
                f"Additional info modal opened for user {interaction.user.id}"
            )
        except Exception as e:
            self.logger.error(f"Error opening additional info modal: {e}")
            await interaction.response.send_message(
                "❌ Failed to open additional info form.", ephemeral=True
            )

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        """Handle report submission."""
        try:
            # Validate required fields
            if self.selected_reason is None:
                await interaction.response.send_message(
                    "❌ Please select a reason for the report.", ephemeral=True
                )
                return

            if self.is_anonymous is None:
                await interaction.response.send_message(
                    "❌ Please choose whether to report anonymously.", ephemeral=True
                )
                return

            # Submit the report
            await self._submit_report(interaction)

        except Exception as e:
            self.logger.error(f"Error in submit callback: {e}")
            await interaction.response.send_message(
                "❌ Failed to submit report. Please try again.", ephemeral=True
            )

    async def _submit_report(self, interaction: discord.Interaction) -> None:
        """Submit the report to the database."""
        try:
            await self.bot.db.execute(
                "INSERT INTO reports (message_id, user_id, reason, anonymous, additional_info, reported_user_id, guild_id, channel_id, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())",
                self.message.id,
                interaction.user.id,
                self.selected_reason,
                self.is_anonymous,
                self.additional_info_text,
                self.message.author.id,
                interaction.guild.id if interaction.guild else None,
                self.message.channel.id,
            )

            self.logger.info(
                f"Report submitted by user {interaction.user.id} for message {self.message.id} with reason {self.selected_reason}"
            )

            await interaction.response.send_message(
                "✅ **Report submitted successfully!**\n"
                f"**Reason:** {self.selected_reason.replace('_', ' ').title()}\n"
                f"**Anonymous:** {'Yes' if self.is_anonymous else 'No'}\n"
                "Thank you for helping keep our community safe.",
                ephemeral=True,
            )

            self.stop()

        except Exception as e:
            self.logger.error(f"Database error submitting report: {e}")
            raise DatabaseError("Failed to submit report to database") from e

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.logger.info("Report view timed out")
        for item in self.children:
            item.disabled = True


class ReportCog(commands.Cog, name="report"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("report_cog")
        self.report = app_commands.ContextMenu(
            name="Report Message", callback=self.report
        )
        self.bot.tree.add_command(self.report)

    @handle_interaction_errors
    async def report(self, interaction: discord.Interaction, message: discord.Message):
        """
        Report a message using the context menu.

        Args:
            interaction: The Discord interaction object
            message: The message being reported

        Raises:
            ValidationError: If the message or user is invalid
            PermissionError: If user doesn't have permission to report
            DatabaseError: If database operations fail
        """
        # Validate inputs
        if not message:
            raise ValidationError(message="No message selected for reporting")

        if not interaction.user:
            raise ValidationError(message="Unable to identify reporting user")

        # Prevent self-reporting
        if message.author.id == interaction.user.id:
            raise ValidationError(message="You cannot report your own messages")

        # Prevent reporting bot messages
        if message.author.bot:
            raise ValidationError(message="You cannot report bot messages")

        # Check if user has already reported this message
        try:
            existing_report = await self.bot.db.fetchrow(
                "SELECT id FROM reports WHERE message_id = $1 AND user_id = $2",
                message.id,
                interaction.user.id,
            )

            if existing_report:
                raise ValidationError(message="You have already reported this message")

        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            self.logger.error(f"Error checking existing reports: {e}")
            raise DatabaseError("Failed to check existing reports") from e

        # Create and send the report view
        try:
            view = ReportView(message, self.bot)

            embed = discord.Embed(
                title="🚨 Report Message",
                description=f"You are reporting a message by {message.author.mention}",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Message Content",
                value=(
                    message.content[:1000]
                    + ("..." if len(message.content) > 1000 else "")
                    if message.content
                    else "*No text content*"
                ),
                inline=False,
            )
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Message ID", value=str(message.id), inline=True)
            embed.set_footer(text="Please select a reason and submit your report")

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            self.logger.info(
                f"Report interface opened by user {interaction.user.id} for message {message.id}"
            )

        except Exception as e:
            self.logger.error(f"Error creating report interface: {e}")
            raise DatabaseError("Failed to create report interface") from e

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("Report cog loaded successfully")

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("Report cog unloading")
        try:
            self.bot.tree.remove_command(self.report.name, type=self.report.type)
            self.logger.info("Report context menu removed successfully")
        except Exception as e:
            self.logger.error(f"Error removing report context menu: {e}")


async def setup(bot):
    await bot.add_cog(ReportCog(bot))
