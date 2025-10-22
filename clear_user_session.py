#!/usr/bin/env python3
"""
Clear user session and cache to force fresh login
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache_manager import CacheManager
import redis

def main():
    email = "dhruvsshah05@gmail.com"
    
    print(f"=== Clearing Session and Cache for {email} ===\n")
    
    # 1. Clear user cache
    try:
        cache_manager = CacheManager()
        cache_key = f"user_{email}"
        
        # Delete user cache
        result = cache_manager.delete(cache_key)
        print(f"1. User cache cleared: {result}")
        
        # Also try to clear any session-related cache
        session_keys = [
            f"session_{email}",
            f"flask_session_{email}",
            f"user_session_{email}"
        ]
        
        for key in session_keys:
            try:
                cache_manager.delete(key)
                print(f"   Cleared potential session key: {key}")
            except:
                pass
                
    except Exception as e:
        print(f"1. Cache clear error: {e}")
    
    # 2. Try to clear Redis sessions directly (if Redis is available)
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Get all keys that might be related to sessions
        session_keys = r.keys("flask_session:*")
        user_keys = r.keys(f"*{email}*")
        
        all_keys = session_keys + user_keys
        
        if all_keys:
            deleted = r.delete(*all_keys)
            print(f"2. Deleted {deleted} Redis session keys")
        else:
            print("2. No Redis session keys found")
            
    except Exception as e:
        print(f"2. Redis clear error: {e}")
    
    print("\n" + "="*50)
    print("Session and cache cleared!")
    print("Please:")
    print("1. Close your browser completely")
    print("2. Restart the Flask application")
    print("3. Open a new browser window and login again")
    print("="*50)

if __name__ == "__main__":
    main()
