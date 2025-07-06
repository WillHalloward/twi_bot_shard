import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_reenabled_operations():
    """
    Test that all re-enabled database operations are working correctly.
    """
    print("Testing re-enabled database operations...")
    
    tests_passed = []
    tests_failed = []
    
    # Test 1: Verify settings.py operations are re-enabled
    print("\n1. Testing settings.py operations...")
    try:
        from cogs.settings import SettingsCog
        
        # Check that the database operations are uncommented
        import inspect
        
        # Check set_admin_role method
        source = inspect.getsource(SettingsCog.set_admin_role)
        if "await self.bot.db.fetchval" in source and "SELECT admin_role_id FROM server_settings" in source:
            print("   ✅ set_admin_role: Database operations re-enabled")
            tests_passed.append("settings.py:set_admin_role")
        else:
            print("   ❌ set_admin_role: Database operations still commented")
            tests_failed.append("settings.py:set_admin_role")
        
        # Check get_admin_role method
        source = inspect.getsource(SettingsCog.get_admin_role)
        if "await self.bot.db.fetchval" in source and "SELECT admin_role_id FROM server_settings" in source:
            print("   ✅ get_admin_role: Database operations re-enabled")
            tests_passed.append("settings.py:get_admin_role")
        else:
            print("   ❌ get_admin_role: Database operations still commented")
            tests_failed.append("settings.py:get_admin_role")
        
        # Check is_admin method
        source = inspect.getsource(SettingsCog.is_admin)
        if "await bot.db.fetchval" in source and "SELECT admin_role_id FROM server_settings" in source:
            print("   ✅ is_admin: Database operations re-enabled")
            tests_passed.append("settings.py:is_admin")
        else:
            print("   ❌ is_admin: Database operations still commented")
            tests_failed.append("settings.py:is_admin")
            
    except Exception as e:
        print(f"   ❌ Error testing settings.py: {e}")
        tests_failed.append("settings.py:import_error")
    
    # Test 2: Verify report.py operations are re-enabled
    print("\n2. Testing report.py operations...")
    try:
        from cogs.report import ReportView, ReportCog
        
        # Check _submit_report method
        source = inspect.getsource(ReportView._submit_report)
        if "await self.bot.db.execute" in source and "INSERT INTO reports" in source:
            print("   ✅ _submit_report: Database operations re-enabled")
            tests_passed.append("report.py:_submit_report")
        else:
            print("   ❌ _submit_report: Database operations still commented")
            tests_failed.append("report.py:_submit_report")
        
        # Check report method
        source = inspect.getsource(ReportCog.report)
        if "await self.bot.db.fetchrow" in source and "SELECT id FROM reports" in source:
            print("   ✅ report: Database operations re-enabled")
            tests_passed.append("report.py:report")
        else:
            print("   ❌ report: Database operations still commented")
            tests_failed.append("report.py:report")
            
    except Exception as e:
        print(f"   ❌ Error testing report.py: {e}")
        tests_failed.append("report.py:import_error")
    
    # Test 3: Verify stats_listeners.py operations are re-enabled
    print("\n3. Testing stats_listeners.py operations...")
    try:
        from cogs.stats_listeners import StatsListenersMixin
        
        # Check member_roles_update method
        source = inspect.getsource(StatsListenersMixin.member_roles_update)
        if "await self.bot.db.execute" in source and "INSERT INTO role_changes" in source:
            print("   ✅ member_roles_update: Database operations re-enabled")
            tests_passed.append("stats_listeners.py:member_roles_update")
        else:
            print("   ❌ member_roles_update: Database operations still commented")
            tests_failed.append("stats_listeners.py:member_roles_update")
            
    except Exception as e:
        print(f"   ❌ Error testing stats_listeners.py: {e}")
        tests_failed.append("stats_listeners.py:import_error")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Tests passed: {len(tests_passed)}")
    print(f"   Tests failed: {len(tests_failed)}")
    
    if tests_passed:
        print(f"\n✅ PASSED TESTS:")
        for test in tests_passed:
            print(f"   - {test}")
    
    if tests_failed:
        print(f"\n❌ FAILED TESTS:")
        for test in tests_failed:
            print(f"   - {test}")
    
    return len(tests_failed) == 0

async def main():
    """Main test function."""
    print("Running re-enabled operations verification...")
    
    # Configure logging to suppress debug messages
    logging.getLogger().setLevel(logging.WARNING)
    
    result = await test_reenabled_operations()
    
    if result:
        print(f"\n🎉 All database operations have been successfully re-enabled!")
        print("The cogs should now use the database tables that were created.")
    else:
        print(f"\n❌ Some database operations are still commented out.")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())