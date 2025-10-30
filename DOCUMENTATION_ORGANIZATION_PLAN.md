# Documentation & Folder Organization Plan
## Twi Bot Shard (Cognita)

**Date:** 2025-10-27
**Status:** Proposed
**Scope:** Comprehensive reorganization of documentation and project structure

---

## Executive Summary

This plan addresses significant issues with documentation redundancy, folder organization, and maintainability. The project currently has **~7,900 lines of documentation across 28 files** with substantial overlap, outdated information, and poor organization. The root directory is cluttered with utility scripts and temporary files.

**Key Goals:**
1. Reduce documentation redundancy by ~40%
2. Create clear separation between user and developer docs
3. Organize utility scripts and tools into dedicated directories
4. Consolidate overlapping content
5. Archive or remove outdated/stale documentation

---

## Part 1: Documentation Reorganization

### 1.1 Critical Issues Identified

#### Redundancy & Overlap (High Priority)
- **Setup/Installation:** Content duplicated across 4 files:
  - `docs/SETUP.md` (273 lines)
  - `docs/developer_onboarding.md` (483 lines)
  - `docs/deployment_guide.md` (362 lines)
  - `.junie/guidelines.md` (208 lines)

- **Architecture:** Content duplicated across 2 files:
  - `docs/PROJECT_STRUCTURE.md` (201 lines)
  - `docs/architecture.md` (296 lines)

- **Project Management:** Multiple stale planning docs:
  - `docs/plan.md` (460 lines)
  - `docs/tasks.md` (189 lines)
  - `doc-review.md` (236 lines) - should be in docs/

#### Outdated Information (High Priority)
Per `doc-review.md` findings:
- Python version conflicts across docs
- Command documentation shows prefix commands (`!command`) but code uses slash commands (`/command`)
- Missing environment variables in setup guides
- References to non-existent files (innktober.py)
- Gallery/mementos command docs don't match implementation

#### Poor Organization (Medium Priority)
- No clear hierarchy beyond `DOCUMENTATION_SUMMARY.md`
- No separation of audience (users vs developers)
- Database docs isolated in `utils/DATABASE.md`
- Root-level documentation files mixed with code

### 1.2 Proposed Documentation Structure

