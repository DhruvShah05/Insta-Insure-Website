import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Environment
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if FLASK_ENV == "development":
            SECRET_KEY = "dev-secret-key-change-in-production"
        else:
            raise ValueError("SECRET_KEY environment variable must be set for production")

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    # Simple Authentication (replaces Clerk)
    # No external authentication service needed - using Supabase directly

    # Admin Emails (for user authorization)
    ADMIN_EMAILS_STR = os.getenv("ADMIN_EMAILS", "")
    if not ADMIN_EMAILS_STR:
        raise ValueError("ADMIN_EMAILS must be set with comma-separated email addresses")
    ADMIN_EMAILS = [email.strip() for email in ADMIN_EMAILS_STR.split(",")]

    # WhatsApp Configuration
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "your_webhook_verify_token")

    # Google Drive Configuration
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

    # Archive Folder ID - Get this from your Google Drive Archive folder URL
    ARCHIVE_FOLDER_ID = os.getenv("ARCHIVE_FOLDER_ID", "YOUR_ARCHIVE_FOLDER_ID_HERE")

    # Email Configuration (Updated for Zoho Mail)
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.zoho.in")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Use your Zoho App Password here
    FROM_EMAIL = os.getenv("FROM_EMAIL")  # Should be the same as SMTP_USERNAME
    FROM_NAME = os.getenv("FROM_NAME", "Insta Insurance Consultancy")

    # Twilio WhatsApp
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    TWILIO_USE_CONTENT_TEMPLATE = os.getenv("TWILIO_USE_CONTENT_TEMPLATE", "false").lower() in ("1", "true", "yes")
    TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID", "")

    # Public base URL (for Twilio to fetch media); set to your deployed URL
    APP_BASE_URL = os.getenv("APP_BASE_URL", "https://admin.instainsure.co.in")