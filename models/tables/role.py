"""SQLAlchemy model for roles table."""

from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Role(Base):
    """Model for roles table.

    This table stores information about Discord roles.
    """

    __tablename__ = "roles"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)

    # Optional fields with defaults
    name: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    color: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    hoisted: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    managed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    guild_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    self_assignable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alias: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    category: Mapped[str] = mapped_column(
        String, nullable=False, default="Uncategorized"
    )
    required_roles: Mapped[list[int] | None] = mapped_column(
        ARRAY(BigInteger), nullable=True, default=None
    )
    auto_replace: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
