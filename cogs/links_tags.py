import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.exc import IntegrityError

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    PermissionError,
    QueryError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ValidationError,
)
from utils.repositories import LinkRepository
from utils.validation import validate_url


class LinkTags(commands.Cog, name="Links"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.links_cache = None
        self.link_repo = LinkRepository(bot.get_db_session)

    async def cog_load(self) -> None:
        # Keep raw SQL for cache - autocomplete expects dictionary format
        self.links_cache = await self.bot.db.fetch("SELECT * FROM links")

    async def _refresh_cache(self) -> None:
        """Refresh the links cache after modifications."""
        try:
            self.links_cache = await self.bot.db.fetch("SELECT * FROM links")
        except Exception:
            # Cache update failure shouldn't break the command
            pass

    async def link_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
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

    async def category_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete choices for link categories/tags.

        Args:
            interaction: The Discord interaction object
            current: The current input from the user

        Returns:
            List of app_commands.Choice objects for categories
        """
        categories = set()
        if self.links_cache:
            for link in self.links_cache:
                tag = link.get("tag")
                if tag:
                    categories.add(tag)
                else:
                    categories.add("Uncategorized")

        return [
            app_commands.Choice(name=category, value=category)
            for category in sorted(categories)
            if current.lower() in category.lower() or current == ""
        ][0:25]

    link = app_commands.Group(name="link", description="Link commands")

    @link.command(name="get", description="Gets a link with the given name")
    @app_commands.autocomplete(title=link_autocomplete)
    @handle_interaction_errors
    async def link_get(self, interaction: discord.Interaction, title: str) -> None:
        """Retrieve and display a link by its title.

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
            link_entry = await self.link_repo.get_by_title(title)
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve link '{title}'") from e

        if link_entry:
            if link_entry.embed:
                await interaction.response.send_message(
                    f"[{link_entry.title}]({link_entry.content})"
                )
            else:
                await interaction.response.send_message(
                    f"**{link_entry.title}**: {link_entry.content}"
                )
        else:
            raise ResourceNotFoundError(
                resource_type="link",
                resource_id=title,
                message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
            )

    @link.command(
        name="list",
        description="View all link categories and counts, or links in a specific category.",
    )
    @app_commands.autocomplete(category=category_autocomplete)
    @handle_interaction_errors
    async def link_list(
        self, interaction: discord.Interaction, category: str = None
    ) -> None:
        """Display a list of all link categories with the number of links in each category,
        or show all links within a specific category if one is provided.
        This is optimized for handling large amounts of links within Discord's character limit.

        Args:
            interaction: The Discord interaction object
            category: Optional category name to show links from that category

        Raises:
            ValidationError: If the category parameter is invalid
            ResourceNotFoundError: If no links exist in the specified category
            DatabaseError: If database query fails
        """
        if category:
            # Show links within the specified category
            # Validate category
            if len(category.strip()) == 0:
                raise ValidationError(
                    field="category", message="Category cannot be empty"
                )

            category = category.strip()

            try:
                # Keep raw SQL for complex ORDER BY with regexp_replace
                # Handle "Uncategorized" as a special case
                if category.lower() == "uncategorized":
                    query_r = await self.bot.db.fetch(
                        "SELECT title FROM links WHERE tag IS NULL ORDER BY NULLIF(regexp_replace(title, '\\D', '', 'g'), '')::int, title"
                    )
                else:
                    query_r = await self.bot.db.fetch(
                        "SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY NULLIF(regexp_replace(title, '\\D', '', 'g'), '')::int, title",
                        category,
                    )
            except asyncpg.PostgresError as e:
                raise DatabaseError(
                    f"Failed to retrieve links for category '{category}'"
                ) from e
            except Exception as e:
                raise QueryError("Unexpected error during category links query") from e

            if not query_r:
                raise ResourceNotFoundError(
                    resource_type="links in category",
                    resource_id=category,
                    message=f"I could not find any links in the category **{category}**. Use `/link list` to see all available categories.",
                )

            # Build the message with proper formatting
            link_titles = [f"`{link['title']}`" for link in query_r]
            message = "\n".join(link_titles)

            # Ensure message doesn't exceed Discord's limit
            if len(message) > 1990:
                message = message[:1990] + "..."

            await interaction.response.send_message(
                f"**Links in category '{category}':**\n{message}"
            )
        else:
            # Show all categories with counts (original behavior)
            try:
                # Keep raw SQL for complex GROUP BY and COALESCE
                query_r = await self.bot.db.fetch(
                    """
                    SELECT
                        COALESCE(tag, 'Uncategorized') as category,
                        COUNT(*) as link_count
                    FROM links
                    GROUP BY tag
                    ORDER BY
                        CASE WHEN tag IS NULL THEN 1 ELSE 0 END,
                        tag
                """
                )
            except asyncpg.PostgresError as e:
                raise DatabaseError("Failed to retrieve links categories") from e
            except Exception as e:
                raise QueryError(
                    "Unexpected error during links categories query"
                ) from e

            if not query_r:
                await interaction.response.send_message(
                    "No links are currently available."
                )
                return

            # Build the message with proper formatting
            # Ensure message doesn't exceed Discord's limit
            message = "**Link Categories:**\n"

            for category_info in query_r:
                category_name = category_info["category"]
                count = category_info["link_count"]
                line = (
                    f"• **{category_name}**: {count} link{'s' if count != 1 else ''}\n"
                )

                # Check if adding this line would exceed Discord's limit
                if len(message) + len(line) < 1990:
                    message += line
                else:
                    message += "..."
                    break

            await interaction.response.send_message(message)

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
    ) -> None:
        """Add a new link with the given title, content, and optional tag.

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
            result = await self.link_repo.create(
                title=title,
                content=content,
                tag=tag,
                user_who_added=interaction.user.display_name,
                id_user_who_added=interaction.user.id,
                embed=embed,
                guild_id=interaction.guild.id if interaction.guild else None,
            )

            if result:
                # Refresh cache
                await self._refresh_cache()

                await interaction.response.send_message(
                    f"✅ Successfully added link **{title}**\n"
                    f"**Content:** <{content}>\n"
                    f"**Tag:** {tag if tag else 'None'}\n"
                    f"**Embed:** {'Yes' if embed else 'No'}"
                )
            else:
                raise DatabaseError(f"Failed to add link '{title}'")

        except IntegrityError:
            raise ResourceAlreadyExistsError(
                resource_type="link",
                resource_id=title,
                message=f"A link with the title **{title}** already exists. Please choose a different title.",
            )
        except ResourceAlreadyExistsError:
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while adding link") from e

    @link.command(name="delete", description="Deletes a link with the given name")
    @app_commands.autocomplete(title=link_autocomplete)
    @handle_interaction_errors
    async def link_delete(self, interaction: discord.Interaction, title: str) -> None:
        """Delete a link by its title.

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
            existing_link = await self.link_repo.get_by_title(title)

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="link",
                    resource_id=title,
                    message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
                )

            # Delete the link
            await self.link_repo.delete_by_title(title)

            # Refresh cache
            await self._refresh_cache()

            await interaction.response.send_message(
                f"✅ Successfully deleted link **{existing_link.title}** (added by {existing_link.user_who_added})."
            )

        except ResourceNotFoundError:
            # Re-raise ResourceNotFoundError as-is
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while deleting link") from e

    @link.command(
        name="edit",
        description="Edits a link with the given name",
    )
    @handle_interaction_errors
    async def link_edit(
        self, interaction: discord.Interaction, title: str, content: str
    ) -> None:
        """Edit an existing link's content.

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
            existing_link = await self.link_repo.get_by_title(title)

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="link",
                    resource_id=title,
                    message=f"I could not find a link with the title **{title}**. Use `/link list` to see all available links.",
                )

            # Check permissions
            if (
                existing_link.id_user_who_added != interaction.user.id
                and not interaction.user.guild_permissions.administrator
            ):
                raise PermissionError(
                    message=f"You can only edit links you added yourself. This link was added by {existing_link.user_who_added}."
                )

            # Update the link
            await self.link_repo.update(title=title, content=content)

            # Refresh cache
            await self._refresh_cache()

            await interaction.response.send_message(
                f"✅ Successfully edited link **{existing_link.title}**\n"
                f"**New Content:** <{content}>"
            )

        except (ResourceNotFoundError, PermissionError):
            # Re-raise these exceptions as-is
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while editing link") from e

    @app_commands.command(
        name="tag", description="View all links that got a certain tag"
    )
    @handle_interaction_errors
    async def tag(self, interaction: discord.Interaction, tag: str) -> None:
        """Display all links that have a specific tag.

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
            # Keep raw SQL for complex ORDER BY with regexp_replace
            query_r = await self.bot.db.fetch(
                "SELECT title FROM links WHERE lower(tag) = lower($1) ORDER BY NULLIF(regexp_replace(title, '\\D', '', 'g'), '')::int",
                tag,
            )
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to retrieve links for tag '{tag}'") from e
        except Exception as e:
            raise QueryError("Unexpected error during tag query") from e

        if not query_r:
            raise ResourceNotFoundError(
                resource_type="links with tag",
                resource_id=tag,
                message=f"I could not find any links with the tag **{tag}**. Use `/link list` to see all available categories.",
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


async def setup(bot) -> None:
    await bot.add_cog(LinkTags(bot))
