import logging
import re
from typing import List, Optional

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_interaction_errors
from utils.validation import validate_url
from utils.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    PermissionError,
)


class LinkTags(commands.Cog, name="Links"):
    def __init__(self, bot):
        self.bot = bot
        self.links_cache = None

    async def cog_load(self) -> None:
        self.links_cache = await self.bot.db.fetch("SELECT * FROM links")

    async def link_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        ln = []
        for x in self.links_cache:
            ln.append({"title": x["title"], "content": x["content"]})
        return [
            app_commands.Choice(
                name=f"{link['title']}: {link['content']}"[0:100], value=link["title"]
            )
            for link in ln
            if current.lower() in link["title"].lower() or current == ""
        ][0:25]

    link = app_commands.Group(name="link", description="Link commands")

    @link.command(name="get", description="Gets a link with the given name")
    @app_commands.autocomplete(title=link_autocomplete)
    @handle_interaction_errors
    async def link_get(self, interaction: discord.Interaction, title: str):
        """
        Retrieve and display a link by its title.

        Args:
            interaction: The Discord interaction object
            title: The title of the link to retrieve

        Raises:
            ValidationError: If the title is invalid
            ResourceNotFoundError: If no link with this title exists
            DatabaseError: If database query fails
        """
        # Validate title
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        title = title.strip()

        try:
            query_r = await self.bot.db.fetchrow(
                "SELECT content, title, embed FROM links WHERE lower(title) = lower($1)",
                title,
            )
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to retrieve link '{title}'") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during link query") from e

        if query_r:
            if query_r["embed"]:
                await interaction.response.send_message(
                    f"[{query_r['title']}]({query_r['content']})"
                )
            else:
                await interaction.response.send_message(
                    f"**{query_r['title']}**: {query_r['content']}"
                )
        else:
            raise ResourceNotFoundError(
                resource_type="link",
                resource_id=title,
                message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
            )

    @link.command(name="list", description="View all links.")
    @handle_interaction_errors
    async def link_list(self, interaction: discord.Interaction):
        """
        Display a list of all available links.

        Args:
            interaction: The Discord interaction object

        Raises:
            DatabaseError: If database query fails
        """
        try:
            query_r = await self.bot.db.fetch("SELECT title FROM links ORDER BY title")
        except asyncpg.PostgresError as e:
            raise DatabaseError("Failed to retrieve links list") from e
        except Exception as e:
            raise QueryError("Unexpected error during links list query") from e

        if not query_r:
            await interaction.response.send_message("No links are currently available.")
            return

        # Build the message with proper formatting
        link_titles = [f"`{link['title']}`" for link in query_r]
        message = " ".join(link_titles)

        # Ensure message doesn't exceed Discord's limit
        if len(message) > 1990:
            message = message[:1990] + "..."

        await interaction.response.send_message(f"**Available Links:** {message}")

    @link.command(
        name="add",
        description="Adds a link with the given name to the given url and tag",
    )
    @handle_interaction_errors
    async def link_add(
        self,
        interaction: discord.Interaction,
        content: str,
        title: str,
        tag: str = None,
        embed: bool = True,
    ):
        """
        Add a new link with the given title, content, and optional tag.

        Args:
            interaction: The Discord interaction object
            content: The URL or content of the link
            title: The title/name for the link
            tag: Optional tag to categorize the link
            embed: Whether to display the link as an embed (default: True)

        Raises:
            ValidationError: If the URL format or other inputs are invalid
            ResourceAlreadyExistsError: If a link with this title already exists
            DatabaseError: If database operation fails
        """
        # Validate inputs
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        if not content or len(content.strip()) == 0:
            raise ValidationError(field="content", message="Content cannot be empty")

        title = title.strip()
        content = content.strip()

        # Validate title length
        if len(title) > 100:
            raise ValidationError(
                field="title", message="Title must be 100 characters or less"
            )

        # Validate URL format if it looks like a URL
        if content.startswith(("http://", "https://", "ftp://")):
            try:
                validated_content = validate_url(content)
                content = validated_content
            except ValidationError as e:
                raise ValidationError(
                    field="content", message=f"Invalid URL format: {str(e)}"
                ) from e

        # Validate tag if provided
        if tag and len(tag.strip()) > 50:
            raise ValidationError(
                field="tag", message="Tag must be 50 characters or less"
            )

        if tag:
            tag = tag.strip()

        try:
            await self.bot.db.execute(
                "INSERT INTO links(content, tag, user_who_added, id_user_who_added, time_added, title, embed) "
                "VALUES ($1, $2, $3, $4, now(), $5, $6)",
                content,
                tag,
                interaction.user.display_name,
                interaction.user.id,
                title,
                embed,
            )

            # Update cache
            try:
                self.links_cache = await self.bot.db.fetch("SELECT * FROM links")
            except Exception:
                # Cache update failure shouldn't break the command
                pass

            await interaction.response.send_message(
                f"✅ Successfully added link **{title}**\n"
                f"**Content:** <{content}>\n"
                f"**Tag:** {tag if tag else 'None'}\n"
                f"**Embed:** {'Yes' if embed else 'No'}"
            )

        except asyncpg.UniqueViolationError:
            raise ResourceAlreadyExistsError(
                resource_type="link",
                resource_id=title,
                message=f"A link with the title **{title}** already exists. Please choose a different title.",
            )
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to add link '{title}'") from e
        except Exception as e:
            raise DatabaseError(f"Unexpected error while adding link") from e

    @link.command(name="delete", description="Deletes a link with the given name")
    @app_commands.autocomplete(title=link_autocomplete)
    @handle_interaction_errors
    async def link_delete(self, interaction: discord.Interaction, title: str):
        """
        Delete a link by its title.

        Args:
            interaction: The Discord interaction object
            title: The title of the link to delete

        Raises:
            ValidationError: If the title is invalid
            ResourceNotFoundError: If no link with this title exists
            DatabaseError: If database operation fails
        """
        # Validate title
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        title = title.strip()

        try:
            # First check if the link exists
            existing_link = await self.bot.db.fetchrow(
                "SELECT title, user_who_added, id_user_who_added FROM links WHERE lower(title) = lower($1)",
                title,
            )

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="link",
                    resource_id=title,
                    message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
                )

            # Delete the link
            result = await self.bot.db.execute(
                "DELETE FROM links WHERE lower(title) = lower($1)", title
            )

            # Update cache
            try:
                self.links_cache = await self.bot.db.fetch("SELECT * FROM links")
            except Exception:
                # Cache update failure shouldn't break the command
                pass

            await interaction.response.send_message(
                f"✅ Successfully deleted link **{existing_link['title']}** (added by {existing_link['user_who_added']})."
            )

        except ResourceNotFoundError:
            # Re-raise ResourceNotFoundError as-is
            raise
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to delete link '{title}'") from e
        except Exception as e:
            raise DatabaseError(f"Unexpected error while deleting link") from e

    @link.command(
        name="edit",
        description="Edits a link with the given name",
    )
    @handle_interaction_errors
    async def link_edit(
        self, interaction: discord.Interaction, title: str, content: str
    ):
        """
        Edit an existing link's content.

        Args:
            interaction: The Discord interaction object
            title: The title of the link to edit
            content: The new content/URL for the link

        Raises:
            ValidationError: If the URL format or other inputs are invalid
            ResourceNotFoundError: If no link with this title exists
            PermissionError: If user doesn't have permission to edit this link
            DatabaseError: If database operation fails
        """
        # Validate inputs
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        if not content or len(content.strip()) == 0:
            raise ValidationError(field="content", message="Content cannot be empty")

        title = title.strip()
        content = content.strip()

        # Validate URL format if it looks like a URL
        if content.startswith(("http://", "https://", "ftp://")):
            try:
                validated_content = validate_url(content)
                content = validated_content
            except ValidationError as e:
                raise ValidationError(
                    field="content", message=f"Invalid URL format: {str(e)}"
                ) from e

        try:
            # Check if the link exists
            existing_link = await self.bot.db.fetchrow(
                "SELECT * FROM links WHERE lower(title) = lower($1)",
                title,
            )

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="link",
                    resource_id=title,
                    message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
                )

            # Check permissions
            if (
                existing_link["id_user_who_added"] != interaction.user.id
                and not interaction.user.guild_permissions.administrator
            ):
                raise PermissionError(
                    message=f"You can only edit links you added yourself. This link was added by {existing_link['user_who_added']}."
                )

            # Update the link
            await self.bot.db.execute(
                "UPDATE links SET content = $1 WHERE lower(title) = lower($2)",
                content,
                title,
            )

            # Update cache
            try:
                self.links_cache = await self.bot.db.fetch("SELECT * FROM links")
            except Exception:
                # Cache update failure shouldn't break the command
                pass

            await interaction.response.send_message(
                f"✅ Successfully edited link **{existing_link['title']}**\n"
                f"**New Content:** <{content}>"
            )

        except (ResourceNotFoundError, PermissionError):
            # Re-raise these exceptions as-is
            raise
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to edit link '{title}'") from e
        except Exception as e:
            raise DatabaseError(f"Unexpected error while editing link") from e

    @app_commands.command(name="tags", description="See all available tags")
    @handle_interaction_errors
    async def tags(self, interaction: discord.Interaction):
        """
        Display a list of all available tags.

        Args:
            interaction: The Discord interaction object

        Raises:
            DatabaseError: If database query fails
        """
        try:
            query_r = await self.bot.db.fetch(
                "SELECT DISTINCT tag FROM links WHERE tag IS NOT NULL ORDER BY tag"
            )
        except asyncpg.PostgresError as e:
            raise DatabaseError("Failed to retrieve tags list") from e
        except Exception as e:
            raise QueryError("Unexpected error during tags query") from e

        if not query_r:
            await interaction.response.send_message("No tags are currently available.")
            return

        # Build the message with proper formatting
        tag_list = [f"`{tag['tag']}`" for tag in query_r if tag["tag"]]

        if not tag_list:
            await interaction.response.send_message("No tags are currently available.")
            return

        message = " ".join(tag_list)

        # Ensure message doesn't exceed Discord's limit
        if len(message) > 1990:
            message = message[:1990] + "..."

        await interaction.response.send_message(f"**Available Tags:** {message}")

    @app_commands.command(
        name="tag", description="View all links that got a certain tag"
    )
    @handle_interaction_errors
    async def tag(self, interaction: discord.Interaction, tag: str):
        """
        Display all links that have a specific tag.

        Args:
            interaction: The Discord interaction object
            tag: The tag to search for

        Raises:
            ValidationError: If the tag is invalid
            ResourceNotFoundError: If no links with this tag exist
            DatabaseError: If database query fails
        """
        # Validate tag
        if not tag or len(tag.strip()) == 0:
            raise ValidationError(field="tag", message="Tag cannot be empty")

        tag = tag.strip()

        try:
            query_r = await self.bot.db.fetch(
                "SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY NULLIF(regexp_replace(title, '\\D', '', 'g'), '')::int",
                tag,
            )
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to retrieve links for tag '{tag}'") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during tag query") from e

        if not query_r:
            raise ResourceNotFoundError(
                resource_type="links with tag",
                resource_id=tag,
                message=f"I could not find any links with the tag **{tag}**. Use `/tags` to see all available tags or `/link list` to see all links.",
            )

        # Build the message with proper formatting
        link_titles = [f"`{link['title']}`" for link in query_r]
        message = "\n".join(link_titles)

        # Ensure message doesn't exceed Discord's limit
        if len(message) > 1990:
            message = message[:1990] + "..."

        await interaction.response.send_message(
            f"**Links with tag '{tag}':**\n{message}"
        )


async def setup(bot):
    await bot.add_cog(LinkTags(bot))
