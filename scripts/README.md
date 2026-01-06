# Utility Scripts

This directory contains utility scripts for database operations, schema management, and development tools.

## Directory Structure

```
scripts/
├── database/           # Database utility scripts
├── schema/             # Schema indexing and query scripts
└── development/        # Development tools
```

## Database Scripts (`database/`)

### apply_optimizations.py

Applies the base database optimizations defined in `database/optimizations/base.sql`.

**Usage:**
```bash
python scripts/database/apply_optimizations.py
```

**What it does:**
- Creates database indexes for improved query performance
- Applies table-level optimizations
- Sets up performance monitoring

**When to run:**
- After initial database schema setup
- After major schema changes
- When performance degrades

### apply_additional.py

Applies additional database optimizations including materialized views and cache statistics.

**Usage:**
```bash
python scripts/database/apply_additional.py
```

**What it does:**
- Creates and refreshes materialized views
- Applies advanced optimizations
- Generates cache statistics

**When to run:**
- After base optimizations
- Before production deployment
- Periodically for maintenance

## Schema Scripts (`schema/`)

### build_faiss_index.py

Builds a FAISS vector index for semantic search over the database schema.

**Usage:**
```bash
python scripts/schema/build_faiss_index.py
```

**Requirements:**
- `OPENAI_API_KEY` environment variable
- `faiss-cpu` or `faiss-gpu` package
- Schema descriptions in `.cache/faiss/schema_descriptions.txt`

**What it does:**
- Reads schema descriptions from text file
- Generates embeddings using OpenAI's embedding model
- Creates FAISS index for fast similarity search
- Saves index and lookup table to `.cache/faiss/`

**Output files:**
- `.cache/faiss/schema_index.faiss` - FAISS vector index
- `.cache/faiss/schema_lookup.json` - Schema chunk lookup table

### query_faiss_schema.py

Interactive tool for querying the database schema using natural language.

**Usage:**
```bash
python scripts/schema/query_faiss_schema.py
```

**Requirements:**
- `OPENAI_API_KEY` environment variable
- Existing FAISS index (run `build_faiss_index.py` first)

**What it does:**
- Takes a natural language question about the database
- Searches the schema index for relevant tables
- Generates a SQL query using GPT-4
- Displays the generated SQL

**Example:**
```
🔍 Ask your database: How many messages were sent today?
🔗 Searching schema...
🧠 Generating prompt...
🤖 Generating SQL...

✅ Generated SQL:
SELECT COUNT(*) FROM messages
WHERE DATE(created_at) = CURRENT_DATE;
```

## Development Scripts (`development/`)

### format.py

Formats Python code using Black and Ruff.

**Usage:**
```bash
python scripts/development/format.py
```

**What it does:**
- Runs Black formatter on all Python files
- Applies Ruff auto-fixes
- Ensures consistent code style

**Configuration:**
- Black: Line length 88, configured in `pyproject.toml`
- Ruff: Rules configured in `pyproject.toml`

### lint.py

Lints Python code using Ruff.

**Usage:**
```bash
python scripts/development/lint.py
```

**What it does:**
- Checks code for style violations
- Identifies potential bugs
- Enforces best practices

**Configuration:**
- Rules defined in `pyproject.toml`
- Can be customized per project needs

### setup_hooks.py

Sets up git pre-commit hooks for automatic code quality checks.

**Usage:**
```bash
python scripts/development/setup_hooks.py
```

**What it does:**
- Installs pre-commit hook script
- Configures hook to run formatting and linting
- Prevents commits with style violations

**Hooks installed:**
- Pre-commit: Runs `format.py` and `lint.py`
- Checks are automatic before each commit

## Running Scripts from Root

All scripts should be run from the project root directory:

```bash
# From project root
python scripts/database/apply_optimizations.py
python scripts/schema/build_faiss_index.py
python scripts/development/format.py
```

## Path Configuration

Scripts reference the following paths:

**Database scripts:**
- `database/optimizations/base.sql`
- `database/optimizations/additional.sql`
- `ssl-cert/` - SSL certificates

**Schema scripts:**
- `.cache/faiss/schema_descriptions.txt`
- `.cache/faiss/schema_index.faiss`
- `.cache/faiss/schema_lookup.json`

**Development scripts:**
- Operate on all Python files in project

## Dependencies

Most scripts require project dependencies to be installed:

```bash
uv pip install -e .
```

Additional requirements for schema scripts:
- `openai` - OpenAI API client
- `faiss-cpu` or `faiss-gpu` - Vector similarity search
- `numpy` - Numerical operations

## Troubleshooting

### Database Scripts

**Error:** `Database connection error`
- Verify `.env` file has correct database credentials
- Check PostgreSQL is running
- Verify SSL certificates are in `ssl-cert/`

**Error:** `Failed to apply database optimizations`
- Check SQL syntax in optimization files
- Verify you have database permissions
- Check for conflicting indexes/constraints

### Schema Scripts

**Error:** `No module named 'faiss'`
```bash
pip install faiss-cpu  # or faiss-gpu for GPU support
```

**Error:** `OPENAI_API_KEY not set`
- Add `OPENAI_API_KEY=...` to `.env` file
- Restart script after setting

**Error:** `File not found: schema_descriptions.txt`
- Ensure `.cache/faiss/schema_descriptions.txt` exists
- Create schema descriptions file if missing

### Development Scripts

**Error:** `No module named 'black'` or `'ruff'`
```bash
uv pip install black ruff
```

**Error:** `Permission denied` (setup_hooks.py)
```bash
chmod +x .git/hooks/pre-commit
```

## Contributing

When adding new scripts:

1. Place in appropriate subdirectory
2. Add documentation to this README
3. Include usage examples
4. Handle errors gracefully
5. Use logging for output
6. Make scripts idempotent when possible

## Related Documentation

- [Developer Guide](../docs/developer/getting-started.md)
- [Database Documentation](../docs/developer/database.md)
