"""SQLAlchemy model for messages table."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

# Discord message link, derived from the IDs. Explicit ::text casts keep the
# expression IMMUTABLE, which generated columns require.
JUMP_URL_EXPR = (
    "'https://discord.com/channels/' || server_id::text || '/' || "
    "channel_id::text || '/' || message_id::text"
)


class Message(Base):
    """Model for messages table.

    This table stores information about Discord messages.
    """

    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Message text is deliberately NOT stored (Discord Message Content intent
    # policy); only its length is kept for the average-length stats.
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    server_name: Mapped[str] = mapped_column(String, nullable=False)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.server_id"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(100))
    user_nick: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Virtual generated column (Postgres 18): computed on read, takes no disk
    # space. Never insert it. See migration 20261104_04.
    jump_url: Mapped[str] = mapped_column(
        Text,
        Computed(JUMP_URL_EXPR, persisted=False),
    )
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    reference: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Define __table_args__ to create composite indexes
    __table_args__ = ()
