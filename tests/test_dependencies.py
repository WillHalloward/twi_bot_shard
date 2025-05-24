import sys
import importlib

def test_import(module_name):
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name} successfully imported")
        return True
    except ImportError as e:
        print(f"❌ Failed to import {module_name}: {e}")
        return False

def main():
    dependencies = [
        "aiohttp",
        "discord",
        "PIL",  # pillow
        "googleapiclient",  # google-api-python-client
        "lxml",
        "AO3",  # ao3-api
        "openpyxl",
        "asyncpg",
        "openai",
        "setuptools",
        "gallery_dl",
        "sqlalchemy",  # Added missing dependency
    ]

    success = True
    print(f"Python version: {sys.version}")
    print("Testing imports for all dependencies:")

    for dep in dependencies:
        if not test_import(dep):
            success = False

    if success:
        print("\nAll dependencies successfully imported! The uv setup is working correctly.")
    else:
        print("\nSome dependencies failed to import. Please check the errors above.")

if __name__ == "__main__":
    main()
