"""
SQLAlchemy model for command_history table.
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, JSON, BigInteger, ForeignKey, Interval
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

class CommandHistory(Base):
    """
    Model for command_history table.

    This table stores information about command executions.
    """
    __tablename__ = "command_history"

    serial: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    command_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("channels.id"), nullable=True)
    guild_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("servers.server_id"), nullable=True)
    args: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    run_time: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)

    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    slash_command: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_successfully: Mapped[bool] = mapped_column(Boolean, default=False)
    finished_successfully: Mapped[bool] = mapped_column(Boolean, default=False)
    # Define indexes
    __table_args__ = (
        {'schema': 'public'},
    )
