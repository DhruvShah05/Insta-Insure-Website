import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import Config
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def indian_date_filter(date_string):
    """Convert date from YYYY-MM-DD to DD/MM/YYYY format"""
    if not date_string:
        return 'N/A'
    
    try:
        if isinstance(date_string, str):
            if '/' in date_string and len(date_string.split('/')) == 3:
                parts = date_string.split('/')
                if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                    return date_string
            
            if '-' in date_string and len(date_string.split('-')) == 3:
                parts = date_string.split('-')
                if len(parts[0]) == 4:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
                elif len(parts[2]) == 4:
                    return f"{parts[0]}/{parts[1]}/{parts[2]}"
        
        if hasattr(date_string, 'strftime'):
            return date_string.strftime('%d/%m/%Y')
        
        try:
            date_obj = datetime.strptime(str(date_string), '%Y-%m-%d')
            return date_obj.strftime('%d/%m/%Y')
        except ValueError:
            try:
                date_obj = datetime.strptime(str(date_string), '%d/%m/%Y')
                return date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass
        
        return str(date_string)
    except Exception as e:
        logger.error(f"Error formatting date {date_string}: {e}")
        return str(date_string)

# Setup Jinja2 to load HTML templates
env = Environment(
    loader=FileSystemLoader('templates/email'),
    autoescape=select_autoescape(['html', 'xml'])
)

# Register the date filter for use in templates
env.filters['indian_date'] = indian_date_filter

def _render_template(template_name, context):
    """Loads and renders an email template with the given context."""
    try:
        template = env.get_template(template_name)
        return template.render(context)
    except Exception as e:
        logger.error(f"Error rendering email template {template_name}: {e}")
        return None

def send_email(to_email, subject, html_body, attachments=None):
    """
    Send an HTML email with optional attachments.
    """
    try:
        if not all([Config.SMTP_SERVER, Config.SMTP_USERNAME, Config.SMTP_PASSWORD, Config.FROM_EMAIL]):
            logger.warning("Email configuration incomplete. Skipping email send.")
            return False, "Email configuration incomplete"

        msg = MIMEMultipart()
        msg['From'] = f"{Config.FROM_NAME} <{Config.FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_body, 'html'))

        if attachments:
            for attachment_path in attachments:
                if os.path.exists(attachment_path):
                    with open(attachment_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(attachment_path)}')
                    msg.attach(part)
                    logger.info(f"Attached file: {attachment_path}")

        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.sendmail(Config.FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False, str(e)


def send_policy_email(customer_email, policy_data, file_path=None):
    """
    Render and send the 'Policy Issued' email.
    """
    try:
        # Use the official policy number in the subject
        subject = f"Your {policy_data.get('policy_type','')} Policy Document – {policy_data.get('policy_no','')}"

        # Create the context for the template
        context = policy_data.copy()
        context['app_base_url'] = Config.APP_BASE_URL

        html_body = _render_template('policy_issued_template.html', context)
        if not html_body:
            return False, "Failed to render email template"

        attachments = [file_path] if file_path and os.path.exists(file_path) else None
        
        return send_email(customer_email, subject, html_body, attachments)

    except Exception as e:
        logger.error(f"Error sending policy email: {e}")
        return False, str(e)


def send_renewal_reminder_email(customer_email, renewal_data, file_path=None):
    """
    Render and send the 'Renewal Reminder' email.
    """
    try:
        subject = f"🔔 Renewal Reminder – Policy No: {renewal_data.get('policy_no', '')}"
        
        # Create the context for the template
        context = renewal_data.copy()
        context['app_base_url'] = Config.APP_BASE_URL

        html_body = _render_template('renewal_reminder_template.html', context)
        if not html_body:
            return False, "Failed to render email template"

        attachments = [file_path] if file_path and os.path.exists(file_path) else None
        
        return send_email(customer_email, subject, html_body, attachments)

    except Exception as e:
        logger.error(f"Error sending renewal reminder email: {e}")
        return False, str(e)


def get_customer_email(phone):
    """
    Get customer email from database using phone number
    
    Args:
        phone (str): Customer phone number
    
    Returns:
        str: Customer email address or None
    """
    try:
        from supabase import create_client
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        
        # Try different phone number formats against clients table
        normalized_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        
        for phone_format in [normalized_phone, f'+{normalized_phone}', phone]:
            client_response = supabase.table('clients').select('email').eq('phone', phone_format).execute()
            if client_response.data:
                return client_response.data[0].get('email')
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching customer email: {e}")
        return None
