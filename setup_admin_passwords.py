#!/usr/bin/env python3
"""
Script to set up admin user passwords in the database.
Run this after applying the database migration to set passwords for admin users.
"""

import os
import sys
import getpass
from supabase import create_client
from models import User
from config import Config

def setup_admin_passwords():
    """Set up passwords for admin users"""
    print("🔐 Admin Password Setup")
    print("=" * 50)
    
    # Initialize Supabase client
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    print(f"Admin emails configured: {', '.join(Config.ADMIN_EMAILS)}")
    print()
    
    for email in Config.ADMIN_EMAILS:
        print(f"Setting up password for: {email}")
        
        # Check if user exists
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data:
            # Create user if doesn't exist
            print(f"  Creating new user: {email}")
            new_user_data = {
                'email': email,
                'name': email.split('@')[0],
                'is_admin': True,
                'password_hash': None  # Will be set below
            }
            supabase.table('users').insert(new_user_data).execute()
        
        # Get password from user
        while True:
            password = getpass.getpass(f"  Enter password for {email}: ")
            if len(password) < 8:
                print("  ❌ Password must be at least 8 characters long")
                continue
            
            confirm_password = getpass.getpass(f"  Confirm password for {email}: ")
            if password != confirm_password:
                print("  ❌ Passwords don't match")
                continue
            
            break
        
        # Hash password and update database
        password_hash = User.hash_password(password)
        
        result = supabase.table('users').update({
            'password_hash': password_hash
        }).eq('email', email).execute()
        
        if result.data:
            print(f"  ✅ Password set successfully for {email}")
        else:
            print(f"  ❌ Failed to set password for {email}")
        
        print()
    
    print("🎉 Admin password setup complete!")
    print()
    print("Next steps:")
    print("1. Run the database migration: add_password_migration.sql")
    print("2. Start the application")
    print("3. Login with your email and password")

if __name__ == "__main__":
    try:
        setup_admin_passwords()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)
