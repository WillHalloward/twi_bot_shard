# Test Scripts for Twi Bot Shard

This directory contains test scripts for verifying different aspects of the Twi Bot Shard project.

## Available Tests

### 1. `test_dependencies.py`

Tests that all required Python dependencies can be imported correctly.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_dependencies.py
```

### 2. `test_db_connection.py`

Tests the database connection to ensure the bot can connect to the database.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_db_connection.py
```

### 3. `test_sqlalchemy_models.py`

Tests the SQLAlchemy models to ensure they work correctly.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_sqlalchemy_models.py
```

### 4. `test_cogs.py`

Tests loading all cogs to ensure they can be loaded without errors. This is particularly useful after making updates to verify that all changes work correctly.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_cogs.py
```

**What it does:**
- Attempts to load all cogs defined in both main.py and owner.py
- Reports which cogs loaded successfully and which failed
- Provides detailed error messages for failed cogs
- Sets exit code to 0 if all cogs load successfully, 1 otherwise (useful for CI/CD)

### 5. `test_decorators.py`

Tests the decorator utilities in `utils/decorators.py` to ensure they work correctly.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_decorators.py
```

### 6. `test_permissions.py`

Tests the permission utilities in `utils/permissions.py` to ensure they work correctly.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_permissions.py
```

### 7. `test_integration.py`

Tests critical bot workflows by simulating interactions between multiple components and verifying database state after operations.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_integration.py
```

**What it does:**
- Tests the `save_message` function with realistic message data
- Tests the `save_reaction` function with realistic reaction data
- Tests the `message_count` command from the StatsCogs with database interactions
- Tests the `find_links` method from the ModCogs for link detection in messages
- Tests the `filter_new_users` method from the ModCogs for role assignment based on account age
- Mocks Discord objects, database connections, and external services
- Verifies that database operations are performed correctly
- Verifies that event handlers respond appropriately to different scenarios

### 8. `test_stats_cog.py`

Tests the StatsCogs class, which is responsible for collecting and storing statistics about Discord servers, users, and events.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_stats_cog.py
```

**What it does:**
- Tests standalone functions (save_message, save_reaction)
- Tests StatsCogs class methods (save_users, save_servers, save_channels)
- Tests the message_count command
- Verifies that database operations are performed correctly

### 9. `test_other_cog.py`

Tests the OtherCogs class, which provides various utility commands for server management and user interaction.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_other_cog.py
```

**What it does:**
- Tests the user_info_function
- Tests OtherCogs class methods (ping, av, info_user, info_server, roll, say)
- Verifies that commands produce the expected responses

### 10. `test_interactive_help.py`

Tests the InteractiveHelp class, which provides an interactive help system for the bot's commands.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_interactive_help.py
```

**What it does:**
- Tests the HelpView class and its components (CategorySelect)
- Tests InteractiveHelp class methods (get_commands_for_category, help_command, help_slash)
- Verifies that the help system displays the correct information

### 11. `test_property_based.py`

Tests various functions using property-based testing to ensure they maintain certain properties for a wide range of inputs.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_property_based.py
```

### 12. `test_validation.py`

Tests the validation functions in `utils/validation.py`.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_validation.py -v
```

**What it does:**
- Tests validate_string with various length constraints and pattern matching
- Tests validate_integer with range constraints
- Tests validate_float with range constraints
- Tests validate_boolean with different input formats
- Tests validate_email with format validation
- Tests validate_url with scheme validation
- Tests validate_discord_id with range validation
- Tests sanitize_string with different validation levels
- Tests sanitize_json with different input types
- Verifies that all validation functions maintain their expected properties

### 13. `test_chaos_engineering.py`

Tests the bot's resilience under various failure conditions using chaos engineering principles.

**Usage:**
```bash
ENVIRONMENT=testing python tests/test_chaos_engineering.py
```

**What it does:**
- Tests database connection failures and timeouts
- Tests network failures and API unavailability
- Tests memory pressure and resource exhaustion
- Tests external service failures
- Tests concurrent failure scenarios
- Tests recovery and graceful degradation
- Tests intermittent failures and slow responses
- Provides a resilience score (0-100) based on test results
- Records detailed metrics including recovery times and degradation events

**Chaos Engineering Scenarios:**
- **Database Failure**: Simulates database connection failures to test graceful degradation
- **External API Failure**: Tests resilience when external APIs (Google, Twitter, etc.) are unavailable
- **Memory Pressure**: Tests bot performance under high memory usage conditions
- **Concurrent Failures**: Tests multiple failure scenarios happening simultaneously
- **Intermittent Failures**: Tests handling of sporadic, unpredictable failures
- **Slow Responses**: Tests timeout handling and performance under slow response conditions

**Example output:**
```
Starting Chaos Engineering Tests for Twi Bot Shard
============================================================
CHAOS ENGINEERING TEST RESULTS
============================================================
Overall Success: PASS
Resilience Score: 83.3/100
Scenarios Tested: 6
Total Failures Injected: 6
Average Recovery Time: 0.12s
Max Recovery Time: 0.15s
Degradation Events: 2

Individual Test Results:
  database_failure: PASS
  external_api_failure: PASS
  memory_pressure: PASS
  concurrent_failures: PASS
  intermittent_failures: PASS
  slow_responses: PASS
```

