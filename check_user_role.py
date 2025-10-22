#!/usr/bin/env python3
"""
Script to check and display user role from database
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

def check_user_role(email):
    """Check user role in database"""
    print(f"🔍 Checking user role for {email}...")
    
    # Initialize Supabase client
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    try:
        # Get user from database
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data:
            print(f"❌ User {email} not found in database")
            return False
        
        user = result.data[0]
        print(f"📋 User details from database:")
        print(f"   Email: {user.get('email')}")
        print(f"   Name: {user.get('name')}")
        print(f"   Role: {user.get('role')}")
        print(f"   Is Admin (legacy): {user.get('is_admin')}")
        print(f"   Created At: {user.get('created_at')}")
        print(f"   Last Login: {user.get('last_login')}")
        
        # Check if role is admin
        if user.get('role') == 'admin':
            print("✅ User has admin role")
        else:
            print("❌ User does NOT have admin role")
            print("🔧 Attempting to fix...")
            
            # Update user role to admin
            update_result = supabase.table('users').update({
                'role': 'admin',
                'is_admin': True
            }).eq('email', email).execute()
            
            if update_result.data:
                print("✅ Successfully updated user role to admin")
                
                # Verify the update
                verify_result = supabase.table('users').select('role, is_admin').eq('email', email).execute()
                if verify_result.data:
                    updated_user = verify_result.data[0]
                    print(f"✅ Verified - Role: {updated_user.get('role')}, Is Admin: {updated_user.get('is_admin')}")
                
                return True
            else:
                print("❌ Failed to update user role")
                return False
        
        return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_user_role.py <email>")
        print("Example: python check_user_role.py dhruvsshah05@gmail.com")
        sys.exit(1)
    
    email = sys.argv[1]
    success = check_user_role(email)
    
    if success:
        print("\n🚀 Next steps:")
        print("1. Restart the application server")
        print("2. Clear browser cache or use incognito mode")
        print("3. Login again")
        print("4. Try accessing settings page")
    else:
        print("\n❌ Failed to check/fix user role. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
