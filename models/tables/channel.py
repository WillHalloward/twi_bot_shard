"""SQLAlchemy model for channels table."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Channel(Base):
    """Model for channels table.

    This table stores information about Discord channels.
    """

    __tablename__ = "channels"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)

    # Optional fields with defaults
    name: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    guild_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    topic: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    is_nsfw: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_pins: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
