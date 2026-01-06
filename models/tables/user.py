"""SQLAlchemy model for users table."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class User(Base):
    """Model for users table.

    This table stores information about Discord users.
    """

    __tablename__ = "users"

    # Primary key
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)

    # Required fields
    username: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime(1970, 1, 1)
    )

    # Optional fields
    serial_id: Mapped[int | None] = mapped_column(
        Integer, autoincrement=True, default=None
    )
    bot: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
