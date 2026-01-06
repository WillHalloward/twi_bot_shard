"""SQLAlchemy model for reports table."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Report(Base):
    """Model for reports table.

    This table stores user reports for messages that violate server rules.
    """

    __tablename__ = "reports"

    # Required fields (no defaults) must come first
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    reported_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Optional fields (with defaults) must come after required fields
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, insert_default=datetime.utcnow
    )
