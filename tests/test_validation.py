"""
Unit tests for validation utilities.

Tests the validation and sanitization functions in utils/validation.py.
"""

import os
import re
import sys

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from utils.exceptions import ValidationError
from utils.validation import (
    sanitize_json,
    sanitize_string,
    validate_integer,
    validate_string,
)


def test_validate_string_basic():
    """Test basic string validation."""
    # Valid string
    result = validate_string("test")
    assert result == "test"

    # String with whitespace (should strip)
    result = validate_string("  test  ")
    assert result == "test"

    # None without allow_empty
    with pytest.raises(ValidationError):
        validate_string(None)

    # Empty string without allow_empty
    with pytest.raises(ValidationError):
        validate_string("")


def test_validate_string_length():
    """Test string length validation."""
    # Min length
    result = validate_string("test", min_length=3)
    assert result == "test"

    with pytest.raises(ValidationError):
        validate_string("ab", min_length=3)

    # Max length
    result = validate_string("test", max_length=10)
    assert result == "test"

    with pytest.raises(ValidationError):
        validate_string("very long string", max_length=5)


def test_validate_string_pattern():
    """Test string pattern validation."""
    # Email pattern
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    result = validate_string("test@example.com", pattern=email_pattern)
    assert result == "test@example.com"

    with pytest.raises(ValidationError):
        validate_string("invalid-email", pattern=email_pattern)


def test_validate_integer_basic():
    """Test basic integer validation."""
    # Valid integer
    result = validate_integer(42)
    assert result == 42

    # String that can be converted
    result = validate_integer("42")
    assert result == 42

    # Invalid value
    with pytest.raises(ValidationError):
        validate_integer("not a number")


def test_validate_integer_range():
    """Test integer range validation."""
    # Within range
    result = validate_integer(5, min_value=0, max_value=10)
    assert result == 5

    # Below minimum
    with pytest.raises(ValidationError):
        validate_integer(-5, min_value=0)

    # Above maximum
    with pytest.raises(ValidationError):
        validate_integer(15, max_value=10)


def test_sanitize_string_basic():
    """Test basic string sanitization."""
    from utils.validation import ValidationLevel

    # Normal string
    result = sanitize_string("Hello World")
    assert result == "Hello World"

    # String with HTML tags - default MODERATE level HTML-escapes tags
    result = sanitize_string("<script>alert('xss')</script>")
    assert "&lt;script&gt;" in result  # Should be escaped

    # String with special characters - LENIENT level removes control characters
    result = sanitize_string("Test\x00\x01\x02", level=ValidationLevel.LENIENT)
    assert "\x00" not in result
    assert "\x01" not in result
    assert "Test" in result


def test_sanitize_json():
    """Test JSON sanitization - returns JSON string."""
    # Valid JSON - sanitize_json returns a JSON string
    data = {"key": "value", "number": 42}
    result = sanitize_json(data)
    assert isinstance(result, str)
    assert '"key": "value"' in result or '"key":"value"' in result

    # Invalid value should still return valid JSON
    result = sanitize_json(object())  # Non-serializable object
    assert isinstance(result, str)
    # Should either return stringified version or null


def test_validate_string_allow_empty():
    """Test string validation with allow_empty flag."""
    # Should allow None and empty strings when allow_empty=True
    result = validate_string(None, allow_empty=True)
    assert result == ""

    result = validate_string("", allow_empty=True)
    assert result == ""

    result = validate_string("   ", allow_empty=True, strip=True)
    assert result == ""


def test_validate_string_custom_error():
    """Test string validation with custom error message."""
    custom_message = "Custom validation error"

    with pytest.raises(ValidationError) as exc_info:
        validate_string("", error_message=custom_message)

    assert custom_message in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
