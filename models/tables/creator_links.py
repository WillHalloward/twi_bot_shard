"""SQLAlchemy model for creator_links table."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CreatorLink(Base):
    """Model for creator_links table.

    This table stores links to creator content for Discord users.
    """

    __tablename__ = "creator_links"

    # Required fields (no defaults) must come first for dataclass compatibility
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    link: Mapped[str] = mapped_column(String(255))

    # Optional fields (with defaults) must come after required fields
    serial_id: Mapped[int | None] = mapped_column(
        Integer, autoincrement=True, default=None
    )
    nsfw: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    feature: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_changed: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, insert_default=datetime.now
    )

    # Define __table_args__ to create composite indexes and primary key
    __table_args__ = (PrimaryKeyConstraint("user_id", "title", "serial_id"),)
