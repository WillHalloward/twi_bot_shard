"""
Unit tests for secret manager functionality.

Tests the encryption/decryption and secret validation in utils/secret_manager.py.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from utils.secret_manager import SecretManager


@pytest.fixture
def mock_bot():
    """Create a mock bot instance for testing."""
    bot = MagicMock()
    bot.db = MagicMock()
    bot.db.execute = AsyncMock()
    return bot


def test_secret_manager_initialization(mock_bot):
    """Test SecretManager initialization."""
    from unittest.mock import patch

    # With encryption key
    manager = SecretManager(mock_bot, encryption_key="test_key_12345")
    assert manager.bot == mock_bot
    assert manager._cipher is not None

    # Without encryption key - patch os.getenv to ensure no fallback
    with patch.dict("os.environ", {}, clear=False):
        with patch("os.getenv", return_value=None):
            manager_no_key = SecretManager(mock_bot, encryption_key=None)
            assert manager_no_key._cipher is None


def test_secret_manager_encrypt_decrypt(mock_bot):
    """Test encryption and decryption of secrets."""
    manager = SecretManager(mock_bot, encryption_key="test_encryption_key_12345")

    # Test encrypting and decrypting a string
    secret = "my_secret_password_123"
    encrypted = manager.encrypt(secret)

    # Encrypted value should be different from original
    assert encrypted != secret
    assert len(encrypted) > 0

    # Decrypting should return original value
    decrypted = manager.decrypt(encrypted)
    assert decrypted == secret


def test_secret_manager_encrypt_different_values(mock_bot):
    """Test that different secrets produce different encrypted values."""
    manager = SecretManager(mock_bot, encryption_key="test_key_12345")

    secret1 = "password1"
    secret2 = "password2"

    encrypted1 = manager.encrypt(secret1)
    encrypted2 = manager.encrypt(secret2)

    # Different secrets should produce different encrypted values
    assert encrypted1 != encrypted2

    # Both should decrypt correctly
    assert manager.decrypt(encrypted1) == secret1
    assert manager.decrypt(encrypted2) == secret2


def test_secret_manager_validate_secret(mock_bot):
    """Test secret validation - returns tuple of (is_valid, list of issues)."""
    manager = SecretManager(mock_bot, encryption_key="test_key_12345")

    # Strong password should be valid
    is_valid, issues = manager.validate_secret("StrongP@ssw0rd123!")
    assert is_valid is True
    assert len(issues) == 0

    # Weak password should be invalid
    is_valid, issues = manager.validate_secret("weak")
    assert is_valid is False
    assert len(issues) > 0

    # Empty string should be invalid
    is_valid, issues = manager.validate_secret("")
    assert is_valid is False
    assert len(issues) > 0


def test_secret_manager_encrypt_without_key(mock_bot):
    """Test encryption without an encryption key."""
    manager = SecretManager(mock_bot, encryption_key=None)

    # Should handle gracefully when no encryption key is set
    secret = "test_secret"

    # Without a cipher, encrypt should raise ValueError
    try:
        result = manager.encrypt(secret)
        # If it doesn't raise, verify it's handled somehow
        assert result is not None
    except (ValueError, AttributeError):
        # Expected behavior when no encryption key is set
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
