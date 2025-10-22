#!/usr/bin/env python3
"""
User Role Checker
Check current users and their roles in the system
"""

import os
from dotenv import load_dotenv

load_dotenv()

def check_users():
    """Check all users and their roles"""
    try:
        from models import User
        
        print("👥 Current Users in System:")
        print("=" * 50)
        
        users = User.get_all_users()
        
        if not users:
            print("❌ No users found in the database")
            return
        
        for user in users:
            role_emoji = "👑" if user.get('role') == 'admin' else "👤"
            status = "ADMIN" if user.get('role') == 'admin' else "MEMBER"
            
            print(f"{role_emoji} {user.get('email', 'N/A')}")
            print(f"   Name: {user.get('name', 'N/A')}")
            print(f"   Role: {status}")
            print(f"   Created: {user.get('created_at', 'N/A')}")
            print(f"   Last Login: {user.get('last_login', 'Never')}")
            print()
        
        # Check for specific user
        target_email = "dhruvsshah05@gmail.com"
        target_user = next((u for u in users if u.get('email') == target_email), None)
        
        if target_user:
            print(f"🔍 Status for {target_email}:")
            print(f"   Role: {target_user.get('role', 'Unknown').upper()}")
            if target_user.get('role') != 'admin':
                print(f"   ⚠️  You are currently a MEMBER, not an admin")
                print(f"   💡 To access settings, you need admin role")
        else:
            print(f"❌ User {target_email} not found in database")
            print(f"   💡 You may need to log in first to create your account")
        
    except Exception as e:
        print(f"❌ Error checking users: {e}")

def make_user_admin(email):
    """Make a user admin"""
    try:
        from models import User
        
        success, message = User.update_user_role(email, 'admin', 'system_admin')
        
        if success:
            print(f"✅ {email} is now an admin!")
        else:
            print(f"❌ Failed to make {email} admin: {message}")
            
    except Exception as e:
        print(f"❌ Error updating user role: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "make-admin":
        if len(sys.argv) > 2:
            email = sys.argv[2]
            print(f"🔧 Making {email} an admin...")
            make_user_admin(email)
        else:
            print("Usage: python check_users.py make-admin <email>")
    else:
        check_users()
