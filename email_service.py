import smtplib
import os
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_email(to_email, subject, body, attachments=None, customer_name=None):
    """
    Send an email with optional attachments
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
        attachments (list): List of file paths to attach
        customer_name (str): Customer name for personalization
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if email configuration is available
        if not all([Config.SMTP_SERVER, Config.SMTP_USERNAME, Config.SMTP_PASSWORD, Config.FROM_EMAIL]):
            logger.warning("Email configuration incomplete. Skipping email send.")
            return False, "Email configuration incomplete"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{Config.FROM_NAME} <{Config.FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Personalize body if customer name is provided
        if customer_name:
            personalized_body = body.replace("Dear Customer,", f"Dear {customer_name},")
        else:
            personalized_body = body
        
        # Add body to email
        msg.attach(MIMEText(personalized_body, 'plain'))
        
        # Add attachments if provided
        if attachments:
            for attachment_path in attachments:
                if os.path.exists(attachment_path):
                    with open(attachment_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(attachment_path)}'
                    )
                    msg.attach(part)
                    logger.info(f"Attached file: {attachment_path}")
        
        # Connect to server and send email
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(Config.FROM_EMAIL, to_email, text)
        server.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False, str(e)


def send_policy_email(customer_email, customer_name, policy, file_path=None):
    """
    Send policy document via email
    
    Args:
        customer_email (str): Customer email address
        customer_name (str): Customer name
        policy (dict): Policy information
        file_path (str): Path to policy document file
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        subject = f"Your {policy.get('product_name','')} Policy Document - {policy.get('insurance_company','')}"
        
        body = f"""Dear {customer_name},

Please find attached your {policy.get('product_name','')} policy document from {policy.get('insurance_company','')}.

Policy Details:
- Product: {policy.get('product_name','')}
- Company: {policy.get('insurance_company','')}
- Policy ID: {policy.get('policy_id', 'N/A')}"""
        
        if policy.get('policy_to'):
            body += f"\n- Expiry Date: {policy['policy_to']}"
        
        body += f"""

If you have any questions or need assistance, please don't hesitate to contact us.

Best regards,
{Config.FROM_NAME}"""
        
        attachments = [file_path] if file_path and os.path.exists(file_path) else None
        
        return send_email(customer_email, subject, body, attachments, customer_name)
        
    except Exception as e:
        logger.error(f"Error sending policy email: {e}")
        return False, str(e)


def send_renewal_reminder_email(customer_email, customer_name, policy, file_path=None, payment_link=None):
    """
    Send renewal reminder via email
    
    Args:
        customer_email (str): Customer email address
        customer_name (str): Customer name
        policy (dict): Policy information
        file_path (str): Path to renewal document file
        payment_link (str): Payment link for renewal
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        subject = f"🔔 Renewal Reminder - {policy.get('product_name','')} Policy"
        
        body = f"""Dear {customer_name},

This is a friendly reminder that your {policy.get('product_name','')} policy with {policy.get('insurance_company','')} is expiring on {policy.get('policy_to')}.

Policy Details:
- Product: {policy.get('product_name','')}
- Company: {policy.get('insurance_company','')}
- Policy ID: {policy.get('policy_id', 'N/A')}
- Expiry Date: {policy.get('policy_to')}"""
        
        if payment_link:
            body += f"""

To renew your policy, please click on the following link:
{payment_link}"""
        
        body += f"""

Please ensure you renew your policy before the expiry date to maintain continuous coverage.

If you have any questions or need assistance with the renewal process, please don't hesitate to contact us.

Best regards,
{Config.FROM_NAME}"""
        
        attachments = [file_path] if file_path and os.path.exists(file_path) else None
        
        return send_email(customer_email, subject, body, attachments, customer_name)
        
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
