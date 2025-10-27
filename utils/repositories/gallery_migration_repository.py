"""Repository for gallery migration operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.gallery_migration import GalleryMigration


class GalleryMigrationRepository:
    """Repository for managing gallery migration data."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def create_migration_entry(
        self,
        message_id: int,
        channel_id: int,
        channel_name: str,
        guild_id: int,
        title: str | None = None,
        images: list[str] | None = None,
        creator: str | None = None,
        tags: list[str] | None = None,
        jump_url: str | None = None,
        author_id: int = 0,
        author_name: str = "",
        is_bot: bool = False,
        created_at: datetime | None = None,
        target_forum: str | None = None,
        content_type: str | None = None,
        has_attachments: bool = False,
        attachment_count: int = 0,
        needs_manual_review: bool = False,
        raw_embed_data: dict[str, Any] | None = None,
        raw_content: str | None = None,
    ) -> GalleryMigration | None:
        """Create a new gallery migration entry.

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
                    created_at=created_at or datetime.now(UTC),
                    target_forum=target_forum,
                    content_type=content_type,
                    has_attachments=has_attachments,
                    attachment_count=attachment_count,
                    needs_manual_review=needs_manual_review,
                    raw_embed_data=raw_embed_data,
                    raw_content=raw_content,
                    extracted_at=datetime.now(UTC),
                )

                session.add(migration_entry)
                await session.commit()
                await session.refresh(migration_entry)

                self.logger.info(
                    f"Created gallery migration entry for message {message_id}"
                )
                return migration_entry
            finally:
                await session.close()

        except Exception as e:
            self.logger.error(f"Error creating gallery migration entry: {e}")
            return None

    async def get_by_message_id(self, message_id: int) -> GalleryMigration | None:
        """Get migration entry by message ID."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(
                        GalleryMigration.message_id == message_id
                    )
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting migration entry by message ID {message_id}: {e}"
            )
            return None

    async def get_all_unmigrated(self) -> list[GalleryMigration]:
        """Get all unmigrated entries."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(not GalleryMigration.migrated)
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting unmigrated entries: {e}")
            return []

    async def get_entries_needing_review(self) -> list[GalleryMigration]:
        """Get entries that need manual review."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMigration).where(
                        GalleryMigration.needs_manual_review,
                        not GalleryMigration.reviewed,
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
        migrated_at: datetime | None = None,
    ) -> bool:
        """Update migration status for an entry."""
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(GalleryMigration)
                    .where(GalleryMigration.message_id == message_id)
                    .values(
                        migrated=migrated, migrated_at=migrated_at or datetime.now(UTC)
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
        reviewed_by: int | None = None,
        reviewed_at: datetime | None = None,
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
                        reviewed_at=reviewed_at or datetime.now(UTC),
                    )
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating review status for {message_id}: {e}")
            return False

    async def update_tags(self, message_id: int, tags: list[str]) -> bool:
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

    async def get_statistics(self) -> dict[str, Any]:
        """Get migration statistics."""
        try:
            session = await self.session_factory()
            try:
                # Total entries
                total_result = await session.execute(select(GalleryMigration))
                total_entries = len(list(total_result.scalars().all()))

                # Migrated entries
                migrated_result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.migrated)
                )
                migrated_entries = len(list(migrated_result.scalars().all()))

                # Entries needing review
                review_result = await session.execute(
                    select(GalleryMigration).where(
                        GalleryMigration.needs_manual_review,
                        not GalleryMigration.reviewed,
                    )
                )
                review_entries = len(list(review_result.scalars().all()))

                # Bot vs manual posts
                bot_result = await session.execute(
                    select(GalleryMigration).where(GalleryMigration.is_bot)
                )
                bot_entries = len(list(bot_result.scalars().all()))

                return {
                    "total_entries": total_entries,
                    "migrated_entries": migrated_entries,
                    "pending_migration": total_entries - migrated_entries,
                    "needs_review": review_entries,
                    "bot_posts": bot_entries,
                    "manual_posts": total_entries - bot_entries,
                    "migration_progress": (
                        (migrated_entries / total_entries * 100)
                        if total_entries > 0
                        else 0
                    ),
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
                    delete(GalleryMigration).where(
                        GalleryMigration.message_id == message_id
                    )
                )
                await session.commit()
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting migration entry {message_id}: {e}")
            return False

    async def bulk_create_entries(self, entries: list[dict[str, Any]]) -> int:
        """Bulk create migration entries, skipping duplicates."""
        created_count = 0
        skipped_count = 0
        try:
            session = await self.session_factory()
            try:
                # First, get all message_ids from the entries to check for existing ones
                message_ids = [
                    entry.get("message_id")
                    for entry in entries
                    if entry.get("message_id")
                ]

                # Query existing message_ids in a single batch query
                if message_ids:
                    existing_result = await session.execute(
                        select(GalleryMigration.message_id).where(
                            GalleryMigration.message_id.in_(message_ids)
                        )
                    )
                    existing_message_ids = {
                        row[0] for row in existing_result.fetchall()
                    }
                else:
                    existing_message_ids = set()

                self.logger.info(
                    f"Found {len(existing_message_ids)} existing entries out of {len(entries)} total entries"
                )

                # Track message_ids processed in this batch to avoid duplicates within the same batch
                processed_in_batch = set()

                for entry_data in entries:
                    try:
                        message_id = entry_data.get("message_id")

                        # Skip if message_id is None or empty
                        if not message_id:
                            skipped_count += 1
                            self.logger.debug("Skipping entry with missing message_id")
                            continue

                        # Skip if this message_id already exists in database
                        if message_id in existing_message_ids:
                            skipped_count += 1
                            self.logger.debug(
                                f"Skipping duplicate entry for message_id: {message_id} (exists in database)"
                            )
                            continue

                        # Skip if this message_id was already processed in this batch
                        if message_id in processed_in_batch:
                            skipped_count += 1
                            self.logger.debug(
                                f"Skipping duplicate entry for message_id: {message_id} (duplicate in batch)"
                            )
                            continue

                        # Mark this message_id as processed in this batch
                        processed_in_batch.add(message_id)

                        # Create a copy to avoid modifying the original data
                        processed_entry = entry_data.copy()

                        # List of ALL possible datetime fields in the model
                        datetime_fields = [
                            "created_at",
                            "extracted_at",
                            "migrated_at",
                            "reviewed_at",
                        ]

                        # Convert ALL datetime fields to timezone-naive for database insertion
                        # Database columns are TIMESTAMP WITHOUT TIME ZONE
                        for field in datetime_fields:
                            if (
                                field in processed_entry
                                and processed_entry[field] is not None
                            ):
                                dt_value = processed_entry[field]
                                if isinstance(dt_value, datetime):
                                    if dt_value.tzinfo is not None:
                                        # Convert timezone-aware to timezone-naive (assume UTC)
                                        processed_entry[field] = dt_value.replace(
                                            tzinfo=None
                                        )
                                    # If already timezone-naive, keep as is

                        # Ensure extracted_at is always set with timezone-naive datetime
                        if (
                            "extracted_at" not in processed_entry
                            or processed_entry["extracted_at"] is None
                        ):
                            processed_entry["extracted_at"] = datetime.now(UTC).replace(
                                tzinfo=None
                            )

                        # Additional safety check: scan for any remaining timezone-aware datetime objects
                        for key, value in processed_entry.items():
                            if isinstance(value, datetime) and value.tzinfo is not None:
                                self.logger.warning(
                                    f"Found timezone-aware datetime in field '{key}', converting to timezone-naive"
                                )
                                processed_entry[key] = value.replace(tzinfo=None)

                        migration_entry = GalleryMigration(**processed_entry)
                        session.add(migration_entry)
                        created_count += 1

                    except Exception as e:
                        self.logger.error(
                            f"Error creating entry for message {entry_data.get('message_id')}: {e}"
                        )
                        # Log the problematic data for debugging
                        self.logger.error(f"Problematic entry data: {entry_data}")
                        continue

                await session.commit()
                self.logger.info(
                    f"Bulk created {created_count} migration entries, skipped {skipped_count} duplicates"
                )
                return created_count
            finally:
                await session.close()

        except Exception as e:
            self.logger.error(f"Error in bulk create: {e}")
            return created_count
