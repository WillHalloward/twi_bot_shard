"""Base model for SQLAlchemy ORM."""

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass
