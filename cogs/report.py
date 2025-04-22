import discord
from discord import app_commands
from discord.ext import commands
import logging


class ReportModal(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.additional_info = discord.ui.TextArea(placeholder="Additional info", min_length=0, max_length=2000, required=False)
        self.add_item(self.additional_info)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("on_submit")
        print("on_submit")


class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

        self.reason_select = discord.ui.Select(placeholder="Select a reason", options=[
            discord.SelectOption(label="Spam", value="spam"),
            discord.SelectOption(label="NSFW", value="nsfw"),
            discord.SelectOption(label="Harassment", value="harassment"),
            discord.SelectOption(label="Other", value="other"),
            discord.SelectOption(label="Wrong Channel", value="wrong_channel"),
            discord.SelectOption(label="Spoiler", value="spoiler")
        ])
        self.reason_select.callback = self.reason_select_callback
        self.add_item(self.reason_select)

        self.anonymous = discord.ui.Select(placeholder="Anonymous?", options=[discord.SelectOption(label="Yes", value="yes"), discord.SelectOption(label="No", value="no")])
        self.anonymous.callback = self.anonymous_callback
        self.add_item(self.anonymous)

        self.additional_info = discord.ui.Button(label="Additional info", style=discord.ButtonStyle.secondary)
        self.additional_info.callback = self.additional_info_callback
        self.add_item(self.additional_info)

        self.submit = discord.ui.Button(label="Submit", style=discord.ButtonStyle.primary)
        self.submit.callback = self.submit_callback
        self.add_item(self.submit)

    async def reason_select_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("reason_select_callback")
        print("reason_select_callback")

    async def anonymous_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("anonymous_callback")
        print("anonymous_callback")

    async def additional_info_callback(self, interaction: discord.Interaction) -> None:
        modal = ReportModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        print("additional_info_callback")

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("submit_callback")
        self.stop()
        print("submit_callback")


class ReportCog(commands.Cog, name="report"):
    def __init__(self, bot):
        self.bot = bot
        self.report = app_commands.ContextMenu(
            name="Report",
            callback=self.report
        )
        self.bot.tree.add_command(self.report)

    async def report(self, interaction: discord.Interaction, message: discord.Message):
        print("report")
        view = ReportView()
        await interaction.response.send_message("Report", view=view)
        await self.bot.db.execute("INSERT INTO reports (message_id, user_id, reason, anonymous, additional_info) VALUES ($1, $2, $3, $4, $5)",
                                      message.id, interaction.user.id, "reason", False, "additional_info")

    async def cog_load(self) -> None:
        print()

    async def cog_unload(self) -> None:
        print()
        self.bot.tree.remove_command(self.report.name, type=self.report.type)


async def setup(bot):
    await bot.add_cog(ReportCog(bot))
