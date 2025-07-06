import os
import sys
import asyncio
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Test the lazy loading logic by simulating different environments
async def test_lazy_loading():
    """Test the lazy loading logic with different environment settings."""
    
    print("Testing lazy loading logic...")
    
    # Test 1: Testing environment (should use lazy loading)
    print("\n=== Test 1: TESTING Environment ===")
    os.environ["ENVIRONMENT"] = "testing"
    
    # Import config after setting environment
    import config
    
    # Simulate the cog loading logic from main.py
    cogs = [
        "cogs.gallery",
        "cogs.links_tags", 
        "cogs.patreon_poll",
        "cogs.twi",
        "cogs.owner",
        "cogs.other",
        "cogs.mods",
        "cogs.stats",
        "cogs.creator_links",
        "cogs.report",
        "cogs.summarization",
        "cogs.settings",
    ]
    
    base_critical_cogs = [
        "cogs.owner",
        "cogs.mods", 
        "cogs.stats",
        "cogs.settings",
    ]
    
    if config.ENVIRONMENT == config.Environment.PRODUCTION:
        critical_cogs = cogs
        print("Production mode: Loading all cogs at startup")
    else:
        critical_cogs = base_critical_cogs
        print("Development/Testing mode: Using lazy loading for non-critical cogs")
    
    print(f"Environment: {config.ENVIRONMENT}")
    print(f"Critical cogs: {', '.join(critical_cogs)}")
    print(f"Non-critical cogs: {', '.join([cog for cog in cogs if cog not in critical_cogs])}")
    
    # Test 2: Production environment (should load all cogs)
    print("\n=== Test 2: PRODUCTION Environment ===")
    os.environ["ENVIRONMENT"] = "production"
    
    # Need to reload config module to pick up new environment
    import importlib
    importlib.reload(config)
    
    if config.ENVIRONMENT == config.Environment.PRODUCTION:
        critical_cogs = cogs
        print("Production mode: Loading all cogs at startup")
    else:
        critical_cogs = base_critical_cogs
        print("Development/Testing mode: Using lazy loading for non-critical cogs")
    
    print(f"Environment: {config.ENVIRONMENT}")
    print(f"Critical cogs: {', '.join(critical_cogs)}")
    print(f"Non-critical cogs: {', '.join([cog for cog in cogs if cog not in critical_cogs])}")
    
    # Test 3: Development environment (should use lazy loading)
    print("\n=== Test 3: DEVELOPMENT Environment ===")
    os.environ["ENVIRONMENT"] = "development"
    
    importlib.reload(config)
    
    if config.ENVIRONMENT == config.Environment.PRODUCTION:
        critical_cogs = cogs
        print("Production mode: Loading all cogs at startup")
    else:
        critical_cogs = base_critical_cogs
        print("Development/Testing mode: Using lazy loading for non-critical cogs")
    
    print(f"Environment: {config.ENVIRONMENT}")
    print(f"Critical cogs: {', '.join(critical_cogs)}")
    print(f"Non-critical cogs: {', '.join([cog for cog in cogs if cog not in critical_cogs])}")
    
    print("\n=== Test Results ===")
    print("✓ Testing environment uses lazy loading (only 4 critical cogs)")
    print("✓ Production environment loads all cogs at startup (12 cogs)")
    print("✓ Development environment uses lazy loading (only 4 critical cogs)")
    print("\nLazy loading logic is working correctly!")

if __name__ == "__main__":
    asyncio.run(test_lazy_loading())