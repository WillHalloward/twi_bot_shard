"""
Tests for the common patterns utility module.

This module tests the consolidated utilities for error handling,
parameter validation, logging patterns, and common responses.
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord import Interaction

from utils.common_patterns import (
    CommonPatterns,
    with_db_error_handling,
    with_parameter_validation,
)
from utils.exceptions import DatabaseError, ValidationError, QueryError


class TestCommonPatterns:
    """Test cases for the CommonPatterns utility class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = MagicMock(spec=logging.Logger)
        self.user_id = 12345
        self.operation_name = "test_operation"

    @pytest.mark.asyncio
    async def test_safe_db_query_success(self):
        """Test successful database query execution."""
        # Arrange
        expected_result = {"id": 1, "name": "test"}
        db_operation = AsyncMock(return_value=expected_result)

        # Act
        result = await CommonPatterns.safe_db_query(
            db_operation, self.operation_name, self.user_id, self.logger
        )

        # Assert
        assert result == expected_result
        db_operation.assert_called_once()
        self.logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_safe_db_query_postgres_error(self):
        """Test database query with PostgreSQL error."""
        # Arrange
        import asyncpg

        postgres_error = asyncpg.PostgresError("Connection failed")
        db_operation = AsyncMock(side_effect=postgres_error)

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await CommonPatterns.safe_db_query(
                db_operation, self.operation_name, self.user_id, self.logger
            )

        assert "Database operation failed: Connection failed" in str(exc_info.value)
        self.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_db_query_unexpected_error(self):
        """Test database query with unexpected error."""
        # Arrange
        unexpected_error = ValueError("Unexpected issue")
        db_operation = AsyncMock(side_effect=unexpected_error)

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await CommonPatterns.safe_db_query(
                db_operation, self.operation_name, self.user_id, self.logger
            )

        assert "Database operation failed: Unexpected error occurred" in str(
            exc_info.value
        )
        self.logger.error.assert_called_once()

    def test_validate_positive_number_valid(self):
        """Test positive number validation with valid input."""
        # Should not raise any exception
        CommonPatterns.validate_positive_number(5, "test_field", max_value=10)
        CommonPatterns.validate_positive_number(1, "test_field")
        CommonPatterns.validate_positive_number(10.5, "test_field", max_value=20)

    def test_validate_positive_number_too_small(self):
        """Test positive number validation with value too small."""
        with pytest.raises(ValidationError) as exc_info:
            CommonPatterns.validate_positive_number(0, "test_field")

        assert "Test_field must be at least 1" in str(exc_info.value)

    def test_validate_positive_number_too_large(self):
        """Test positive number validation with value too large."""
        with pytest.raises(ValidationError) as exc_info:
            CommonPatterns.validate_positive_number(15, "test_field", max_value=10)

        assert "Test_field cannot exceed 10" in str(exc_info.value)

    def test_validate_string_length_valid(self):
        """Test string length validation with valid input."""
        # Should not raise any exception
        CommonPatterns.validate_string_length("hello", "test_field", max_length=10)
        CommonPatterns.validate_string_length(
            "test", "test_field", max_length=10, min_length=2
        )

    def test_validate_string_length_empty(self):
        """Test string length validation with empty string."""
        with pytest.raises(ValidationError) as exc_info:
            CommonPatterns.validate_string_length("", "test_field", max_length=10)

        assert "Test_field cannot be empty" in str(exc_info.value)

    def test_validate_string_length_too_short(self):
        """Test string length validation with string too short."""
        with pytest.raises(ValidationError) as exc_info:
            CommonPatterns.validate_string_length(
                "a", "test_field", max_length=10, min_length=3
            )

        assert "Test_field must be at least 3 characters" in str(exc_info.value)

    def test_validate_string_length_too_long(self):
        """Test string length validation with string too long."""
        with pytest.raises(ValidationError) as exc_info:
            CommonPatterns.validate_string_length(
                "this is too long", "test_field", max_length=5
            )

        assert "Test_field cannot exceed 5 characters" in str(exc_info.value)

    def test_log_command_execution(self):
        """Test command execution logging."""
        # Act
        CommonPatterns.log_command_execution(
            "test_command",
            12345,
            "TestUser",
            self.logger,
            additional_info="extra info",
            guild_id=67890,
        )

        # Assert
        self.logger.info.assert_called_once()
        call_args = self.logger.info.call_args
        assert (
            "TEST_COMMAND: Executed by TestUser (12345) - extra info" in call_args[0][0]
        )
        assert call_args[1]["extra"]["command"] == "test_command"
        assert call_args[1]["extra"]["user_id"] == 12345
        assert call_args[1]["extra"]["guild_id"] == 67890

    def test_log_command_error(self):
        """Test command error logging."""
        # Arrange
        test_error = ValueError("Test error message")

        # Act
        CommonPatterns.log_command_error(
            "test_command",
            12345,
            test_error,
            self.logger,
            additional_context="test context",
        )

        # Assert
        self.logger.error.assert_called_once()
        call_args = self.logger.error.call_args
        assert (
            "TEST_COMMAND ERROR: ValueError: Test error message - test context"
            in call_args[0][0]
        )
        assert call_args[1]["extra"]["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_send_error_response_new_interaction(self):
        """Test sending error response to new interaction."""
        # Arrange
        interaction = MagicMock(spec=Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        # Act
        await CommonPatterns.send_error_response(
            interaction, "Test Error", "This is a test error"
        )

        # Assert
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        assert call_args[1]["ephemeral"] is True
        embed = call_args[1]["embed"]
        assert "❌ Test Error" in embed.title
        assert "This is a test error" in embed.description

    @pytest.mark.asyncio
    async def test_send_error_response_followup(self):
        """Test sending error response as followup."""
        # Arrange
        interaction = MagicMock(spec=Interaction)
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()

        # Act
        await CommonPatterns.send_error_response(
            interaction, "Test Error", "This is a test error"
        )

        # Assert
        interaction.followup.send.assert_called_once()

    def test_create_success_embed(self):
        """Test creating success embed."""
        # Act
        embed = CommonPatterns.create_success_embed(
            "Success",
            "Operation completed",
            fields={
                "Field 1": "Value 1",
                "Field 2": {"value": "Value 2", "inline": True},
            },
        )

        # Assert
        assert embed.title == "✅ Success"
        assert embed.description == "Operation completed"
        assert embed.color == discord.Color.green()
        assert len(embed.fields) == 2


class TestDecorators:
    """Test cases for the decorator functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = MagicMock(spec=logging.Logger)

    @pytest.mark.asyncio
    async def test_with_db_error_handling_success(self):
        """Test database error handling decorator with successful operation."""

        # Arrange
        @with_db_error_handling("test_op", "Test failed")
        async def test_method(self, interaction):
            return "success"

        mock_self = MagicMock()
        mock_self.logger = self.logger
        mock_interaction = MagicMock(spec=Interaction)
        mock_interaction.user.id = 12345

        # Act
        result = await test_method(mock_self, mock_interaction)

        # Assert
        assert result == "success"
        self.logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_db_error_handling_custom_exception(self):
        """Test database error handling decorator with custom exception."""

        # Arrange
        @with_db_error_handling("test_op", "Test failed")
        async def test_method(self, interaction):
            raise ValidationError("Custom validation error")

        mock_self = MagicMock()
        mock_self.logger = self.logger
        mock_interaction = MagicMock(spec=Interaction)
        mock_interaction.user.id = 12345

        # Act & Assert
        with pytest.raises(ValidationError):
            await test_method(mock_self, mock_interaction)

    @pytest.mark.asyncio
    async def test_with_db_error_handling_unexpected_exception(self):
        """Test database error handling decorator with unexpected exception."""

        # Arrange
        @with_db_error_handling("test_op", "Test failed")
        async def test_method(self, interaction):
            raise ValueError("Unexpected error")

        mock_self = MagicMock()
        mock_self.logger = self.logger
        mock_interaction = MagicMock(spec=Interaction)
        mock_interaction.user.id = 12345

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await test_method(mock_self, mock_interaction)

        assert "Test failed: Unexpected error" in str(exc_info.value)
        self.logger.error.assert_called_once()  # CommonPatterns.log_command_error is called

    @pytest.mark.asyncio
    async def test_with_parameter_validation_success(self):
        """Test parameter validation decorator with valid parameters."""

        # Arrange
        def validate_hours(hours):
            CommonPatterns.validate_positive_number(hours, "hours", max_value=24)

        @with_parameter_validation(hours=validate_hours)
        async def test_method(self, interaction, hours):
            return f"Hours: {hours}"

        mock_self = MagicMock()
        mock_interaction = MagicMock(spec=Interaction)

        # Act
        result = await test_method(mock_self, mock_interaction, hours=12)

        # Assert
        assert result == "Hours: 12"

    @pytest.mark.asyncio
    async def test_with_parameter_validation_invalid(self):
        """Test parameter validation decorator with invalid parameters."""

        # Arrange
        def validate_hours(hours):
            CommonPatterns.validate_positive_number(hours, "hours", max_value=24)

        @with_parameter_validation(hours=validate_hours)
        async def test_method(self, interaction, hours):
            return f"Hours: {hours}"

        mock_self = MagicMock()
        mock_interaction = MagicMock(spec=Interaction)

        # Act & Assert
        with pytest.raises(ValidationError):
            await test_method(mock_self, mock_interaction, hours=30)


if __name__ == "__main__":
    # Run tests with asyncio support
    pytest.main([__file__, "-v"])
