import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_join_leave_fix():
    """
    Test that the join_leave table fix is correctly implemented.
    """
    print("Testing join_leave table fix...")
    
    # Read the stats_queries.py file to verify the fix
    try:
        with open('cogs/stats_queries.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check that the incorrect column names are not present
        if 'join_date' in content:
            print("❌ ERROR: 'join_date' still found in stats_queries.py")
            return False
            
        if 'leave_date' in content:
            print("❌ ERROR: 'leave_date' still found in stats_queries.py")
            return False
            
        # Check that the correct query structure is present
        expected_query_part = "COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'join')"
        if expected_query_part not in content:
            print("❌ ERROR: Correct join query not found in stats_queries.py")
            return False
            
        expected_query_part2 = "COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'leave')"
        if expected_query_part2 not in content:
            print("❌ ERROR: Correct leave query not found in stats_queries.py")
            return False
            
        print("✅ SUCCESS: stats_queries.py correctly uses 'date' and 'join_or_leave' columns")
        
        # Verify stats_listeners.py is also correct
        with open('cogs/stats_listeners.py', 'r', encoding='utf-8') as f:
            listeners_content = f.read()
            
        # Check that stats_listeners.py uses the correct column names
        if "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at)" in listeners_content:
            print("✅ SUCCESS: stats_listeners.py correctly uses proper column names")
        else:
            print("❌ ERROR: stats_listeners.py may not be using correct column names")
            return False
            
        return True
        
    except FileNotFoundError as e:
        print(f"❌ ERROR: Could not find file: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Main test function."""
    print("Running join_leave table fix verification...")
    
    success = test_join_leave_fix()
    
    if success:
        print("\n🎉 All tests passed! The join_leave table issue has been successfully fixed.")
        print("\nSummary of changes:")
        print("1. Fixed SQL query in cogs/stats_queries.py to use 'date' and 'join_or_leave' columns")
        print("2. Updated test file to reflect the resolved issues")
        print("3. Verified that stats_listeners.py already uses correct column names")
    else:
        print("\n❌ Some tests failed. Please review the issues above.")
    
    return success

if __name__ == "__main__":
    main()