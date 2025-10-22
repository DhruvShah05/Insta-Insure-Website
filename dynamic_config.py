"""
Dynamic Configuration System
Replaces static config.py with database-driven settings
Falls back to environment variables if settings are not available
"""

import os
from dotenv import load_dotenv
from typing import Any, Optional
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class DynamicConfig:
    """Configuration class that loads from database settings with environment fallbacks"""
    
    def __init__(self):
        self._settings_service = None
        self._fallback_to_env = True
        
        # Core settings that must come from environment (for initial database connection)
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        
        if not self.SUPABASE_URL or not self.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
    
    def _get_settings_service(self):
        """Lazy load settings service to avoid circular imports"""
        if self._settings_service is None:
            try:
                from settings_service import settings
                self._settings_service = settings
            except Exception as e:
                logger.warning(f"Could not load settings service: {e}")
                self._fallback_to_env = True
        return self._settings_service
    
    def _get_setting(self, category: str, key: str, default: Any = None, env_key: str = None) -> Any:
        """Get setting from database or fall back to environment variable"""
        try:
            settings_service = self._get_settings_service()
            if settings_service:
                value = settings_service.get(category, key)
                if value is not None:
                    return value
        except Exception as e:
            logger.warning(f"Error getting setting {category}.{key}: {e}")
        
        # Fall back to environment variable
        if env_key:
            env_value = os.getenv(env_key, default)
            return env_value
        
        return default
    
    # Application Settings
    @property
    def FLASK_ENV(self):
        return self._get_setting('app', 'environment', 'production', 'FLASK_ENV')
    
    @property
    def DEBUG(self):
        debug_setting = self._get_setting('app', 'debug', False)
        if isinstance(debug_setting, bool):
            return debug_setting
        if isinstance(debug_setting, str):
            return debug_setting.lower() in ("1", "true", "yes")
        return self.FLASK_ENV == "development"
    
    @property
    def SECRET_KEY(self):
        secret = self._get_setting('app', 'secret_key', None, 'SECRET_KEY')
        if not secret:
            if self.FLASK_ENV == "development":
                return "dev-secret-key-change-in-production"
            else:
                raise ValueError("SECRET_KEY must be set in settings or environment")
        return secret
    
    @property
    def APP_BASE_URL(self):
        return self._get_setting('app', 'base_url', 'https://admin.instainsure.co.in', 'APP_BASE_URL')
    
    # Company Information
    @property
    def COMPANY_NAME(self):
        return self._get_setting('company', 'name', 'Insta Insurance Consultancy')
    
    @property
    def PORTAL_NAME(self):
        return self._get_setting('company', 'portal_name', 'Insta Insurance Consultancy Portal')
    
    @property
    def PORTAL_TITLE(self):
        return self._get_setting('company', 'portal_title', 'Insta Insurances Portal')
    
    @property
    def LOGO_PATH(self):
        return self._get_setting('company', 'logo_path', 'ico.png')
    
    @property
    def COMPANY_LOGO_URL(self):
        return self._get_setting('company', 'logo_url', '')
    
    @property
    def COMPANY_ADDRESS(self):
        return self._get_setting('company', 'address', '')
    
    @property
    def COMPANY_PHONE(self):
        return self._get_setting('company', 'phone', '')
    
    @property
    def COMPANY_EMAIL(self):
        return self._get_setting('company', 'email', '')
    
    @property
    def COMPANY_WEBSITE(self):
        return self._get_setting('company', 'website', '')
    
    # Email Configuration
    @property
    def SMTP_SERVER(self):
        return self._get_setting('email', 'smtp_server', 'smtp.zoho.in', 'SMTP_SERVER')
    
    @property
    def SMTP_PORT(self):
        port = self._get_setting('email', 'smtp_port', 587, 'SMTP_PORT')
        return int(port) if port else 587
    
    @property
    def SMTP_USERNAME(self):
        return self._get_setting('email', 'smtp_username', None, 'SMTP_USERNAME')
    
    @property
    def SMTP_PASSWORD(self):
        return self._get_setting('email', 'smtp_password', None, 'SMTP_PASSWORD')
    
    @property
    def FROM_EMAIL(self):
        return self._get_setting('email', 'from_email', None, 'FROM_EMAIL')
    
    @property
    def FROM_NAME(self):
        return self._get_setting('email', 'from_name', 'Insta Insurance Consultancy', 'FROM_NAME')
    
    # WhatsApp Configuration
    @property
    def WHATSAPP_TOKEN(self):
        return self._get_setting('whatsapp', 'token', None, 'WHATSAPP_TOKEN')
    
    @property
    def WHATSAPP_PHONE_ID(self):
        return self._get_setting('whatsapp', 'phone_id', None, 'WHATSAPP_PHONE_ID')
    
    @property
    def VERIFY_TOKEN(self):
        return self._get_setting('whatsapp', 'verify_token', 'your_webhook_verify_token', 'VERIFY_TOKEN')
    
    # Twilio Configuration
    @property
    def TWILIO_ACCOUNT_SID(self):
        return self._get_setting('twilio', 'account_sid', '', 'TWILIO_ACCOUNT_SID')
    
    @property
    def TWILIO_AUTH_TOKEN(self):
        return self._get_setting('twilio', 'auth_token', '', 'TWILIO_AUTH_TOKEN')
    
    @property
    def TWILIO_WHATSAPP_FROM(self):
        return self._get_setting('twilio', 'whatsapp_from', 'whatsapp:+14155238886', 'TWILIO_WHATSAPP_FROM')
    
    @property
    def TWILIO_USE_CONTENT_TEMPLATE(self):
        use_template = self._get_setting('twilio', 'use_content_template', False)
        if isinstance(use_template, bool):
            return use_template
        # Handle string values from database or environment
        if isinstance(use_template, str):
            return use_template.lower() in ("1", "true", "yes")
        # Final fallback to environment variable
        env_value = os.getenv("TWILIO_USE_CONTENT_TEMPLATE", "false")
        return env_value.lower() in ("1", "true", "yes")
    
    @property
    def TWILIO_CONTENT_SID(self):
        return self._get_setting('twilio', 'content_sid', '', 'TWILIO_CONTENT_SID')
    
    # Google Drive Configuration
    @property
    def GOOGLE_CREDENTIALS_FILE(self):
        return self._get_setting('google_drive', 'credentials_file', 'credentials.json', 'GOOGLE_CREDENTIALS_FILE')
    
    @property
    def GOOGLE_DRIVE_ROOT_FOLDER_ID(self):
        return self._get_setting('google_drive', 'root_folder_id', '', 'GOOGLE_DRIVE_ROOT_FOLDER_ID')
    
    @property
    def ROOT_FOLDER_ID(self):
        """Alias for GOOGLE_DRIVE_ROOT_FOLDER_ID for backward compatibility"""
        return self.GOOGLE_DRIVE_ROOT_FOLDER_ID
    
    @property
    def ARCHIVE_FOLDER_ID(self):
        return self._get_setting('google_drive', 'archive_folder_id', 'YOUR_ARCHIVE_FOLDER_ID_HERE', 'ARCHIVE_FOLDER_ID')
    
    # Business Settings
    @property
    def DEFAULT_GST_PERCENTAGE(self):
        gst = self._get_setting('business', 'default_gst_percentage', 18.0)
        return float(gst) if gst else 18.0
    
    @property
    def DEFAULT_COMMISSION_PERCENTAGE(self):
        commission = self._get_setting('business', 'default_commission_percentage', 10.0)
        return float(commission) if commission else 10.0
    
    @property
    def RENEWAL_REMINDER_DAYS(self):
        days = self._get_setting('notifications', 'renewal_reminder_days', 30)
        return int(days) if days else 30
    
    @property
    def ENABLE_EMAIL_NOTIFICATIONS(self):
        enable_email = self._get_setting('notifications', 'enable_email_notifications', True)
        if isinstance(enable_email, bool):
            return enable_email
        if isinstance(enable_email, str):
            return enable_email.lower() in ("1", "true", "yes")
        return True
    
    @property
    def ENABLE_WHATSAPP_NOTIFICATIONS(self):
        enable_whatsapp = self._get_setting('notifications', 'enable_whatsapp_notifications', True)
        if isinstance(enable_whatsapp, bool):
            return enable_whatsapp
        if isinstance(enable_whatsapp, str):
            return enable_whatsapp.lower() in ("1", "true", "yes")
        return True
    
    # File Upload Settings
    @property
    def MAX_FILE_SIZE_MB(self):
        size = self._get_setting('uploads', 'max_file_size_mb', 10)
        return int(size) if size else 10
    
    @property
    def ALLOWED_EXTENSIONS(self):
        extensions = self._get_setting('uploads', 'allowed_extensions', ["pdf", "jpg", "jpeg", "png", "doc", "docx"])
        if isinstance(extensions, list):
            return extensions
        return ["pdf", "jpg", "jpeg", "png", "doc", "docx"]
    
    # Legacy compatibility - keep old admin emails system as fallback
    @property
    def ADMIN_EMAILS(self):
        """Legacy admin emails - now managed through user roles in database"""
        admin_emails_str = os.getenv("ADMIN_EMAILS", "")
        if admin_emails_str:
            return [email.strip() for email in admin_emails_str.split(",")]
        return []
    
    def get_company_info(self):
        """Get all company information as a dictionary"""
        return {
            'name': self.COMPANY_NAME,
            'logo_url': self.COMPANY_LOGO_URL,
            'address': self.COMPANY_ADDRESS,
            'phone': self.COMPANY_PHONE,
            'email': self.COMPANY_EMAIL,
            'website': self.COMPANY_WEBSITE
        }
    
    def get_email_config(self):
        """Get email configuration as a dictionary"""
        return {
            'smtp_server': self.SMTP_SERVER,
            'smtp_port': self.SMTP_PORT,
            'smtp_username': self.SMTP_USERNAME,
            'smtp_password': self.SMTP_PASSWORD,
            'from_email': self.FROM_EMAIL,
            'from_name': self.FROM_NAME
        }
    
    def refresh_settings(self):
        """Force refresh of settings from database"""
        if self._settings_service:
            self._settings_service.clear_cache()
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled"""
        feature_map = {
            'email_notifications': self.ENABLE_EMAIL_NOTIFICATIONS,
            'whatsapp_notifications': self.ENABLE_WHATSAPP_NOTIFICATIONS,
        }
        return feature_map.get(feature, False)


# Global configuration instance
Config = DynamicConfig()

# For backward compatibility, also create a class-based Config
class ConfigClass:
    """Backward compatibility class that delegates to DynamicConfig instance"""
    def __getattr__(self, name):
        return getattr(Config, name)

# Export both for different usage patterns
__all__ = ['Config', 'ConfigClass', 'DynamicConfig']
