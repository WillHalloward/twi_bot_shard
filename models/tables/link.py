"""SQLAlchemy model for links table."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Link(Base):
    """Model for links table.

    This table stores links/tags for the tag system.
    """

    __tablename__ = "links"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Optional fields
    content: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    tag: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    user_who_added: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    id_user_who_added: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    time_added: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    embed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    guild_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
