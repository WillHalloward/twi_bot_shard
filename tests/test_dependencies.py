import importlib
import sys

import pytest


def check_import(module_name) -> bool | None:
    """Helper function to check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name} successfully imported")
        return True
    except ImportError as e:
        print(f"❌ Failed to import {module_name}: {e}")
        return False


@pytest.mark.parametrize(
    "module_name",
    [
        "aiohttp",
        "discord",
        "PIL",  # pillow
        "googleapiclient",  # google-api-python-client
        "AO3",  # ao3-api
        "asyncpg",
        "openai",
        "sqlalchemy",
        "gallery_dl",
    ],
)
def test_import(module_name) -> None:
    """Test that all required dependencies can be imported."""
    assert check_import(module_name), f"Failed to import {module_name}"


def main() -> None:
    dependencies = [
        "aiohttp",
        "discord",
        "PIL",  # pillow
        "googleapiclient",  # google-api-python-client
        "AO3",  # ao3-api
        "asyncpg",
        "openai",
        "sqlalchemy",
        "gallery_dl",
    ]

    success = True
    print(f"Python version: {sys.version}")
    print("Testing imports for all dependencies:")

    for dep in dependencies:
        if not test_import(dep):
            success = False

    if success:
        print(
            "\nAll dependencies successfully imported! The uv setup is working correctly."
        )
    else:
        print("\nSome dependencies failed to import. Please check the errors above.")


if __name__ == "__main__":
    main()
