from flask import request, jsonify
import os
import time
from supabase import create_client
from config import Config
import tempfile
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from email_service import send_policy_email, send_renewal_reminder_email, get_customer_email, indian_date_filter
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import quote
import json
import requests
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize Supabase
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Twilio WhatsApp Configuration
TWILIO_ACCOUNT_SID = Config.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = Config.TWILIO_AUTH_TOKEN
TWILIO_FROM = Config.TWILIO_WHATSAPP_FROM  # e.g., 'whatsapp:+14155238886'
TWILIO_USE_CONTENT_TEMPLATE = Config.TWILIO_USE_CONTENT_TEMPLATE
TWILIO_CONTENT_SID = Config.TWILIO_CONTENT_SID
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'your_webhook_verify_token')
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else None

# Content Template SIDs - APPROVED TEMPLATES
POLICY_DOCUMENT_TEMPLATE_SID = "HX09943977f51524767ed93c7cc670fb47"  # Policy Issued Template
RENEWAL_REMINDER_TEMPLATE_SID = "HX169afdf8bae849bb296476c9d4e4db9d"   # Renewal Reminder Template

# WhatsApp Media Configuration
USE_CONTENT_TEMPLATES = os.getenv('USE_WHATSAPP_CONTENT_TEMPLATES', 'true').lower() == 'true'

# Google Drive Configuration
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

# Store user sessions
user_sessions = {}

# Track processed messages to prevent duplicates
processed_messages = {}  # Track processed message IDs
MESSAGE_EXPIRY = 300  # 5 minutes

# Store temporary renewal files (cleaned up automatically when temp files are deleted)
temp_renewal_files = {}


def is_duplicate_message(message_id):
    """Check if message was already processed and clean old entries"""
    current_time = time.time()

    # Clean up old message IDs
    expired_ids = [mid for mid, timestamp in processed_messages.items()
                   if current_time - timestamp > MESSAGE_EXPIRY]
    for mid in expired_ids:
        del processed_messages[mid]

    # Check if this message was already processed
    if message_id in processed_messages:
        return True

    # Mark as processed
    processed_messages[message_id] = current_time
    return False


def send_whatsapp_message(to_number, message_text):
    """Send a WhatsApp text message via Twilio. If configured, use Content Template."""
    if not twilio_client:
        return {"error": "Twilio not configured"}
    try:
        if TWILIO_USE_CONTENT_TEMPLATE and TWILIO_CONTENT_SID:
            msg = twilio_client.messages.create(
                from_=format_whatsapp_address(TWILIO_FROM),
                content_sid=TWILIO_CONTENT_SID,
                content_variables=json.dumps({"1": message_text}),
                to=format_whatsapp_address(to_number)
            )
        else:
            msg = twilio_client.messages.create(
                from_=format_whatsapp_address(TWILIO_FROM),
                body=message_text,
                to=format_whatsapp_address(to_number)
            )
        return {"sid": msg.sid}
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return {"error": str(e)}


def send_content_template_message(to_number, content_sid, variables, media_url=None):
    """Send a WhatsApp message using Content Template with optional media"""
    if not twilio_client:
        return {"error": "Twilio not configured"}
    
    try:
        message_params = {
            'from_': format_whatsapp_address(TWILIO_FROM),
            'content_sid': content_sid,
            'content_variables': json.dumps(variables),
            'to': format_whatsapp_address(to_number)
        }
        
        # Add media URL if provided
        if media_url:
            message_params['media_url'] = [media_url]
        
        msg = twilio_client.messages.create(**message_params)
        return {"sid": msg.sid}
    except Exception as e:
        logger.error(f"Error sending content template message: {e}")
        return {"error": str(e)}


