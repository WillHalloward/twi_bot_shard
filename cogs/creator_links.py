import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.exc import IntegrityError

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ValidationError,
)
from utils.repositories import CreatorLinkRepository
from utils.validation import validate_url


class CreatorLinks(commands.Cog, name="Creator"):
    def __init__(self, bot) -> None:
        self.links_cache: list = []
        self.bot = bot
        self.creator_link_repo = CreatorLinkRepository(bot.get_db_session)

    async def cog_load(self) -> None:
        self.links_cache = await self.creator_link_repo.get_all_for_cache()

    creator_link = app_commands.Group(
        name="creator_link", description="Creator Link commands"
    )

    @creator_link.command(
        name="get",
        description="Posts the creators links.",
    )
    @handle_interaction_errors
    async def creator_link_get(
        self, interaction: discord.Interaction, creator: discord.User | None = None
    ) -> None:
        """Retrieve and display a creator's links.

        Args:
            interaction: The Discord interaction object
            creator: The user whose links to retrieve (defaults to command user)

        Raises:
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if creator is None:
            creator = interaction.user

        try:
            creator_links = await self.creator_link_repo.get_by_user_id(creator.id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve creator links for user {creator.id}"
            ) from e

        if creator_links:
            embed = discord.Embed(
                title=f"{creator.display_name}'s links", color=0x00FF00
            )
            embed.set_thumbnail(url=creator.display_avatar.url)

            for link in creator_links:
                if interaction.channel.is_nsfw() or not link.nsfw:
                    embed.add_field(
                        name=f"{link.title}{' - NSFW' if link.nsfw else ''}",
                        value=link.link,
                        inline=False,
                    )

            if len(embed.fields) == 0:
                await interaction.response.send_message(
                    f"**{creator.display_name}** has links, but none are appropriate for this channel."
                )
            else:
                await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"I could not find any links for **{creator.display_name}**."
            )

    @creator_link.command(
        name="add",
        description="Adds a link to your creator links.",
    )
    @handle_interaction_errors
    async def creator_link_add(
        self,
        interaction: discord.Interaction,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> None:
        """Add a new link to the user's creator links.

        Args:
            interaction: The Discord interaction object
            title: The title/name for the link
            link: The URL to add
            nsfw: Whether the link contains NSFW content (default: False)
            weight: Priority weight for ordering (higher = shown first, default: 0)
            feature: Whether to feature this link (default: True)

        Raises:
            ValidationError: If the URL format is invalid
            ResourceAlreadyExistsError: If a link with this title already exists
            DatabaseError: If database operation fails
        """
        # Validate the URL format
        try:
            validated_link = validate_url(link)
        except ValidationError as e:
            raise ValidationError(
                field="link", message=f"Invalid URL format: {str(e)}"
            ) from e

        # Validate title length and content
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        title = title.strip()
        if len(title) > 100:  # Reasonable limit for title length
            raise ValidationError(
                field="title", message="Title must be 100 characters or less"
            )

        # Validate weight range
        if weight < -1000 or weight > 1000:
            raise ValidationError(
                field="weight", message="Weight must be between -1000 and 1000"
            )

        try:
            result = await self.creator_link_repo.create(
                user_id=interaction.user.id,
                title=title,
                link=validated_link,
                nsfw=nsfw,
                weight=weight,
                feature=feature,
            )
            if result:
                await interaction.response.send_message(
                    f"✅ Successfully added link **{title}** to your creator links."
                )
            else:
                raise DatabaseError(
                    f"Failed to add creator link '{title}' for user {interaction.user.id}"
                )
        except IntegrityError as e:
            raise ResourceAlreadyExistsError(
                resource_type="creator link",
                resource_id=title,
                message=f"You already have a link with the title **{title}**. Please choose a different title or edit the existing link.",
            ) from e
        except ResourceAlreadyExistsError:
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while adding creator link") from e

    @creator_link.command(
        name="remove",
        description="Removes a link from your creator links.",
    )
    @handle_interaction_errors
    async def creator_link_remove(
        self, interaction: discord.Interaction, title: str
    ) -> None:
        """Remove a link from the user's creator links.

        Args:
            interaction: The Discord interaction object
            title: The title of the link to remove

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
            existing_link = await self.creator_link_repo.get_by_user_and_title(
                interaction.user.id, title
            )

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="creator link",
                    resource_id=title,
                    message=f"You don't have a link with the title **{title}**. Use `/creator_link get` to see your current links.",
                )

            # Delete the link
            await self.creator_link_repo.delete(interaction.user.id, title)

            await interaction.response.send_message(
                f"✅ Successfully removed link **{existing_link.title}** from your creator links."
            )

        except ResourceNotFoundError:
            # Re-raise ResourceNotFoundError as-is
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while removing creator link") from e

    @creator_link.command(
        name="edit",
        description="Edits a link from your creator links.",
    )
    @handle_interaction_errors
    async def creator_link_edit(
        self,
        interaction: discord.Interaction,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> None:
        """Edit an existing link in the user's creator links.

        Args:
            interaction: The Discord interaction object
            title: The title of the link to edit
            link: The new URL for the link
            nsfw: Whether the link contains NSFW content (default: False)
            weight: Priority weight for ordering (higher = shown first, default: 0)
            feature: Whether to feature this link (default: True)

        Raises:
            ValidationError: If the URL format or other inputs are invalid
            ResourceNotFoundError: If no link with this title exists
            DatabaseError: If database operation fails
        """
        # Validate the URL format
        try:
            validated_link = validate_url(link)
        except ValidationError as e:
            raise ValidationError(
                field="link", message=f"Invalid URL format: {str(e)}"
            ) from e

        # Validate title
        if not title or len(title.strip()) == 0:
            raise ValidationError(field="title", message="Title cannot be empty")

        title = title.strip()

        # Validate weight range
        if weight < -1000 or weight > 1000:
            raise ValidationError(
                field="weight", message="Weight must be between -1000 and 1000"
            )

        try:
            # First check if the link exists
            existing_link = await self.creator_link_repo.get_by_user_and_title(
                interaction.user.id, title
            )

            if not existing_link:
                raise ResourceNotFoundError(
                    resource_type="creator link",
                    resource_id=title,
                    message=f"You don't have a link with the title **{title}**. Use `/creator_link get` to see your current links or `/creator_link add` to create a new one.",
                )

            # Update the link
            await self.creator_link_repo.update(
                user_id=interaction.user.id,
                title=title,
                link=validated_link,
                nsfw=nsfw,
                weight=weight,
                feature=feature,
            )

            await interaction.response.send_message(
                f"✅ Successfully updated link **{existing_link.title}** in your creator links."
            )

        except ResourceNotFoundError:
            # Re-raise ResourceNotFoundError as-is
            raise
        except Exception as e:
            raise DatabaseError("Unexpected error while editing creator link") from e


async def setup(bot) -> None:
    await bot.add_cog(CreatorLinks(bot))
