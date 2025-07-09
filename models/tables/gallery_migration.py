"""
SQLAlchemy model for gallery_migration table.
"""

from sqlalchemy import String, Integer, BigInteger, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from models.base import Base


class GalleryMigration(Base):
    """
    Model for gallery_migration table.

    This table stores extracted gallery posts for migration to forum format.
    Contains the 5 key fields: title, images, creator, tags, jump_url
    """

    __tablename__ = "gallery_migration"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Original message information (required fields first)
    message_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Message author
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Original message timestamp

    # Optional fields (nullable fields)
    title: Mapped[str] = mapped_column(Text, nullable=True)  # Post title from embed
    images: Mapped[str] = mapped_column(JSON, nullable=True)  # Array of image URLs
    creator: Mapped[str] = mapped_column(String(200), nullable=True)  # Creator info (user_id or name)
    tags: Mapped[str] = mapped_column(JSON, nullable=True)  # Array of tags
    jump_url: Mapped[str] = mapped_column(Text, nullable=True)  # Discord jump URL
    target_forum: Mapped[str] = mapped_column(String(10), nullable=True)  # 'sfw' or 'nsfw'
    content_type: Mapped[str] = mapped_column(String(50), nullable=True)  # fanart, official, meme, etc.
    migrated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    raw_embed_data: Mapped[str] = mapped_column(JSON, nullable=True)  # Full embed data
    raw_content: Mapped[str] = mapped_column(Text, nullable=True)  # Original message content

    # Fields with defaults (must come last)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    migrated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
