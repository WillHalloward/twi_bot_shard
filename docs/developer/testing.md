# Property-Based Testing in Twi Bot Shard

This document explains the property-based testing approach used in the Twi Bot Shard project, including what property-based testing is, why it's useful, and how to use it in the project.

## What is Property-Based Testing?

Property-based testing is a testing methodology that focuses on verifying that certain properties or invariants of a function hold for a wide range of inputs, rather than just specific examples. Instead of writing individual test cases with specific inputs and expected outputs, you define properties that should always be true for any valid input.

The testing framework (in our case, Hypothesis) then generates a large number of random inputs and checks that the property holds for all of them. If it finds an input that violates the property, it reports it as a failing test case and often tries to simplify the input to find the smallest example that still fails.

## Why Use Property-Based Testing?

Property-based testing offers several advantages over traditional unit testing:

1. **Better coverage**: By testing with a wide range of inputs, property-based testing can find edge cases that you might not have thought to test explicitly.

2. **Concise tests**: Instead of writing many similar test cases with different inputs, you can define a single property that covers all of them.

3. **Focus on behavior**: Property-based testing encourages you to think about the fundamental properties of your code rather than specific input-output pairs.

4. **Automatic simplification**: When a test fails, the framework tries to simplify the failing input to make it easier to understand what went wrong.

## When to Use Property-Based Testing

Property-based testing is particularly useful for:

1. **Pure functions**: Functions that always return the same output for the same input and have no side effects.

2. **Complex logic**: Functions with complex logic that might have edge cases you haven't considered.

3. **Data transformations**: Functions that transform data from one format to another.

4. **Invariants**: Functions that should maintain certain invariants regardless of input.

In the Twi Bot Shard project, property-based testing is currently used for:

- **Decorators**: The `log_command` and `handle_errors` decorators are tested to verify they preserve function metadata and correctly call the underlying functions.
- **Permission checks**: The `admin_or_me_check` function is tested to verify it always returns a boolean value.
- **Error handling**: Functions like `get_error_response`, `log_error`, and `detect_sensitive_info` are tested to ensure they provide appropriate user feedback, don't raise exceptions themselves, and correctly identify sensitive information.

## How to Use Property-Based Testing in Twi Bot Shard

### Dependencies

To use property-based testing in the Twi Bot Shard project, you need to install the Hypothesis library:

```bash
uv pip install hypothesis
```

### Writing Property-Based Tests

Property-based tests are written using the `@given` decorator from Hypothesis, which specifies the strategies to use for generating inputs. A strategy is a recipe for generating random values of a particular type.

Here's an example of a property-based test from the project:

```python
@given(command_name=command_name_strategy)
def test_log_command_preserves_function_metadata(command_name: str) -> None:
    """Test that log_command preserves function metadata."""
    # Define a test function
    async def test_func(self, ctx):
        """Test function docstring."""
        return "test"

    # Apply the decorator
    decorated = log_command(command_name)(test_func)

    # Check that the metadata is preserved
    assert decorated.__name__ == test_func.__name__
    assert decorated.__doc__ == test_func.__doc__
    assert decorated.__module__ == test_func.__module__
    assert decorated.__annotations__ == test_func.__annotations__
    assert decorated.__qualname__ == test_func.__qualname__
```

This test verifies that the `log_command` decorator preserves the metadata of the function it decorates, such as the function name, docstring, and annotations.

### Defining Strategies

Strategies define how to generate random values for your tests. Hypothesis provides a wide range of built-in strategies, and you can compose them to create more complex strategies.

Here are some examples of strategies used in the project:

```python
# Strategy for generating command names
command_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), blacklist_characters=()),
    min_size=1,
    max_size=20
)

# Strategy for generating user IDs
user_id_strategy = st.integers(min_value=100000000000000000, max_value=999999999999999999)

# Strategy for generating exceptions
def exception_strategy() -> SearchStrategy[Exception]:
    """Generate a strategy for exceptions."""
    return st.one_of(
        st.builds(ValueError, error_message_strategy),
        st.builds(TypeError, error_message_strategy),
        st.builds(RuntimeError, error_message_strategy),
        st.builds(KeyError, st.text(min_size=1, max_size=20)),
        st.builds(IndexError, error_message_strategy),
        st.builds(AttributeError, error_message_strategy)
    )
```

### Running Property-Based Tests

To run the property-based tests, you can use the following commands:

```bash
# Run the general property-based tests (decorators, permissions, basic error handling)
python -m tests.test_property_based

# Run the error handling property-based tests (sensitive info detection, error responses)
python -m tests.test_error_handling_property_based
```

These commands will run the property-based tests defined in the respective test files.

## Adding New Property-Based Tests

To add new property-based tests to the project:

1. Identify functions that are good candidates for property-based testing (pure functions, complex logic, data transformations, invariants).

2. Define the properties that should hold for these functions.

3. Write property-based tests using the `@given` decorator and appropriate strategies.

4. Add the tests to the `tests/test_property_based.py` file or create a new file for them.

5. Run the tests to verify that the properties hold.

## Best Practices

When writing property-based tests, keep the following best practices in mind:

1. **Focus on properties, not examples**: Think about what properties should always be true for your function, not specific input-output pairs.

2. **Keep tests simple**: Each test should verify a single property. If you need to verify multiple properties, write multiple tests.

3. **Use appropriate strategies**: Choose strategies that generate a wide range of inputs, including edge cases.

4. **Handle stateful tests carefully**: If your function has side effects or depends on state, you may need to reset the state between test runs.

5. **Consider performance**: Property-based tests can be slower than traditional unit tests because they run many examples. Keep your tests efficient.

## Conclusion

Property-based testing is a powerful technique for verifying that your code behaves correctly for a wide range of inputs. By focusing on properties rather than specific examples, you can write more concise tests that provide better coverage and catch more bugs.

In the Twi Bot Shard project, we use property-based testing to verify the behavior of:

- **Decorators**: The `log_command` and `handle_errors` decorators, ensuring they preserve function metadata and call underlying handlers correctly.
- **Permission checks**: The `admin_or_me_check` function, verifying it always returns a boolean value.
- **Error handling functions**: Testing `get_error_response`, `log_error`, and `detect_sensitive_info` to ensure they handle various error types correctly, don't raise exceptions themselves, and properly identify sensitive information.

This approach helps ensure that these critical components of the bot behave correctly with a wide range of inputs, including edge cases that might not be covered by traditional unit tests.