def send_policy_document_whatsapp(phone, policy, customer_name):
    """
    Send policy document via WhatsApp using the appropriate method:
    - Content Templates (for approved templates)
    - Traditional media messages (for Google Drive files)
    """
    if not twilio_client:
        return {"error": "Twilio not configured"}
    
    try:
        # Get file information
        file_id = extract_file_id_from_url(policy.get('drive_url'))
        if not file_id:
            return {"error": "No drive URL found"}
        
        # Format dates
        coverage_start = policy.get('policy_from', '')
        expiry_date = policy.get('policy_to', '')
        
        # Convert dates to Indian format (DD/MM/YYYY)
        if coverage_start and isinstance(coverage_start, str) and '-' in coverage_start:
            parts = coverage_start.split('-')
            if len(parts) == 3 and len(parts[0]) == 4:
                coverage_start = f"{parts[2]}/{parts[1]}/{parts[0]}"
        
        if expiry_date and isinstance(expiry_date, str) and '-' in expiry_date:
            parts = expiry_date.split('-')
            if len(parts) == 3 and len(parts[0]) == 4:
                expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
        
        # Use approved Content Templates with dynamic media URLs
        if USE_CONTENT_TEMPLATES:
            # Generate the media URL path for template variable {{7}}
            filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
            safe_filename = quote(filename, safe='')
            media_path = f"media/drive/{file_id}/{safe_filename}"  # Path only, not full URL
            
            # Prepare template variables for approved template
            template_variables = {
                "1": customer_name,
                "2": policy.get('product_name', 'Insurance Policy'),
                "3": policy.get('policy_number', 'N/A'),
                "4": policy.get('remarks', 'N/A'),
                "5": coverage_start or 'N/A',
                "6": expiry_date or 'N/A',
                "7": media_path  # This will be used in template as: https://admin.instainsure.co.in/{{7}}
            }
            
            return send_content_template_message(
                phone, 
                POLICY_DOCUMENT_TEMPLATE_SID, 
                template_variables, 
                None  # No separate media_url needed since it's in template
            )
        
        else:
            # Fallback: Traditional approach with media URL (Google Drive files)
            filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
            safe_filename = quote(filename, safe='')
            base_url = Config.APP_BASE_URL.rstrip('/')
            media_url = f"{base_url}/media/drive/{file_id}/{safe_filename}"
            
            # Create message body using template format
            message_body = f"""Hello {customer_name}!

We're happy to inform you that your new *{policy.get('product_name', 'Insurance Policy')}* policy has been successfully issued.

Company: {policy.get('insurance_company', '')}
Policy Number: {policy.get('policy_number', 'N/A')}
Coverage Start Date: {coverage_start or 'N/A'}
Expiry Date: {expiry_date or 'N/A'}

You can reply with *HI* anytime to view all your policy documents.

Best regards,
Insta Insurance Consultancy"""

            # Send with media attachment
            msg = twilio_client.messages.create(
                from_=format_whatsapp_address(TWILIO_FROM),
                body=message_body,
                media_url=[media_url],
                to=format_whatsapp_address(phone)
            )
            
            return {"sid": msg.sid}
            
    except Exception as e:
        logger.error(f"Error sending policy document via WhatsApp: {e}")
        return {"error": str(e)}


