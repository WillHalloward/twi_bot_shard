# Code Linting and Formatting

This document describes how to use Ruff and Black for code linting and formatting in the Twi Bot Shard project.

## Overview

### Ruff

[Ruff](https://github.com/astral-sh/ruff) is a fast Python linter written in Rust. It's used in this project to enforce code style and catch common errors.

### Black

[Black](https://github.com/psf/black) is the uncompromising Python code formatter. It's used in this project to ensure consistent code formatting.

## Configuration

### Ruff Configuration

Ruff is configured in the `pyproject.toml` file with the following rules enabled:

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

The configuration follows the Google docstring convention and has a line length of 88 characters (same as Black).

### Black Configuration

Black is configured in the `pyproject.toml` file with the following settings:

- `line-length`: 88 characters
- `target-version`: Python 3.12
- Appropriate exclusions for common directories like `.git`, `.venv`, etc.

## Running Linting and Formatting Checks

### Using the Lint Script

The project includes a `lint.py` script that runs Ruff on the codebase:

```bash
python scripts/development/lint.py
```

This will:
1. Run `ruff check` to identify code style issues
2. Run `ruff format --diff` to show formatting changes that would be made (without making them)

### Using the Format Script

The project includes a `format.py` script that runs Black on the codebase:

```bash
python scripts/development/format.py
```

This will:
1. Run `black --check --diff .` to show what formatting changes would be made
2. Automatically apply the changes if any files need formatting

### Using Ruff Directly

You can also run Ruff directly:

```bash
# Check for linting issues
ruff check .

# Show formatting issues
ruff format . --diff

# Fix formatting issues
ruff format .

# Fix auto-fixable issues
ruff check . --fix
```

### Using Black Directly

You can also run Black directly:

```bash
# Check what would be formatted
black --check --diff .

# Format files
black .

# Format specific files or directories
black path/to/file.py path/to/directory
```

## Common Issues and How to Fix Them

### Missing Type Annotations

Ruff will flag missing type annotations with `ANN` codes. Add type hints to function parameters and return values:

```python
# Before
def get_user(user_id):
    return db.get_user(user_id)

# After
def get_user(user_id: int) -> User:
    return db.get_user(user_id)
```

### Missing Docstrings

Ruff will flag missing docstrings with `D` codes. Add docstrings following the Google style:

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

Ruff will flag incorrect import ordering with `I` codes. The correct order is:

1. Standard library imports
2. Third-party imports
3. Local application imports

Each group should be separated by a blank line.

## IDE Integration

### VS Code

1. Install the [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) and [Black Formatter extension](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter)
2. Add the following to your settings.json:

```json
{
    "editor.formatOnSave": true,
    "ruff.organizeImports": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": true,
            "source.organizeImports.ruff": true
        }
    },
    "black-formatter.args": ["--line-length", "88"]
}
```

### PyCharm

1. Install the [Ruff plugin](https://plugins.jetbrains.com/plugin/20574-ruff)
2. Configure it to run on save in Settings → Tools → Ruff
3. For Black, go to Settings → Tools → Black and enable "Run on save"

## Ignoring Rules

If you need to ignore a specific rule for a specific line, you can use a comment:

```python
# This line will trigger a warning, but we're ignoring it
some_variable = "value"  # noqa: ANN001
```

For file-specific ignores, use the `per-file-ignores` section in `pyproject.toml`.

## Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) to automatically run linting and formatting checks before each commit.

### Installation

#### Option 1: Using the setup script (recommended)

Run the setup script to automatically install pre-commit and set up the git hooks:

```bash
python scripts/development/setup_hooks.py
```

This script will:
1. Check if pre-commit is installed and install it if needed
2. Set up the git hooks for the project
3. Run pre-commit on all files to verify the setup

#### Option 2: Manual installation

1. Install pre-commit:
   ```bash
   # Using uv
   uv pip install pre-commit

   # Using pip
   pip install pre-commit
   ```

2. Install the git hooks:
   ```bash
   pre-commit install
   ```

### Usage

Once installed, pre-commit will automatically run the configured hooks on the files you're committing. If any issues are found, the commit will be aborted and you'll need to fix the issues before trying again.

You can also run the hooks manually on all files:

```bash
pre-commit run --all-files
```

Or on specific files:

```bash
pre-commit run --files path/to/file1.py path/to/file2.py
```

### Configured Hooks

The following hooks are configured in `.pre-commit-config.yaml`:

1. **pre-commit-hooks**: Basic file checks (trailing whitespace, end of file, etc.)
2. **ruff**: Python linting and formatting
3. **black**: Python code formatting
4. **mypy**: Static type checking

## Conclusion

Using Ruff and Black helps maintain consistent code style and quality across the project. All contributors should run linting and formatting checks before submitting changes. The combination of Ruff for linting and Black for formatting ensures that code is both functionally correct and visually consistent.

Pre-commit hooks automate this process by running checks before each commit, ensuring that code quality standards are maintained throughout the development process.
