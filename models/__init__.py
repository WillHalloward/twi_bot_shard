# SQLAlchemy models package
from models.base import Base

# Import all models to ensure they're registered with the Base class
from models.tables import *  # noqa: F403  (re-exports all ORM model classes)
