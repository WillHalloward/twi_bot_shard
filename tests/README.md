# Test Scripts for Twi Bot Shard

This directory contains test scripts for verifying different aspects of the Twi Bot Shard project.

## Available Tests

### 1. `test_dependencies.py`

Tests that all required Python dependencies can be imported correctly.

**Usage:**
```bash
python tests\test_dependencies.py
```

### 2. `test_db_connection.py`

Tests the database connection to ensure the bot can connect to the database.

**Usage:**
```bash
python tests\test_db_connection.py
```

### 3. `test_sqlalchemy_models.py`

Tests the SQLAlchemy models to ensure they work correctly.

**Usage:**
```bash
python tests\test_sqlalchemy_models.py
```

### 4. `test_cogs.py`

Tests loading all cogs to ensure they can be loaded without errors. This is particularly useful after making updates to verify that all changes work correctly.

**Usage:**
```bash
python tests\test_cogs.py
```

**What it does:**
- Attempts to load all cogs defined in both main.py and owner.py
- Reports which cogs loaded successfully and which failed
- Provides detailed error messages for failed cogs
- Sets exit code to 0 if all cogs load successfully, 1 otherwise (useful for CI/CD)

**Example output:**
```
[2023-05-01 12:34:56] [INFO] test_cogs: Testing cog loading...
[2023-05-01 12:34:56] [INFO] test_cogs: Attempting to load cogs.gallery...
[2023-05-01 12:34:56] [INFO] test_cogs: ✅ Successfully loaded cogs.gallery
[2023-05-01 12:34:56] [INFO] test_cogs: Attempting to load cogs.links_tags...
[2023-05-01 12:34:56] [INFO] test_cogs: ✅ Successfully loaded cogs.links_tags
...
[2023-05-01 12:34:57] [INFO] test_cogs: 
Summary: 13/13 cogs loaded successfully
[2023-05-01 12:34:57] [INFO] test_cogs: 
Test passed: All cogs loaded successfully!
```

## Running All Tests

To run all tests in sequence, you can use the following command:

```bash
python -m tests.test_dependencies && python -m tests.test_db_connection && python -m tests.test_sqlalchemy_models && python -m tests.test_cogs
```

This will run each test in sequence and stop if any test fails.