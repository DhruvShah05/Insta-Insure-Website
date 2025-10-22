# Settings System Implementation Guide

## Overview

This comprehensive settings system replaces hardcoded configuration values with a database-driven, admin-configurable system. Admins can now change everything including company information, API keys, email settings, and user roles through a web interface.

## Features

### ✅ **Completed Features**

1. **Database-Driven Settings**
   - All configuration stored in `settings` table
   - Organized by categories (company, email, whatsapp, etc.)
   - Support for different data types (string, number, boolean, json)
   - Sensitive settings marked and handled securely

2. **Role-Based Access Control**
   - Admin and Member roles
   - Settings page accessible only to admins
   - User management for admins
   - First user automatically becomes admin

3. **Admin Settings Interface**
   - Modern, responsive web interface
   - Organized by categories with tabs
   - Real-time saving and validation
   - Sensitive field handling (passwords, tokens)

4. **User Management**
   - Create new users with roles
   - Change user roles (admin ↔ member)
   - Reset user passwords
   - Delete users (except self)

5. **Dynamic Configuration**
   - Automatic fallback to environment variables
   - Cached settings for performance
   - Hot-reload capability

## Installation & Setup

### 1. Database Migration

Run the database migration to create the settings table and add user roles:

```sql
-- Run this SQL script in your Supabase dashboard
-- File: settings_system_migration.sql
```

### 2. Migrate Existing Settings

Run the migration script to populate settings from environment variables:

```bash
python migrate_settings.py
```

### 3. Update Application

The application has been updated to use the new settings system:
- `app_multiuser.py` - Updated to use `dynamic_config`
- `models.py` - Updated for role-based authentication
- Navigation updated with Settings link for admins

## Settings Categories

### 🏢 **Company Information**
- Company name, logo, address
- Contact information (phone, email, website)
- Displayed throughout the application

### 📧 **Email Configuration**
- SMTP server settings
- Authentication credentials
- From address and name
- Used for policy notifications and renewals

### 📱 **WhatsApp Settings**
- WhatsApp Business API configuration
- Phone ID and tokens
- Webhook verification

### 📞 **Twilio Configuration**
- Twilio account credentials
- WhatsApp integration settings
- Content template configuration

### 💾 **Google Drive Settings**
- Credentials file path
- Root and archive folder IDs
- File storage configuration

### ⚙️ **Application Settings**
- Base URL and environment
- Security settings
- Debug mode configuration

### 💼 **Business Settings**
- Default GST percentage
- Default commission rates
- Renewal reminder timing

### 📁 **File Upload Settings**
- Maximum file size limits
- Allowed file extensions
- Upload restrictions

## User Roles

### 👑 **Admin Role**
- Full access to settings page
- Can manage all users
- Can change user roles
- Can create/delete users
- Access to all application features

### 👤 **Member Role**
- Standard application access
- Cannot access settings
- Cannot manage users
- Policy and claims management only

## Settings Management

### Accessing Settings
1. Log in as an admin user
2. Click "Settings" in the sidebar or user menu
3. Navigate through different categories using tabs

### Managing Settings
- **Edit Values**: Click on any setting field to edit
- **Save Changes**: Click "Save Changes" button for each category
- **Sensitive Fields**: Password fields show as masked, only update if new value entered
- **Data Types**: Automatic validation based on field type

### User Management
1. Go to Settings → User Management tab
2. **Add User**: Click "Add New User" button
3. **Change Role**: Click role change button next to user
4. **Reset Password**: Click "Reset Password" button
5. **Delete User**: Click "Delete" button (cannot delete yourself)

## API Endpoints

### Settings API
- `GET /settings/api/get/<category>` - Get category settings
- `POST /settings/api/update` - Update multiple settings
- `POST /settings/api/create` - Create new setting
- `POST /settings/api/delete` - Delete setting
- `GET /settings/api/export` - Export settings for backup
- `POST /settings/api/import` - Import settings from backup

