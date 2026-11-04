"""The gallery migration extractor must not persist raw message content.

The bot certifies to Discord (Message Content intent review) that it does not
store message content off-platform. ``extract_and_prepare_for_db`` used to
include the full message text (``raw_content``) and embed JSON
(``raw_embed_data``) in every gallery_migration row.
"""

import datetime
import os
import sys
from unittest.mock import MagicMock

import pytest

# conftest purges modules between tests; keep the repo root importable.
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


def _message() -> MagicMock:
    message = MagicMock()
    message.id = 111
    message.content = "Created by: @artist\nsecret message text"
    message.embeds = []
    message.attachments = []
    message.jump_url = "https://discord.com/channels/1/2/111"
    message.channel.id = 2
    message.channel.name = "gallery"
    message.channel.is_nsfw.return_value = False
    message.guild.id = 1
    message.author.id = 3
    message.author.name = "poster"
    message.author.bot = False
    message.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return message


@pytest.mark.asyncio
async def test_db_entry_has_no_raw_message_content() -> None:
    from utils.gallery_data_extractor import GalleryDataExtractor

    entry = await GalleryDataExtractor().extract_and_prepare_for_db(_message())

    assert "raw_content" not in entry
    assert "raw_embed_data" not in entry
    assert "secret message text" not in repr(entry)


def test_model_has_no_raw_content_columns() -> None:
    from models.tables.gallery_migration import GalleryMigration

    columns = set(GalleryMigration.__table__.columns.keys())
    assert "raw_content" not in columns
    assert "raw_embed_data" not in columns
