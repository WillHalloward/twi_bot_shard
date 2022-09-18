import logging
from distutils import util

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands


class forumCog(commands.GroupCog, name="forum"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()  # this is now required in this context.

    @app_commands.command()
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.choices(rule=[
        Choice(name='archived', value=2),
        Choice(name='locked', value=3),
        Choice(name='auto_archive_duration', value=4),
        Choice(name='slowmode_delay', value=5),
    ])
    async def set_rules(self, interaction: discord.Interaction, rule: Choice[int], value: str, reason: str = None):
        try:
            if isinstance(interaction.channel.parent, discord.ForumChannel):
                if rule.value == 2:
                    try:
                        value = bool(util.strtobool(value))
                    except ValueError:
                        await interaction.response.send_message('Invalid value for archived. Valid values are y, yes, t, true, on, 1, n, no, f, false, off, 0', ephemeral=True)
                        return
                elif rule.value == 3:
                    try:
                        value = bool(util.strtobool(value))
                    except ValueError:
                        await interaction.response.send_message('Invalid value for archived. Valid values are y, yes, t, true, on, 1, n, no, f, false, off, 0', ephemeral=True)
                        return
                elif rule.value == 4:
                    if value in {'60', '1440', '4320', '10080'}:
                        value = int(value)
                    else:
                        await interaction.response.send_message("Invalid value for auto_archive_duration. Valid values are 60, 1440, 4320, 10080", ephemeral=True)
                        return
                elif rule.value == 5:
                    try:
                        value = int(value)
                    except ValueError:
                        await interaction.response.send_message("Invalid value for slowmode_delay. Valid values are integers", ephemeral=True)
                await interaction.response.send_message(f"Changing the rules now!", ephemeral=True)
                for thread in interaction.channel.parent.threads:
                    try:
                        await thread.edit(reason=reason, **{rule.name: value})
                    except discord.Forbidden or discord.HTTPException as e:
                        await interaction.edit_original_response(content=f'**`ERROR:`** {type(e).__name__} - {e}')
                        logging.error(f'Forums set_rules: {type(e).__name__} - {e}')
                        return
                await interaction.edit_original_response(content=f"Changed rules in {len(interaction.channel.parent.threads)} threads in this forum")
            else:
                await interaction.response.send_message("This command can only be used in a forum channel", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f' **`ERROR:`** {type(e).__name__} - {e}', ephemeral=True)
            logging.error(f'Forums set_rules: {type(e).__name__} - {e}')


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(forumCog(bot))
