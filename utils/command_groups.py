"""Shared command groups for organizing bot commands across multiple cogs.

This module defines command groups that can be used across different cogs to
organize related commands under a single parent command. This allows for better
command organization and prevents duplication of group definitions.

Groups defined here:
    - admin: Personal/owner-only commands for bot administration
    - mod: Server moderation commands for server staff
    - gallery_admin: Gallery-specific administration commands
"""

from discord import app_commands

# Admin group - Owner-only commands for bot administration
# These commands should be restricted to the bot owner only
admin = app_commands.Group(
    name="admin",
    description="Owner-only commands for bot administration"
)

# Mod group - Server moderation commands
# These commands are for server moderators and staff
mod = app_commands.Group(
    name="mod",
    description="Server moderation commands"
)

# Gallery admin group - Gallery-specific administration
# These commands are for managing the gallery system
gallery_admin = app_commands.Group(
    name="gallery_admin",
    description="Gallery administration and management commands"
)
