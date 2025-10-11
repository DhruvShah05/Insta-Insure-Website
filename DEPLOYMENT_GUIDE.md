# Insurance Portal - Windows Deployment Guide

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** installed on Windows
- **Google Account** with OAuth setup
- **Supabase Account** with database
- **Admin email addresses** for access control

### 1. Setup Database

1. **Run the SQL script** in your Supabase dashboard:
   ```sql
   -- Copy and paste contents of create_users_table.sql
   ```

2. **Verify your existing tables** are present:
   - `clients`
   - `members` 
   - `policies`
   - `pending_policies`
   - `users` (newly created)

### 2. Configure Environment

1. **Copy environment file**:
   ```cmd
   copy .env.example .env
   ```

2. **Edit `.env` file** with your actual values:
   ```env
   SECRET_KEY=generate-a-strong-secret-key
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-anon-key
   GOOGLE_CLIENT_ID=your-google-oauth-client-id
   GOOGLE_CLIENT_SECRET=your-google-oauth-secret
   ADMIN_EMAILS=admin1@company.com,admin2@company.com
   ```

### 3. Setup Google OAuth

1. **Go to Google Cloud Console**: https://console.cloud.google.com
2. **Create/Select Project**
3. **Enable Google+ API**
4. **Create OAuth 2.0 Credentials**:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:5000/auth`
5. **Download credentials** and update `.env`

### 4. Deploy Application

1. **Run deployment script**:
   ```cmd
   deploy_windows.bat
   ```

2. **Access the application**:
   - Open browser: http://localhost:5000
   - Login with authorized Google account

## 🔧 Production Configuration

### Multi-User Support
- ✅ **Google OAuth** authentication
- ✅ **Session management** (24-hour sessions)
- ✅ **User tracking** in database
- ✅ **Admin-only access** control
- ✅ **Concurrent user support** (4-5 users)

### Security Features
- ✅ **Secure sessions** with HttpOnly cookies
- ✅ **CSRF protection** built-in
- ✅ **File upload validation** (PDF only, 50MB max)
- ✅ **SQL injection protection** via Supabase
- ✅ **XSS protection** headers

### Performance Features
- ✅ **Threaded requests** for concurrent users
- ✅ **Connection pooling** via Supabase
- ✅ **File size limits** to prevent abuse
- ✅ **Request logging** for monitoring
- ✅ **Error handling** with user-friendly messages

## 📊 Monitoring & Logs

### Log Files
- **Location**: `logs/insurance_portal.log`
- **Rotation**: 10MB files, 10 backups
- **Content**: Requests, errors, user actions

### User Management
- **View users**: Check `users` table in Supabase
- **Add admin**: Update `ADMIN_EMAILS` in `.env`
- **Monitor activity**: Check `last_login` column

## 🛠️ Troubleshooting

### Common Issues

**1. "Google OAuth Error"**
- Check `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- Verify redirect URI in Google Console
- Ensure Google+ API is enabled

**2. "Database Connection Error"**
- Verify `SUPABASE_URL` and `SUPABASE_KEY`
- Check internet connection
- Confirm Supabase project is active

**3. "Access Denied"**
- Add user email to `ADMIN_EMAILS` in `.env`
- Restart application after changing `.env`
- Check email spelling and formatting

**4. "File Upload Error"**
- Check file size (max 50MB)
- Ensure file is PDF format
- Verify Google Drive credentials

### Performance Optimization

**For 4-5 concurrent users:**
- ✅ Default configuration is sufficient
- ✅ Flask's threaded mode handles concurrent requests
- ✅ Supabase handles database connection pooling

**For more users (10+):**
- Consider using Gunicorn: `gunicorn -w 4 -b 0.0.0.0:5000 app:app`
- Monitor system resources
- Consider database query optimization

## 🔄 Updates & Maintenance

### Regular Tasks
1. **Monitor logs** for errors
2. **Check user activity** in database
3. **Update dependencies** periodically
4. **Backup database** regularly

### Updating Application
1. **Stop the application** (Ctrl+C)
2. **Pull latest changes**
3. **Update dependencies**: `pip install -r requirements_production.txt`
4. **Restart**: `deploy_windows.bat`

## 📞 Support

### System Requirements
- **OS**: Windows 10/11
- **Python**: 3.8+
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 1GB for application + logs
- **Network**: Internet connection required

### CORE FUNCTIONALITY:
- Policy renewal system with file upload/replacement
- WhatsApp bot with professional messaging and document delivery
- Email notifications with attachments
- Excel data management with Google Drive integration
- Database schema fully aligned (clients, members, policies)
- Professional UI with proper status indicators