```
docs/
├── README.md                          # Overview and navigation hub
├── INDEX.md                           # Complete documentation index
│
├── user/                              # USER-FACING DOCUMENTATION
│   ├── README.md                      # User docs overview
│   ├── getting-started.md             # Quick start for users
│   ├── commands/                      # Command reference
│   │   ├── README.md                  # Commands overview
│   │   ├── moderation.md              # Moderation commands
│   │   ├── utility.md                 # Utility commands
│   │   ├── twi-specific.md            # TWI-specific commands
│   │   ├── gallery.md                 # Gallery/repost commands
│   │   └── stats.md                   # Statistics commands
│   ├── features.md                    # Feature descriptions
│   └── troubleshooting.md             # User troubleshooting
│
├── developer/                         # DEVELOPER DOCUMENTATION
│   ├── README.md                      # Dev docs overview
│   ├── getting-started.md             # Quick dev setup (consolidated)
│   ├── setup/                         # Setup guides
│   │   ├── local-development.md       # Local setup (from guidelines.md)
│   │   ├── database-setup.md          # Database configuration
│   │   └── environment-variables.md   # Complete env var reference
│   ├── architecture/                  # Architecture docs
│   │   ├── overview.md                # High-level architecture (merged)
│   │   ├── cog-system.md              # Cog architecture
│   │   ├── database-layer.md          # Database architecture (from DATABASE.md)
│   │   ├── dependency-injection.md    # DI patterns (from existing)
│   │   └── error-handling.md          # Error handling (from ERROR_HANDLING.md)
│   ├── guides/                        # How-to guides
│   │   ├── creating-cogs.md           # Cog creation guide
│   │   ├── adding-commands.md         # Command creation
│   │   ├── database-operations.md     # Working with DB
│   │   ├── testing.md                 # Testing guide
│   │   └── debugging.md               # Debugging tips
│   ├── reference/                     # Reference documentation
│   │   ├── api.md                     # API reference (from api_documentation.md)
│   │   ├── cogs.md                    # Cog reference (from cog_documentation.md)
│   │   ├── database-schema.md         # Schema reference
│   │   └── configuration.md           # Config reference
│   └── advanced/                      # Advanced topics
│       ├── performance.md             # Performance optimization
│       ├── caching.md                 # Caching strategy
│       ├── monitoring.md              # Monitoring & alerting
│       ├── security.md                # Security best practices
│       └── property-based-testing.md  # Advanced testing
│
├── operations/                        # OPERATIONS DOCUMENTATION
│   ├── README.md                      # Ops docs overview
│   ├── deployment/                    # Deployment guides
│   │   ├── local.md                   # Local deployment
│   │   ├── production.md              # Production deployment
│   │   └── docker.md                  # Docker deployment
│   ├── database/                      # Database operations
│   │   ├── migrations.md              # Migration guide
│   │   ├── optimizations.md           # DB optimizations
│   │   ├── backup-recovery.md         # Backup procedures
│   │   └── best-practices.md          # DB best practices
│   ├── monitoring.md                  # Monitoring setup
│   └── maintenance.md                 # Maintenance procedures
│
├── meta/                              # META DOCUMENTATION
│   ├── contributing.md                # From root CONTRIBUTING.md
│   ├── documentation-guide.md         # How to write/maintain docs
│   ├── changelog.md                   # Change history
│   └── archived/                      # Archived content
│       ├── old-commands.md            # Deprecated command reference
│       ├── archived-code.md           # From docs/archived_code.md
│       └── migration-notes.md         # Historical migration info
│
└── project/                           # PROJECT MANAGEMENT (optional)
    ├── roadmap.md                     # Future plans
    └── completed/                     # Completed plans
        ├── plan-2024.md               # From docs/plan.md
        └── tasks-2024.md              # From docs/tasks.md
```

### 1.3 File Actions

#### MERGE & CONSOLIDATE

1. **Setup Documentation → `developer/getting-started.md` + `developer/setup/`**
   - Merge: `docs/SETUP.md` + `.junie/guidelines.md` + parts of `developer_onboarding.md`
   - Result: Single comprehensive setup guide with clear sections
   - Keep: Environment-specific details in dedicated files

2. **Architecture → `developer/architecture/overview.md`**
   - Merge: `docs/PROJECT_STRUCTURE.md` + `docs/architecture.md`
   - Result: Single comprehensive architecture document
   - Extract: Specific subsystems into dedicated files

3. **Database Documentation → `developer/architecture/database-layer.md` + `operations/database/`**
   - Move: `utils/DATABASE.md` → `developer/architecture/database-layer.md`
   - Split: Operational content to `operations/database/`
   - Result: Clear separation of architecture vs operations

4. **Deployment → `operations/deployment/`**
   - Consolidate: `deployment_guide.md` → Split into `local.md`, `production.md`, `docker.md`
   - Remove: Duplicate setup content (reference developer docs instead)

5. **Commands → `docs/user/commands/`**
   - Split: `FEATURES.md` → Multiple command category files
   - Update: All commands to reflect slash command syntax
   - Add: Permission requirements and usage examples

#### MOVE

1. **Root Level → Appropriate Locations**
   - `CONTRIBUTING.md` → `docs/meta/contributing.md`
   - `doc-review.md` → `docs/meta/archived/doc-review-2024-10.md`

2. **Legacy → Archive**
   - `docs/plan.md` → `docs/project/completed/plan-2024.md`
   - `docs/tasks.md` → `docs/project/completed/tasks-2024.md`
   - `docs/archived_code.md` → `docs/meta/archived/archived-code.md`

3. **Remove .junie Directory**
   - Content already consolidated into main docs
   - Archive: `.junie/guidelines.md` content merged into developer docs
   - Delete: `.junie/` directory after consolidation

