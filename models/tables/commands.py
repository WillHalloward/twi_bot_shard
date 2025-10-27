"""SQLAlchemy model for command_history table."""

from datetime import datetime, timedelta

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Interval,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CommandHistory(Base):
    """Model for command_history table.

    This table stores information about command executions.
    """

    __tablename__ = "command_history"

    serial: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    command_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    guild_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("servers.server_id"), nullable=True
    )
    args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_time: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)

    start_date: Mapped[datetime] = mapped_column(
        DateTime, insert_default=datetime.now, nullable=False
    )
    slash_command: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_successfully: Mapped[bool] = mapped_column(Boolean, default=False)
    finished_successfully: Mapped[bool] = mapped_column(Boolean, default=False)
    # Define indexes
    __table_args__ = ()
