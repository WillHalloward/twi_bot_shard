# Code Linting and Formatting

This document describes how the Twi Bot Shard project uses [Ruff](https://github.com/astral-sh/ruff) for both linting and formatting, and [mypy](https://mypy-lang.org/) for type checking.

## Overview

The project uses a single tool — **Ruff** — for both linting and code formatting. Ruff is a fast Python linter and formatter written in Rust. `ruff format` is a drop-in, Black-compatible formatter, so the project does **not** use Black itself.

Type checking is handled by **mypy**.

## Configuration

All tool configuration lives in `pyproject.toml` (there is no separate `ruff.toml`, `mypy.ini`, or Black config).

### Ruff Configuration

Ruff is configured with the following rule groups enabled:

- `E`: pycodestyle errors
- `F`: pyflakes
- `B`: flake8-bugbear
- `I`: isort
- `N`: pep8-naming
- `UP`: pyupgrade
- `ANN`: flake8-annotations
- `D`: pydocstyle
- `C`: flake8-comprehensions
- `SIM`: flake8-simplify

The configuration follows the Google docstring convention and uses a line length of 88 characters (the same default as Black, which is why `ruff format` output is Black-compatible).

## Running Linting and Formatting

Run Ruff and mypy directly from the project root:

```bash
# Check for linting issues
ruff check .

# Auto-fix the issues Ruff can fix
ruff check . --fix

# Show formatting changes without applying them
ruff format . --diff

# Check formatting (used in CI; fails if anything is unformatted)
ruff format --check .

# Apply formatting
ruff format .

# Type checking
mypy .
```

These are the exact commands the CI lint job runs (`ruff check .`, `ruff format --check .`, `mypy .`) — see [CI/CD](../operations/ci.md). The lint job is a **hard gate**, so code must pass all three before it can merge.

## Common Issues and How to Fix Them

### Missing Type Annotations

Ruff flags missing type annotations with `ANN` codes. Add type hints to function parameters and return values:

```python
# Before
def get_user(user_id):
    return db.get_user(user_id)

# After
def get_user(user_id: int) -> User:
    return db.get_user(user_id)
```

### Missing Docstrings

Ruff flags missing docstrings with `D` codes. Add docstrings following the Google style:

```python
def get_user(user_id: int) -> User:
    """Get a user by ID.

    Args:
        user_id: The ID of the user to get.

    Returns:
        The user object.

    Raises:
        UserNotFoundError: If the user doesn't exist.
    """
    return db.get_user(user_id)
```

### Import Ordering

Ruff flags incorrect import ordering with `I` codes. The correct order is:

1. Standard library imports
2. Third-party imports
3. Local application imports

Each group should be separated by a blank line. `ruff check . --fix` reorders imports automatically.

## IDE Integration

### VS Code

1. Install the [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).
2. Add the following to your `settings.json`:

```json
{
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    }
}
```

### PyCharm

1. Install the [Ruff plugin](https://plugins.jetbrains.com/plugin/20574-ruff).
2. Configure it to run on save in Settings → Tools → Ruff (enable "Run ruff format on save").

## Ignoring Rules

To ignore a specific rule for a specific line, use a `noqa` comment:

```python
some_variable = "value"  # noqa: ANN001
```

For file-specific ignores, use the `per-file-ignores` section in `pyproject.toml`.

## Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) to run linting, formatting, and type checks automatically before each commit.

### Installation

1. Install pre-commit (it ships with the `[dev]` extra, or install it standalone):
   ```bash
   uv pip install pre-commit
   ```

2. Install the git hooks:
   ```bash
   pre-commit install
   ```

### Usage

Once installed, pre-commit runs the configured hooks on staged files. If any hook fails, the commit is aborted until the issues are fixed.

Run the hooks manually on all files:

```bash
pre-commit run --all-files
```

Or on specific files:

```bash
pre-commit run --files path/to/file1.py path/to/file2.py
```

### Configured Hooks

The hooks configured in `.pre-commit-config.yaml` are:

1. **pre-commit-hooks**: Basic file checks (trailing whitespace, end-of-file fixer, check-yaml, check-toml, check-added-large-files, debug-statements)
2. **ruff**: Python linting (with `--fix`)
3. **ruff-format**: Python code formatting
4. **mypy**: Static type checking (excludes `tests/`)

## Conclusion

Ruff (lint + format) and mypy keep the codebase consistent and type-safe. Run `ruff check .`, `ruff format .`, and `mypy .` before submitting changes, and install the pre-commit hooks so these checks run automatically.
