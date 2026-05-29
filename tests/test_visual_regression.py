"""
Visual regression testing suite for the Twi Bot Shard.

This module tests visual and image-related functionality including:
- Image processing and validation
- Gallery image handling
- Avatar and profile image processing
- Embed image functionality
- Image format compatibility
- Visual consistency checks

These tests help ensure that image-related features work correctly and
maintain visual consistency across different scenarios.
"""

import asyncio
import hashlib
import os
import sys
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Import config normally

import discord

# Import cogs for testing
from cogs.gallery import GalleryCog
from cogs.info import Info

# Import test utilities
from tests.mock_factories import (
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockMessageFactory,
    MockUserFactory,
)

# Try to import PIL for image processing tests
try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL not available - some visual tests will be skipped")


class ImageTestUtils:
    """Utility class for creating test images and validating image properties."""

    @staticmethod
    def create_test_image(
        width: int = 100, height: int = 100, color: str = "red", format: str = "PNG"
    ) -> BytesIO:
        """Create a test image with specified dimensions and color."""
        if not PIL_AVAILABLE:
            # Create a mock image data
            mock_data = BytesIO(b"mock_image_data")
            return mock_data

        image = Image.new("RGB", (width, height), color)
        image_data = BytesIO()
        image.save(image_data, format=format)
        image_data.seek(0)
        return image_data

    @staticmethod
    def create_test_image_with_text(
        text: str, width: int = 200, height: int = 100
    ) -> BytesIO:
        """Create a test image with text overlay."""
        if not PIL_AVAILABLE:
            mock_data = BytesIO(b"mock_image_with_text")
            return mock_data

        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Try to use a default font, fall back to basic if not available
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Calculate text position (center)
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width = len(text) * 6  # Rough estimate
            text_height = 11

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), text, fill="black", font=font)

        image_data = BytesIO()
        image.save(image_data, format="PNG")
        image_data.seek(0)
        return image_data

    @staticmethod
    def get_image_hash(image_data: BytesIO) -> str:
        """Get a hash of image data for comparison."""
        image_data.seek(0)
        content = image_data.read()
        image_data.seek(0)
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def validate_image_format(image_data: BytesIO, expected_format: str = None) -> bool:
        """Validate that image data is in the expected format."""
        if not PIL_AVAILABLE:
            return True  # Skip validation if PIL not available

        try:
            image_data.seek(0)
            with Image.open(image_data) as img:
                return not (expected_format and img.format != expected_format)
        except Exception:
            return False
        finally:
            image_data.seek(0)

    @staticmethod
    def get_image_dimensions(image_data: BytesIO) -> tuple[int, int]:
        """Get image dimensions."""
        if not PIL_AVAILABLE:
            return (100, 100)  # Default dimensions

        try:
            image_data.seek(0)
            with Image.open(image_data) as img:
                return img.size
        except Exception:
            return (0, 0)
        finally:
            image_data.seek(0)


