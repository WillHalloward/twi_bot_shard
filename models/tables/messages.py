"""
SQLAlchemy model for messages table.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, Text, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

class Message(Base):
    """
    Model for messages table.

    This table stores information about Discord messages.
    """
    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    server_name: Mapped[str] = mapped_column(String, nullable=False)
    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.server_id"), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(100))
    user_nick: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jump_url: Mapped[str] = mapped_column(String, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    reference: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Define __table_args__ to create composite indexes
    __table_args__ = (
        {'schema': 'public'},
    )
