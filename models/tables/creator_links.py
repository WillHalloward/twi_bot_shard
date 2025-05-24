"""
SQLAlchemy model for creator_links table.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, BigInteger, ForeignKey, DateTime, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

class CreatorLink(Base):
    """
    Model for creator_links table.

    This table stores links to creator content for Discord users.
    """
    __tablename__ = "creator_links"

    serial_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, primary_key=True)
    link: Mapped[str] = mapped_column(String(255))
    nsfw: Mapped[bool] = mapped_column(Boolean, default=False)
    last_changed: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    feature: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Define __table_args__ to create composite indexes and primary key
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'title', 'serial_id'),
        {'schema': 'public'}
    )
