"""
Permission utilities for Cognita bot.

This module provides utilities for permission checks across the bot,
including functions to check if a user is an admin or the bot owner.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('permissions')

async def admin_or_me_check(ctx_or_interaction):
    """
    Check if the user is an admin or the bot owner.
    
    This function works with both Context objects (for traditional commands)
    and Interaction objects (for application commands).
    
    Args:
        ctx_or_interaction: The command context or interaction
        
    Returns:
        bool: True if the user is an admin or the bot owner, False otherwise
    """
    # Determine if we're dealing with a Context or an Interaction
    is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
    
    # Get the appropriate bot instance
    bot = ctx_or_interaction.client if is_interaction else ctx_or_interaction.bot
    
    # Get the user and guild
    user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.message.author
    guild = ctx_or_interaction.guild
    
    if not guild:
        return False
    
    # Get user roles for efficiency
    user_roles = [role.id for role in user.roles]
    
    # Get the settings cog
    settings_cog = bot.get_cog("Settings")
    
    # Use the is_admin utility from the settings cog
    if settings_cog:
        return await settings_cog.is_admin(
            bot,
            guild.id,
            user.id,
            user_roles
        )
    else:
        # Fallback to the old hardcoded check if settings cog is not loaded
        role = discord.utils.get(guild.roles, id=346842813687922689)
        if user.id == 268608466690506753:
            return True
        elif role in user.roles:
            return True
        else:
            return False

def admin_or_me_check_wrapper(ctx):
    """
    Wrapper for async admin_or_me_check to use with @commands.check decorator.
    
    Args:
        ctx: The command context
        
    Returns:
        A check function that can be used with @commands.check
    """
    async def predicate(ctx):
        return await admin_or_me_check(ctx)
    return commands.check(predicate)

def app_admin_or_me_check(interaction):
    """
    Wrapper for async admin_or_me_check to use with @app_commands.check decorator.
    
    Args:
        interaction: The interaction object
        
    Returns:
        bool: True if the user is an admin or the bot owner, False otherwise
    """
    return admin_or_me_check(interaction)