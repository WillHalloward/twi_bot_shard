"""Repository for creator_links table.

This module provides a repository for accessing creator_links data.
"""

from typing import Any

from sqlalchemy import delete, select

from models.tables.creator_links import CreatorLink
from utils.repository import BaseRepository


class CreatorLinkRepository(BaseRepository):
    """Repository for creator_links table."""

    def __init__(self, session_maker) -> None:
        """Initialize the repository.

        Args:
            session_maker: Factory function to create database sessions.
        """
        super().__init__(session_maker, CreatorLink)

    async def get_by_user_id(self, user_id: int) -> list[CreatorLink]:
        """Get all creator links for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of creator links for the user.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                select(self.entity_type)
                .where(self.entity_type.user_id == user_id)
                .order_by(self.entity_type.weight.desc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_user_and_title(
        self, user_id: int, title: str
    ) -> CreatorLink | None:
        """Get a creator link by user ID and title.

        Args:
            user_id: The ID of the user.
            title: The title of the link.

        Returns:
            The creator link if found, None otherwise.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                select(self.entity_type)
                .where(self.entity_type.user_id == user_id)
                .where(self.entity_type.title.ilike(title))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_link(
        self,
        user_id: int,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> CreatorLink:
        """Add a new creator link.

        Args:
            user_id: The ID of the user.
            title: The title of the link.
            link: The URL of the link.
            nsfw: Whether the link is NSFW.
            weight: The weight of the link for sorting.
            feature: Whether the link should be featured.

        Returns:
            The created creator link.
        """
        creator_link = CreatorLink(
            user_id=user_id,
            title=title,
            link=link,
            nsfw=nsfw,
            weight=weight,
            feature=feature,
        )
        return await self.create(creator_link)

    async def update_link(
        self,
        user_id: int,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> CreatorLink | None:
        """Update a creator link.

        Args:
            user_id: The ID of the user.
            title: The title of the link.
            link: The URL of the link.
            nsfw: Whether the link is NSFW.
            weight: The weight of the link for sorting.
            feature: Whether the link should be featured.

        Returns:
            The updated creator link if found, None otherwise.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                select(self.entity_type)
                .where(self.entity_type.user_id == user_id)
                .where(self.entity_type.title.ilike(title))
            )
            result = await session.execute(stmt)
            creator_link = result.scalar_one_or_none()

            if not creator_link:
                return None

            creator_link.link = link
            creator_link.nsfw = nsfw
            creator_link.weight = weight
            creator_link.feature = feature

            await session.commit()
            await session.refresh(creator_link)
            return creator_link

    async def delete_link(self, user_id: int, title: str) -> bool:
        """Delete a creator link.

        Args:
            user_id: The ID of the user.
            title: The title of the link.

        Returns:
            True if the link was deleted, False otherwise.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                delete(self.entity_type)
                .where(self.entity_type.user_id == user_id)
                .where(self.entity_type.title.ilike(title))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def get_all_titles_and_users(self) -> list[dict[str, Any]]:
        """Get all titles and user IDs.

        Returns:
            A list of dictionaries with title and user_id.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(self.entity_type.title, self.entity_type.user_id)
            result = await session.execute(stmt)
            return [{"title": row[0], "user_id": row[1]} for row in result.all()]
