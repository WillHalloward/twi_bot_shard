"""Interactive help system for Twi Bot Shard.

This module provides an interactive help system using Discord's buttons and select menus.
"""

import discord
import structlog
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_command_errors, handle_interaction_errors


class HelpView(discord.ui.View):
    """Interactive help view with buttons and select menus."""

    def __init__(self, cog: "InteractiveHelp", timeout: int = 60) -> None:
        """Initialize the help view.

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

        def __init__(self, cog: "InteractiveHelp") -> None:
            """Initialize the category select menu.

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

        async def callback(self, interaction: discord.Interaction) -> None:
            """Handle category selection.

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
                description="Select a command to view detailed help.",
                color=discord.Color.blue(),
            )

            for cmd in commands:
                embed.add_field(
                    name=cmd["name"], value=cmd["short_description"], inline=False
                )

            await interaction.response.edit_message(embed=embed, view=view)

    class CommandSelect(discord.ui.Select):
        """Select menu for commands within a category."""

        def __init__(
            self, cog: "InteractiveHelp", commands: list[dict], category: str
        ) -> None:
            """Initialize the command select menu.

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

        async def callback(self, interaction: discord.Interaction) -> None:
            """Handle command selection.

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

        def __init__(self, cog: "InteractiveHelp", category: str) -> None:
            """Initialize the back button.

            Args:
                cog: The InteractiveHelp cog instance
                category: The category to go back to
            """
            self.cog = cog
            self.category = category

            super().__init__(
                style=discord.ButtonStyle.secondary, label="Back to Category", emoji="⬅️"
            )

        async def callback(self, interaction: discord.Interaction) -> None:
            """Handle button click.

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
                description="Select a command to view detailed help.",
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

    def __init__(self, bot) -> None:
        """Initialize the interactive help cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = structlog.get_logger("cogs.interactive_help")

        # Command database — kept in sync with the cogs' actual command surface.
        self.commands_db = {
            "Moderation": [
                {
                    "name": "mod reset",
                    "syntax": "/mod reset [command]",
                    "short_description": "Reset a command's cooldown",
                    "description": "Resets the cooldown of a command for the user.",
                    "examples": ["/mod reset poll"],
                    "permissions": "Ban Members",
                },
                {
                    "name": "mod state",
                    "syntax": "/mod state [message]",
                    "short_description": "Post an official moderator message",
                    "description": "Posts an official, formatted moderator message.",
                    "examples": ["/mod state The channel is now read-only"],
                    "permissions": "Ban Members",
                },
                {
                    "name": "moderate",
                    "syntax": "/moderate [num_messages=50]",
                    "short_description": "AI-check recent messages for rule violations",
                    "description": "Analyzes the last X messages in the channel for potential rule violations using AI.",
                    "examples": ["/moderate", "/moderate 100"],
                },
                {
                    "name": "Report Message",
                    "syntax": "Right-click a message → Apps → Report Message",
                    "short_description": "Report a message to the moderators",
                    "description": "Context-menu command that reports a message to the moderators, with an optional reason and anonymous option.",
                    "examples": ["Right-click a message → Apps → Report Message"],
                },
                {
                    "name": "Pin",
                    "syntax": "Right-click a message → Apps → Pin",
                    "short_description": "Pin a message",
                    "description": "Context-menu command that pins a message in channels where pinning is enabled.",
                    "examples": ["Right-click a message → Apps → Pin"],
                },
            ],
            "Utility": [
                {
                    "name": "help",
                    "syntax": "/help [command]",
                    "short_description": "Show help information",
                    "description": "Displays help information for commands.",
                    "examples": ["/help", "/help ping"],
                },
                {
                    "name": "ping",
                    "syntax": "/ping",
                    "short_description": "Check bot latency",
                    "description": "Gives the latency of the bot.",
                    "examples": ["/ping"],
                },
                {
                    "name": "roll",
                    "syntax": "/roll [dice=20] [amount=1] [modifier=0]",
                    "short_description": "Roll dice",
                    "description": "Rolls dice, e.g. 2d6+3.",
                    "examples": ["/roll", "/roll dice:6 amount:2 modifier:1"],
                },
                {
                    "name": "pat",
                    "syntax": "/pat",
                    "short_description": "Give Cognita a pat",
                    "description": "Give Cognita a pat for a job well done!",
                    "examples": ["/pat"],
                },
                {
                    "name": "avatar",
                    "syntax": "/avatar [member]",
                    "short_description": "Show a user's avatar",
                    "description": "Posts the full version of a user's avatar.",
                    "examples": ["/avatar", "/avatar @Username"],
                },
                {
                    "name": "info user",
                    "syntax": "/info user [member]",
                    "short_description": "Show user information",
                    "description": "Gives the account information of a user.",
                    "examples": ["/info user", "/info user @Username"],
                },
                {
                    "name": "info server",
                    "syntax": "/info server",
                    "short_description": "Show server information",
                    "description": "Gives information about the current server.",
                    "examples": ["/info server"],
                },
                {
                    "name": "info role",
                    "syntax": "/info role [role]",
                    "short_description": "Show role information",
                    "description": "Gives information about a role.",
                    "examples": ["/info role @Members"],
                },
                {
                    "name": "summarize",
                    "syntax": "/summarize [num_messages=50]",
                    "short_description": "Summarize recent messages",
                    "description": "Summarizes the last X messages in the channel using AI.",
                    "examples": ["/summarize", "/summarize 100"],
                },
                {
                    "name": "User info",
                    "syntax": "Right-click a user → Apps → User info",
                    "short_description": "Show detailed user information",
                    "description": "Context-menu command that displays detailed information about a Discord user.",
                    "examples": ["Right-click a user → Apps → User info"],
                },
            ],
            "Configuration": [
                {
                    "name": "set_admin_role",
                    "syntax": "/set_admin_role [role]",
                    "short_description": "Set the server's admin role",
                    "description": "Sets the admin role for this server. Members with this role are treated as bot admins.",
                    "examples": ["/set_admin_role @Admin"],
                    "permissions": "Manage Messages",
                },
                {
                    "name": "get_admin_role",
                    "syntax": "/get_admin_role",
                    "short_description": "Show the configured admin role",
                    "description": "Shows the currently configured admin role for this server.",
                    "examples": ["/get_admin_role"],
                },
                {
                    "name": "admin set_pin_channels",
                    "syntax": "/admin set_pin_channels [channel]",
                    "short_description": "Set channels where Pin works",
                    "description": "Adds or removes a channel from the list where the Pin context-menu command is allowed.",
                    "examples": ["/admin set_pin_channels #art"],
                    "permissions": "Ban Members",
                },
                {
                    "name": "update_password",
                    "syntax": "/update_password [password] [link]",
                    "short_description": "Update the chapter password",
                    "description": "Updates the password and link returned by /password.",
                    "examples": ["/update_password swordmaster https://..."],
                    "permissions": "Admin or bot owner",
                },
                {
                    "name": "admin_role add",
                    "syntax": "/admin_role add [role] [category] [auto_replace=False] [required_roles]",
                    "short_description": "Add a self-assignable role",
                    "description": "Adds a role to the self-assignable roles list.",
                    "examples": ["/admin_role add @Artist category:Hobbies"],
                    "permissions": "Admin or bot owner",
                },
                {
                    "name": "admin_role remove",
                    "syntax": "/admin_role remove [role]",
                    "short_description": "Remove a self-assignable role",
                    "description": "Removes a role from the self-assignable roles list.",
                    "examples": ["/admin_role remove @Artist"],
                    "permissions": "Admin or bot owner",
                },
                {
                    "name": "admin_role weight",
                    "syntax": "/admin_role weight [role] [new_weight]",
                    "short_description": "Change a role's sort weight",
                    "description": "Changes the sort weight of a self-assignable role.",
                    "examples": ["/admin_role weight @Artist 10"],
                    "permissions": "Admin or bot owner",
                },
            ],
            "Gallery": [
                {
                    "name": "Repost",
                    "syntax": "Right-click a message → Apps → Repost",
                    "short_description": "Repost a message's content",
                    "description": "Context-menu command that analyzes a message and reposts its content (images, AO3/Twitter/Instagram links, files) to the configured repost channels.",
                    "examples": ["Right-click a message → Apps → Repost"],
                    "permissions": "Ban Members",
                },
                {
                    "name": "gallery_admin set_repost",
                    "syntax": "/gallery_admin set_repost [channel]",
                    "short_description": "Configure a repost channel",
                    "description": "Adds or removes a channel from the repost destination channels.",
                    "examples": ["/gallery_admin set_repost #gallery"],
                    "permissions": "Admin or bot owner",
                },
            ],
            "Creator Links": [
                {
                    "name": "creator_link get",
                    "syntax": "/creator_link get [creator]",
                    "short_description": "Show a creator's links",
                    "description": "Posts the creator's links (defaults to your own).",
                    "examples": ["/creator_link get", "/creator_link get @Username"],
                },
                {
                    "name": "creator_link add",
                    "syntax": "/creator_link add [title] [link] [nsfw=False] [weight=0] [feature=True]",
                    "short_description": "Add a creator link",
                    "description": "Adds a link to your creator links.",
                    "examples": ["/creator_link add Twitter https://twitter.com/me"],
                },
                {
                    "name": "creator_link remove",
                    "syntax": "/creator_link remove [title]",
                    "short_description": "Remove a creator link",
                    "description": "Removes a link from your creator links.",
                    "examples": ["/creator_link remove Twitter"],
                },
                {
                    "name": "creator_link edit",
                    "syntax": "/creator_link edit [title] [link] [nsfw=False] [weight=0] [feature=True]",
                    "short_description": "Edit a creator link",
                    "description": "Edits a link in your creator links.",
                    "examples": ["/creator_link edit Twitter https://twitter.com/new"],
                },
            ],
            "Statistics": [
                {
                    "name": "messagecount",
                    "syntax": "/messagecount [channel] [hours]",
                    "short_description": "Count messages in a channel",
                    "description": "Retrieves the message count from a channel over the last X hours.",
                    "examples": ["/messagecount #general 24"],
                },
                {
                    "name": "stats server",
                    "syntax": "/stats server [days=7]",
                    "short_description": "View server statistics",
                    "description": "Comprehensive server activity statistics for the given period.",
                    "examples": ["/stats server", "/stats server 30"],
                },
                {
                    "name": "stats channel",
                    "syntax": "/stats channel [channel] [days=7]",
                    "short_description": "View channel statistics",
                    "description": "Comprehensive channel activity statistics for the given period.",
                    "examples": [
                        "/stats channel #general",
                        "/stats channel #general 14",
                    ],
                },
                {
                    "name": "stats user",
                    "syntax": "/stats user [user] [days=7]",
                    "short_description": "View user statistics",
                    "description": "Comprehensive user activity statistics for the given period.",
                    "examples": ["/stats user @Username", "/stats user @Username 14"],
                },
                {
                    "name": "stats role",
                    "syntax": "/stats role [role] [days=7]",
                    "short_description": "View role statistics",
                    "description": "Comprehensive activity statistics for a role's members.",
                    "examples": ["/stats role @Moderator", "/stats role @Members 30"],
                },
                {
                    "name": "stats category",
                    "syntax": "/stats category [category] [days=7]",
                    "short_description": "View category statistics",
                    "description": "Comprehensive statistics for all channels in a category.",
                    "examples": [
                        "/stats category General",
                        "/stats category Gaming 14",
                    ],
                },
                {
                    "name": "stats thread",
                    "syntax": "/stats thread [thread] [days=7]",
                    "short_description": "View thread statistics",
                    "description": "Comprehensive thread activity statistics for the given period.",
                    "examples": [
                        "/stats thread ThreadName",
                        "/stats thread ThreadName 7",
                    ],
                },
            ],
            "Other": [
                {
                    "name": "wiki",
                    "syntax": "/wiki [query]",
                    "short_description": "Search The Wandering Inn wiki",
                    "description": "Searches The Wandering Inn wiki for a matching article.",
                    "examples": ["/wiki Erin"],
                },
                {
                    "name": "find",
                    "syntax": "/find [query]",
                    "short_description": "Search wanderinginn.com",
                    "description": "Does a Google search on wanderinginn.com and returns the results.",
                    "examples": ["/find acid flies"],
                    "permissions": "Bot channel only",
                },
                {
                    "name": "password",
                    "syntax": "/password",
                    "short_description": "Get the latest chapter password",
                    "description": "Gives the password for the latest chapter (patrons) or instructions for non-patrons.",
                    "examples": ["/password"],
                },
                {
                    "name": "connectdiscord",
                    "syntax": "/connectdiscord",
                    "short_description": "Connect Patreon to Discord",
                    "description": "Information for patrons on how to connect their Patreon account to Discord.",
                    "examples": ["/connectdiscord"],
                },
                {
                    "name": "invistext",
                    "syntax": "/invistext [chapter]",
                    "short_description": "List invisible text",
                    "description": "Gives a list of all the invisible text in TWI.",
                    "examples": ["/invistext"],
                },
                {
                    "name": "coloredtext",
                    "syntax": "/coloredtext",
                    "short_description": "List colored text",
                    "description": "Lists the different colored texts in TWI.",
                    "examples": ["/coloredtext"],
                },
                {
                    "name": "ao3",
                    "syntax": "/ao3 [ao3_url]",
                    "short_description": "Show AO3 work info",
                    "description": "Posts information about an Archive of Our Own work.",
                    "examples": ["/ao3 https://archiveofourown.org/works/123"],
                },
                {
                    "name": "poll",
                    "syntax": "/poll [poll_id]",
                    "short_description": "Show a Patreon poll",
                    "description": "Displays the latest active poll or a specific poll by ID.",
                    "examples": ["/poll", "/poll 42"],
                },
                {
                    "name": "polllist",
                    "syntax": "/polllist [year]",
                    "short_description": "List polls for a year",
                    "description": "Displays a list of polls from a specific year with their IDs.",
                    "examples": ["/polllist", "/polllist 2024"],
                    "permissions": "Bot channel only",
                },
                {
                    "name": "getpoll",
                    "syntax": "/getpoll",
                    "short_description": "Fetch polls from Patreon",
                    "description": "Fetches and updates polls from the Patreon API.",
                    "examples": ["/getpoll"],
                    "permissions": "Ban Members",
                },
                {
                    "name": "findpoll",
                    "syntax": "/findpoll [query]",
                    "short_description": "Search poll options",
                    "description": "Searches through poll options using keywords or phrases.",
                    "examples": ["/findpoll dragon"],
                },
                {
                    "name": "roles",
                    "syntax": "/roles",
                    "short_description": "List self-assignable roles",
                    "description": "Posts all the roles in the server you can assign yourself.",
                    "examples": ["/roles"],
                },
                {
                    "name": "role",
                    "syntax": "/role [role]",
                    "short_description": "Add/remove a self-assignable role",
                    "description": "Adds or removes a self-assignable role from yourself.",
                    "examples": ["/role @Artist"],
                },
                {
                    "name": "quote add",
                    "syntax": "/quote add [quote]",
                    "short_description": "Add a quote",
                    "description": "Adds a quote to the list of quotes.",
                    "examples": ['/quote add "It was a good day."'],
                },
                {
                    "name": "quote get",
                    "syntax": "/quote get [index]",
                    "short_description": "Get a quote",
                    "description": "Posts a random quote, or the quote with the given index.",
                    "examples": ["/quote get", "/quote get 12"],
                },
                {
                    "name": "quote find",
                    "syntax": "/quote find [search]",
                    "short_description": "Search quotes",
                    "description": "Searches for a quote.",
                    "examples": ["/quote find good day"],
                },
                {
                    "name": "quote who",
                    "syntax": "/quote who [index]",
                    "short_description": "Show who added a quote",
                    "description": "Posts who added the quote with the given index.",
                    "examples": ["/quote who 12"],
                },
                {
                    "name": "quote delete",
                    "syntax": "/quote delete [delete]",
                    "short_description": "Delete a quote",
                    "description": "Deletes a quote.",
                    "examples": ["/quote delete 12"],
                },
                {
                    "name": "link get",
                    "syntax": "/link get [title]",
                    "short_description": "Get a saved link",
                    "description": "Gets a link with the given name.",
                    "examples": ["/link get faq"],
                },
                {
                    "name": "link list",
                    "syntax": "/link list [category]",
                    "short_description": "List links",
                    "description": "Views all link categories and counts, or links in a specific category.",
                    "examples": ["/link list", "/link list guides"],
                },
                {
                    "name": "link add",
                    "syntax": "/link add [content] [title] [tag] [embed=True]",
                    "short_description": "Add a link",
                    "description": "Adds a link with the given name, URL, and tag.",
                    "examples": ["/link add https://example.com faq guides"],
                },
                {
                    "name": "link edit",
                    "syntax": "/link edit [title] [content]",
                    "short_description": "Edit a link",
                    "description": "Edits a link with the given name (your own links, or any as an admin).",
                    "examples": ["/link edit faq https://example.com/new"],
                },
                {
                    "name": "link delete",
                    "syntax": "/link delete [title]",
                    "short_description": "Delete a link",
                    "description": "Deletes a link with the given name.",
                    "examples": ["/link delete faq"],
                },
                {
                    "name": "tag",
                    "syntax": "/tag [tag]",
                    "short_description": "List links with a tag",
                    "description": "Views all links that have a certain tag.",
                    "examples": ["/tag guides"],
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
            "Other": "Miscellaneous commands",
        }
        self.commands_by_category = self.commands_db

    def get_commands_for_category(self, category: str) -> list[dict]:
        """Get commands for a specific category.

        Args:
            category: The category name

        Returns:
            List of command dictionaries
        """
        return self.commands_db.get(category, [])

    @commands.command(name="help")
    @handle_command_errors
    async def help_command(self, ctx, *, command_name: str | None = None) -> None:
        """Show help for commands.

        Args:
            ctx: The command context
            command_name: Optional command name to get help for
        """
        if command_name:
            # Search for the command in all categories
            for _category, commands in self.commands_db.items():
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

            for category in self.commands_db:
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
        self, interaction: discord.Interaction, command: str | None = None
    ) -> None:
        """Show help for commands.

        Args:
            interaction: The interaction
            command: Optional command name to get help for
        """
        if command:
            # Search for the command in all categories
            for _category, commands in self.commands_db.items():
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

            for category in self.commands_db:
                cmd_count = len(self.commands_db[category])
                embed.add_field(
                    name=category, value=f"{cmd_count} commands", inline=True
                )

            view = HelpView(self)
            await interaction.response.send_message(embed=embed, view=view)


async def setup(bot) -> None:
    """Set up the interactive help cog.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(InteractiveHelp(bot))
