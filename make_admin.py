#!/usr/bin/env python3
"""
Script to make a user admin in the database.
Usage: python make_admin.py <email>
"""

import sys
import os
from supabase import create_client

# Add the current directory to Python path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from dynamic_config import Config
except ImportError:
    # Fallback to regular config if dynamic_config doesn't exist
    from config import Config

def make_user_admin(email):
    """Make a user admin by updating their role in the database"""
    print(f"🔧 Making user {email} an admin...")
    
    # Initialize Supabase client
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    try:
        # Check if user exists
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data:
            print(f"❌ User {email} not found in database")
            return False
        
        user = result.data[0]
        print(f"📋 Current user details:")
        print(f"   Email: {user.get('email')}")
        print(f"   Name: {user.get('name')}")
        print(f"   Current Role: {user.get('role', 'member')}")
        
        # Update user role to admin
        update_result = supabase.table('users').update({
            'role': 'admin'
        }).eq('email', email).execute()
        
        if update_result.data:
            print(f"✅ Successfully made {email} an admin!")
            print("🎉 User can now access the settings page")
            return True
        else:
            print(f"❌ Failed to update user role")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <email>")
        print("Example: python make_admin.py dhruvsshah05@gmail.com")
        sys.exit(1)
    
    email = sys.argv[1]
    success = make_user_admin(email)
    
    if success:
        print("\n🚀 Next steps:")
        print("1. Refresh your browser or restart the application")
        print("2. Login again if needed")
        print("3. You should now see the Settings link in the dashboard")
        print("4. Access settings at: http://127.0.0.1:5050/settings")
    else:
        print("\n❌ Failed to make user admin. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
