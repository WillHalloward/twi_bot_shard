"""
Repository for gallery migration operations.
"""

import logging
from typing import List, Optional, Dict, Any, Callable, Awaitable
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.gallery_migration import GalleryMigration


class GalleryMigrationRepository:
    """Repository for managing gallery migration data."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]):
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def create_migration_entry(
        self,
        message_id: int,
        channel_id: int,
        channel_name: str,
        guild_id: int,
        title: Optional[str] = None,
        images: Optional[List[str]] = None,
        creator: Optional[str] = None,
        tags: Optional[List[str]] = None,
        jump_url: Optional[str] = None,
        author_id: int = 0,
        author_name: str = "",
        is_bot: bool = False,
        created_at: Optional[datetime] = None,
        target_forum: Optional[str] = None,
        content_type: Optional[str] = None,
        has_attachments: bool = False,
        attachment_count: int = 0,
        needs_manual_review: bool = False,
        raw_embed_data: Optional[Dict[str, Any]] = None,
        raw_content: Optional[str] = None
    ) -> Optional[GalleryMigration]:
        """
        Create a new gallery migration entry.

        Args:
            message_id: Discord message ID
            channel_id: Discord channel ID
            channel_name: Channel name
            guild_id: Discord guild ID
            title: Post title
            images: List of image URLs
            creator: Creator information
            tags: List of tags
            jump_url: Discord jump URL
            author_id: Message author ID
            author_name: Message author name
            is_bot: Whether message was from bot
            created_at: Original message timestamp
            target_forum: Target forum (sfw/nsfw)
            content_type: Content type classification
            has_attachments: Whether message has attachments
            attachment_count: Number of attachments
            needs_manual_review: Whether entry needs manual review
            raw_embed_data: Raw embed data for reference
            raw_content: Original message content

        Returns:
            Created GalleryMigration entry or None if failed
        """
        try:
            session = await self.session_factory()
            try:
                migration_entry = GalleryMigration(
                    message_id=message_id,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    guild_id=guild_id,
                    title=title,
                    images=images,
                    creator=creator,
                    tags=tags,
                    jump_url=jump_url,
                    author_id=author_id,
                    author_name=author_name,
                    is_bot=is_bot,
                    created_at=created_at or datetime.utcnow(),
                    target_forum=target_forum,
                    content_type=content_type,
                    has_attachments=has_attachments,
                    attachment_count=attachment_count,
                    needs_manual_review=needs_manual_review,
                    raw_embed_data=raw_embed_data,
                    raw_content=raw_content
                )

                session.add(migration_entry)
                await session.commit()
                await session.refresh(migration_entry)

                self.logger.info(f"Created gallery migration entry for message {message_id}")
                return migration_entry
            finally:
                await session.close()

        except Exception as e:
            self.logger.error(f"Error creating gallery migration entry: {e}")
            return None

    async def get_by_message_id(self, message_id: int) -> Optional[GalleryMigration]:
        """Get migration entry by message ID."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.message_id == message_id)
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting migration entry by message ID {message_id}: {e}")
            return None

    async def get_all_unmigrated(self) -> List[GalleryMigration]:
        """Get all unmigrated entries."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.migrated == False)
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting unmigrated entries: {e}")
            return []

    async def get_entries_needing_review(self) -> List[GalleryMigration]:
        """Get entries that need manual review."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(
                        GalleryMigration.needs_manual_review == True,
                        GalleryMigration.reviewed == False
                    )
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting entries needing review: {e}")
            return []

    async def update_migration_status(
        self, 
        message_id: int, 
        migrated: bool = True, 
        migrated_at: Optional[datetime] = None
    ) -> bool:
        """Update migration status for an entry."""
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(GalleryMigration)
                    .where(GalleryMigration.message_id == message_id)
                    .values(
                        migrated=migrated,
                        migrated_at=migrated_at or datetime.utcnow()
                    )
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating migration status for {message_id}: {e}")
            return False

    async def update_review_status(
        self, 
        message_id: int, 
        reviewed: bool = True,
        reviewed_by: Optional[int] = None,
        reviewed_at: Optional[datetime] = None
    ) -> bool:
        """Update review status for an entry."""
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(GalleryMigration)
                    .where(GalleryMigration.message_id == message_id)
                    .values(
                        reviewed=reviewed,
                        reviewed_by=reviewed_by,
                        reviewed_at=reviewed_at or datetime.utcnow()
                    )
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating review status for {message_id}: {e}")
            return False

    async def update_tags(self, message_id: int, tags: List[str]) -> bool:
        """Update tags for an entry."""
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(GalleryMigration)
                    .where(GalleryMigration.message_id == message_id)
                    .values(tags=tags)
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating tags for {message_id}: {e}")
            return False

    async def get_statistics(self) -> Dict[str, Any]:
        """Get migration statistics."""
        try:
            session = await self.session_factory()
            try:
                # Total entries
                total_result = await session.execute(select(GalleryMigration))
                total_entries = len(list(total_result.scalars().all()))

                # Migrated entries
                migrated_result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.migrated == True)
                )
                migrated_entries = len(list(migrated_result.scalars().all()))

                # Entries needing review
                review_result = await session.execute(
                    select(GalleryMigration).where(
                        GalleryMigration.needs_manual_review == True,
                        GalleryMigration.reviewed == False
                    )
                )
                review_entries = len(list(review_result.scalars().all()))

                # Bot vs manual posts
                bot_result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.is_bot == True)
                )
                bot_entries = len(list(bot_result.scalars().all()))

                return {
                    "total_entries": total_entries,
                    "migrated_entries": migrated_entries,
                    "pending_migration": total_entries - migrated_entries,
                    "needs_review": review_entries,
                    "bot_posts": bot_entries,
                    "manual_posts": total_entries - bot_entries,
                    "migration_progress": (migrated_entries / total_entries * 100) if total_entries > 0 else 0
                }
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting migration statistics: {e}")
            return {}

    async def delete_entry(self, message_id: int) -> bool:
        """Delete a migration entry."""
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    delete(GalleryMigration).where(GalleryMigration.message_id == message_id)
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting migration entry {message_id}: {e}")
            return False

    async def bulk_create_entries(self, entries: List[Dict[str, Any]]) -> int:
        """Bulk create migration entries."""
        created_count = 0
        try:
            session = await self.session_factory()
            try:
                for entry_data in entries:
                    try:
                        migration_entry = GalleryMigration(**entry_data)
                        session.add(migration_entry)
                        created_count += 1
                    except Exception as e:
                        self.logger.error(f"Error creating entry for message {entry_data.get('message_id')}: {e}")
                        continue

                await session.commit()
                self.logger.info(f"Bulk created {created_count} migration entries")
                return created_count
            finally:
                await session.close()

        except Exception as e:
            self.logger.error(f"Error in bulk create: {e}")
            return created_count