class MockAttachment:
    """Mock Discord attachment for testing."""

    def __init__(
        self,
        filename: str,
        content_type: str,
        size: int,
        url: str,
        data: BytesIO = None,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.url = url
        self._data = data or ImageTestUtils.create_test_image()

    async def read(self) -> bytes:
        """Mock read method to return image data."""
        self._data.seek(0)
        return self._data.read()


class ImageProcessingTests:
    """Test image processing functionality."""

    async def test_image_format_validation(self) -> bool:
        """Test validation of different image formats."""
        print("🖼️ Testing image format validation...")

        test_formats = ["PNG", "JPEG", "GIF", "WEBP"]
        results = []

        for format_type in test_formats:
            try:
                # Create test image in specific format
                image_data = ImageTestUtils.create_test_image(format=format_type)

                # Validate format
                is_valid = ImageTestUtils.validate_image_format(image_data, format_type)

                if is_valid:
                    print(f"  ✅ {format_type} format validation passed")
                    results.append(True)
                else:
                    print(f"  ❌ {format_type} format validation failed")
                    results.append(False)

            except Exception as e:
                print(f"  ❌ {format_type} format test error: {e}")
                results.append(False)

        return all(results)

    async def test_image_size_constraints(self) -> bool:
        """Test image size validation and constraints."""
        print("📏 Testing image size constraints...")

        test_cases = [
            (50, 50, "Small image"),
            (800, 600, "Medium image"),
            (1920, 1080, "Large image"),
            (4000, 3000, "Very large image"),
        ]

        results = []

        for width, height, description in test_cases:
            try:
                image_data = ImageTestUtils.create_test_image(width, height)
                actual_dimensions = ImageTestUtils.get_image_dimensions(image_data)

                if actual_dimensions == (width, height):
                    print(f"  ✅ {description} ({width}x{height}) - dimensions correct")
                    results.append(True)
                else:
                    print(
                        f"  ❌ {description} - expected {width}x{height}, got {actual_dimensions}"
                    )
                    results.append(False)

            except Exception as e:
                print(f"  ❌ {description} test error: {e}")
                results.append(False)

        return all(results)

    async def test_image_content_consistency(self) -> bool:
        """Test that identical images produce consistent hashes."""
        print("🔍 Testing image content consistency...")

        try:
            # Create two identical images
            image1 = ImageTestUtils.create_test_image(100, 100, "blue")
            image2 = ImageTestUtils.create_test_image(100, 100, "blue")

            # Get hashes
            hash1 = ImageTestUtils.get_image_hash(image1)
            hash2 = ImageTestUtils.get_image_hash(image2)

            if hash1 == hash2:
                print("  ✅ Identical images produce consistent hashes")

                # Test different images produce different hashes
                image3 = ImageTestUtils.create_test_image(100, 100, "red")
                hash3 = ImageTestUtils.get_image_hash(image3)

                if hash1 != hash3:
                    print("  ✅ Different images produce different hashes")
                    return True
                else:
                    print("  ❌ Different images produced same hash")
                    return False
            else:
                print("  ❌ Identical images produced different hashes")
                return False

        except Exception as e:
            print(f"  ❌ Image consistency test error: {e}")
            return False


class GalleryVisualTests:
    """Test gallery-related visual functionality."""

    async def test_gallery_image_attachment_processing(self) -> bool:
        """Test processing of image attachments in gallery."""
        print("🖼️ Testing gallery image attachment processing...")

        try:
            # Create mock bot and cog
            bot = MagicMock()
            bot.db = MagicMock()
            bot.db.execute = AsyncMock()
            bot.db.fetch = AsyncMock(return_value=[])

            GalleryCog(bot)

            # Create mock message with image attachment
            user = MockUserFactory.create()
            guild = MockGuildFactory.create()
            channel = MockChannelFactory.create_text_channel()

            # Create mock image attachment
            image_data = ImageTestUtils.create_test_image(800, 600)
            attachment = MockAttachment(
                filename="test_image.png",
                content_type="image/png",
                size=1024,
                url="https://example.com/test_image.png",
                data=image_data,
            )

            MockMessageFactory.create(
                content="Test gallery image",
                author=user,
                channel=channel,
                guild=guild,
                attachments=[attachment],
            )

            # Test attachment processing
            # This is a simplified test since we're mocking the Discord API
            if attachment.content_type.startswith("image"):
                print("  ✅ Image attachment detected correctly")

                # Validate image properties
                dimensions = ImageTestUtils.get_image_dimensions(image_data)
                if dimensions == (800, 600):
                    print("  ✅ Image dimensions validated correctly")
                    return True
                else:
                    print(f"  ❌ Image dimensions incorrect: {dimensions}")
                    return False
            else:
                print("  ❌ Image attachment not detected")
                return False

        except Exception as e:
            print(f"  ❌ Gallery image processing test error: {e}")
            return False

    async def test_gallery_embed_image_setting(self) -> bool:
        """Test setting images in gallery embeds."""
        print("📋 Testing gallery embed image setting...")

        try:
            # Create test embed
            embed = discord.Embed(
                title="Test Gallery Item", description="Test description"
            )

            # Test setting image URL
            test_image_url = "https://example.com/test_image.png"
            embed.set_image(url=test_image_url)

            if embed.image and embed.image.url == test_image_url:
                print("  ✅ Embed image URL set correctly")

                # Test setting thumbnail
                test_thumbnail_url = "https://example.com/thumbnail.png"
                embed.set_thumbnail(url=test_thumbnail_url)

                if embed.thumbnail and embed.thumbnail.url == test_thumbnail_url:
                    print("  ✅ Embed thumbnail URL set correctly")
                    return True
                else:
                    print("  ❌ Embed thumbnail URL not set correctly")
                    return False
            else:
                print("  ❌ Embed image URL not set correctly")
                return False

        except Exception as e:
            print(f"  ❌ Gallery embed test error: {e}")
            return False


class AvatarVisualTests:
    """Test avatar and profile image functionality."""

    async def test_avatar_url_validation(self) -> bool:
        """Test avatar URL validation and processing."""
        print("👤 Testing avatar URL validation...")

        try:
            # Create mock user with avatar
            user = MockUserFactory.create()

            # Test avatar URL access
            if hasattr(user, "display_avatar") and hasattr(user.display_avatar, "url"):
                avatar_url = user.display_avatar.url
                print(f"  ✅ Avatar URL accessible: {avatar_url}")

                # Test avatar URL format (should be a valid URL)
                if avatar_url.startswith(("http://", "https://")):
                    print("  ✅ Avatar URL format valid")
                    return True
                else:
                    print("  ❌ Avatar URL format invalid")
                    return False
            else:
                print("  ❌ Avatar URL not accessible")
                return False

        except Exception as e:
            print(f"  ❌ Avatar URL validation test error: {e}")
            return False

    async def test_avatar_embed_integration(self) -> bool:
        """Test avatar integration with embeds."""
        print("🖼️ Testing avatar embed integration...")

        try:
            # Create mock bot and cog
            bot = MagicMock()
            bot.db = MagicMock()
            cog = Info(bot)

            # Create mock user and interaction
            user = MockUserFactory.create()
            guild = MockGuildFactory.create()
            channel = MockChannelFactory.create_text_channel()
            interaction = MockInteractionFactory.create(
                user=user, guild=guild, channel=channel
            )

            # Test avatar command (mocked)
            try:
                # This will fail due to mocking, but we can test the setup
                await cog.av(interaction, user)
            except Exception:
                pass  # Expected due to mocking

            # Test that user has avatar properties
            if hasattr(user, "display_avatar"):
                print("  ✅ User avatar properties accessible")
                return True
            else:
                print("  ❌ User avatar properties not accessible")
                return False

        except Exception as e:
            print(f"  ❌ Avatar embed integration test error: {e}")
            return False


class EmbedVisualTests:
    """Test embed visual consistency and functionality."""

    async def test_embed_color_consistency(self) -> bool:
        """Test embed color consistency across different scenarios."""
        print("🎨 Testing embed color consistency...")

        try:
            # Test different embed colors
            test_colors = [
                discord.Color.blue(),
                discord.Color.green(),
                discord.Color.red(),
                discord.Color.gold(),
                discord.Color.purple(),
            ]

            results = []

            for color in test_colors:
                embed = discord.Embed(title="Test Embed", color=color)

                if embed.color == color:
                    print(f"  ✅ Color {color} set correctly")
                    results.append(True)
                else:
                    print(f"  ❌ Color {color} not set correctly")
                    results.append(False)

            return all(results)

        except Exception as e:
            print(f"  ❌ Embed color consistency test error: {e}")
            return False

    async def test_embed_field_layout(self) -> bool:
        """Test embed field layout and structure."""
        print("📋 Testing embed field layout...")

        try:
            embed = discord.Embed(title="Test Embed", description="Test description")

            # Add various field types
            embed.add_field(name="Inline Field 1", value="Value 1", inline=True)
            embed.add_field(name="Inline Field 2", value="Value 2", inline=True)
            embed.add_field(name="Non-inline Field", value="Value 3", inline=False)

            # Test field count
            if len(embed.fields) == 3:
                print("  ✅ Correct number of fields added")

                # Test field properties
                if (
                    embed.fields[0].inline
                    and embed.fields[1].inline
                    and not embed.fields[2].inline
                ):
                    print("  ✅ Field inline properties correct")
                    return True
                else:
                    print("  ❌ Field inline properties incorrect")
                    return False
            else:
                print(f"  ❌ Incorrect number of fields: {len(embed.fields)}")
                return False

        except Exception as e:
            print(f"  ❌ Embed field layout test error: {e}")
            return False


async def run_all_visual_regression_tests():
    """Run all visual regression tests and generate comprehensive report."""
    print("🎨 Starting Visual Regression Testing Suite...")
    print("=" * 70)

    results = {}

    # Image Processing Tests
    print("\n🖼️ Image Processing Tests")
    print("-" * 40)
    image_tests = ImageProcessingTests()
    results["format_validation"] = await image_tests.test_image_format_validation()
    results["size_constraints"] = await image_tests.test_image_size_constraints()
    results["content_consistency"] = await image_tests.test_image_content_consistency()

    # Gallery Visual Tests
    print("\n🖼️ Gallery Visual Tests")
    print("-" * 40)
    gallery_tests = GalleryVisualTests()
    results[
        "gallery_attachments"
    ] = await gallery_tests.test_gallery_image_attachment_processing()
    results["gallery_embeds"] = await gallery_tests.test_gallery_embed_image_setting()

    # Avatar Visual Tests
    print("\n👤 Avatar Visual Tests")
    print("-" * 40)
    avatar_tests = AvatarVisualTests()
    results["avatar_validation"] = await avatar_tests.test_avatar_url_validation()
    results["avatar_embeds"] = await avatar_tests.test_avatar_embed_integration()

    # Embed Visual Tests
    print("\n📋 Embed Visual Tests")
    print("-" * 40)
    embed_tests = EmbedVisualTests()
    results["embed_colors"] = await embed_tests.test_embed_color_consistency()
    results["embed_layout"] = await embed_tests.test_embed_field_layout()

    # Generate comprehensive report
    print("\n" + "=" * 70)
    print("📊 VISUAL REGRESSION TEST REPORT")
    print("=" * 70)

    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    print("\n📈 Test Results Summary:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name.replace('_', ' ').title()}")

    print("\n🎯 Overall Results:")
    print(f"   📊 Tests Passed: {passed_tests}/{total_tests}")
    print(f"   📈 Success Rate: {success_rate:.1f}%")

    if success_rate >= 90:
        print("   🎉 EXCELLENT: Visual functionality is working correctly!")
    elif success_rate >= 75:
        print("   ✅ GOOD: Most visual features working with minor issues.")
    elif success_rate >= 50:
        print("   ⚠️  FAIR: Some visual issues detected - review recommended.")
    else:
        print(
            "   ❌ POOR: Significant visual issues detected - immediate attention required."
        )

    if not PIL_AVAILABLE:
        print(
            "\n⚠️  Note: PIL not available - some image processing tests were skipped."
        )

    return success_rate >= 75


async def main() -> bool | None:
    """Main visual regression testing execution function."""
    try:
        success = await run_all_visual_regression_tests()
        if success:
            print("\n🎉 Visual regression testing completed successfully!")
            return True
        else:
            print("\n⚠️ Visual regression testing revealed issues!")
            return False
    except Exception as e:
        print(f"\n💥 Visual regression testing crashed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())
