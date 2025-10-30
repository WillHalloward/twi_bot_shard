# Test Coverage Improvement Roadmap
## Twi Bot Shard (Cognita)

**Current Status**: Grade A (95.5% pass rate, 147/154 passing)
**Target**: Grade A+ (98%+ pass rate, comprehensive cog coverage)
**Estimated Total Effort**: 40-50 hours

---

## Phase 1: High Priority Cog Tests (20-25 hours)

### 1.1 Owner Cog Tests - `test_owner_cog.py` (8-10 hours)

**File**: `tests/test_owner_cog.py` (NEW)
**Coverage Target**: `cogs/owner.py` (9 commands)

**Tasks**:
- ✅ Test `/admin load <extension>` - Load cog dynamically
- ✅ Test `/admin unload <extension>` - Unload cog
- ✅ Test `/admin reload <extension>` - Reload cog
- ✅ Test `/admin cmd <command>` - Execute shell commands
- ✅ Test `/admin sync` - Sync command tree
- ✅ Test `/admin exit` - Graceful bot shutdown
- ✅ Test `/admin resources` - Resource monitoring
- ✅ Test `/admin sql <query>` - Direct SQL execution
- ✅ Test `/admin ask_db <query>` - Natural language DB queries

**Test Scenarios**:
- ✅ Permission checks (owner-only)
- ✅ Error handling (invalid extension names, syntax errors)
- ✅ Success cases with proper mocking
- ✅ Edge cases (empty queries, special characters)

**Complexity**: High (requires mocking bot internals, cog loading, subprocess)

### 1.2 Gallery Cog Tests - Part 1: Repost Logic (6-8 hours)

**File**: `tests/test_gallery_cog_repost.py` (NEW)
**Coverage Target**: `cogs/gallery.py` (repost detection & menu)

**Tasks**:
- ✅ Test `repost_attachment()` - Repost detection algorithm
- ✅ Test repost cache management
- ✅ Test `RepostMenu` view and button interactions
- ✅ Test database lookups for similar posts
- ✅ Test image similarity checking (if implemented)
- ✅ Test creator link matching

**Test Scenarios**:
- ✅ Exact duplicates detected
- ✅ Similar posts detected
- ✅ No reposts found
- ✅ Cache hit vs cache miss
- ✅ Menu button interactions (keep/delete)

**Complexity**: Medium-High (requires mocking Discord attachments, file I/O)

### 1.3 Gallery Cog Tests - Part 2: Admin Commands (6-7 hours)

**File**: `tests/test_gallery_cog_admin.py` (NEW)
**Coverage Target**: `cogs/gallery.py` (6 admin commands)

**Tasks**:
- ✅ Test `/gallery_admin set_repost` - Configure repost settings
- ✅ Test `/gallery_admin extract_data` - Extract gallery data
- ✅ Test `/gallery_admin migration_stats` - Show migration progress
- ✅ Test `/gallery_admin review_entries` - Review pending entries
- ✅ Test `/gallery_admin update_tags` - Update entry tags
- ✅ Test `/gallery_admin mark_reviewed` - Mark entries as reviewed

**Test Scenarios**:
- ✅ Permission checks (admin-only)
- ✅ Database operations (create, read, update)
- ✅ Modal interactions
- ✅ Pagination for large datasets
- ✅ Error handling (invalid IDs, missing data)

**Complexity**: Medium (requires mocking modals, database operations)

---

## Phase 2: New Feature Tests (8-10 hours)

### 2.1 Command Groups Integration Tests (3-4 hours)

**File**: `tests/test_command_groups.py` (NEW)
**Coverage Target**: `utils/command_groups.py`, command registration

**Tasks**:
- ✅ Test command group registration in setup_hook
- ✅ Test `/admin` group commands are accessible
- ✅ Test `/mod` group commands are accessible
- ✅ Test `/gallery_admin` group commands are accessible
- ✅ Test command tree sync includes groups
- ✅ Test group permissions (default_permissions)
- ✅ Test group descriptions

