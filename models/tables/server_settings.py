"""SQLAlchemy model for server_settings table."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ServerSettings(Base):
    """Model for server_settings table.

    This table stores guild-specific configuration settings.
    """

    __tablename__ = "server_settings"

    # Primary key
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)

    # Optional fields
    admin_role_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, insert_default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, insert_default=datetime.utcnow
    )
