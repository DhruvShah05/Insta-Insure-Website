#!/usr/bin/env python3
"""
WhatsApp Logs Migration Script
Run this script to create the whatsapp_logs table in your database
"""
import os
import sys
from supabase import create_client
from config import Config

def run_migration():
    """Run the WhatsApp logs migration"""
    try:
        # Initialize Supabase client
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        
        # Read the migration SQL file
        migration_file = os.path.join(os.path.dirname(__file__), 'whatsapp_logs_migration.sql')
        
        if not os.path.exists(migration_file):
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("🔄 Running WhatsApp logs migration...")
        
        # Execute the migration
        # Note: Supabase Python client doesn't support raw SQL execution
        # You'll need to run this SQL manually in your Supabase SQL editor
        print("📝 Please run the following SQL in your Supabase SQL editor:")
        print("=" * 60)
        print(migration_sql)
        print("=" * 60)
        
        print("✅ Migration SQL displayed above. Please execute it in Supabase SQL editor.")
        print("🔗 Go to: https://app.supabase.com/project/YOUR_PROJECT/sql")
        
        return True
        
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

if __name__ == "__main__":
    print("WhatsApp Logs Migration Script")
    print("=" * 40)
    
    success = run_migration()
    
    if success:
        print("\n✅ Migration preparation completed!")
        print("📋 Next steps:")
        print("1. Copy the SQL above and run it in Supabase SQL editor")
        print("2. Restart your Flask application")
        print("3. Visit /whatsapp_logs to see the new page")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
