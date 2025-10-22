#!/usr/bin/env python3
"""
Debug script to trace exactly how the user is being loaded
"""

import sys
import os
from supabase import create_client

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from dynamic_config import Config
    from models import User
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def debug_user_loading():
    """Debug the user loading process step by step"""
    email = "dhruvsshah05@gmail.com"
    
    print("🔍 Debugging User Loading Process")
    print("=" * 50)
    
    # Step 1: Direct database query
    print("1️⃣ Direct Database Query:")
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    result = supabase.table('users').select('*').eq('email', email).execute()
    
    if result.data:
        user_data = result.data[0]
        print(f"   ✅ Found user in database")
        print(f"   📧 Email: {user_data.get('email')}")
        print(f"   👤 Name: {user_data.get('name')}")
        print(f"   🎭 Role: {user_data.get('role')}")
        print(f"   👑 Is Admin: {user_data.get('is_admin')}")
        print(f"   🔑 Has Password: {'Yes' if user_data.get('password_hash') else 'No'}")
    else:
        print("   ❌ User not found in database")
        return
    
    # Step 2: Test User.get_or_create method
    print("\n2️⃣ Testing User.get_or_create():")
    try:
        user_obj = User.get_or_create(email)
        if user_obj:
            print(f"   ✅ User object created")
            print(f"   📧 Email: {user_obj.email}")
            print(f"   👤 Name: {user_obj.name}")
            print(f"   🎭 Role: {user_obj.role}")
            print(f"   👑 Is Admin: {user_obj.is_admin}")
            print(f"   🔑 Has Password Hash: {'Yes' if user_obj.password_hash else 'No'}")
        else:
            print("   ❌ Failed to create user object")
    except Exception as e:
        print(f"   ❌ Error in get_or_create: {e}")
    
    # Step 3: Test User.from_dict method
    print("\n3️⃣ Testing User.from_dict():")
    try:
        user_dict = {
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'picture': user_data.get('picture'),
            'user_id': user_data.get('id'),
            'role': user_data.get('role')
        }
        user_from_dict = User.from_dict(user_dict)
        print(f"   ✅ User from dict created")
        print(f"   📧 Email: {user_from_dict.email}")
        print(f"   👤 Name: {user_from_dict.name}")
        print(f"   🎭 Role: {user_from_dict.role}")
        print(f"   👑 Is Admin: {user_from_dict.is_admin}")
    except Exception as e:
        print(f"   ❌ Error in from_dict: {e}")
    
    # Step 4: Test User constructor directly
    print("\n4️⃣ Testing User constructor directly:")
    try:
        direct_user = User(
            email=user_data.get('email'),
            name=user_data.get('name'),
            picture=user_data.get('picture'),
            user_id=user_data.get('id'),
            password_hash=user_data.get('password_hash'),
            role=user_data.get('role')
        )
        print(f"   ✅ Direct user created")
        print(f"   📧 Email: {direct_user.email}")
        print(f"   👤 Name: {direct_user.name}")
        print(f"   🎭 Role: {direct_user.role}")
        print(f"   👑 Is Admin: {direct_user.is_admin}")
    except Exception as e:
        print(f"   ❌ Error in direct constructor: {e}")
    
    # Step 5: Check what happens with None role
    print("\n5️⃣ Testing with None role:")
    try:
        none_role_user = User(
            email=user_data.get('email'),
            name=user_data.get('name'),
            role=None  # Explicitly None
        )
        print(f"   🎭 Role when None: {none_role_user.role}")
        print(f"   👑 Is Admin when None: {none_role_user.is_admin}")
    except Exception as e:
        print(f"   ❌ Error with None role: {e}")

def main():
    debug_user_loading()
    
    print("\n🎯 Analysis:")
    print("If all steps show 'admin' role but the app still loads 'member',")
    print("the issue might be in:")
    print("1. Flask-Login user_loader function")
    print("2. Session/cache management")
    print("3. Authentication middleware")

if __name__ == "__main__":
    main()