def send_list_picker_message(to, body_text, button_text, items, variables=None):
    """Send a list picker message using Twilio Content API"""
    if not twilio_client:
        return {"error": "Twilio not configured"}
        
    try:
        # Create a unique friendly name for this content template
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        friendly_name = f"policy_list_{timestamp}"
        
        # Prepare content template data following Twilio docs exactly
        content_data = {
            "friendly_name": friendly_name,
            "language": "en",
            "variables": variables or {"1": "customer_name"},
            "types": {
                "twilio/list-picker": {
                    "body": body_text,
                    "button": button_text,
                    "items": items
                },
                "twilio/text": {
                    "body": body_text + "\n\n" + "\n".join([f"{i+1}. {item['item']}" for i, item in enumerate(items)])
                }
            }
        }
        
        print(f"Creating content template with data: {json.dumps(content_data, indent=2)}")
        
        # Create content template using Twilio REST API
        url = "https://content.twilio.com/v1/Content"
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(url, json=content_data, auth=auth, headers=headers)
        
        print(f"Content template creation response: {response.status_code} - {response.text}")
        
        if response.status_code == 201:
            content = response.json()
            content_sid = content.get('sid')
            print(f"Content template created successfully: {content_sid}")
            
            # Send message using the content template
            msg = twilio_client.messages.create(
                from_=format_whatsapp_address(TWILIO_FROM),
                content_sid=content_sid,
                content_variables=json.dumps(variables or {}),
                to=format_whatsapp_address(to)
            )
            
            return {"sid": msg.sid, "content_sid": content_sid}
        else:
            print(f"Error creating content template: {response.status_code} - {response.text}")
            # Fallback to plain text menu
            return send_interactive_list_fallback(to, body_text, button_text, items)
            
    except Exception as e:
        print(f"Error sending list picker message: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to plain text menu
        return send_interactive_list_fallback(to, body_text, button_text, items)


def send_interactive_list_fallback(to, body_text, button_text, items):
    """Fallback to plain text menu when list picker fails"""
    menu_lines = [body_text, ""]
    for idx, item in enumerate(items):
        menu_lines.append(f"{item.get('id', idx)}. {item.get('item', item.get('title', ''))}")
    menu_lines.append("\nReply with the number to choose.")
    return send_whatsapp_message(to, "\n".join(menu_lines))


def send_interactive_list(to, body_text, button_text, sections):
    """If content template is enabled, send with ContentSID and vars; else send a plain text menu."""
    if TWILIO_USE_CONTENT_TEMPLATE and TWILIO_CONTENT_SID:
        # Flatten first 10 items as variables for a template like: 1) {{1}}, 2) {{2}}, ...
        rows = sections[0]['rows'] if sections else []
        variables = {str(i + 1): rows[i].get('title', '') for i in range(min(10, len(rows)))}
        variables['body'] = body_text
        try:
            msg = twilio_client.messages.create(
                from_=format_whatsapp_address(TWILIO_FROM),
                content_sid=TWILIO_CONTENT_SID,
                content_variables=json.dumps(variables),
                to=format_whatsapp_address(to)
            )
            return {"sid": msg.sid}
        except Exception as e:
            print(f"Error sending content template: {e}")
            # Fallback to plain text menu
    # Plain text fallback
    menu_lines = [body_text, ""]
    for idx, row in enumerate(sections[0]['rows'] if sections else []):
        menu_lines.append(f"{row.get('id', idx)}. {row.get('title','')}")
    menu_lines.append("\nReply with the number to choose.")
    return send_whatsapp_message(to, "\n".join(menu_lines))


def upload_media_to_whatsapp(file_path):
    """No-op in Twilio flow (uses media_url). Kept for backward compatibility."""
    return None


def send_document(to, media_url, filename, caption=''):
    """Send a document via Twilio WhatsApp using media_url"""
    if not twilio_client:
        return {"error": "Twilio not configured"}
    try:
        msg = twilio_client.messages.create(
            from_=format_whatsapp_address(TWILIO_FROM),
            body=caption if caption else None,
            media_url=[media_url],
            to=format_whatsapp_address(to)
        )
        return {"sid": msg.sid}
    except Exception as e:
        print(f"Error sending document: {e}")
        return {"error": str(e)}


def get_drive_service():
    """Initialize Google Drive service"""
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error initializing Google Drive service: {e}")
        return None


def extract_file_id_from_url(drive_url):
    """Extract file ID from Google Drive URL"""
    if not drive_url:
        return None

    if '/file/d/' in drive_url:
        file_id = drive_url.split('/file/d/')[1].split('/')[0]
    elif '/open?id=' in drive_url:
        file_id = drive_url.split('/open?id=')[1].split('&')[0]
    elif 'id=' in drive_url:
        file_id = drive_url.split('id=')[1].split('&')[0]
    else:
        file_id = drive_url.strip()

    return file_id


def download_file_from_drive(file_id, filename):
    """Download file from Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            return None

        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, filename)

        request_obj = service.files().get_media(fileId=file_id)
        fh = io.FileIO(temp_file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request_obj)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.close()
        return temp_file_path

    except Exception as e:
        print(f"Error downloading file from Drive: {e}")
        return None


def delete_temp_file(file_path):
    """Delete temporary file with retry logic"""
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                # Close any file handles first
                time.sleep(0.5)  # Give system time to release file
                os.remove(file_path)
                print(f"Successfully deleted temp file: {file_path}")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} deleting file: {e}")
                time.sleep(retry_delay)
            else:
                print(f"Warning: Could not delete temp file after {max_retries} attempts: {e}")
                # Don't raise error - just log it
                return False
    return False


def normalize_phone(phone):
    """Normalize phone number"""
    return phone.replace('+', '').replace(' ', '').replace('-', '')


def format_whatsapp_address(number: str) -> str:
    """Ensure Twilio WhatsApp address format: 'whatsapp:+<E164>'"""
    # If already in whatsapp format, return as is
    if number.startswith('whatsapp:'):
        return number
    # Otherwise, format it properly
    return f"whatsapp:+{normalize_phone(number)}"


def get_customer_policies(phone):
    """Fetch client and policies from Supabase"""
    normalized_phone = normalize_phone(phone)

    try:
        for phone_format in [normalized_phone, f'+{normalized_phone}', phone]:
            client_response = supabase.table('clients').select('*').eq('phone', phone_format).execute()
            if client_response.data:
                break

        if not client_response.data:
            return None, []

        client = client_response.data[0]
        client_id = client['client_id']

        policies_response = supabase.table('policies').select('*').eq('client_id', client_id).execute()
        return client, policies_response.data

    except Exception as e:
        print(f"Error fetching customer policies: {e}")
        return None, []


def send_all_policies_to_customer(phone, policies):
    """Send all policy documents to customer in one email and individual WhatsApp messages"""
    try:
        if not phone or not policies:
            logger.error(f"Invalid parameters: phone={phone}, policies_count={len(policies) if policies else 0}")
            return False, "Invalid phone number or no policies provided"
            
        if not isinstance(policies, list) or len(policies) == 0:
            logger.error(f"Invalid policies data: {type(policies)}")
            return False, "No valid policies found"
            
        whatsapp_success_count = 0
        email_success = False
        email_message = ""
        
        logger.info(f"Sending {len(policies)} policies to {phone}")
        
        # Send each policy via WhatsApp individually (WhatsApp doesn't support multiple attachments)
        for policy in policies:
            success, msg = send_policy_to_customer(phone, policy, send_email=False)  # Skip email for individual policies
            if success:
                whatsapp_success_count += 1
        
        # Send all policies in ONE email with multiple attachments
        try:
            customer_email = get_customer_email(phone)
        except Exception as e:
            logger.error(f"Error getting customer email for {phone}: {e}")
            customer_email = None
            
        if customer_email:
            try:
                client, _ = get_customer_policies(phone)
                customer_name = client['name'] if client else "Customer"
            except Exception as e:
                logger.error(f"Error getting customer data for {phone}: {e}")
                customer_name = "Customer"
            
            # Download all policy files temporarily
            temp_files = []
            policy_details = []
            download_errors = []
            
            for policy in policies:
                if policy.get('drive_url'):
                    try:
                        file_id = extract_file_id_from_url(policy.get('drive_url'))
                        if file_id:
                            filename = f"{policy.get('insurance_company', 'Policy')}_{policy.get('product_name', 'Document')}.pdf".replace(' ', '_')
                            temp_file_path = download_file_from_drive(file_id, filename)
                            if temp_file_path:
                                temp_files.append(temp_file_path)
                                
                                # Format expiry date
                                expiry_date = policy.get('policy_to', 'N/A')
                                if expiry_date and expiry_date != 'N/A':
                                    try:
                                        if isinstance(expiry_date, str) and '-' in expiry_date:
                                            parts = expiry_date.split('-')
                                            if len(parts) == 3 and len(parts[0]) == 4:
                                                expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                                    except:
                                        pass
                                
                                policy_details.append({
                                    'insurance': policy.get('product_name', 'Insurance Policy'),
                                    'company': policy.get('insurance_company', ''),
                                    'policy_number': policy.get('policy_number', 'N/A'),
                                    'expiry': expiry_date
                                })
                    except Exception as e:
                        error_msg = f"Failed to download {policy.get('product_name', 'policy')}: {str(e)}"
                        download_errors.append(error_msg)
                        logger.error(f"Download error for policy {policy.get('policy_id')}: {e}")
                else:
                    download_errors.append(f"No drive URL for {policy.get('product_name', 'policy')}")
            
            # Send one email with all attachments
            if temp_files:
                subject = f"Your Insurance Policy Documents - {len(temp_files)} Policies"
                
                body = f"""Dear {customer_name},

Thank you for using Insta Insurance Consultancy Portal! Please find all your insurance policy documents attached to this email.

Policy Summary:
"""
                for i, details in enumerate(policy_details, 1):
                    body += f"""
{i}. {details['insurance']}
   • Company: {details['company']}
   • Policy Number: {details['policy_number']}
   • Expiry Date: {details['expiry']}
"""
                
                body += f"""

All {len(temp_files)} policy documents are attached to this email for your records.

For any queries or assistance, please feel free to contact us.

Thank you for choosing our services!

Best regards,
Insta Insurance Consultancy Portal"""

                try:
                    from email_service import send_email
                    email_success, email_message = send_email(
                        customer_email, 
                        subject, 
                        body, 
                        attachments=temp_files,
                        customer_name=customer_name
                    )
                    if email_success:
                        logger.info(f"Successfully sent {len(temp_files)} policies via email to {customer_email}")
                    else:
                        logger.error(f"Email sending failed: {email_message}")
                except Exception as e:
                    email_success = False
                    email_message = f"Email service error: {str(e)}"
                    logger.error(f"Email service error: {e}")
                
                # Clean up temp files
                for temp_file in temp_files:
                    try:
                        import os
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
        
        # Prepare response messages
        messages = []
        if whatsapp_success_count > 0:
            messages.append(f"WhatsApp: {whatsapp_success_count}/{len(policies)} documents sent")
        else:
            messages.append("WhatsApp: Failed to send documents")

        if email_success:
            messages.append(f"Email: All {len(policies)} documents sent in one email")
        else:
            messages.append(f"Email: {email_message}")

        overall_success = whatsapp_success_count > 0 or email_success
        return overall_success, " | ".join(messages)
        
    except Exception as e:
        logger.error(f"Error sending all policies to customer: {e}")
        return False, str(e)


def send_policy_to_customer(phone, policy, send_email=True):
    """Send a single policy document to customer via WhatsApp and email"""
    temp_file_path = None
    try:
        file_id = extract_file_id_from_url(policy.get('drive_url'))
        if not file_id:
            return False, "No drive URL found"

        filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
        
        # For email, we need to download the file temporarily
        if send_email:
            temp_file_path = download_file_from_drive(file_id, filename)
            if not temp_file_path:
                return False, "Could not download file for email"

        # Send via WhatsApp using the appropriate method
        whatsapp_success = False
        if policy.get('drive_url'):
            # Get customer name
            try:
                client, _ = get_customer_policies(phone)
                customer_name = client['name'] if client else "Customer"
            except:
                customer_name = "Customer"
            
            # Send policy document via WhatsApp
            send_res = send_policy_document_whatsapp(phone, policy, customer_name)
            whatsapp_success = not send_res.get('error')
            
            if send_res.get('error'):
                logger.error(f"WhatsApp sending failed: {send_res['error']}")
            else:
                logger.info(f"Policy document sent via WhatsApp to {phone}: {send_res.get('sid')}")

        # Send via email (only if send_email is True)
        email_success = False
        email_message = ""

        if send_email:
            customer_email = get_customer_email(phone)
            if customer_email:
                client, _ = get_customer_policies(phone)
                customer_name = client['name'] if client else "Customer"

                # Prepare policy data for the new template-based function
                policy_data = {
                    'client_name': customer_name,
                    'policy_type': policy.get('product_name', 'Insurance'),
                    'policy_no': policy.get('policy_number', 'N/A'),
                    'asset': policy.get('remarks', 'N/A'),
                    'start_date': indian_date_filter(policy.get('policy_from')),
                    'expiry_date': indian_date_filter(policy.get('policy_to'))
                }
                
                email_success, email_message = send_policy_email(
                    customer_email, policy_data, temp_file_path
                )
            else:
                email_message = "No email address found for customer"

        # Prepare response message
        messages = []
        if whatsapp_success:
            messages.append("WhatsApp: Document sent successfully")
        else:
            messages.append("WhatsApp: Failed to send")

        if send_email:
            if email_success:
                messages.append("Email: Document sent successfully")
            else:
                messages.append(f"Email: {email_message}")

        overall_success = whatsapp_success or (send_email and email_success)
        return overall_success, " | ".join(messages)

    except Exception as e:
        print(f"Error sending policy: {e}")
        return False, str(e)
    finally:
        # Clean up temp file in finally block with delay
        if temp_file_path:
            time.sleep(1)  # Wait for all operations to complete
            delete_temp_file(temp_file_path)


def send_renewal_reminder(phone, policy, renewal_filename=None, payment_link=None):
    """Send renewal reminder with optional file or payment link via WhatsApp and email"""
    try:
        # Get member name for template (use member name instead of client name)
        try:
            # Get member name from policy data if available
            member_name = "Customer"  # Default fallback
            if policy.get('members') and policy['members'].get('member_name'):
                member_name = policy['members']['member_name']
            else:
                # Fallback to client name if member name not available
                customer, _ = get_customer_policies(phone)
                member_name = customer['name'] if customer else "Customer"
        except:
            member_name = "Customer"
        
        # Convert expiry date to Indian format
        expiry_date = policy.get('policy_to') or policy.get('expiry_date')
        if isinstance(expiry_date, str) and '-' in expiry_date:
            parts = expiry_date.split('-')
            if len(parts) == 3 and len(parts[0]) == 4:
                expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
        
        # Prepare template variables for approved renewal template
        template_variables = {
            "1": member_name,
            "2": policy.get('policy_number', 'N/A'),
            "3": policy.get('insurance_company', ''),
            "4": policy.get('remarks', 'N/A'),
            "5": expiry_date or 'N/A',
            "6": "Please contact us for renewal assistance.",  # Default message
            "7": "test-policy.pdf"  # Default media path for renewal reminders
        }
        
        # Handle user-uploaded content - simplified approach
        if payment_link:
            # Payment link provided - include in message
            template_variables["6"] = f"💳 *Renew Now:* {payment_link}"
            # Use default test PDF for media since we have payment link
            template_variables["7"] = "test-policy.pdf"
        elif renewal_filename:
            # User uploaded a renewal document - it's already saved in static/renewals
            media_path = f"static/renewals/{renewal_filename}"
            template_variables["6"] = "Renewal document attached below."
            template_variables["7"] = media_path
            
            logger.info(f"Using renewal document for WhatsApp: {media_path}")
            
            # Schedule cleanup after 1 hour (enough time for WhatsApp to fetch)
            import threading
            def cleanup_file():
                time.sleep(3600)  # Wait 1 hour
                try:
                    static_file_path = os.path.join(os.path.dirname(__file__), 'static', 'renewals', renewal_filename)
                    if os.path.exists(static_file_path):
                        os.remove(static_file_path)
                        logger.info(f"Cleaned up renewal document: {static_file_path}")
                except Exception as e:
                    logger.error(f"Error cleaning up renewal document: {e}")
            
            cleanup_thread = threading.Thread(target=cleanup_file, daemon=True)
            cleanup_thread.start()
        else:
            # No payment link or file - use default message and test PDF
            template_variables["6"] = "Please contact us for renewal assistance."
            template_variables["7"] = "test-policy.pdf"
        
        # Send using approved renewal reminder content template
        send_res = send_content_template_message(
            phone, 
            RENEWAL_REMINDER_TEMPLATE_SID, 
            template_variables, 
            None  # No separate media_url needed since it's in template
        )
        whatsapp_success = not send_res.get('error')
            
        # Send via email
        email_success = False
        email_message = ""

        customer_email = get_customer_email(phone)
        if customer_email:
            customer, _ = get_customer_policies(phone)
            customer_name = customer['name'] if customer else "Customer"

            # For email, construct file path if renewal filename exists
            email_file_path = None
            if renewal_filename:
                email_file_path = os.path.join(os.path.dirname(__file__), 'static', 'renewals', renewal_filename)
            
            # Prepare renewal data for the new template-based function
            renewal_data = {
                'client_name': customer_name,
                'policy_no': policy.get('policy_number', policy.get('policy_id', 'N/A')),
                'asset': policy.get('remarks', 'N/A'),
                'company': policy.get('insurance_company', 'N/A'),
                'expiry_date': policy.get('policy_to', 'N/A'),
                'payment_link': payment_link
            }
            
            email_success, email_message = send_renewal_reminder_email(
                customer_email, renewal_data, email_file_path
            )
        else:
            email_message = "No email address found for customer"

        # Update last_reminder_sent timestamp if either channel succeeded
        if whatsapp_success or email_success:
            try:
                from datetime import datetime
                current_time = datetime.now().isoformat()

                update_result = supabase.table('policies').update({
                    'last_reminder_sent': current_time
                }).eq('policy_id', policy['policy_id']).execute()

                print(f"Updated last_reminder_sent for policy {policy['policy_id']}")
            except Exception as e:
                print(f"Warning: Could not update last_reminder_sent: {e}")

        # Prepare response message
        messages = []
        if whatsapp_success:
            messages.append("WhatsApp: Reminder sent successfully")
        else:
            messages.append("WhatsApp: Failed to send")

        if email_success:
            messages.append("Email: Reminder sent successfully")
        else:
            messages.append(f"Email: {email_message}")

        overall_success = whatsapp_success or email_success
        return overall_success, " | ".join(messages)

    except Exception as e:
        print(f"Error sending renewal reminder: {e}")
        return False, str(e)


def handle_greeting(phone, page=0):
    """Handle HI greeting - now with list picker functionality and pagination"""
    customer, policies = get_customer_policies(phone)

    if not customer:
        send_whatsapp_message(phone, "Sorry, we couldn't find your records. Please contact support.")
        return

    if not policies:
        send_whatsapp_message(phone, f"Hello {customer['name']}! You don't have any active policies.")
        return

    user_sessions[phone] = {
        'customer': customer,
        'policies': policies,
        'state': 'policy_selection',
        'current_page': page
    }

    # Pagination settings
    MAX_ITEMS_PER_PAGE = 8  # Leave room for navigation and "Send All" buttons
    TITLE_CHAR_LIMIT = 24  # Twilio's actual limit is 24 characters
    DESCRIPTION_CHAR_LIMIT = 72
    
    total_policies = len(policies)
    total_pages = (total_policies + MAX_ITEMS_PER_PAGE - 1) // MAX_ITEMS_PER_PAGE
    
    # Calculate start and end indices for current page
    start_idx = page * MAX_ITEMS_PER_PAGE
    end_idx = min(start_idx + MAX_ITEMS_PER_PAGE, total_policies)
    current_page_policies = policies[start_idx:end_idx]
    
    # Prepare list picker items for current page
    items = []
    
    for i, policy in enumerate(current_page_policies):
        # Use remarks if available, otherwise fallback to company-policy type
        if policy.get('remarks'):
            policy_title = policy['remarks']
        else:
            policy_title = f"{policy.get('insurance_company','')} - {policy.get('product_name','')}"

        # Truncate title to character limit
        if len(policy_title) > TITLE_CHAR_LIMIT:
            policy_title = policy_title[:TITLE_CHAR_LIMIT-3] + "..."

        # Format expiry date for display
        expiry_display = ""
        if policy.get('policy_to'):
            expiry_date = policy['policy_to']
            if isinstance(expiry_date, str) and '-' in expiry_date:
                parts = expiry_date.split('-')
                if len(parts) == 3 and len(parts[0]) == 4:
                    expiry_display = f" | Exp: {parts[2]}/{parts[1]}/{parts[0]}"
        
        description = f"{policy.get('policy_number', 'Policy Document')}{expiry_display}"
        if len(description) > DESCRIPTION_CHAR_LIMIT:
            description = description[:DESCRIPTION_CHAR_LIMIT-3] + "..."
        
        items.append({
            "item": policy_title,
            "description": description,
            "id": str(start_idx + i)  # Global index across all pages
        })

    # Add next page button if needed
    if page < total_pages - 1:
        items.append({
            "item": "➡️ Next Page",
            "description": f"Go to page {page+2}",
            "id": f"next_{page+1}"
        })

    # Add "Send All Documents" option (always available)
    items.append({
        "item": "📄 Send All Documents",
        "description": "Get all policy documents",
        "id": "all"
    })

    # Greeting message for list picker
    page_info = f" (Page {page+1}/{total_pages})" if total_pages > 1 else ""
    greeting_msg = f"Hello {customer['name']}! 👋\n\n"
    greeting_msg += f"Welcome to Insta Insurance Consultancy Portal. We found {total_policies} insurance policy/policies for you{page_info}.\n\n"
    greeting_msg += "📋 Please select which document you'd like to receive:"

    # Send list picker message
    result = send_list_picker_message(
        phone, 
        greeting_msg, 
        "Select Policy", 
        items,
        variables={"1": customer['name']}  # Can be used in template if needed
    )
    
    if result.get('error'):
        print(f"List picker failed, falling back to text menu: {result['error']}")
        # Fallback to original interactive list if list picker fails
        sections = [{'title': 'Your Policies', 'rows': []}]
        for item in items:
            sections[0]['rows'].append({
                'id': item['id'],
                'title': item['item'],
                'description': item['description']
            })
        send_interactive_list(phone, greeting_msg, 'Select Policy', sections)


def handle_policy_selection(phone, selection_id):
    """Handle policy selection from list picker or text input with pagination support"""
    if phone not in user_sessions:
        send_whatsapp_message(phone, "❌ Your session has expired. Please reply with *HI* to start again.")
        return

    session = user_sessions[phone]
    policies = session['policies']
    customer = session['customer']

    print(f"Processing policy selection for {phone}: '{selection_id}'")

    # Handle pagination navigation
    if selection_id.startswith('next_'):
        try:
            next_page = int(selection_id.split('_')[1])
            handle_greeting(phone, next_page)
            return
        except (ValueError, IndexError):
            send_whatsapp_message(phone, "❌ Invalid navigation. Please reply with *HI* to start again.")
            return

    # Handle "Send All Documents" selection
    if selection_id.lower() == 'all':
        send_whatsapp_message(phone, f"📤 Sending all {len(policies)} policy documents...")

        # Use the new function that sends all policies in one email
        success, msg = send_all_policies_to_customer(phone, policies)

        if success:
            send_whatsapp_message(phone,
                                  f"✅ All {len(policies)} policy documents sent successfully!\n\n"
                                  f"📧 All documents have been sent in one email for your convenience.\n\n"
                                  f"Thank you for using Insta Insurance Consultancy Portal.\n\n"
                                  f"Reply with *HI* anytime to access your documents again.")
        else:
            send_whatsapp_message(phone,
                                  f"❌ There was an issue sending your documents: {msg}\n\n"
                                  f"Please try again by replying with *HI*.")

        # Clean up session
        if phone in user_sessions:
            del user_sessions[phone]
        return

    # Handle individual policy selection
    try:
        policy_index = int(selection_id)
        if 0 <= policy_index < len(policies):
            policy = policies[policy_index]
            policy_name = policy.get('remarks') or f"{policy.get('insurance_company', '')} - {policy.get('product_name', '')}"
            
            # Truncate policy name for display if too long
            if len(policy_name) > 50:
                display_name = policy_name[:47] + "..."
            else:
                display_name = policy_name
                
            send_whatsapp_message(phone, f"📤 Sending {display_name} document...")

            success, msg = send_policy_to_customer(phone, policy)

            if success:
                send_whatsapp_message(phone,
                                      f"✅ {display_name} document sent successfully!\n\n"
                                      f"📧 Document has been sent via email and WhatsApp.\n\n"
                                      f"Thank you for using Insta Insurance Consultancy Portal.\n\n"
                                      f"Reply with *HI* anytime to access your documents again.")
            else:
                send_whatsapp_message(phone, f"❌ Sorry, there was an error sending {display_name}: {msg}\n\nPlease try again by replying with *HI*.")

        else:
            send_whatsapp_message(phone, f"❌ Invalid selection '{selection_id}'. Please reply with *HI* to start again and select a valid option.")
    except ValueError:
        # Handle non-numeric selections (maybe user typed something else)
        send_whatsapp_message(phone, f"❌ Invalid selection '{selection_id}'. Please reply with *HI* to start again and select a valid option.")
    except Exception as e:
        print(f"Error in handle_policy_selection: {e}")
        send_whatsapp_message(phone, "❌ An error occurred. Please reply with *HI* to start again.")
    finally:
        # Clean up session only for non-navigation actions
        if not selection_id.startswith('next_'):
            if phone in user_sessions:
                del user_sessions[phone]


def setup_whatsapp_webhook(app):
    """Setup Twilio WhatsApp webhook route"""

    @app.route('/twilio/whatsapp', methods=['POST'])
    def twilio_whatsapp_webhook():
        try:
            incoming_msg = (request.values.get('Body', '') or '').strip()
            from_raw = request.values.get('From', '')  # e.g., 'whatsapp:+9198...'
            from_number = from_raw.replace('whatsapp:', '')
            
            # Get additional Twilio parameters for list picker responses
            button_response = request.values.get('ButtonResponse')
            list_response = request.values.get('ListResponse')
            
            # Log incoming message details for debugging
            print(f"Incoming WhatsApp message from {from_number}:")
            print(f"  Body: {incoming_msg}")
            print(f"  ButtonResponse: {button_response}")
            print(f"  ListResponse: {list_response}")

            # Basic dedup (optional):
            msg_sid = request.values.get('MessageSid')
            if msg_sid and is_duplicate_message(msg_sid):
                return str(MessagingResponse())

            # Handle list picker responses
            if list_response:
                try:
                    import json
                    list_data = json.loads(list_response)
                    selection_id = list_data.get('id', '')
                    print(f"List picker selection: {selection_id}")
                    
                    if from_number in user_sessions:
                        handle_policy_selection(from_number, selection_id)
                    else:
                        send_whatsapp_message(from_number, "❌ Your session has expired. Please reply with *HI* to start again.")
                    
                    return str(MessagingResponse())
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Error parsing list response: {e}")
                    # Fall through to regular message handling

            # Handle regular text messages
            upper = incoming_msg.upper()
            if upper in ['HI', 'HELLO', 'HEY', 'START']:
                handle_greeting(from_number)
            else:
                # If user is in a session expecting a selection
                if from_number in user_sessions:
                    selection_id = incoming_msg.strip()
                    handle_policy_selection(from_number, selection_id)
                else:
                    send_whatsapp_message(from_number, "👋 Welcome to Insta Insurance Consultancy Portal!\n\nReply with *HI* to get started and view your insurance policies.")

            # Respond with empty TwiML (we're sending proactive messages via API)
            return str(MessagingResponse())
        except Exception as e:
            print(f"Error processing Twilio webhook: {e}")
            import traceback
            traceback.print_exc()
            return str(MessagingResponse())