### User Management API
- `GET /settings/api/users` - Get all users
- `POST /settings/api/users/create` - Create new user
- `POST /settings/api/users/update-role` - Update user role
- `POST /settings/api/users/delete` - Delete user
- `POST /settings/api/users/reset-password` - Reset user password

## Security Features

### 🔒 **Access Control**
- Role-based route protection
- Admin-only settings access
- Self-modification prevention
- Session-based authentication

### 🛡️ **Data Protection**
- Sensitive settings marked and masked
- Password fields handled securely
- API key protection
- Audit logging for changes

### 🔐 **Authentication**
- Database-driven user roles
- Secure password hashing (bcrypt)
- Session management
- Automatic first-user admin setup

## Configuration Files

### Core Files
- `settings_service.py` - Settings management service
- `dynamic_config.py` - Dynamic configuration system
- `auth_decorators.py` - Role-based access control
- `routes/settings_routes.py` - Settings API endpoints
- `models.py` - Updated User model with roles

### Templates
- `templates/settings/index.html` - Settings management interface

### Migration Files
- `settings_system_migration.sql` - Database schema changes
- `migrate_settings.py` - Environment variable migration script

## Usage Examples

### Getting Settings in Code
```python
from dynamic_config import Config

# Get individual settings
company_name = Config.COMPANY_NAME
smtp_server = Config.SMTP_SERVER
max_file_size = Config.MAX_FILE_SIZE_MB

# Get category settings
email_config = Config.get_email_config()
company_info = Config.get_company_info()

# Check feature flags
if Config.is_feature_enabled('email_notifications'):
    send_email_notification()
```

### Using Settings Service Directly
```python
from settings_service import settings

# Get setting
value = settings.get('company', 'name', 'Default Company')

# Set setting
success = settings.set('company', 'name', 'New Company Name', 'admin@example.com')

# Get category
email_settings = settings.get_category('email')
```

### Role-Based Route Protection
```python
from auth_decorators import admin_required, role_required

@admin_required
def admin_only_route():
    return "Admin only content"

@role_required('member')
def member_route():
    return "Member content"
```

## Troubleshooting

### Common Issues

1. **Settings not loading**
   - Check database connection
   - Verify settings table exists
   - Run migration script

2. **Permission denied**
   - Check user role in database
   - Verify admin status
   - Check session authentication

3. **Settings not saving**
   - Check database permissions
   - Verify API endpoints
   - Check browser console for errors

### Migration Issues

1. **Database connection failed**
   - Verify SUPABASE_URL and SUPABASE_KEY
   - Check network connectivity
   - Ensure Supabase project is active

2. **Settings table not found**
   - Run the SQL migration script first
   - Check table creation in Supabase dashboard
   - Verify table permissions

## Future Enhancements

### Planned Features
- [ ] Settings backup/restore functionality
- [ ] Settings change history/audit log
- [ ] Bulk settings import/export
- [ ] Settings validation rules
- [ ] Environment-specific settings
- [ ] Settings templates for quick setup

### API Improvements
- [ ] GraphQL API for settings
- [ ] Webhook notifications for setting changes
- [ ] Settings versioning
- [ ] Rollback functionality

## Support

For issues or questions about the settings system:

1. Check this documentation
2. Review the migration scripts
3. Check database table structure
4. Verify user roles and permissions
5. Check application logs for errors

## Migration Checklist

- [ ] Run database migration SQL script
- [ ] Run settings migration Python script
- [ ] Update environment variables (optional)
- [ ] Test admin login and settings access
- [ ] Verify all settings categories load
- [ ] Test user management functionality
- [ ] Confirm application still works with new config
- [ ] Update any custom code using old config
- [ ] Train admin users on new interface
- [ ] Document any custom settings added

---

**🎉 Congratulations!** You now have a fully configurable, database-driven settings system with role-based access control. No more hardcoded values!
