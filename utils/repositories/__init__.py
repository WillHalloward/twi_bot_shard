"""Repository package initialization.

This module initializes the repository package and registers all repositories
with the repository factory.
"""

from models.tables.creator_links import CreatorLink
from models.tables.gallery import GalleryMementos
from models.tables.messages import Message
from utils.repositories.creator_link_repository import CreatorLinkRepository
from utils.repositories.gallery_repository import GalleryRepository
from utils.repositories.message_repository import MessageRepository
from utils.repository_factory import RepositoryFactory


def register_repositories(factory: RepositoryFactory) -> None:
    """Register all repositories with the repository factory.

    Args:
        factory: The repository factory to register repositories with.
    """
    # Register repositories
    factory.register_repository(GalleryMementos, GalleryRepository)
    factory.register_repository(CreatorLink, CreatorLinkRepository)
    factory.register_repository(Message, MessageRepository)
