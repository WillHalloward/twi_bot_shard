# Utility Scripts

This directory contains utility scripts for database operations, schema indexing, and maintenance.

## Directory Structure

```
scripts/
├── database/           # Database optimization and migration scripts
├── schema/             # FAISS schema-embedding and natural-language query tools
└── maintenance/        # One-off maintenance scripts
```

> **Note:** There is no `scripts/development/` directory. Linting, formatting, and
> pre-commit setup are run directly with `ruff`, `mypy`, and `pre-commit` — see the
> [Linting guide](../docs/developer/linting.md).

## Database Scripts (`database/`)

### optimize.py

Applies the database performance optimizations defined in `database/optimizations/base.sql` and `database/optimizations/additional.sql` (indexes, materialized views, functions), and refreshes materialized views.

**Usage:**
```bash
# Apply everything (base + additional)
python scripts/database/optimize.py

# Apply only base optimizations
python scripts/database/optimize.py --base

# Apply only additional optimizations (and refresh materialized views)
python scripts/database/optimize.py --additional
```

**When to run:**
- After initial database schema setup
- After major schema changes
- When query performance degrades

### apply_migrations.py

Applies pending SQL schema migrations from `database/schema/migrations/*.sql`, tracked in a `schema_migrations` table. Designed to run as a Railway pre-deploy step so code and database schema stay in sync.

**Usage:**
```bash
python scripts/database/apply_migrations.py
```

**What it does:**
- Ensures a `schema_migrations` tracking table exists
- Applies each not-yet-recorded migration (in filename order) inside a transaction, then records it
- Migrations listed in the script's `MANUAL_MIGRATIONS` set are recorded as applied **without** being executed (for heavy/locking migrations that must be run by hand in a maintenance window)

Migrations must be idempotent (`IF NOT EXISTS` / guarded `DO` blocks) and single-transaction safe. Statements that can't run in a transaction (e.g. `CREATE INDEX CONCURRENTLY`) must be added to `MANUAL_MIGRATIONS`.

## Schema Scripts (`schema/`)

These tools build and query a FAISS vector index over the database schema for the owner-only `ask_db` natural-language SQL feature.

### populate_schema_embeddings.py

Generates embeddings for the database schema and stores them (used to seed the search corpus).

**Usage:**
```bash
python scripts/schema/populate_schema_embeddings.py
```

### build_faiss_index.py

Builds a FAISS vector index for semantic search over the database schema.

**Usage:**
```bash
python scripts/schema/build_faiss_index.py
```

**Requirements:**
- `OPENAI_API_KEY` environment variable
- `faiss-cpu` package (install via the `[ml]` extra: `uv pip install -e ".[ml]"`)

### query_faiss_schema.py

Interactive tool for querying the database schema using natural language. Searches the schema index for relevant tables and generates a SQL query.

**Usage:**
```bash
python scripts/schema/query_faiss_schema.py
```

**Requirements:**
- `OPENAI_API_KEY` environment variable
- An existing FAISS index (run `build_faiss_index.py` first)

## Maintenance Scripts (`maintenance/`)

### nuke_user_messages.py

One-off script to bulk-delete a user's stored messages from the database. Destructive — review before running.

**Usage:**
```bash
python scripts/maintenance/nuke_user_messages.py
```

## Running Scripts from Root

All scripts should be run from the project root directory so relative paths
(`database/optimizations/`, `ssl-cert/`, etc.) and the `.env` file resolve correctly:

```bash
python scripts/database/optimize.py
python scripts/database/apply_migrations.py
python scripts/schema/build_faiss_index.py
```

## Dependencies

Most scripts require project dependencies to be installed:

```bash
uv pip install -e .
```

The schema (FAISS) scripts additionally need the ML extra:

```bash
uv pip install -e ".[ml]"
```

## Troubleshooting

### Database Scripts

**Error:** `Database connection error`
- Verify `.env` has correct database credentials
- Check PostgreSQL is running
- For local SSL, verify certificates are in `ssl-cert/`

### Schema Scripts

**Error:** `No module named 'faiss'`
```bash
uv pip install -e ".[ml]"
```

**Error:** `OPENAI_API_KEY not set`
- Add `OPENAI_API_KEY=...` to `.env`

## Contributing

When adding new scripts:

1. Place them in the appropriate subdirectory
2. Add documentation to this README
3. Include usage examples
4. Handle errors gracefully and use logging for output
5. Make scripts idempotent when possible

## Related Documentation

- [Developer Getting Started](../docs/developer/getting-started.md)
- [Database Guide](../docs/developer/database.md)
