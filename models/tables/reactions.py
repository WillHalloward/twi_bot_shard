"""
SQLAlchemy model for reactions table.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    BigInteger,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Reaction(Base):
    """
    Model for reactions table.

    This table stores information about reactions to Discord messages.
    """

    __tablename__ = "reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unicode_emoji: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emoji_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    animated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    emoji_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_custom_emoji: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Define __table_args__ to create composite indexes and unique constraints
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            "emoji_id",
            name="reactions_message_id_user_id_emoji_id_uindex",
        ),
        UniqueConstraint(
            "message_id",
            "user_id",
            "unicode_emoji",
            name="reactions_message_id_user_id_unicode_emoji_uindex",
        ),
    )
