"""
Interactive help system for Twi Bot Shard.

This module provides an interactive help system using Discord's buttons and select menus.
"""

import logging
from typing import Dict, List, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_command_errors, handle_interaction_errors


class HelpView(discord.ui.View):
    """Interactive help view with buttons and select menus."""

    def __init__(self, cog: "InteractiveHelp", timeout: int = 60):
        """
        Initialize the help view.

        Args:
            cog: The InteractiveHelp cog instance
            timeout: View timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.current_category = None
        self.current_command = None

        # Add the category select menu
        self.add_item(self.CategorySelect(cog))

    class CategorySelect(discord.ui.Select):
        """Select menu for command categories."""

        def __init__(self, cog: "InteractiveHelp"):
            """
            Initialize the category select menu.

            Args:
                cog: The InteractiveHelp cog instance
            """
            self.cog = cog
            options = [
                discord.SelectOption(
                    label="Moderation",
                    description="Commands for moderating your server",
                    emoji="🛡️",
                ),
                discord.SelectOption(
                    label="Utility", description="General utility commands", emoji="🔧"
                ),
                discord.SelectOption(
                    label="Configuration",
                    description="Server configuration commands",
                    emoji="⚙️",
                ),
                discord.SelectOption(
                    label="Gallery", description="Image gallery commands", emoji="🖼️"
                ),
                discord.SelectOption(
                    label="Creator Links",
                    description="Creator link management commands",
                    emoji="🔗",
                ),
                discord.SelectOption(
                    label="Statistics",
                    description="Statistics tracking commands",
                    emoji="📊",
                ),
                discord.SelectOption(
                    label="Other", description="Miscellaneous commands", emoji="📦"
                ),
            ]

            super().__init__(
                placeholder="Select a command category",
                min_values=1,
                max_values=1,
                options=options,
            )

        async def callback(self, interaction: discord.Interaction):
            """
            Handle category selection.

            Args:
                interaction: The interaction that triggered this callback
            """
            # Get the selected category
            category = self.values[0]
            view = self.view

            # Update the current category
            view.current_category = category
            view.current_command = None

            # Get commands for this category
            commands = self.cog.get_commands_for_category(category)

            # Create the command select menu
            command_select = HelpView.CommandSelect(self.cog, commands, category)

            # Update the view
            for item in view.children[:]:
                if isinstance(item, HelpView.CommandSelect):
                    view.remove_item(item)

            view.add_item(command_select)

            # Create the embed
            embed = discord.Embed(
                title=f"{category} Commands",
                description=f"Select a command to view detailed help.",
                color=discord.Color.blue(),
            )

            for cmd in commands:
                embed.add_field(
                    name=cmd["name"], value=cmd["short_description"], inline=False
                )

            await interaction.response.edit_message(embed=embed, view=view)

    class CommandSelect(discord.ui.Select):
        """Select menu for commands within a category."""

        def __init__(self, cog: "InteractiveHelp", commands: List[Dict], category: str):
            """
            Initialize the command select menu.

            Args:
                cog: The InteractiveHelp cog instance
                commands: List of command dictionaries
                category: The current category
            """
            self.cog = cog
            self.commands = commands
            self.category = category

            options = []
            for cmd in commands:
                options.append(
                    discord.SelectOption(
                        label=cmd["name"],
                        description=cmd["short_description"][
                            :100
                        ],  # Truncate if too long
                    )
                )

            super().__init__(
                placeholder="Select a command",
                min_values=1,
                max_values=1,
                options=options,
            )

        async def callback(self, interaction: discord.Interaction):
            """
            Handle command selection.

            Args:
                interaction: The interaction that triggered this callback
            """
            # Get the selected command
            command_name = self.values[0]
            view = self.view

            # Update the current command
            view.current_command = command_name

            # Get command details
            command = next(
                (cmd for cmd in self.commands if cmd["name"] == command_name), None
            )

            if not command:
                await interaction.response.send_message(
                    "Command not found.", ephemeral=True
                )
                return

            # Create the embed
            embed = discord.Embed(
                title=f"Command: {command['name']}",
                description=command["description"],
                color=discord.Color.green(),
            )

            # Add syntax
            embed.add_field(name="Syntax", value=f"`{command['syntax']}`", inline=False)

            # Add examples if available
            if command.get("examples"):
                embed.add_field(
                    name="Examples",
                    value="\n".join(f"`{ex}`" for ex in command["examples"]),
                    inline=False,
                )

            # Add permissions if available
            if command.get("permissions"):
                embed.add_field(
                    name="Required Permissions",
                    value=command["permissions"],
                    inline=False,
                )

            # Add back button
            back_button = HelpView.BackButton(self.cog, self.category)

            # Update the view
            for item in view.children[:]:
                if isinstance(item, HelpView.BackButton):
                    view.remove_item(item)

            view.add_item(back_button)

            await interaction.response.edit_message(embed=embed, view=view)

    class BackButton(discord.ui.Button):
        """Button to go back to category view."""

        def __init__(self, cog: "InteractiveHelp", category: str):
            """
            Initialize the back button.

            Args:
                cog: The InteractiveHelp cog instance
                category: The category to go back to
            """
            self.cog = cog
            self.category = category

            super().__init__(
                style=discord.ButtonStyle.secondary, label="Back to Category", emoji="⬅️"
            )

        async def callback(self, interaction: discord.Interaction):
            """
            Handle button click.

            Args:
                interaction: The interaction that triggered this callback
            """
            view = self.view

            # Reset current command
            view.current_command = None

            # Get commands for this category
            commands = self.cog.get_commands_for_category(self.category)

            # Create the embed
            embed = discord.Embed(
                title=f"{self.category} Commands",
                description=f"Select a command to view detailed help.",
                color=discord.Color.blue(),
            )

            for cmd in commands:
                embed.add_field(
                    name=cmd["name"], value=cmd["short_description"], inline=False
                )

            # Remove this button
            for item in view.children[:]:
                if isinstance(item, HelpView.BackButton):
                    view.remove_item(item)

            await interaction.response.edit_message(embed=embed, view=view)


class InteractiveHelp(commands.Cog):
    """Interactive help system using Discord's UI components."""

    def __init__(self, bot):
        """
        Initialize the interactive help cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger("interactive_help")

        # Command database
        self.commands_db = {
            "Moderation": [
                {
                    "name": "ban",
                    "syntax": "/ban <user> [reason] [delete_days=1]",
                    "short_description": "Ban a user from the server",
                    "description": "Bans a user from the server and optionally deletes their recent messages.",
                    "examples": [
                        "/ban @Username Spamming in channels",
                        "/ban 123456789012345678 Inappropriate behavior 7",
                    ],
                    "permissions": "Ban Members",
                },
                {
                    "name": "kick",
                    "syntax": "/kick <user> [reason]",
                    "short_description": "Kick a user from the server",
                    "description": "Removes a user from the server, but they can rejoin with an invite.",
                    "examples": ["/kick @Username Disruptive behavior"],
                    "permissions": "Kick Members",
                },
                {
                    "name": "mute",
                    "syntax": "/mute <user> <duration> [reason]",
                    "short_description": "Temporarily mute a user",
                    "description": "Temporarily prevents a user from sending messages or joining voice channels.",
                    "examples": [
                        "/mute @Username 30m Excessive spam",
                        "/mute 123456789012345678 2h Inappropriate language",
                    ],
                    "permissions": "Manage Roles",
                },
                {
                    "name": "unmute",
                    "syntax": "/unmute <user> [reason]",
                    "short_description": "Unmute a user",
                    "description": "Removes a mute from a previously muted user.",
                    "examples": ["/unmute @Username Time served"],
                    "permissions": "Manage Roles",
                },
                {
                    "name": "warn",
                    "syntax": "/warn <user> <reason>",
                    "short_description": "Warn a user",
                    "description": "Issues a formal warning to a user, which is logged in the database.",
                    "examples": ["/warn @Username Breaking rule #3"],
                    "permissions": "Manage Messages",
                },
                {
                    "name": "history",
                    "syntax": "/history <user>",
                    "short_description": "View a user's moderation history",
                    "description": "Shows a user's moderation history (warnings, mutes, kicks, bans).",
                    "examples": ["/history @Username"],
                    "permissions": "Manage Messages",
                },
                {
                    "name": "purge",
                    "syntax": "/purge <count> [user]",
                    "short_description": "Delete multiple messages",
                    "description": "Deletes a specified number of messages from a channel.",
                    "examples": ["/purge 50", "/purge 20 @Username"],
                    "permissions": "Manage Messages",
                },
                {
                    "name": "slowmode",
                    "syntax": "/slowmode <seconds>",
                    "short_description": "Set channel slowmode",
                    "description": "Sets the slowmode delay for the current channel.",
                    "examples": ["/slowmode 5", "/slowmode 0"],
                    "permissions": "Manage Channels",
                },
            ],
            "Utility": [
                {
                    "name": "help",
                    "syntax": "/help [command]",
                    "short_description": "Show help information",
                    "description": "Displays help information for commands.",
                    "examples": ["/help", "/help ban"],
                },
                {
                    "name": "ping",
                    "syntax": "/ping",
                    "short_description": "Check bot latency",
                    "description": "Checks the bot's response time and API latency.",
                    "examples": ["/ping"],
                },
                {
                    "name": "userinfo",
                    "syntax": "/userinfo [user]",
                    "short_description": "Show user information",
                    "description": "Displays information about a user.",
                    "examples": ["/userinfo", "/userinfo @Username"],
                },
                {
                    "name": "serverinfo",
                    "syntax": "/serverinfo",
                    "short_description": "Show server information",
                    "description": "Displays information about the current server.",
                    "examples": ["/serverinfo"],
                },
                {
                    "name": "search",
                    "syntax": "/search <query>",
                    "short_description": "Search for messages",
                    "description": "Searches for messages containing the query.",
                    "examples": ["/search announcement"],
                },
            ],
            "Configuration": [
                {
                    "name": "settings view",
                    "syntax": "/settings view",
                    "short_description": "View bot settings",
                    "description": "Displays the current bot settings for the server.",
                    "examples": ["/settings view"],
                    "permissions": "Manage Server",
                },
                {
                    "name": "settings prefix",
                    "syntax": "/settings prefix <new_prefix>",
                    "short_description": "Change command prefix",
                    "description": "Changes the command prefix for the server.",
                    "examples": ["/settings prefix !", "/settings prefix ?"],
                    "permissions": "Manage Server",
                },
                {
                    "name": "settings logs",
                    "syntax": "/settings logs <channel>",
                    "short_description": "Set logging channel",
                    "description": "Sets the channel for logging bot actions.",
                    "examples": ["/settings logs #bot-logs"],
                    "permissions": "Manage Server",
                },
                {
                    "name": "settings permissions",
                    "syntax": "/settings permissions <command|feature>=<name> roles=<roles>",
                    "short_description": "Configure command permissions",
                    "description": "Configures which roles can use specific commands or features.",
                    "examples": [
                        "/settings permissions command=ban roles=@Moderator,@Admin",
                        "/settings permissions feature=gallery roles=@ContentCreator",
                    ],
                    "permissions": "Manage Server",
                },
            ],
            "Gallery": [
                {
                    "name": "gallery add",
                    "syntax": "/gallery add <title> <url> [description]",
                    "short_description": "Add an image to the gallery",
                    "description": "Adds an image to the gallery.",
                    "examples": [
                        '/gallery add "Sunset Artwork" https://example.com/image.png "A beautiful sunset"'
                    ],
                    "permissions": "Manage Messages or configured role",
                },
                {
                    "name": "gallery view",
                    "syntax": "/gallery view <id>",
                    "short_description": "View a gallery image",
                    "description": "Displays a specific image from the gallery.",
                    "examples": ["/gallery view 123"],
                },
                {
                    "name": "gallery search",
                    "syntax": "/gallery search <query>",
                    "short_description": "Search gallery images",
                    "description": "Searches for images in the gallery.",
                    "examples": ["/gallery search sunset"],
                },
                {
                    "name": "gallery remove",
                    "syntax": "/gallery remove <id>",
                    "short_description": "Remove a gallery image",
                    "description": "Removes an image from the gallery.",
                    "examples": ["/gallery remove 123"],
                    "permissions": "Manage Messages or configured role",
                },
            ],
            "Creator Links": [
                {
                    "name": "link add",
                    "syntax": "/link add <platform> <username> <url>",
                    "short_description": "Add a creator link",
                    "description": "Adds a creator link to the database.",
                    "examples": [
                        "/link add Twitter artist_name https://twitter.com/artist_name"
                    ],
                    "permissions": "Manage Messages or configured role",
                },
                {
                    "name": "link view",
                    "syntax": "/link view <platform> <username>",
                    "short_description": "View a creator link",
                    "description": "Displays a specific creator link.",
                    "examples": ["/link view Twitter artist_name"],
                },
                {
                    "name": "link search",
                    "syntax": "/link search <query>",
                    "short_description": "Search creator links",
                    "description": "Searches for creator links in the database.",
                    "examples": ["/link search artist_name"],
                },
                {
                    "name": "link remove",
                    "syntax": "/link remove <platform> <username>",
                    "short_description": "Remove a creator link",
                    "description": "Removes a creator link from the database.",
                    "examples": ["/link remove Twitter artist_name"],
                    "permissions": "Manage Messages or configured role",
                },
            ],
            "Statistics": [
                {
                    "name": "stats server",
                    "syntax": "/stats server",
                    "short_description": "View server statistics",
                    "description": "Displays server activity statistics.",
                    "examples": ["/stats server"],
                },
                {
                    "name": "stats user",
                    "syntax": "/stats user [user]",
                    "short_description": "View user statistics",
                    "description": "Displays user activity statistics.",
                    "examples": ["/stats user", "/stats user @Username"],
                },
                {
                    "name": "stats commands",
                    "syntax": "/stats commands",
                    "short_description": "View command usage statistics",
                    "description": "Displays command usage statistics.",
                    "examples": ["/stats commands"],
                    "permissions": "Manage Server",
                },
            ],
            "Other": [
                {
                    "name": "custom add",
                    "syntax": "/custom add <name> <response>",
                    "short_description": "Create a custom command",
                    "description": "Creates a new custom command that responds with predefined text.",
                    "examples": ["/custom add rules Please read the rules in #rules"],
                    "permissions": "Manage Server",
                },
                {
                    "name": "custom remove",
                    "syntax": "/custom remove <name>",
                    "short_description": "Remove a custom command",
                    "description": "Removes a custom command.",
                    "examples": ["/custom remove rules"],
                    "permissions": "Manage Server",
                },
                {
                    "name": "summarize",
                    "syntax": "/summarize <message_count>",
                    "short_description": "Summarize recent messages",
                    "description": "Summarizes recent messages in the channel.",
                    "examples": ["/summarize 50"],
                },
                {
                    "name": "report",
                    "syntax": "/report <message_link> <reason>",
                    "short_description": "Report a message",
                    "description": "Reports a message to the moderators.",
                    "examples": [
                        "/report https://discord.com/channels/123/456/789 Inappropriate content"
                    ],
                },
            ],
        }

        # Set up attributes expected by tests
        self.command_categories = list(self.commands_db.keys())
        self.category_descriptions = {
            "Moderation": "Commands for moderating your server",
            "Utility": "General utility commands",
            "Configuration": "Server configuration commands",
            "Gallery": "Image gallery management commands",
            "Creator Links": "Creator link management commands",
            "Statistics": "Statistics tracking commands",
            "Other": "Miscellaneous commands"
        }
        self.commands_by_category = self.commands_db

    def get_commands_for_category(self, category: str) -> List[Dict]:
        """
        Get commands for a specific category.

        Args:
            category: The category name

        Returns:
            List of command dictionaries
        """
        return self.commands_db.get(category, [])

    @commands.command(name="help")
    @handle_command_errors
    async def help_command(self, ctx, *, command_name: Optional[str] = None):
        """
        Show help for commands.

        Args:
            ctx: The command context
            command_name: Optional command name to get help for
        """
        if command_name:
            # Search for the command in all categories
            for category, commands in self.commands_db.items():
                for cmd in commands:
                    if cmd["name"] == command_name:
                        embed = discord.Embed(
                            title=f"Command: {cmd['name']}",
                            description=cmd["description"],
                            color=discord.Color.green(),
                        )

                        embed.add_field(
                            name="Syntax", value=f"`{cmd['syntax']}`", inline=False
                        )

                        if cmd.get("examples"):
                            embed.add_field(
                                name="Examples",
                                value="\n".join(f"`{ex}`" for ex in cmd["examples"]),
                                inline=False,
                            )

                        if cmd.get("permissions"):
                            embed.add_field(
                                name="Required Permissions",
                                value=cmd["permissions"],
                                inline=False,
                            )

                        await ctx.send(embed=embed)
                        return

            # Command not found
            await ctx.send(
                f"Command '{command_name}' not found. Use `{ctx.prefix}help` to see all commands."
            )
        else:
            # Show interactive help
            embed = discord.Embed(
                title="Interactive Help System",
                description="Select a category to view commands.",
                color=discord.Color.blue(),
            )

            for category in self.commands_db.keys():
                cmd_count = len(self.commands_db[category])
                embed.add_field(
                    name=category, value=f"{cmd_count} commands", inline=True
                )

            view = HelpView(self)
            await ctx.send(embed=embed, view=view)

    @app_commands.command(name="help")
    @app_commands.describe(command="The command to get help for")
    @handle_interaction_errors
    async def help_slash(
        self, interaction: discord.Interaction, command: Optional[str] = None
    ):
        """
        Show help for commands.

        Args:
            interaction: The interaction
            command: Optional command name to get help for
        """
        if command:
            # Search for the command in all categories
            for category, commands in self.commands_db.items():
                for cmd in commands:
                    if cmd["name"] == command:
                        embed = discord.Embed(
                            title=f"Command: {cmd['name']}",
                            description=cmd["description"],
                            color=discord.Color.green(),
                        )

                        embed.add_field(
                            name="Syntax", value=f"`{cmd['syntax']}`", inline=False
                        )

                        if cmd.get("examples"):
                            embed.add_field(
                                name="Examples",
                                value="\n".join(f"`{ex}`" for ex in cmd["examples"]),
                                inline=False,
                            )

                        if cmd.get("permissions"):
                            embed.add_field(
                                name="Required Permissions",
                                value=cmd["permissions"],
                                inline=False,
                            )

                        await interaction.response.send_message(embed=embed)
                        return

            # Command not found
            await interaction.response.send_message(
                f"Command '{command}' not found. Use `/help` to see all commands."
            )
        else:
            # Show interactive help
            embed = discord.Embed(
                title="Interactive Help System",
                description="Select a category to view commands.",
                color=discord.Color.blue(),
            )

            for category in self.commands_db.keys():
                cmd_count = len(self.commands_db[category])
                embed.add_field(
                    name=category, value=f"{cmd_count} commands", inline=True
                )

            view = HelpView(self)
            await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    """
    Set up the interactive help cog.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(InteractiveHelp(bot))
