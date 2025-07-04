"""
SQLAlchemy model for servers table.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    BigInteger,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Server(Base):
    """
    Model for servers table.

    This table stores information about Discord servers (guilds).
    """

    __tablename__ = "servers"

    server_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    server_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Define indexes and constraints
    __table_args__ = ()
