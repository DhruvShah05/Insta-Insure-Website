-- Settings System Migration
-- Run this script to add settings table and update users table with roles

-- 1. Add role column to users table
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('admin', 'member'));

-- Update existing users to have admin role if they were previously admin
UPDATE public.users SET role = 'admin' WHERE is_admin = true;

-- 2. Create settings table to store all configurable values
CREATE TABLE IF NOT EXISTS public.settings (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    data_type VARCHAR(20) DEFAULT 'string' CHECK (data_type IN ('string', 'number', 'boolean', 'json')),
    description TEXT,
    is_sensitive BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by TEXT REFERENCES public.users(email) ON DELETE SET NULL,
    UNIQUE(category, key)
);

-- 3. Insert default settings
INSERT INTO public.settings (category, key, value, data_type, description, is_sensitive) VALUES
-- Company Information
('company', 'name', 'Insta Insurance Consultancy', 'string', 'Company name displayed in the application', false),
('company', 'logo_url', '', 'string', 'URL to company logo image', false),
('company', 'address', '', 'string', 'Company address', false),
('company', 'phone', '', 'string', 'Company phone number', false),
('company', 'email', '', 'string', 'Company email address', false),
('company', 'website', '', 'string', 'Company website URL', false),

-- Email Configuration
('email', 'smtp_server', 'smtp.zoho.in', 'string', 'SMTP server hostname', false),
('email', 'smtp_port', '587', 'number', 'SMTP server port', false),
('email', 'smtp_username', '', 'string', 'SMTP username', true),
('email', 'smtp_password', '', 'string', 'SMTP password', true),
('email', 'from_email', '', 'string', 'From email address', false),
('email', 'from_name', 'Insta Insurance Consultancy', 'string', 'From name for emails', false),

-- WhatsApp Configuration
('whatsapp', 'token', '', 'string', 'WhatsApp API token', true),
('whatsapp', 'phone_id', '', 'string', 'WhatsApp phone number ID', false),
('whatsapp', 'verify_token', '', 'string', 'Webhook verify token', true),

-- Twilio WhatsApp Configuration
('twilio', 'account_sid', '', 'string', 'Twilio Account SID', true),
('twilio', 'auth_token', '', 'string', 'Twilio Auth Token', true),
('twilio', 'whatsapp_from', 'whatsapp:+14155238886', 'string', 'Twilio WhatsApp from number', false),
('twilio', 'use_content_template', 'false', 'boolean', 'Use Twilio content templates', false),
('twilio', 'content_sid', '', 'string', 'Twilio content template SID', false),

-- Google Drive Configuration
('google_drive', 'credentials_file', 'credentials.json', 'string', 'Google credentials file path', false),
('google_drive', 'root_folder_id', '', 'string', 'Google Drive root folder ID', false),
('google_drive', 'archive_folder_id', '', 'string', 'Google Drive archive folder ID', false),

-- Database Configuration
('database', 'supabase_url', '', 'string', 'Supabase URL', true),
('database', 'supabase_key', '', 'string', 'Supabase API key', true),

-- Application Configuration
('app', 'base_url', 'https://admin.instainsure.co.in', 'string', 'Application base URL', false),
('app', 'secret_key', '', 'string', 'Flask secret key', true),
('app', 'environment', 'production', 'string', 'Application environment', false),
('app', 'debug', 'false', 'boolean', 'Debug mode enabled', false),

-- Notification Settings
('notifications', 'renewal_reminder_days', '30', 'number', 'Days before expiry to send renewal reminders', false),
('notifications', 'enable_email_notifications', 'true', 'boolean', 'Enable email notifications', false),
('notifications', 'enable_whatsapp_notifications', 'true', 'boolean', 'Enable WhatsApp notifications', false),

-- Business Settings
('business', 'default_gst_percentage', '18.00', 'number', 'Default GST percentage', false),
('business', 'default_commission_percentage', '10.00', 'number', 'Default commission percentage', false),

-- File Upload Settings
('uploads', 'max_file_size_mb', '10', 'number', 'Maximum file size in MB', false),
('uploads', 'allowed_extensions', '["pdf", "jpg", "jpeg", "png", "doc", "docx"]', 'json', 'Allowed file extensions', false)

ON CONFLICT (category, key) DO NOTHING;

-- 4. Create function to update timestamp
CREATE OR REPLACE FUNCTION update_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Create trigger for updated_at
DROP TRIGGER IF EXISTS settings_updated_at_trigger ON public.settings;
CREATE TRIGGER settings_updated_at_trigger
    BEFORE UPDATE ON public.settings
    FOR EACH ROW
    EXECUTE FUNCTION update_settings_updated_at();

-- 6. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_settings_category ON public.settings(category);
CREATE INDEX IF NOT EXISTS idx_settings_key ON public.settings(key);
CREATE INDEX IF NOT EXISTS idx_settings_category_key ON public.settings(category, key);
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