#### DELETE / ARCHIVE

**Consider Deleting:**
- `docs/documentation_maintenance.md` - Outdated meta-doc, replace with new documentation-guide.md
- `docs/ci.md` - If not using CI/CD, remove; if using, update and move to operations/
- `docs/log_aggregation.md` - Seems incomplete/unused
- Duplicate content after consolidation

**Archive (Move to `docs/meta/archived/`):**
- `doc-review.md` (root) → Historical record of documentation issues
- Stale project management docs (plan.md, tasks.md)

#### UPDATE & ENHANCE

**High Priority Updates:**
1. **Create New Index Files:**
   - `docs/README.md` - Main documentation hub
   - `docs/INDEX.md` - Complete searchable index
   - Category README.md files for navigation

2. **Update Command Documentation:**
   - Convert all prefix commands to slash commands
   - Add actual command syntax from codebase
   - Include permission requirements
   - Add usage examples

3. **Environment Variables:**
   - Create comprehensive `developer/setup/environment-variables.md`
   - Document all variables from config.py
   - Include optional vs required
   - Provide examples

4. **Quick References:**
   - `developer/quick-reference.md` - Common patterns and code snippets
   - `CLAUDE.md` - Keep and enhance (already good!)

---

## Part 2: Folder Structure Reorganization

### 2.1 Current Issues

1. **Root Directory Clutter:** 14+ utility/script files in root
2. **No Organization:** Scripts mixed with configs and docs
3. **Database Files:** SQL files in separate `database/` directory
4. **Schema Files:** FAISS schema files scattered in root
5. **No Scripts Directory:** No dedicated location for utilities

### 2.2 Proposed Folder Structure

```
twi_bot_shard/
├── .github/                    # GitHub workflows & configs
├── .claude/                    # Claude Code configuration
├── cogs/                       # Bot cogs (no change)
├── config/                     # Configuration (no change)
├── database/                   # Database files (reorganized)
│   ├── schema/                 # Schema definitions
│   │   ├── tables.sql          # Renamed from cognita_db_tables.sql
│   │   ├── indexes.sql         # Extracted indexes
│   │   └── views.sql           # Materialized views
│   ├── migrations/             # Alembic migrations (if using)
│   ├── optimizations/          # Performance SQL
│   │   ├── base.sql            # Renamed from db_optimizations.sql
│   │   └── additional.sql      # Renamed from additional_optimizations.sql
│   └── utilities/              # Database utility SQL
│       ├── error-telemetry.sql
│       └── gallery-migration.sql
├── docs/                       # Documentation (see Part 1)
├── models/                     # SQLAlchemy models (no change)
├── scripts/                    # Utility scripts (NEW)
│   ├── database/               # DB utility scripts
│   │   ├── apply_optimizations.py    # From run_db_optimizations.py
│   │   └── apply_additional.py       # From run_additional_optimizations.py
│   ├── schema/                 # Schema utility scripts
│   │   ├── build_faiss_index.py      # From root
│   │   └── query_faiss_schema.py     # From root
│   ├── development/            # Dev utility scripts
│   │   ├── setup_hooks.py           # From root
│   │   ├── format.py                # From root
│   │   └── lint.py                  # From root
│   └── README.md               # Scripts documentation
├── tests/                      # Tests (minimal changes)
│   ├── unit/                   # Unit tests (organize by type)
│   ├── integration/            # Integration tests
│   ├── fixtures/               # Test fixtures
│   └── README.md               # Testing guide
├── utils/                      # Utilities (no major change)
│   └── (remove DATABASE.md, moved to docs/)
├── .cache/                     # Cache directory (NEW, gitignored)
│   └── faiss/                  # FAISS index files
│       ├── schema_index.faiss        # From root
│       ├── schema_lookup.json        # From root
│       └── schema_descriptions.txt   # From root
├── CLAUDE.md                   # AI assistant guide (keep, enhance)
├── README.md                   # Project overview (simplify, link to docs/)
├── pyproject.toml              # Python project config (no change)
├── requirements.txt            # Requirements (consider removing if using pyproject.toml)
└── ... (other config files)
```

