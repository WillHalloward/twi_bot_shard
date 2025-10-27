"""Utility for extracting gallery migration data from Discord messages."""

import logging
import re
from typing import Any

import discord


class GalleryDataExtractor:
    """Extracts the 5 key fields from gallery posts for migration."""

    # The 10 predefined tags
    AVAILABLE_TAGS = [
        "Fanart",
        "Official",
        "Music",
        "Fanfic",
        "Cosplay",
        "Innktober",
        "Crafting",
        "tattoo",
        "meme",
        "Commission",
    ]

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

        # Regex patterns for creator extraction
        self.creator_patterns = [
            r"Created by:\s*<@!?(\d+)>",  # Created by: @user
            r"Creator:\s*<@!?(\d+)>",  # Creator: @user
            r"Artist:\s*<@!?(\d+)>",  # Artist: @user
            r"By:\s*<@!?(\d+)>",  # By: @user
            r"<@!?(\d+)>",  # Just @user mention
        ]

        # Content type keywords for auto-tagging
        self.content_keywords = {
            "Official": ["official", "pirateaba", "author", "canon"],
            "Music": ["music", "song", "audio", "sound", "track"],
            "Fanfic": ["fanfic", "fanfiction", "story", "ao3", "archive"],
            "Cosplay": ["cosplay", "costume", "outfit", "irl"],
            "Innktober": ["innktober", "inktober", "ink"],
            "Crafting": ["craft", "made", "diy", "handmade", "sculpture"],
            "tattoo": ["tattoo", "ink", "skin"],
            "meme": ["meme", "funny", "joke", "humor"],
            "Commission": ["commission", "commissioned", "comm"],
        }

    async def extract_gallery_data(
        self, message: discord.Message, default_tags: list[str] | None = None
    ) -> dict[str, Any]:
        """Extract the 5 key fields from a Discord message.

        Args:
            message: Discord message to extract data from
            default_tags: Default tags to apply (e.g., ["Fanart"] for gallery channel)

        Returns:
            Dictionary containing extracted data
        """
        try:
            # Initialize extracted data
            extracted_data = {
                "title": None,
                "images": [],
                "creator": None,
                "tags": default_tags or [],
                "jump_url": message.jump_url,
                "needs_manual_review": False,
            }

            # Extract from embeds (bot posts)
            if message.embeds:
                embed_data = await self._extract_from_embeds(message.embeds)
                extracted_data.update(embed_data)

            # Extract from attachments
            attachment_images = await self._extract_from_attachments(
                message.attachments
            )
            extracted_data["images"].extend(attachment_images)

            # Extract from message content (manual posts)
            if message.content:
                content_data = await self._extract_from_content(message.content)
                # Only update if embed data didn't provide these fields
                if not extracted_data["title"] and content_data["title"]:
                    extracted_data["title"] = content_data["title"]
                if not extracted_data["creator"] and content_data["creator"]:
                    extracted_data["creator"] = content_data["creator"]

            # Auto-tag based on content analysis
            auto_tags = await self._analyze_content_for_tags(message, extracted_data)
            extracted_data["tags"].extend(auto_tags)

            # Remove duplicates from tags
            extracted_data["tags"] = list(set(extracted_data["tags"]))

            # Determine if manual review is needed
            extracted_data["needs_manual_review"] = await self._needs_manual_review(
                message, extracted_data
            )

            return extracted_data

        except Exception as e:
            self.logger.error(
                f"Error extracting gallery data from message {message.id}: {e}"
            )
            return {
                "title": None,
                "images": [],
                "creator": None,
                "tags": default_tags or [],
                "jump_url": message.jump_url,
                "needs_manual_review": True,
            }

    async def _extract_from_embeds(self, embeds: list[discord.Embed]) -> dict[str, Any]:
        """Extract data from Discord embeds."""
        data = {"title": None, "images": [], "creator": None}

        for embed in embeds:
            # Extract title
            if embed.title and not data["title"]:
                data["title"] = embed.title

            # Extract images
            if embed.image:
                data["images"].append(embed.image.url)
            if embed.thumbnail:
                data["images"].append(embed.thumbnail.url)

            # Extract creator from fields
            if embed.fields:
                for field in embed.fields:
                    creator = await self._extract_creator_from_text(field.value)
                    if creator and not data["creator"]:
                        data["creator"] = creator
                        break

            # Extract creator from description
            if embed.description and not data["creator"]:
                creator = await self._extract_creator_from_text(embed.description)
                if creator:
                    data["creator"] = creator

        return data

    async def _extract_from_attachments(
        self, attachments: list[discord.Attachment]
    ) -> list[str]:
        """Extract image URLs from message attachments."""
        image_urls = []

        for attachment in attachments:
            # Check if attachment is an image
            if (
                attachment.content_type
                and attachment.content_type.startswith("image/")
                or attachment.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                )
            ):
                image_urls.append(attachment.url)

        return image_urls

    async def _extract_from_content(self, content: str) -> dict[str, Any]:
        """Extract data from message content (manual posts)."""
        data = {"title": None, "creator": None}

        # Try to extract creator
        creator = await self._extract_creator_from_text(content)
        if creator:
            data["creator"] = creator

        # For manual posts, use first line as potential title if it's not too long
        lines = content.strip().split("\n")
        if lines and len(lines[0]) < 100:  # Reasonable title length
            data["title"] = lines[0].strip()

        return data

    async def _extract_creator_from_text(self, text: str) -> str | None:
        """Extract creator information from text using regex patterns."""
        if not text:
            return None

        for pattern in self.creator_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Return the user ID if it's a mention pattern
                if match.groups():
                    return f"<@{match.group(1)}>"
                return match.group(0)

        return None

    async def _analyze_content_for_tags(
        self, message: discord.Message, extracted_data: dict[str, Any]
    ) -> list[str]:
        """Analyze content to suggest additional tags."""
        suggested_tags = []

        # Combine all text content for analysis
        text_content = []
        if message.content:
            text_content.append(message.content.lower())

        for embed in message.embeds:
            if embed.title:
                text_content.append(embed.title.lower())
            if embed.description:
                text_content.append(embed.description.lower())
            for field in embed.fields:
                text_content.append(field.name.lower())
                text_content.append(field.value.lower())

        combined_text = " ".join(text_content)

        # Check for content type keywords
        for tag, keywords in self.content_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                if tag not in extracted_data["tags"]:
                    suggested_tags.append(tag)

        return suggested_tags

    async def _needs_manual_review(
        self, message: discord.Message, extracted_data: dict[str, Any]
    ) -> bool:
        """Determine if the post needs manual review."""
        # Manual posts (non-bot) always need review
        if not message.author.bot:
            return True

        # Bot posts without title need review
        if not extracted_data["title"]:
            return True

        # Bot posts without creator need review
        if not extracted_data["creator"]:
            return True

        # Posts with no images might need review (could be text-only content)
        if not extracted_data["images"]:
            return True

        # Posts with only default tags might need more specific tagging
        return len(extracted_data["tags"]) <= 1

    def get_channel_default_tags(self, channel_name: str) -> list[str]:
        """Get default tags based on channel name."""
        channel_lower = channel_name.lower()

        if "gallery" in channel_lower:
            return ["Fanart"]
        elif "meme" in channel_lower:
            return ["meme"]
        elif "official" in channel_lower:
            return ["Official"]

        return ["Fanart"]  # Default fallback

    def classify_for_forum(
        self, message: discord.Message, extracted_data: dict[str, Any]
    ) -> str:
        """Classify content for SFW or NSFW forum."""
        # Check source channel NSFW status
        if hasattr(message.channel, "is_nsfw") and message.channel.is_nsfw():
            return "nsfw"

        # Content analysis for NSFW indicators
        nsfw_keywords = ["nsfw", "lewd", "adult", "mature", "18+"]

        # Check message content
        if message.content:
            content_lower = message.content.lower()
            if any(keyword in content_lower for keyword in nsfw_keywords):
                return "nsfw"

        # Check embed content
        for embed in message.embeds:
            if embed.title and any(
                keyword in embed.title.lower() for keyword in nsfw_keywords
            ):
                return "nsfw"
            if embed.description and any(
                keyword in embed.description.lower() for keyword in nsfw_keywords
            ):
                return "nsfw"

        # Check for spoiler attachments (conservative approach)
        if any(att.is_spoiler for att in message.attachments):
            return "nsfw"

        return "sfw"  # Default to SFW

    async def extract_and_prepare_for_db(
        self, message: discord.Message, channel_name: str = None
    ) -> dict[str, Any]:
        """Extract data and prepare it for database insertion.

        Args:
            message: Discord message to extract from
            channel_name: Channel name for default tag assignment

        Returns:
            Dictionary ready for database insertion
        """
        # Get default tags based on channel
        default_tags = self.get_channel_default_tags(
            channel_name or message.channel.name
        )

        # Extract the 5 key fields
        extracted_data = await self.extract_gallery_data(message, default_tags)

        # Classify for forum
        target_forum = self.classify_for_forum(message, extracted_data)

        # Determine content type
        content_type = "fanart"  # Default
        if extracted_data["tags"]:
            # Use the first non-default tag as content type
            for tag in extracted_data["tags"]:
                if tag.lower() != "fanart":
                    content_type = tag.lower()
                    break

        # Prepare database entry
        db_entry = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "channel_name": message.channel.name,
            "guild_id": message.guild.id if message.guild else 0,
            "title": extracted_data["title"],
            "images": extracted_data["images"],
            "creator": extracted_data["creator"],
            "tags": extracted_data["tags"],
            "jump_url": extracted_data["jump_url"],
            "author_id": message.author.id,
            "author_name": message.author.name,
            "is_bot": message.author.bot,
            "created_at": message.created_at,
            "target_forum": target_forum,
            "content_type": content_type,
            "has_attachments": len(message.attachments) > 0,
            "attachment_count": len(message.attachments),
            "needs_manual_review": extracted_data["needs_manual_review"],
            "raw_embed_data": (
                [embed.to_dict() for embed in message.embeds]
                if message.embeds
                else None
            ),
            "raw_content": message.content,
        }

        return db_entry