**Test Scenarios**:
- ✅ All groups registered successfully
- ✅ Commands routed to correct groups
- ✅ Permissions enforced at group level
- ✅ Help text shows group structure

**Complexity**: Low-Medium (straightforward command testing)

### 2.2 AO3 Async Authentication Tests (5-6 hours)

**File**: `tests/test_ao3_auth.py` (NEW)
**Coverage Target**: `cogs/other.py` (`_initialize_ao3_session`, `ao3_status`)

**Tasks**:
- ✅ Test `_initialize_ao3_session()` - Successful auth
- ✅ Test retry logic (3 attempts with exponential backoff)
- ✅ Test auth failure handling
- ✅ Test executor pattern (non-blocking)
- ✅ Test session state tracking (`ao3_login_successful`, `ao3_login_in_progress`)
- ✅ Test `/admin ao3_status` command
- ✅ Test manual retry via command

**Test Scenarios**:
- ✅ Successful auth on first try
- ✅ Auth fails, retries succeed on attempt 2
- ✅ All retries fail, error logged
- ✅ Concurrent auth attempts handled
- ✅ Status command shows correct state

**Complexity**: Medium-High (requires mocking AO3 library, async executors)

---

## Phase 3: Medium Priority Cog Tests (10-12 hours)

### 3.1 Mods Cog Tests (4-5 hours)

**File**: `tests/test_mods_cog_unit.py` (NEW)
**Coverage Target**: `cogs/mods.py`

**Tasks**:
- ✅ Test `/mod reset` - Reset command cooldowns
- ✅ Test `/mod state` - Post moderator messages
- ✅ Test `log_attachment` listener
- ✅ Test `dm_watch` listener
- ✅ Test `find_links` listener
- ✅ Test `filter_new_users` listener

**Complexity**: Medium (webhook mocking, event listeners)

### 3.2 Settings Cog Tests (2-3 hours)

**File**: `tests/test_settings_cog.py` (NEW)
**Coverage Target**: `cogs/settings.py`

**Tasks**:
- ✅ Test settings retrieval
- ✅ Test settings updates
- ✅ Test permission checks
- ✅ Test is_admin utility function

**Complexity**: Low-Medium

### 3.3 Patreon Poll Cog Tests (2-3 hours)

**File**: `tests/test_patreon_poll_cog.py` (NEW)
**Coverage Target**: `cogs/patreon_poll.py`

**Tasks**:
- ✅ Test poll creation
- ✅ Test vote tracking
- ✅ Test Patreon API integration (mocked)

**Complexity**: Medium (external API mocking)

### 3.4 Button Roles & Threads Cog Tests (2 hours each)

**Files**: `tests/test_button_roles_cog.py`, `tests/test_threads_cog.py` (NEW)

**Tasks**:
- ✅ Test button role assignment
- ✅ Test thread creation and management

**Complexity**: Low

---

## Phase 4: Fix Flaky Tests (3-5 hours)

### 4.1 Config Import Timing Fix (2-3 hours)

**Files Modified**: `tests/conftest.py` (NEW), multiple test files

**Tasks**:
- ✅ Create pytest fixture for config mocking
- ✅ Apply fixture to permission tests
- ✅ Apply fixture to regression tests
- ✅ Test isolation between test runs

**Complexity**: Medium (requires pytest fixture knowledge)

### 4.2 Webhook Manager AsyncMock Fix (1 hour)

**File Modified**: `tests/test_integration.py`

**Tasks**:
- ✅ Fix `test_find_links` webhook mocking
- ✅ Add proper AsyncMock for context manager

**Complexity**: Low

### 4.3 Add Flaky Test Markers (1 hour)

**Files Modified**: Multiple test files

**Tasks**:
- ✅ Install `pytest-flaky`
- ✅ Mark remaining flaky tests with `@pytest.mark.flaky(reruns=3)`

**Complexity**: Low

---

## Phase 5: Edge Cases & Negative Testing (5-7 hours)

### 5.1 Gallery Negative Tests (2-3 hours)

**File**: `tests/test_gallery_cog_edge_cases.py` (NEW)