### 14. `test_twi_cog.py`

Tests the TwiCog class, which provides commands related to "The Wandering Inn" wiki and content.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_twi_cog.py -v
```

### 15. `test_owner_cog.py`

Tests the owner-only commands for bot administration.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_owner_cog.py -v
```

### 16. `test_mods_cog_unit.py`

Unit tests for the moderation cog functionality.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_mods_cog_unit.py -v
```

### 17. `test_gallery_cog_admin.py` and `test_gallery_cog_repost.py`

Tests for the gallery cog's admin and repost detection features.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_gallery_cog_admin.py tests/test_gallery_cog_repost.py -v
```

### 18. `test_error_handling_property_based.py`

Property-based tests for error handling functionality.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_error_handling_property_based.py -v
```

### 19. `test_database_transactions.py`

Tests database transaction handling and rollback behavior.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_database_transactions.py -v
```

### 20. `test_external_api_integration.py`

Tests integration with external APIs (Google, Twitter, etc.).

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_external_api_integration.py -v
```

### 21. `test_load_testing.py` and `test_performance_benchmarks.py`

Performance and load testing for the bot.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_load_testing.py tests/test_performance_benchmarks.py -v
```

### 22. `test_secret_manager.py`

Tests the secret management functionality.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_secret_manager.py -v
```

### 23. `test_query_cache.py`

Tests the query caching functionality.

**Usage:**
```bash
ENVIRONMENT=testing pytest tests/test_query_cache.py -v
```

## Running All Tests

To run all tests using pytest with the testing environment:

```bash
ENVIRONMENT=testing pytest tests/ -v
```

To run all tests with coverage reporting:

```bash
ENVIRONMENT=testing pytest tests/ --cov=. --cov-report=xml
```

This will generate a coverage report in XML format that can be used by tools like Codecov to track code coverage over time.

## Using pytest-mock and pytest-timeout

The project includes support for pytest-mock and pytest-timeout, which provide additional testing capabilities:

### pytest-mock

pytest-mock provides a fixture called `mocker` that helps with mocking dependencies in tests. It's a thin wrapper around the unittest.mock module with some additional features:

```python
def test_example(mocker):
    # Mock a function or method
    mock_function = mocker.patch('module.function')

    # Configure the mock
    mock_function.return_value = 'mocked result'

    # Call the code that uses the mocked function
    result = some_function_that_calls_module_function()

    # Verify the mock was called correctly
    mock_function.assert_called_once_with(expected_args)
```

### pytest-timeout

pytest-timeout helps prevent tests from hanging indefinitely by setting timeouts:

```python
@pytest.mark.timeout(5)  # 5 seconds timeout
def test_example():
    # This test will fail if it takes longer than 5 seconds
    time.sleep(1)
    assert True
```

You can also set a global timeout for all tests by using the `--timeout` command-line option:

```bash
pytest --timeout=10  # 10 seconds timeout for all tests
```

## Using Faker with Mock Factories

The project includes support for Faker, which provides realistic test data for mock objects. The mock factories in `tests/mock_factories.py` have been enhanced to use Faker for generating realistic data.

### Mock Factories with Faker

The following mock factories have been enhanced with Faker:

- `MockUserFactory`: Creates mock Discord users with realistic usernames, discriminators, etc.
- `MockMemberFactory`: Creates mock Discord guild members with realistic data.
- `MockGuildFactory`: Creates mock Discord guilds with realistic server names, etc.
- `MockChannelFactory`: Creates mock Discord channels with realistic channel names, topics, etc.
- `MockMessageFactory`: Creates mock Discord messages with realistic content.

### Using Enhanced Mock Factories

You can use the enhanced mock factories in your tests to create more realistic mock objects:

```python
# Create a mock user with random realistic data
user = MockUserFactory.create()

# Create a mock user with specific values (backward compatible)
custom_user = MockUserFactory.create(user_id=123456789, name="CustomUser")

# Create a mock guild with random realistic data
guild = MockGuildFactory.create()

# Create a mock channel with random realistic data
channel = MockChannelFactory.create_text_channel(guild=guild)

# Create a mock message with random realistic content
message = MockMessageFactory.create(author=user, channel=channel, guild=guild)
```

The mock factories are designed to be backward compatible, so you can still provide specific values for any parameter if needed. If you don't provide a value, Faker will generate a realistic value for you.

See the `example_usage()` function in `tests/mock_factories.py` for more examples of how to use the enhanced mock factories.

## Related Documentation

- [Testing Guide](../docs/developer/testing.md) - Property-based testing and testing strategies
- [CI/CD Pipeline](../docs/operations/ci.md) - Continuous integration configuration
- [Getting Started](../docs/developer/getting-started.md) - Developer setup guide