### 2.3 File Actions

#### CREATE NEW DIRECTORIES

```bash
mkdir -p scripts/{database,schema,development}
mkdir -p database/{schema,migrations,optimizations,utilities}
mkdir -p .cache/faiss
mkdir -p tests/{unit,integration,fixtures}
mkdir -p docs/{user,developer,operations,meta,project}
mkdir -p docs/user/commands
mkdir -p docs/developer/{setup,architecture,guides,reference,advanced}
mkdir -p docs/operations/{deployment,database}
mkdir -p docs/meta/archived
```

#### MOVE FILES

**Scripts (Root → scripts/):**
```bash
# Database scripts
mv run_db_optimizations.py scripts/database/apply_optimizations.py
mv run_additional_optimizations.py scripts/database/apply_additional.py

# Schema scripts
mv build_faiss_index.py scripts/schema/
mv query_faiss_schema.py scripts/schema/

# Development scripts
mv setup_hooks.py scripts/development/
mv format.py scripts/development/
mv lint.py scripts/development/
```

**Database Files (database/ reorganization):**
```bash
# Schema files
mv database/cognita_db_tables.sql database/schema/tables.sql

# Optimizations
mv database/db_optimizations.sql database/optimizations/base.sql
mv database/additional_optimizations.sql database/optimizations/additional.sql

# Utilities
mv database/error_telemetry.sql database/utilities/
mv database/gallery_migration_table.sql database/utilities/gallery-migration.sql
```

**Cache Files (Root → .cache/):**
```bash
mv schema_index.faiss .cache/faiss/
mv schema_lookup.json .cache/faiss/
mv schema_descriptions.txt .cache/faiss/
```

**Documentation (Root → docs/):**
```bash
mv CONTRIBUTING.md docs/meta/contributing.md
```

#### UPDATE REFERENCES

After moving files, update imports and references:

1. **Update script imports:**
   - Fix imports in moved Python scripts
   - Update any shell scripts or documentation that reference old paths

2. **Update pyproject.toml:**
   - If using entry points for scripts, update paths
   - Update any build scripts

3. **Update README.md:**
   - Update file structure diagram
   - Update references to moved files
   - Simplify overview, link to docs/ for details

4. **Update .gitignore:**
   - Add `.cache/` directory
   - Verify all temporary files are ignored

5. **Update CLAUDE.md:**
   - Update critical file paths
   - Update command examples with new script locations

---

## Part 3: Implementation Plan

### Phase 1: Preparation (Est. 2-3 hours)

**Goals:** Backup, document current state, create structure

1. **Create Backup**
   ```bash
   # Create timestamped backup
   tar -czf ../twi_bot_shard_backup_$(date +%Y%m%d_%H%M%S).tar.gz .
   ```

2. **Document Current State**
   - Take inventory of all doc file sizes and content
   - List all root-level files and their purposes
   - Map dependencies between documentation files

3. **Create Directory Structure**
   - Run all `mkdir -p` commands from section 2.3
   - Create placeholder README.md files in new directories
   - Test directory structure is correct

### Phase 2: Documentation Consolidation (Est. 6-8 hours)

**Priority Order:**

1. **High Priority - Setup/Getting Started** (2 hours)
   - Merge SETUP.md + guidelines.md + parts of developer_onboarding.md
   - Create `developer/getting-started.md`
   - Create `developer/setup/*.md` files
   - Update references

2. **High Priority - Commands** (2 hours)
   - Audit actual commands from codebase
   - Split FEATURES.md into command category files
   - Update all command syntax to slash commands
   - Add permission requirements

3. **High Priority - Architecture** (2 hours)
   - Merge PROJECT_STRUCTURE.md + architecture.md
   - Create `developer/architecture/overview.md`
   - Move DATABASE.md → `developer/architecture/database-layer.md`
   - Create architecture subsystem docs

