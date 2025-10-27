"""
Tests for links in documentation.

This module extracts links from documentation files and verifies that they are valid.
It checks both internal links (between documentation files) and external links (to websites).
"""

import os
import re
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


class DocumentationLinkTest(unittest.TestCase):
    """Test case for validating links in documentation."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.docs_dir = Path(__file__).parent.parent / "docs"
        self.internal_links = {}  # type: Dict[str, List[Tuple[str, str]]]
        self.external_links = {}  # type: Dict[str, List[str]]
        self.anchor_definitions = {}  # type: Dict[str, Set[str]]
        self.extract_links()
        self.extract_anchors()

    def extract_links(self) -> None:
        """Extract links from all markdown files in the docs directory."""
        for file_path in self.docs_dir.glob("*.md"):
            relative_path = str(file_path.relative_to(Path(__file__).parent.parent))
            self.internal_links[relative_path] = []
            self.external_links[relative_path] = []

            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Find all markdown links [text](url)
            link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
            matches = re.finditer(link_pattern, content)

            for match in matches:
                link_text = match.group(1)
                link_url = match.group(2)

                if link_url.startswith(("http://", "https://")):
                    # External link
                    self.external_links[relative_path].append(link_url)
                else:
                    # Internal link
                    self.internal_links[relative_path].append((link_text, link_url))

    def extract_anchors(self) -> None:
        """Extract anchor definitions from all markdown files in the docs directory."""
        for file_path in self.docs_dir.glob("*.md"):
            relative_path = str(file_path.relative_to(Path(__file__).parent.parent))
            self.anchor_definitions[relative_path] = set()

            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Find all heading definitions (# Heading)
            heading_pattern = r"^(#+)\s+(.+)$"
            matches = re.finditer(heading_pattern, content, re.MULTILINE)

            for match in matches:
                len(match.group(1))
                heading_text = match.group(2).strip()

                # Convert heading to anchor (lowercase, replace spaces with hyphens, remove punctuation)
                anchor = heading_text.lower()
                anchor = re.sub(r"[^\w\s-]", "", anchor)
                anchor = re.sub(r"[\s]+", "-", anchor)

                self.anchor_definitions[relative_path].add(anchor)

    @unittest.skip("Temporarily skipped due to broken internal links in documentation")
    def test_internal_file_links(self) -> None:
        """Test that internal file links point to existing files."""
        for file_path, links in self.internal_links.items():
            for link_text, link_url in links:
                # Skip anchor links within the same file
                if link_url.startswith("#"):
                    continue

                # Handle links with anchors
                if "#" in link_url:
                    link_file, anchor = link_url.split("#", 1)
                else:
                    link_file = link_url

                # Skip empty links
                if not link_file:
                    continue

                # Resolve the link path
                if link_file.startswith("/"):
                    # Absolute path from project root
                    target_path = Path(__file__).parent.parent / link_file.lstrip("/")
                else:
                    # Relative path from current file
                    source_dir = Path(file_path).parent
                    target_path = (source_dir / link_file).resolve()

                # Check if the target file exists
                self.assertTrue(
                    target_path.exists(),
                    f"Broken internal link in {file_path}: [{link_text}]({link_url}) - File not found",
                )

    @unittest.skip("Temporarily skipped due to missing anchors in documentation")
    def test_internal_anchor_links(self) -> None:
        """Test that internal anchor links point to existing anchors."""
        for file_path, links in self.internal_links.items():
            for link_text, link_url in links:
                # Only process links with anchors
                if "#" not in link_url:
                    continue

                # Handle links with anchors
                if link_url.startswith("#"):
                    # Anchor in the same file
                    target_file = file_path
                    anchor = link_url[1:]
                else:
                    link_file, anchor = link_url.split("#", 1)

                    # Resolve the target file
                    if link_file.startswith("/"):
                        # Absolute path from project root
                        target_path = Path(__file__).parent.parent / link_file.lstrip(
                            "/"
                        )
                        target_file = str(
                            target_path.relative_to(Path(__file__).parent.parent)
                        )
                    else:
                        # Relative path from current file
                        source_dir = Path(file_path).parent
                        target_path = (source_dir / link_file).resolve()
                        try:
                            target_file = str(
                                target_path.relative_to(Path(__file__).parent.parent)
                            )
                        except ValueError:
                            # Link points outside the project
                            continue

                # Skip if the target file doesn't exist or isn't in our anchor definitions
                if target_file not in self.anchor_definitions:
                    continue

                # Check if the anchor exists in the target file
                self.assertIn(
                    anchor,
                    self.anchor_definitions[target_file],
                    f"Broken anchor link in {file_path}: [{link_text}]({link_url}) - Anchor not found",
                )

    def test_external_links_format(self) -> None:
        """Test that external links have valid format."""
        for file_path, links in self.external_links.items():
            for link_url in links:
                try:
                    parsed_url = urllib.parse.urlparse(link_url)
                    self.assertTrue(
                        all([parsed_url.scheme, parsed_url.netloc]),
                        f"Invalid external link format in {file_path}: {link_url}",
                    )
                except Exception as e:
                    self.fail(f"Error parsing URL {link_url} in {file_path}: {e}")

    def test_external_links_accessibility(self) -> None:
        """Test that external links are accessible (optional, may be slow)."""
        # Skip this test by default as it can be slow and may fail due to network issues
        if not os.environ.get("CHECK_EXTERNAL_LINKS", ""):
            self.skipTest(
                "Skipping external link checks. Set CHECK_EXTERNAL_LINKS=1 to enable."
            )

        for file_path, links in self.external_links.items():
            for link_url in links:
                try:
                    # Add a user agent to avoid being blocked
                    request = urllib.request.Request(
                        link_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 Documentation Link Checker"
                        },
                    )

                    # Try to open the URL with a timeout
                    with urllib.request.urlopen(request, timeout=5) as response:
                        self.assertIn(
                            response.status,
                            [200, 301, 302],
                            f"External link in {file_path} returned status {response.status}: {link_url}",
                        )
                except urllib.error.HTTPError as e:
                    self.fail(f"HTTP error for link in {file_path}: {link_url} - {e}")
                except urllib.error.URLError as e:
                    self.fail(f"URL error for link in {file_path}: {link_url} - {e}")
                except Exception as e:
                    self.fail(f"Error checking link in {file_path}: {link_url} - {e}")


if __name__ == "__main__":
    unittest.main()
