"""
SQLAlchemy model for gallery_migration table.
"""

from sqlalchemy import String, Integer, BigInteger, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional

from models.base import Base


class GalleryMigration(Base):
    """
    Model for gallery_migration table.

    This table stores extracted gallery posts for migration to forum format.
    Contains the 5 key fields: title, images, creator, tags, jump_url
    """

    __tablename__ = "gallery_migration"

    # Primary key (must come first)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)

    # Original message information (required fields)
    message_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Message author
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Original message timestamp

    # Optional fields (nullable fields)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)  # Post title from embed
    images: Mapped[Optional[str]] = mapped_column(JSON, nullable=True, default=None)  # Array of image URLs
    creator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default=None)  # Creator info (user_id or name)
    tags: Mapped[Optional[str]] = mapped_column(JSON, nullable=True, default=None)  # Array of tags
    jump_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)  # Discord jump URL
    target_forum: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default=None)  # 'sfw' or 'nsfw'
    content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)  # fanart, official, meme, etc.
    migrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    reviewed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    raw_embed_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True, default=None)  # Full embed data
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)  # Original message content

    # Fields with defaults (must come last)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    migrated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
