"""
Utility functions and classes for The Wandering Inn cog.

This module contains shared utilities used across different TWI cog modules,
including the Google search function and UI components.
"""

import logging
from typing import Dict, Any

import discord
from googleapiclient.discovery import build

import config


def google_search(
    search_term: str, api_key: str, cse_id: str, **kwargs
) -> Dict[str, Any]:
    """
    Perform a Google Custom Search.

    Args:
        search_term: The term to search for
        api_key: Google API key for authentication
        cse_id: Custom Search Engine ID
        **kwargs: Additional parameters to pass to the search API

    Returns:
        dict: The search results as returned by the Google API
    """
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, num=9, **kwargs).execute()
    return res


class ChapterLinkButton(discord.ui.Button):
    """
    A simple link button for directing users to a chapter.

    This button is used in various commands to provide a direct link
    to the relevant chapter on The Wandering Inn website.
    """

    def __init__(self, url: str):
        """
        Initialize the button with a URL.

        Args:
            url: The URL to link to
        """
        super().__init__(style=discord.ButtonStyle.link, url=url, label="Chapter")


def log_command_usage(
    command_name: str, user_id: int, user_display_name: str, additional_info: str = ""
):
    """
    Log command usage with consistent formatting.

    Args:
        command_name: Name of the command being used
        user_id: Discord user ID
        user_display_name: User's display name
        additional_info: Additional information to log
    """
    info_str = f" - {additional_info}" if additional_info else ""
    logging.info(
        f"TWI {command_name.upper()}: User {user_id} ({user_display_name}){info_str}"
    )


def log_command_error(
    command_name: str, user_id: int, error: Exception, context: str = ""
):
    """
    Log command errors with consistent formatting.

    Args:
        command_name: Name of the command that errored
        user_id: Discord user ID
        error: The exception that occurred
        context: Additional context about the error
    """
    context_str = f" - {context}" if context else ""
    logging.error(
        f"TWI {command_name.upper()} ERROR: User {user_id}{context_str}: {error}"
    )


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with optional suffix.

    Args:
        text: The text to truncate
        max_length: Maximum length of the text
        suffix: Suffix to add if text is truncated

    Returns:
        str: The truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def validate_search_query(
    query: str, min_length: int = 2, max_length: int = 100
) -> str:
    """
    Validate and clean a search query.

    Args:
        query: The search query to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        str: The cleaned query

    Raises:
        ValueError: If query is invalid
    """
    if not query:
        raise ValueError("Search query cannot be empty")

    query = query.strip()

    if len(query) < min_length:
        raise ValueError(f"Search query must be at least {min_length} characters")

    if len(query) > max_length:
        raise ValueError(f"Search query must be {max_length} characters or less")

    return query
