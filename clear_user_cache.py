#!/usr/bin/env python3
"""
Script to clear user cache to force reload of user data from database.
This is useful after updating user roles.
"""

import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from cache_manager import cache_manager
    from dynamic_config import Config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the application directory")
    sys.exit(1)

def clear_user_cache(email=None):
    """Clear user cache for a specific user or all users"""
    print("🧹 Clearing user cache...")
    
    try:
        if email:
            # Clear specific user cache
            cache_key = f"user_{email}"
            result = cache_manager.delete(cache_key)
            if result:
                print(f"✅ Cleared cache for user: {email}")
            else:
                print(f"ℹ️  No cache found for user: {email}")
        else:
            # Clear all user caches (pattern matching)
            # This is a simple approach - delete common user cache keys
            print("🔄 Clearing all user caches...")
            
            # Try to clear cache for the admin user specifically
            admin_emails = ["dhruvsshah05@gmail.com"]  # Add other admin emails if needed
            
            for admin_email in admin_emails:
                cache_key = f"user_{admin_email}"
                result = cache_manager.delete(cache_key)
                if result:
                    print(f"✅ Cleared cache for: {admin_email}")
                else:
                    print(f"ℹ️  No cache found for: {admin_email}")
        
        print("🎉 Cache clearing complete!")
        print("\n🚀 Next steps:")
        print("1. Restart the application server")
        print("2. Login again")
        print("3. Check if Settings link appears in dashboard")
        
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        return False
    
    return True

def main():
    email = None
    if len(sys.argv) > 1:
        email = sys.argv[1]
    
    success = clear_user_cache(email)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
