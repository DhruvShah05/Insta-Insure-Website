# Settings Configuration Guide

## Overview

Your insurance portal now has a **fully dynamic settings system** that allows you to configure everything from the admin settings page without touching code or environment files. This includes:

- Portal name and branding
- Company logo
- API keys and credentials
- Google Drive folder IDs
- Email and WhatsApp configuration
- Business settings (GST, commission rates)

## Accessing the Settings Page

1. **Login as Admin**: Only admin users can access the settings page
2. **Navigate to Settings**: Click on the Settings link in the navigation (visible only to admins)
3. **URL**: `https://admin.instainsure.co.in/settings`

## Settings Categories

### 1. Company Information

Configure your portal's branding and company details:

- **Portal Name**: The name displayed in the navigation bar (e.g., "Insta Insurance Consultancy Portal")
- **Portal Title**: The title shown in browser tabs (e.g., "Insta Insurances Portal")
- **Logo Path**: Filename of your logo in the static folder (e.g., "ico.png")
- **Company Name**: Your company's official name
- **Address**: Company address
- **Email**: Company email address
- **Phone**: Company phone number
- **Website**: Company website URL

**How to Change Portal Name/Logo:**
1. Go to Settings → Company Information
2. Update "Portal Name" field (this appears in the navigation bar)
3. Update "Portal Title" field (this appears in browser tabs)
4. Update "Logo Path" to your logo filename (must be in `/static` folder)
5. Click "Save Changes"
6. Refresh any open pages to see the changes

### 2. Email Configuration

Configure SMTP settings for sending emails:

- **SMTP Server**: Email server hostname (e.g., smtp.zoho.in)
- **SMTP Port**: Server port (usually 587 for TLS)
- **SMTP Username**: Your email username
- **SMTP Password**: Your email password (masked for security)
- **From Email**: Email address to send from
- **Use TLS**: Enable TLS encryption (recommended)

### 3. WhatsApp Settings

Configure WhatsApp Business API:

- **Token**: WhatsApp API access token
- **Phone ID**: WhatsApp phone number ID
- **Webhook URL**: Webhook endpoint URL
- **Verify Token**: Webhook verification token

### 4. Twilio Configuration

Configure Twilio for WhatsApp messaging:

- **Account SID**: Twilio account identifier
- **Auth Token**: Twilio authentication token (masked)
- **WhatsApp Number**: Twilio WhatsApp number

### 5. Google Drive Settings

**IMPORTANT**: Configure Google Drive folder IDs here:

- **Credentials File**: Service account credentials filename
- **Root Folder ID**: **Your main Google Drive folder ID for policy uploads**
- **Folder ID**: Additional folder ID if needed
- **Archive Folder ID**: Folder ID for archived policies

**How to Add Root Folder ID:**
1. Go to Settings → Google Drive
2. Find "Root Folder ID" field
3. Paste your Google Drive folder ID (e.g., "0AOc3bRLhlrgzUk9PVA")
4. Click "Save Changes"
5. The system will now use this folder for all policy uploads

**Finding Your Google Drive Folder ID:**
- Open the folder in Google Drive
- Look at the URL: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE`
- Copy the ID after `/folders/`

### 6. Application Settings

Configure application behavior:

- **Base URL**: Your application's public URL
- **Environment**: development or production
- **Debug**: Enable debug mode (disable in production)

### 7. Business Settings

Configure business rules:

- **Default GST**: Default GST percentage (e.g., 18)
- **Default Commission**: Default commission percentage (e.g., 10)
- **Reminder Days**: Days before expiry to send reminders (e.g., 30)

## How Settings Work

### Database-Driven Configuration

All settings are stored in the `settings` table in your Supabase database. The system:

1. **Loads from Database First**: Checks the settings table for values
2. **Falls Back to Environment**: If not in database, uses .env file values
3. **Caches for Performance**: Settings are cached for 5 minutes to reduce database queries
4. **Updates Immediately**: Changes take effect within 5 minutes (or on next page load)

### Settings Priority

```
1. Database Settings (highest priority)
   ↓
2. Environment Variables (.env file)
   ↓
3. Default Values (fallback)
```

## Making Changes

### Through Settings Page (Recommended)

1. Navigate to `/settings`
2. Select the category you want to modify
3. Update the values
4. Click "Save Changes"
5. Changes are saved to database immediately
6. Refresh pages to see changes (or wait up to 5 minutes for cache refresh)

### Through Environment File (Legacy)

You can still use the `.env` file for initial setup, but settings page values will override them:

```bash
# .env file
PORTAL_NAME=My Custom Portal Name
GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id_here
```

## Security Features

### Sensitive Settings

Certain settings are marked as sensitive and are:
- **Masked in the UI**: Shown as password fields (••••••)
- **Only Updated When Changed**: Empty password fields don't overwrite existing values
- **Encrypted in Transit**: Sent over HTTPS

Sensitive settings include:
- SMTP passwords
- API tokens
- Auth tokens
- Credentials

### Admin-Only Access

- Only users with `admin` role can access settings
- Settings page is protected by `@admin_required` decorator
- Audit logging tracks who changed what and when

## Troubleshooting

### Changes Not Appearing

1. **Clear Cache**: Wait 5 minutes or restart the application
2. **Hard Refresh**: Press Ctrl+Shift+R (or Cmd+Shift+R on Mac)
3. **Check Database**: Verify settings were saved in Supabase settings table

### Logo Not Showing

1. **Check File Location**: Logo must be in `/static` folder
2. **Check Filename**: Ensure "Logo Path" matches exact filename (case-sensitive)
3. **Check Permissions**: Ensure file is readable by the application

### Root Folder ID Not Working

1. **Verify ID**: Check the folder ID is correct from Google Drive URL
2. **Check Permissions**: Ensure service account has access to the folder
3. **Test Connection**: Use the Google Drive test function in the application

## Migration from Hardcoded Values

All previously hardcoded values have been moved to settings:

| Old Location | New Location |
|-------------|--------------|
| Hardcoded in templates | Settings → Company Information → Portal Name |
| `ico.png` hardcoded | Settings → Company Information → Logo Path |
| `ROOT_FOLDER_ID` in code | Settings → Google Drive → Root Folder ID |
| `.env` file only | Settings page (with .env fallback) |

## Best Practices

1. **Use Settings Page**: Always use the settings page for configuration changes
2. **Backup Settings**: Use the Export feature to backup your configuration
3. **Test Changes**: Test in development before changing production settings
4. **Document Custom Values**: Keep a record of important IDs and tokens
5. **Secure Sensitive Data**: Never share sensitive settings publicly

## API Endpoints

For programmatic access:

- `GET /settings/api/get/<category>` - Get settings for a category
- `POST /settings/api/update` - Update multiple settings
- `POST /settings/api/create` - Create a new setting
- `POST /settings/api/delete` - Delete a setting
- `GET /settings/api/export` - Export all settings
- `POST /settings/api/import` - Import settings from backup

## Support

If you need help:
1. Check this guide first
2. Verify settings in the database
3. Check application logs for errors
4. Contact your developer for custom configuration needs
