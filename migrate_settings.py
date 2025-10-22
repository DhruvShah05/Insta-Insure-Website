#!/usr/bin/env python3
"""
Settings Migration Script
Migrates existing environment variables to database settings
Run this after applying the database migration
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_settings():
    """Migrate environment variables to database settings"""
    try:
        # Import after loading environment
        from settings_service import settings
        from models import User
        
        print("🔄 Starting settings migration...")
        
        # Get the first admin user to use as updated_by
        try:
            users = User.get_all_users()
            admin_users = [u for u in users if u.get('role') == 'admin']
            if admin_users:
                migration_user = admin_users[0]['email']
                print(f"📧 Using admin user '{migration_user}' for migration tracking")
            else:
                migration_user = None
                print("⚠️  No admin users found, settings will be created without tracking")
        except Exception as e:
            print(f"⚠️  Could not get users: {e}, proceeding without tracking")
            migration_user = None
        
        # Company Information (if available in environment)
        company_settings = {
            'name': os.getenv('COMPANY_NAME', 'Insta Insurance Consultancy'),
            'logo_url': os.getenv('COMPANY_LOGO_URL', ''),
            'address': os.getenv('COMPANY_ADDRESS', ''),
            'phone': os.getenv('COMPANY_PHONE', ''),
            'email': os.getenv('COMPANY_EMAIL', ''),
            'website': os.getenv('COMPANY_WEBSITE', ''),
        }
        
        # Email Configuration
        email_settings = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.zoho.in'),
            'smtp_port': os.getenv('SMTP_PORT', '587'),
            'smtp_username': os.getenv('SMTP_USERNAME', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', ''),
            'from_name': os.getenv('FROM_NAME', 'Insta Insurance Consultancy'),
        }
        
        # WhatsApp Configuration
        whatsapp_settings = {
            'token': os.getenv('WHATSAPP_TOKEN', ''),
            'phone_id': os.getenv('WHATSAPP_PHONE_ID', ''),
            'verify_token': os.getenv('VERIFY_TOKEN', ''),
        }
        
        # Twilio Configuration
        twilio_settings = {
            'account_sid': os.getenv('TWILIO_ACCOUNT_SID', ''),
            'auth_token': os.getenv('TWILIO_AUTH_TOKEN', ''),
            'whatsapp_from': os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886'),
            'use_content_template': os.getenv('TWILIO_USE_CONTENT_TEMPLATE', 'false'),
            'content_sid': os.getenv('TWILIO_CONTENT_SID', ''),
        }
        
        # Google Drive Configuration
        google_drive_settings = {
            'credentials_file': os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json'),
            'root_folder_id': os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_ID', ''),
            'archive_folder_id': os.getenv('ARCHIVE_FOLDER_ID', ''),
        }
        
        # Application Configuration
        app_settings = {
            'base_url': os.getenv('APP_BASE_URL', 'https://admin.instainsure.co.in'),
            'secret_key': os.getenv('SECRET_KEY', ''),
            'environment': os.getenv('FLASK_ENV', 'production'),
            'debug': 'true' if os.getenv('FLASK_ENV') == 'development' else 'false',
        }
        
        # Business Settings
        business_settings = {
            'default_gst_percentage': '18.00',
            'default_commission_percentage': '10.00',
        }
        
        # Notification Settings
        notification_settings = {
            'renewal_reminder_days': '30',
            'enable_email_notifications': 'true',
            'enable_whatsapp_notifications': 'true',
        }
        
        # File Upload Settings
        upload_settings = {
            'max_file_size_mb': '10',
            'allowed_extensions': '["pdf", "jpg", "jpeg", "png", "doc", "docx"]',
        }
        
        # Migrate all settings
        categories = {
            'company': company_settings,
            'email': email_settings,
            'whatsapp': whatsapp_settings,
            'twilio': twilio_settings,
            'google_drive': google_drive_settings,
            'app': app_settings,
            'business': business_settings,
            'notifications': notification_settings,
            'uploads': upload_settings,
        }
        
        total_migrated = 0
        total_failed = 0
        
        for category, category_settings in categories.items():
            print(f"📁 Migrating {category} settings...")
            
            for key, value in category_settings.items():
                try:
                    # Only update if value is not empty (preserve existing settings)
                    if value:
                        current_value = settings.get(category, key)
                        if current_value is None or current_value == '':
                            success = settings.set(category, key, value, migration_user)
                            if success:
                                print(f"  ✅ {category}.{key} = {value if not key.endswith('password') and not key.endswith('token') and not key.endswith('key') else '***'}")
                                total_migrated += 1
                            else:
                                print(f"  ❌ Failed to set {category}.{key}")
                                total_failed += 1
                        else:
                            print(f"  ⏭️  {category}.{key} already set, skipping")
                    else:
                        print(f"  ⚠️  {category}.{key} is empty, skipping")
                        
                except Exception as e:
                    print(f"  ❌ Error setting {category}.{key}: {e}")
                    total_failed += 1
        
        print(f"\n🎉 Migration completed!")
        print(f"✅ Successfully migrated: {total_migrated} settings")
        if total_failed > 0:
            print(f"❌ Failed to migrate: {total_failed} settings")
        
        print(f"\n📋 Next steps:")
        print(f"1. Run the database migration: settings_system_migration.sql")
        print(f"2. Update your application to use dynamic_config instead of config")
        print(f"3. Access the settings page at /settings (admin only)")
        print(f"4. Review and update settings as needed")
        
        return total_migrated, total_failed
        
    except ImportError as e:
        print(f"❌ Error importing settings service: {e}")
        print("Make sure you've run the database migration first!")
        return 0, 1
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 0, 1

def check_database_connection():
    """Check if database connection is working"""
    try:
        from supabase import create_client
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ SUPABASE_URL and SUPABASE_KEY must be set in environment")
            return False
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Test connection by checking if settings table exists
        result = supabase.table('settings').select('id').limit(1).execute()
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Make sure you've run the database migration first!")
        return False

def main():
    """Main migration function"""
    print("🚀 Settings Migration Tool")
    print("=" * 50)
    
    # Check database connection
    if not check_database_connection():
        sys.exit(1)
    
    # Run migration
    migrated, failed = migrate_settings()
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 All done! Your settings have been migrated successfully.")

if __name__ == "__main__":
    main()
