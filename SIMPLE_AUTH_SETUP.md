# Simple Authentication Setup Guide

This guide explains how to migrate from Clerk to simple email/password authentication using Supabase.

## Overview

The new authentication system:
- ✅ Uses Supabase database for user storage
- ✅ Email/password authentication only
- ✅ Sessions expire when browser tab is closed
- ✅ No external dependencies (no Clerk)
- ✅ Admin-only access (configurable via environment variables)

## Migration Steps

### 1. Database Migration

Run the following SQL in your Supabase SQL editor:

```sql
-- Add password field to users table
ALTER TABLE public.users 
ADD COLUMN password_hash text;

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
```

### 2. Install Dependencies

```bash
pip install bcrypt
```

### 3. Set Admin Passwords

Run the password setup script:

```bash
python setup_admin_passwords.py
```

This will:
- Prompt you to set passwords for each admin email
- Hash and store passwords securely in the database
- Create user records if they don't exist

### 4. Update Environment Variables

Remove Clerk-related environment variables:
```bash
# Remove these from your .env file:
# CLERK_PUBLISHABLE_KEY=
# CLERK_SECRET_KEY=
# CLERK_FRONTEND_API=
```

Keep these required variables:
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
ADMIN_EMAILS=email1@domain.com,email2@domain.com
SECRET_KEY=your_secret_key
```

### 5. Start the Application

```bash
python app_multiuser.py
```

## How It Works

### Authentication Flow

1. **Login Page**: Simple email/password form
2. **Authentication**: Validates against Supabase users table
3. **Session**: Creates Flask-Login session (expires on tab close)
4. **Authorization**: Only admin emails can access the system

### Session Security

- **Automatic Logout**: Sessions expire when browser tab is closed
- **No Persistent Sessions**: `remember=False` in login
- **Secure Cookies**: HTTPOnly, SameSite protection
- **HTTPS Ready**: Secure cookies in production

### Password Security

- **bcrypt Hashing**: Industry-standard password hashing
- **Salt**: Automatic salt generation for each password
- **No Plain Text**: Passwords never stored in plain text

## Files Changed

### Core Authentication
- `models.py` - Updated User class with password methods
- `auth.py` - Replaced Clerk with simple email/password auth
- `config.py` - Removed Clerk configuration

### Templates
- `login.html` - Simple email/password form (Clerk version backed up as `login_clerk_backup.html`)

### Session Configuration
- `app.py` - Added session expiry configuration
- `app_multiuser.py` - Added session expiry configuration

### Dependencies
- `requirements.txt` - Added bcrypt dependency

## Testing

1. **Login Test**:
   ```
   URL: http://localhost:5050/login
   Email: your_admin_email@domain.com
   Password: your_set_password
   ```

2. **Session Test**:
   - Login successfully
   - Close browser tab
   - Reopen and navigate to dashboard
   - Should redirect to login page

3. **Security Test**:
   - Try accessing `/dashboard` without login
   - Should redirect to login page
   - Try login with non-admin email
   - Should show "unauthorized" error

## Troubleshooting

### Common Issues

1. **"bcrypt not found"**:
   ```bash
   pip install bcrypt
   ```

2. **"User not found"**:
   - Check ADMIN_EMAILS environment variable
   - Run `python setup_admin_passwords.py` again

3. **"Invalid password"**:
   - Reset password using `python setup_admin_passwords.py`

4. **Session not expiring**:
   - Check browser settings (some browsers may persist sessions)
   - Clear browser cookies and test again

### Database Issues

1. **Migration failed**:
   ```sql
   -- Check if column exists
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'password_hash';
   ```

2. **User creation failed**:
   ```sql
   -- Check users table
   SELECT email, password_hash IS NOT NULL as has_password 
   FROM users WHERE email IN ('your_admin_email@domain.com');
   ```

## Security Considerations

### Production Deployment

1. **HTTPS Required**: Set `SESSION_COOKIE_SECURE=True` in production
2. **Strong Passwords**: Enforce minimum 8 characters
3. **Environment Variables**: Never commit secrets to git
4. **Regular Updates**: Keep dependencies updated

### Admin Access

- Only emails listed in `ADMIN_EMAILS` can access the system
- Add/remove admin emails by updating environment variable
- Restart application after changing admin emails

## Rollback Plan

If you need to rollback to Clerk:

1. Restore original files:
   ```bash
   cp templates/login_clerk_backup.html templates/login.html
   ```

2. Restore Clerk configuration in `config.py`

3. Add Clerk environment variables back

4. Restart application

## Support

For issues or questions:
1. Check application logs: `logs/multiuser_app.log`
2. Verify database connection and user records
3. Test with a fresh browser session
