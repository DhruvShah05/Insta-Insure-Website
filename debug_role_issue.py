#!/usr/bin/env python3
"""
Debug script to check user role issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client
from dynamic_config import Config
from cache_manager import CacheManager
from models import User
import json

def main():
    email = "dhruvsshah05@gmail.com"
    
    print(f"=== Debugging Role Issue for {email} ===\n")
    
    # 1. Check direct database query
    print("1. Direct Supabase Query:")
    try:
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if result.data:
            user_data = result.data[0]
            print(f"   Email: {user_data.get('email')}")
            print(f"   Role: {user_data.get('role')}")
            print(f"   Is Admin (legacy): {user_data.get('is_admin')}")
            print(f"   Created At: {user_data.get('created_at')}")
            print(f"   Updated At: {user_data.get('updated_at')}")
            print(f"   Raw Data: {json.dumps(user_data, indent=2)}")
        else:
            print(f"   User not found in database!")
            return
    except Exception as e:
        print(f"   Database Error: {e}")
        return
    
    print("\n" + "="*50)
    
    # 2. Check cache
    print("2. Cache Check:")
    try:
        cache_manager = CacheManager()
        cache_key = f"user_{email}"
        cached_data = cache_manager.get(cache_key, value_type='json')
        
        if cached_data:
            print(f"   Cached Data Found:")
            print(f"   Email: {cached_data.get('email')}")
            print(f"   Role: {cached_data.get('role')}")
            print(f"   Is Admin: {cached_data.get('is_admin')}")
            print(f"   Raw Cached Data: {json.dumps(cached_data, indent=2)}")
        else:
            print(f"   No cached data found for key: {cache_key}")
    except Exception as e:
        print(f"   Cache Error: {e}")
    
    print("\n" + "="*50)
    
    # 3. Test User.get_or_create
    print("3. User.get_or_create Test:")
    try:
        user = User.get_or_create(email)
        if user:
            print(f"   Email: {user.email}")
            print(f"   Role: {user.role}")
            print(f"   Is Admin: {user.is_admin}")
            print(f"   User Object: {user.to_dict()}")
        else:
            print(f"   User.get_or_create returned None")
    except Exception as e:
        print(f"   User.get_or_create Error: {e}")
    
    print("\n" + "="*50)
    
    # 4. Clear cache and test again
    print("4. Clearing Cache and Testing Again:")
    try:
        cache_manager = CacheManager()
        cache_key = f"user_{email}"
        cache_manager.delete(cache_key)
        print(f"   Cache cleared for key: {cache_key}")
        
        # Test again
        user = User.get_or_create(email)
        if user:
            print(f"   After cache clear - Role: {user.role}")
            print(f"   After cache clear - Is Admin: {user.is_admin}")
        else:
            print(f"   User.get_or_create still returned None")
    except Exception as e:
        print(f"   Cache clear Error: {e}")

if __name__ == "__main__":
    main()