4. **Medium Priority - User Documentation** (1 hour)
   - Create user documentation structure
   - Write user-facing README.md files
   - Create troubleshooting guide

5. **Medium Priority - Operations** (1 hour)
   - Consolidate deployment_guide.md
   - Organize operations documentation
   - Create operations README.md

### Phase 3: File Reorganization (Est. 2-3 hours)

**Priority Order:**

1. **Move Scripts** (30 min)
   - Execute all move commands from section 2.3
   - Test scripts still run from new locations
   - Update any hardcoded paths in scripts

2. **Reorganize Database Files** (30 min)
   - Move and rename SQL files
   - Update any scripts that reference SQL files
   - Test database operations still work

3. **Move Cache Files** (15 min)
   - Move FAISS files to .cache/
   - Update scripts that generate/use these files
   - Update .gitignore

4. **Update Documentation** (1 hour)
   - Move CONTRIBUTING.md
   - Archive old planning docs
   - Remove .junie directory after consolidation

5. **Update References** (30 min)
   - Update all file paths in documentation
   - Update import statements in moved scripts
   - Update README.md and CLAUDE.md

### Phase 4: Create New Documentation (Est. 4-5 hours)

1. **Create Index and Navigation** (1 hour)
   - Write `docs/README.md` as main hub
   - Write `docs/INDEX.md` with complete doc list
   - Create category README.md files

2. **Write Missing Documentation** (2 hours)
   - `developer/setup/environment-variables.md` - comprehensive env var guide
   - `developer/guides/creating-cogs.md` - cog creation guide
   - `docs/user/getting-started.md` - user quick start

3. **Update CLAUDE.md** (1 hour)
   - Update file paths
   - Add new documentation structure references
   - Enhance with additional patterns

4. **Create Quick References** (1 hour)
   - `developer/quick-reference.md` - common patterns
   - Update command references
   - Create troubleshooting quick reference

### Phase 5: Cleanup & Validation (Est. 2-3 hours)

1. **Remove Redundant Files** (30 min)
   - Delete merged documentation files
   - Remove .junie directory
   - Clean up root directory

2. **Validate All Links** (1 hour)
   - Check all documentation cross-references
   - Verify all internal links work
   - Fix broken links

3. **Test Updated Structure** (1 hour)
   - Run all scripts from new locations
   - Verify bot still starts correctly
   - Test documentation is accessible

4. **Update CI/CD** (30 min)
   - Update any CI/CD paths if applicable
   - Update deployment scripts
   - Test automated processes

### Phase 6: Review & Finalization (Est. 1-2 hours)

1. **Documentation Review**
   - Read through main documentation files
   - Check for consistency in tone and style
   - Verify completeness

2. **Update DOCUMENTATION_SUMMARY.md**
   - Replace with new structure overview
   - Document navigation patterns
   - Add maintenance guidelines

3. **Create Migration Guide**
   - Document what changed
   - Provide path mapping (old → new)
   - List any breaking changes

4. **Final Commit**
   - Commit all changes with detailed message
   - Tag as documentation reorg
   - Update changelog if exists

---

## Part 4: Benefits & Expected Outcomes

### Immediate Benefits

1. **Reduced Redundancy:** ~40% reduction in duplicate content
2. **Improved Navigation:** Clear hierarchy and categorization
3. **Better Discoverability:** Index and README files guide users
4. **Cleaner Root Directory:** Scripts organized, clutter removed
5. **Easier Maintenance:** Single source of truth for each topic

### Long-term Benefits

1. **Onboarding:** New developers can find information faster
2. **Scalability:** Structure supports growth and new features
3. **Documentation Quality:** Easier to keep docs current
4. **User Experience:** Users can find command help quickly
5. **AI-Assisted Development:** Better organization for LLM context

### Metrics for Success

- Documentation size reduced from ~7,900 to ~5,500 lines
- Root directory files reduced from 41 to ~25
- Setup time for new developers reduced by 30-50%
- Command reference accuracy at 100% (currently ~60%)
- User documentation completeness increased from ~40% to ~90%

