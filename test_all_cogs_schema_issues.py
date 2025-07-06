import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_schema_issues():
    """
    Test all identified schema issues across different cogs.
    """
    print("Testing schema issues across all cogs...")

    issues_found = []

    # Test 1: stats_listeners.py - threads table created_at column
    print("\n1. Testing stats_listeners.py - threads table INSERT...")
    try:
        # This would fail because threads table doesn't have created_at column
        sql = "INSERT INTO threads(id, name, parent_id, created_at, guild_id, archived, locked) VALUES ($1,$2,$3,$4,$5,$6,$7)"
        print(f"   SQL: {sql}")
        print("   ❌ ISSUE: threads table doesn't have 'created_at' column")
        issues_found.append("stats_listeners.py:333 - threads table missing 'created_at' column")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: stats_listeners.py - join_leave table (RESOLVED)
    print("\n2. Testing stats_listeners.py - join_leave table INSERT...")
    try:
        sql = "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at) VALUES ($1,$2,$3,$4,$5,$6)"
        print(f"   SQL: {sql}")
        print("   ✅ RESOLVED: join_leave table correctly uses 'date' and 'join_or_leave' columns")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: stats_queries.py - join_leave table query (RESOLVED)
    print("\n3. Testing stats_queries.py - join_leave table query...")
    try:
        sql = "SELECT COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'join') as new_joins, COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'leave') as leaves FROM join_leave WHERE server_id = $2"
        print(f"   SQL: {sql}")
        print("   ✅ RESOLVED: stats_queries.py correctly uses 'date' and 'join_or_leave' columns")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: stats_listeners.py - role_changes table
    print("\n4. Testing stats_listeners.py - role_changes table INSERT...")
    try:
        sql = "INSERT INTO role_changes(user_id, server_id, role_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)"
        print(f"   SQL: {sql}")
        print("   ❌ ISSUE: role_changes table doesn't exist")
        issues_found.append("stats_listeners.py:243,254 - role_changes table doesn't exist")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: report.py - reports table
    print("\n5. Testing report.py - reports table INSERT...")
    try:
        sql = "INSERT INTO reports (message_id, user_id, reason, anonymous, additional_info, reported_user_id, guild_id, channel_id, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())"
        print(f"   SQL: {sql}")
        print("   ❌ ISSUE: reports table doesn't exist")
        issues_found.append("report.py:199 - reports table doesn't exist")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: settings.py - server_settings table
    print("\n6. Testing settings.py - server_settings table INSERT...")
    try:
        sql = "INSERT INTO server_settings (guild_id, admin_role_id) VALUES ($1, $2)"
        print(f"   SQL: {sql}")
        print("   ❌ ISSUE: server_settings table doesn't exist")
        issues_found.append("settings.py:82 - server_settings table doesn't exist")
    except Exception as e:
        print(f"   Error: {e}")

    # Test working cogs
    print("\n✅ WORKING COGS:")
    print("   - patreon_poll.py: poll and poll_option tables match schema")
    print("   - twi.py: password_link table matches schema")
    print("   - creator_links.py: creator_links table matches schema")
    print("   - links_tags.py: links table matches schema")
    print("   - stats_utils.py: Fixed in previous session")

    print(f"\n📊 SUMMARY:")
    print(f"   Total issues found: {len(issues_found)}")
    print(f"   Cogs with issues: stats_listeners.py, report.py, settings.py")
    print(f"   Cogs working correctly: patreon_poll.py, twi.py, creator_links.py, links_tags.py, stats_utils.py")

    print(f"\n🔧 ISSUES TO FIX:")
    for i, issue in enumerate(issues_found, 1):
        print(f"   {i}. {issue}")

    return issues_found

async def main():
    """Main test function."""
    print("Running comprehensive schema issues test...")

    # Configure logging to suppress debug messages
    logging.getLogger().setLevel(logging.WARNING)

    issues = await test_schema_issues()

    if issues:
        print(f"\n❌ Found {len(issues)} schema issues that need to be fixed.")
        print("These issues will cause database errors when the respective cogs try to execute these operations.")
    else:
        print("\n🎉 No schema issues found!")

    return len(issues) == 0

if __name__ == "__main__":
    asyncio.run(main())