**Tasks**:
- ✅ Test invalid attachment formats
- ✅ Test missing creator data
- ✅ Test API rate limits
- ✅ Test database constraint violations
- ✅ Test permission denied scenarios

### 5.2 Mods Negative Tests (1-2 hours)

**File**: `tests/test_mods_cog_edge_cases.py` (NEW)

**Tasks**:
- ✅ Test invalid command names
- ✅ Test missing webhook configuration
- ✅ Test permission failures

### 5.3 Owner Admin Command Error Paths (2 hours)

**File**: `tests/test_owner_cog_errors.py` (NEW)

**Tasks**:
- ✅ Test SQL syntax errors
- ✅ Test invalid cog names
- ✅ Test sync failures
- ✅ Test resource monitoring errors

---

## Phase 6: Infrastructure & Optimization (3-5 hours)

### 6.1 View/Modal Persistence Tests (2-3 hours)

**File**: `tests/test_view_persistence.py` (NEW)

**Tasks**:
- ✅ Test button recovery after bot restart
- ✅ Test view state persistence
- ✅ Test timeout handling

### 6.2 Test Optimization (1-2 hours)

**Tasks**:
- ✅ Add `pytest-xdist` for parallel execution
- ✅ Configure `pytest-cov` for coverage reporting
- ✅ Set coverage targets (90%+)

---

## Implementation Priority

### Week 1-2: Critical Gaps (20-25 hours)
1. Owner cog tests ✅ (8-10h)
2. Gallery cog tests ✅ (12-15h)

### Week 3: New Features (8-10 hours)
3. Command groups tests ✅ (3-4h)
4. AO3 auth tests ✅ (5-6h)

### Week 4: Cleanup & Polish (12-15 hours)
5. Mods cog tests ✅ (4-5h)
6. Fix flaky tests ✅ (3-5h)
7. Settings/Patreon/Buttons/Threads tests ✅ (6-8h)

### Week 5: Excellence (5-7 hours)
8. Edge cases & negative testing ✅ (5-7h)

---

## Success Metrics

**Current State**:
- ✅ 95.5% pass rate (147/154)
- ✅ Grade A
- ⚠️ 33% cog coverage

**Target State**:
- 🎯 98%+ pass rate (165+/169)
- 🎯 Grade A+
- 🎯 80%+ cog coverage (12/15 cogs)
- 🎯 0 flaky tests
- 🎯 Comprehensive negative testing

**Coverage Targets**:
- Core cogs: 90%+ line coverage
- Utilities: 85%+ line coverage
- Overall: 80%+ line coverage

---

## Dependencies & Prerequisites

**Required**:
- pytest 8.3.0+
- pytest-asyncio 1.0.0+
- pytest-mock 3.14.0+
- hypothesis 6.135.26+

**New Additions**:
- `pytest-flaky` - For marking flaky tests
- `pytest-xdist` - For parallel test execution
- `pytest-cov` - For coverage reporting
- `coverage[toml]` - For coverage configuration

**Installation**:
```bash
uv pip install pytest-flaky pytest-xdist pytest-cov coverage[toml]
```

---

## Notes & Best Practices

1. **Test Naming**: Use descriptive names like `test_command_name_scenario_expected`
2. **Fixtures**: Reuse common setup via pytest fixtures in `conftest.py`
3. **Mocking**: Use `AsyncMock` for all async methods
4. **Isolation**: Each test should be independent
5. **Documentation**: Add docstrings explaining what each test validates
6. **Performance**: Keep individual tests under 1 second
7. **Flaky Tests**: Fix root cause rather than marking as flaky when possible

---

## Risk Assessment

**Low Risk** (straightforward):
- Command groups tests
- Button roles tests
- Threads tests
- Flaky test markers

**Medium Risk** (requires careful mocking):
- Gallery repost logic tests
- Settings cog tests
- Patreon poll tests
- Config fixture implementation

**High Risk** (complex, time-consuming):
- Owner cog tests (subprocess, cog loading)
- AO3 auth tests (executor pattern, external library)
- View persistence tests (state management)

---

**Last Updated**: 2025-10-29
**Status**: Roadmap created, ready for implementation
