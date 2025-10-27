"""SQLAlchemy model for join_leave table."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class JoinLeave(Base):
    """Model for join_leave table.

    This table stores information about users joining or leaving Discord servers.
    """

    __tablename__ = "join_leave"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    server_id: Mapped[int] = mapped_column(BigInteger, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    join_or_leave: Mapped[str] = mapped_column(String(10), index=True)
    server_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Define __table_args__ to create composite indexes
    __table_args__ = ()
