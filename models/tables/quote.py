"""SQLAlchemy model for quotes table."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Quote(Base):
    """Model for quotes table.

    This table stores user quotes.
    """

    __tablename__ = "quotes"

    # Primary key (serial_id)
    serial_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Optional fields
    quote: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    author: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    author_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    # Note: tokens (tsvector) is managed by PostgreSQL for full-text search
    # We don't map it here as it's auto-generated
