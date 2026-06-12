"""
Property-based tests for error handling utilities in Twi Bot Shard.

This module contains property-based tests using the Hypothesis library
to verify that error handling functions in utils/error_handling.py maintain
certain properties for a wide range of inputs.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Hypothesis for property-based testing
try:
    from hypothesis import example, given
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy
except ImportError:
    print("Hypothesis is not installed. Please install it with:")
    print("uv pip install hypothesis")
    sys.exit(1)

# Import error handling functions
from utils.error_handling import (
    SENSITIVE_PATTERNS,
    ErrorSecurityLevel,
    detect_sensitive_info,
    get_error_response,
    redact_sensitive_info,
    sanitize_error_message,
)

# Define strategies for generating test data

# Strategy for generating strings
string_strategy = st.text(min_size=0, max_size=100)

# Strategy for generating non-empty strings
non_empty_string_strategy = st.text(min_size=1, max_size=100)

# Strategies generating (text, secret) pairs: `text` is a string containing
# sensitive information and `secret` is the substring that must never survive
# redaction. Secret alphabets/lengths are chosen so that a secret can never
# coincidentally be a substring of the redacted output (labels + "[REDACTED]").
_lower_digits = "abcdefghijklmnopqrstuvwxyz0123456789"

sensitive_pair_strategy = st.one_of(
    # API keys and tokens (pattern has capture groups; value >= 20 chars)
    st.builds(
        lambda key, value: (f"{key}={value}", value),
        key=st.sampled_from(["api_key", "token", "secret", "password", "auth"]),
        value=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.",
            min_size=20,
            max_size=40,
        ),
    ),
    # Discord tokens (no capture groups)
    st.from_regex(
        r"M[A-Za-z\d]{23}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27}", fullmatch=True
    ).map(lambda t: (t, t)),
    # Database connection strings (capture group is the scheme)
    st.builds(
        lambda db, user, password, host, port, name: (
            f"{db}://{user}:{password}@{host}:{port}/{name}",
            password,
        ),
        db=st.sampled_from(["postgres", "mysql", "mongodb", "redis"]),
        user=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
        password=st.text(alphabet=_lower_digits, min_size=12, max_size=20),
        host=st.sampled_from(["localhost", "127.0.0.1", "db.example.com"]),
        port=st.integers(min_value=1000, max_value=9999).map(str),
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
    ),
    # IP addresses (no capture groups); built from octets so they are
    # guaranteed ASCII and well-formed
    st.builds(
        lambda a, b, c, d: (f"{a}.{b}.{c}.{d}",) * 2,
        a=st.integers(min_value=0, max_value=255),
        b=st.integers(min_value=0, max_value=255),
        c=st.integers(min_value=0, max_value=255),
        d=st.integers(min_value=0, max_value=255),
    ),
    # Email addresses (no capture groups); built from the character class the
    # detection pattern actually recognizes (st.emails() can generate RFC
    # local parts like "{@A.COM" the pattern legitimately does not match)
    st.builds(
        lambda local, domain, tld: (f"{local}@{domain}.{tld}",) * 2,
        local=st.text(alphabet=_lower_digits, min_size=1, max_size=12),
        domain=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12),
        tld=st.sampled_from(["com", "org", "net", "io"]),
    ),
    # Windows file paths (no capture groups)
    st.builds(
        lambda drive, path: (f"{drive}:\\{path}", path),
        drive=st.sampled_from(["C", "D", "E"]),
        path=st.text(alphabet=_lower_digits + "_-.", min_size=5, max_size=20),
    ),
    # POSIX file paths (no capture groups)
    st.builds(
        lambda a, b: (f"/{a}/{b}",) * 2,
        a=st.text(alphabet=_lower_digits, min_size=3, max_size=10),
        b=st.text(alphabet=_lower_digits, min_size=3, max_size=10),
    ),
    # JSON web tokens (no capture groups)
    st.from_regex(
        r"eyJ[a-zA-Z0-9_-]{10,40}\.[a-zA-Z0-9_-]{10,40}\.[a-zA-Z0-9_-]{10,40}",
        fullmatch=True,
    ).map(lambda t: (t, t)),
)

# Strategy for generating strings that contain sensitive information
sensitive_string_strategy = sensitive_pair_strategy.map(lambda pair: pair[0])

# Strategy for generating mixed strings that may or may not contain sensitive information
mixed_string_strategy = st.one_of(
    string_strategy,
    st.builds(
        lambda normal, sensitive: f"{normal} {sensitive}",
        normal=string_strategy,
        sensitive=sensitive_string_strategy,
    ),
)

# Strategy for generating security levels
security_level_strategy = st.sampled_from(
    [
        ErrorSecurityLevel.DEBUG,
        ErrorSecurityLevel.NORMAL,
        ErrorSecurityLevel.SECURE,
    ]
)


# Strategy for generating exceptions
def exception_strategy() -> SearchStrategy[Exception]:
    """Generate a strategy for exceptions."""
    return st.one_of(
        st.builds(ValueError, string_strategy),
        st.builds(TypeError, string_strategy),
        st.builds(RuntimeError, string_strategy),
        st.builds(KeyError, non_empty_string_strategy),
        st.builds(IndexError, string_strategy),
        st.builds(AttributeError, string_strategy),
    )


# Tests for detect_sensitive_info


@given(text=sensitive_string_strategy)
def test_detect_sensitive_info_with_sensitive_data(text: str) -> None:
    """Test that detect_sensitive_info correctly identifies sensitive information."""
    assert detect_sensitive_info(text) is True


@given(text=string_strategy)
def test_detect_sensitive_info_properties(text: str) -> None:
    """Test properties of detect_sensitive_info function."""
    result = detect_sensitive_info(text)

    # Property 1: Result should be a boolean
    assert isinstance(result, bool)

    # Property 2: Empty strings should not be detected as sensitive
    if not text:
        assert result is False

    # Property 3: If any pattern matches, result should be True
    has_match = any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)
    assert result == has_match


# Tests for redact_sensitive_info


@given(pair=sensitive_pair_strategy)
def test_redact_sensitive_info_with_sensitive_data(pair: tuple[str, str]) -> None:
    """Test that redact_sensitive_info correctly redacts sensitive information."""
    text, secret = pair
    redacted = redact_sensitive_info(text)

    # Something was redacted (every generated input is detectably sensitive,
    # whether or not the matching pattern has capture groups).
    assert "[REDACTED]" in redacted

    # The secret payload itself never survives redaction.
    assert secret not in redacted

    # The redacted output no longer triggers detection.
    assert detect_sensitive_info(redacted) is False


@given(text=mixed_string_strategy)
@example(text="//a")  # single-pass redaction regression: "//a" -> "/[REDACTED]"
def test_redact_sensitive_info_properties(text: str) -> None:
    """Test properties of redact_sensitive_info function."""
    redacted = redact_sensitive_info(text)

    # Property 1: Result is a string.
    assert isinstance(redacted, str)

    # Property 2: Clean input passes through unchanged.
    if not detect_sensitive_info(text):
        assert redacted == text

    # Property 3: Detect -> redact -> nothing sensitive survives.
    assert detect_sensitive_info(redacted) is False

    # Property 4: Redaction is idempotent.
    assert redact_sensitive_info(redacted) == redacted


# Tests for sanitize_error_message


@given(
    error=exception_strategy(),
    security_level=security_level_strategy,
)
def test_sanitize_error_message_properties(
    error: Exception, security_level: int
) -> None:
    """Test properties of sanitize_error_message function."""
    result = sanitize_error_message(error, security_level)

    # Property 1: Result is a string (may be empty at NORMAL level when the
    # underlying error message itself is empty).
    assert isinstance(result, str)

    # Property 2: Sanitization composes with redaction — the final message
    # never contains anything the detector would flag.
    assert detect_sensitive_info(result) is False

    # Property 3: SECURE level always yields the generic message.
    if security_level == ErrorSecurityLevel.SECURE:
        assert (
            result
            == "An error occurred. Please contact an administrator if this persists."
        )

    # Property 4: DEBUG level keeps the exception type as a prefix.
    if security_level == ErrorSecurityLevel.DEBUG:
        assert result.startswith(f"{type(error).__name__}:")


@given(pair=sensitive_pair_strategy, security_level=security_level_strategy)
def test_sanitize_error_message_with_sensitive_data(
    pair: tuple[str, str], security_level: int
) -> None:
    """Sensitive content in an exception message never reaches the user."""
    text, secret = pair
    result = sanitize_error_message(ValueError(text), security_level)

    assert secret not in result
    assert detect_sensitive_info(result) is False


# Tests for get_error_response


@given(
    error=exception_strategy(),
    security_level=security_level_strategy,
)
def test_get_error_response_properties(error: Exception, security_level: int) -> None:
    """Test properties of get_error_response function."""
    response = get_error_response(error, security_level)

    # Property 1: Result should be a dictionary
    assert isinstance(response, dict)

    # Property 2: Response should contain required keys
    assert "message" in response
    assert "log_level" in response
    assert "ephemeral" in response

    # Property 3: Message should be a string
    assert isinstance(response["message"], str)

    # Property 4: Message should not contain sensitive information
    assert not detect_sensitive_info(response["message"])

    # Property 5: log_level should be an integer
    assert isinstance(response["log_level"], int)

    # Property 6: ephemeral should be a boolean
    assert isinstance(response["ephemeral"], bool)


# Main function to run the tests
def main() -> None:
    """Run all property-based tests for error handling functions."""
    print("Running property-based tests for error handling functions...")

    # Run tests
    test_detect_sensitive_info_with_sensitive_data()
    test_detect_sensitive_info_properties()
    test_redact_sensitive_info_with_sensitive_data()
    test_redact_sensitive_info_properties()
    test_sanitize_error_message_properties()
    test_sanitize_error_message_with_sensitive_data()
    test_get_error_response_properties()

    print("All property-based tests for error handling functions passed!")


if __name__ == "__main__":
    main()
