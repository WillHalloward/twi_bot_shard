"""SQLAlchemy model for gallery_mementos table."""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class GalleryMementos(Base):
    """Model for gallery_mementos table.

    This table stores information about channels where gallery content can be reposted.
    """

    __tablename__ = "gallery_mementos"

    channel_name: Mapped[str] = mapped_column(String(100))
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