---

## Part 5: Maintenance Guidelines

### Ongoing Documentation Maintenance

1. **When Adding Features:**
   - Update relevant command documentation in `docs/user/commands/`
   - Add architecture notes to appropriate `docs/developer/architecture/` file
   - Update examples in guides

2. **When Changing Commands:**
   - Update command reference immediately
   - Update examples in guides
   - Add migration note if breaking change

3. **Documentation Reviews:**
   - Quarterly review for outdated information
   - Update after major releases
   - Verify examples still work

4. **File Organization Rules:**
   - New scripts go in `scripts/` subdirectories
   - Cache/generated files go in `.cache/`
   - No documentation in root except README and CLAUDE.md
   - Keep root directory clean

### Documentation Standards

1. **File Naming:**
   - Use kebab-case: `database-operations.md`
   - Be descriptive: `local-development.md` not `dev.md`
   - Use consistent suffixes: `-guide.md`, `-reference.md`

2. **Content Structure:**
   - Start with overview/introduction
   - Use clear hierarchical headings
   - Include table of contents for long docs
   - Add code examples with explanations
   - Include troubleshooting sections

3. **Cross-References:**
   - Use relative links within docs/
   - Keep README files updated with links
   - Maintain INDEX.md with all docs

---

## Part 6: Risk Assessment & Mitigation

### Risks

1. **Breaking References:** Moving files breaks existing links
   - **Mitigation:** Comprehensive search and replace, validation script

2. **Lost Information:** Important content accidentally deleted
   - **Mitigation:** Complete backup, careful merge review

3. **Time Overrun:** Reorganization takes longer than estimated
   - **Mitigation:** Phased approach, can pause between phases

4. **Confusion:** Users/developers can't find migrated docs
   - **Mitigation:** Create migration guide, update all READMEs

5. **Script Breakage:** Moved scripts don't work
   - **Mitigation:** Test after each move, update paths systematically

### Rollback Plan

If issues arise:

1. **Before Phase 3:** Can abandon and restore from backup
2. **During Phase 3-4:** Can pause and fix issues before continuing
3. **After Phase 5:** Restore from backup, identify specific issues, re-apply changes carefully

Backup location: `../twi_bot_shard_backup_[timestamp].tar.gz`

---

## Part 7: Decision Points

### Questions to Answer Before Starting

1. **Project Management Docs:** Keep or archive?
   - **Recommendation:** Archive to `docs/project/completed/`

2. **CI/CD Documentation:** Update or remove?
   - **Decision needed:** Check if CI/CD is actively used

3. **Requirements.txt:** Keep or rely only on pyproject.toml?
   - **Recommendation:** Keep for backward compatibility, note deprecation

4. **Tests Directory:** Reorganize or leave as-is?
   - **Recommendation:** Light reorganization (unit/integration split)

5. **.junie Directory:** Delete or keep?
   - **Recommendation:** Delete after consolidation, purpose unclear

### Optional Enhancements

Consider for future phases:

1. **Documentation Website:** Convert markdown to static site (MkDocs, Docusaurus)
2. **API Documentation:** Auto-generate from docstrings (Sphinx)
3. **Changelog:** Maintain CHANGELOG.md with releases
4. **Diagram Generation:** Create architecture diagrams (Mermaid, PlantUML)
5. **Documentation Tests:** Add automated doc validation

---

## Conclusion

This reorganization will significantly improve the maintainability and usability of the Twi Bot Shard documentation and codebase. The phased approach allows for careful implementation and validation at each step.

**Total Estimated Time:** 17-24 hours
**Recommended Approach:** Execute over 3-5 sessions
**Critical Success Factor:** Thorough testing and validation between phases

**Next Steps:**
1. Review and approve this plan
2. Create backup
3. Begin Phase 1 (Preparation)
4. Proceed through phases systematically
5. Document any deviations from plan

---

**Plan Author:** Claude Code
**Plan Version:** 1.0
**Last Updated:** 2025-10-27
