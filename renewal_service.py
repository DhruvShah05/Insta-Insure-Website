import os
import tempfile
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from supabase import create_client
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Google Drive setup
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = Config.GOOGLE_CREDENTIALS_FILE

# Get Archive folder ID from config
ARCHIVE_FOLDER_ID = Config.ARCHIVE_FOLDER_ID


def get_drive_service():
    """Initialize and return Google Drive service"""
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Error initializing Google Drive service: {e}")
        return None


def find_or_create_folder(parent_folder_id, folder_name):
    """Find existing folder or create new one in parent folder"""
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None
            
        logger.info(f"Looking for folder '{folder_name}' in parent {parent_folder_id}")
        
        # Search for existing folder
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get("files", [])
        
        if folders:
            logger.info(f"Found existing folder: {folders[0]['name']} (ID: {folders[0]['id']})")
            return folders[0]
        else:
            # Create new folder
            logger.info(f"Creating new folder: {folder_name}")
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id]
            }
            
            created_folder = drive_service.files().create(
                body=folder_metadata,
                fields="id, name",
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"Created folder: {created_folder['name']} (ID: {created_folder['id']})")
            return created_folder
            
    except Exception as e:
        logger.error(f"Error finding/creating folder: {e}")
        return None


def archive_file_in_drive(file_id, original_filename, client_id, member_name):
    """
    Move file to Archive folder with year-based client/member structure

    Args:
        file_id (str): Google Drive file ID to archive
        original_filename (str): Original filename
        client_id (str): Client ID for folder structure
        member_name (str): Member name for folder structure

    Returns:
        tuple: (success: bool, message: str, archived_file_id: str)
    """
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return False, "Could not initialize Drive service", None

        # Calculate financial year
        current_year = datetime.now().year
        if datetime.now().month >= 4:  # April onwards is new financial year
            financial_year = f"{current_year}-{str(current_year + 1)[-2:]}"
        else:
            financial_year = f"{current_year - 1}-{str(current_year)[-2:]}"

        # Get root folder ID (assuming it's the same as used in policies.py)
        ROOT_FOLDER_ID = "0AOc3bRLhlrgzUk9PVA"

        # Step 1: Find or create Archive folder
        archive_folder = find_or_create_folder(ROOT_FOLDER_ID, "Archive")
        if not archive_folder:
            return False, "Could not create Archive folder", None

        # Step 2: Find or create financial year folder
        year_folder = find_or_create_folder(archive_folder['id'], financial_year)
        if not year_folder:
            return False, f"Could not create {financial_year} folder", None

        # Step 3: Find or create client folder
        client_folder = find_or_create_folder(year_folder['id'], client_id)
        if not client_folder:
            return False, f"Could not create {client_id} folder", None

        # Step 4: Find or create member folder
        member_folder = find_or_create_folder(client_folder['id'], member_name)
        if not member_folder:
            return False, f"Could not create {member_name} folder", None

        # Step 5: Create archived filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = os.path.splitext(original_filename)
        archived_filename = f"{name_parts[0]}_ARCHIVED_{timestamp}{name_parts[1]}"

        # Step 6: Get current file parents
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields="name, parents",
            supportsAllDrives=True
        ).execute()

        # Step 7: Move file to archive location
        archived_file = drive_service.files().update(
            fileId=file_id,
            body={'name': archived_filename},
            addParents=member_folder['id'],
            removeParents=','.join(file_metadata.get('parents', [])),
            fields='id, name, webViewLink',
            supportsAllDrives=True
        ).execute()

        archive_path = f"Archive/{financial_year}/{client_id}/{member_name}/{archived_filename}"
        logger.info(f"Successfully archived file to: {archive_path}")
        return True, f"File archived to {archive_path}", archived_file['id']

    except Exception as e:
        logger.error(f"Error archiving file: {e}")
        return False, str(e), None


def delete_file_from_drive(file_id):
    """Delete a file from Google Drive (kept for backwards compatibility)"""
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return False, "Could not initialize Drive service"

        drive_service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        logger.info(f"Successfully deleted file {file_id} from Google Drive")
        return True, "File deleted successfully"

    except Exception as e:
        logger.error(f"Error deleting file from Drive: {e}")
        return False, str(e)


def upload_renewed_policy_file(file, policy_id, client_id, member_name):
    """Upload renewed policy file to Google Drive using client/member folder structure"""
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None, "Could not initialize Drive service"

        # Get root folder ID
        ROOT_FOLDER_ID = "0AOc3bRLhlrgzUk9PVA"

        # Step 1: Find or create client folder
        client_folder = find_or_create_folder(ROOT_FOLDER_ID, client_id)
        if not client_folder:
            return None, f"Could not create client folder: {client_id}"

        # Step 2: Find or create member subfolder
        member_folder = find_or_create_folder(client_folder['id'], member_name)
        if not member_folder:
            return None, f"Could not create member folder: {member_name}"

        # Step 3: Use original filename or generate clean filename
        file_extension = os.path.splitext(file.filename)[1]
        # Use original filename if it exists, otherwise generate clean filename
        if file.filename and file.filename.strip():
            new_filename = file.filename
        else:
            new_filename = f"{client_id} - {member_name} - Policy{file_extension}"

        # Step 4: Upload file to member folder
        file_metadata = {
            "name": new_filename,
            "parents": [member_folder['id']]
        }

        # Read file content
        file_content = file.read()

        # Upload file
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=file.mimetype,
            resumable=True
        )

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size, createdTime",
            supportsAllDrives=True
        ).execute()

        drive_path = f"{client_id}/{member_name}/{new_filename}"
        logger.info(f"Successfully uploaded renewed policy file: {drive_path}")

        return {
            "id": uploaded_file.get("id"),
            "name": uploaded_file.get("name"),
            "webViewLink": uploaded_file.get("webViewLink"),
            "size": uploaded_file.get("size"),
            "createdTime": uploaded_file.get("createdTime"),
            "drive_path": drive_path
        }, None

    except Exception as e:
        logger.error(f"Error uploading renewed policy file: {e}")
        return None, str(e)


def renew_policy(policy_id, renewed_file, new_expiry_date=None, new_policy_number=None):
    """
    Renew a policy by replacing the old PDF with a new one

    Args:
        policy_id (int): The policy ID to renew
        renewed_file: The new policy PDF file
        new_expiry_date (str): New expiry date (optional)
        new_policy_number (str): New policy number (optional)

    Returns:
        tuple: (success, message, updated_policy_data)
    """
    try:
        # Input validation
        if not policy_id or not isinstance(policy_id, int):
            logger.error(f"Invalid policy_id: {policy_id}")
            return False, "Invalid policy ID", None
            
        if not renewed_file:
            logger.error(f"No file provided for policy {policy_id}")
            return False, "No renewal file provided", None
            
        if not hasattr(renewed_file, 'read') or not hasattr(renewed_file, 'filename'):
            logger.error(f"Invalid file object for policy {policy_id}")
            return False, "Invalid file object", None
            
        # Get current policy details
        try:
            policy_result = (
                supabase.table("policies")
                .select("*, clients!policies_client_id_fkey(client_id, name, email, phone), members!policies_member_id_fkey(member_name)")
                .eq("policy_id", policy_id)
                .single()
                .execute()
            )
        except Exception as db_error:
            logger.error(f"Database error fetching policy {policy_id}: {db_error}")
            return False, f"Database error: {str(db_error)}", None

        if not policy_result.data:
            return False, "Policy not found", None

        current_policy = policy_result.data
        client_data = current_policy.get('clients', {})
        member_data = current_policy.get('members', {})
        
        if not client_data:
            logger.error(f"No client data found for policy {policy_id}")
            return False, "Client information not found", None
            
        if not member_data:
            logger.error(f"No member data found for policy {policy_id}")
            return False, "Member information not found", None
        
        client_id = client_data.get("client_id")
        member_name = member_data.get("member_name")
        
        if not client_id or not member_name:
            logger.error(f"Missing client_id or member_name for policy {policy_id}")
            return False, "Incomplete client/member information", None

        logger.info(f"Renewing policy {policy_id} for client {client_id}, member {member_name}")
        # Archive old file instead of deleting
        old_file_id = current_policy.get('drive_file_id')
        old_filename = current_policy.get('file_path', 'unknown.pdf')

        if old_file_id:
            archive_success, archive_message, archived_id = archive_file_in_drive(
                old_file_id,
                old_filename,
                client_id,
                member_name
            )
            if archive_success:
                logger.info(f"Archived old policy file: {old_file_id} -> {archived_id}")
            else:
                logger.warning(f"Could not archive old file: {archive_message}")

        # Upload new file to Google Drive
        file_details, upload_error = upload_renewed_policy_file(
            renewed_file,
            policy_id,
            client_id,
            member_name
        )

        if not file_details:
            return False, f"Failed to upload new file: {upload_error}", None

        # Prepare update data
        update_data = {
            "file_path": file_details['name'],
            "drive_file_id": file_details['id'],
            "drive_url": file_details['webViewLink'],
            "drive_path": file_details['drive_path'],
            "last_reminder_sent": None,
            "renewed_at": datetime.now().isoformat()
        }

        # Add optional fields if provided
        if new_expiry_date:
            update_data["policy_to"] = new_expiry_date

        if new_policy_number:
            update_data["policy_number"] = new_policy_number

        # Update policy in database
        update_result = (
            supabase.table("policies")
            .update(update_data)
            .eq("policy_id", policy_id)
            .execute()
        )

        if not update_result.data:
            return False, "Failed to update policy in database", None

        updated_policy = update_result.data[0]

        logger.info(f"Successfully renewed policy {policy_id}")

        return True, "Policy renewed successfully", updated_policy

    except Exception as e:
        logger.error(f"Error renewing policy: {e}")
        return False, str(e), None


def get_policy_renewal_history(policy_id):
    """Get renewal history for a policy"""
    try:
        policy_result = (
            supabase.table("policies")
            .select("policy_id, renewed_at, last_reminder_sent, policy_to")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        if not policy_result.data:
            return None

        policy = policy_result.data

        history = {
            "policy_id": policy_id,
            "current_expiry": policy.get('policy_to'),
            "last_renewed": policy.get('renewed_at'),
            "last_reminder_sent": policy.get('last_reminder_sent')
        }

        return history

    except Exception as e:
        logger.error(f"Error getting renewal history: {e}")
        return None


def update_policy_payment(policy_id, paid_file, new_expiry_date=None, new_policy_number=None):
    """
    Update policy when payment is received - archive old PDF and upload new one

    Args:
        policy_id (int): The policy ID to update
        paid_file: The new policy PDF file after payment
        new_expiry_date (str): New expiry date (optional)
        new_policy_number (str): New policy number (optional)

    Returns:
        tuple: (success: bool, message: str, updated_policy: dict)
    """
    try:
        # Get current policy details with client and member information
        policy_result = (
            supabase.table("policies")
            .select("*, clients!policies_client_id_fkey(client_id, name), members!policies_member_id_fkey(member_name)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        if not policy_result.data:
            return False, "Policy not found", None

        current_policy = policy_result.data
        client_data = current_policy.get('clients', {})
        member_data = current_policy.get('members', {})
        
        if not client_data:
            logger.error(f"No client data found for policy {policy_id}")
            return False, "Client information not found", None
            
        if not member_data:
            logger.error(f"No member data found for policy {policy_id}")
            return False, "Member information not found", None
        
        client_id = client_data.get("client_id")
        member_name = member_data.get("member_name")
        
        if not client_id or not member_name:
            logger.error(f"Missing client_id or member_name for policy {policy_id}")
            return False, "Incomplete client/member information", None

        logger.info(f"Updating payment for policy {policy_id} for client {client_id}, member {member_name}")
        # Archive old file instead of deleting
        old_file_id = current_policy.get('drive_file_id')
        old_filename = current_policy.get('file_path', 'unknown.pdf')

        if old_file_id:
            archive_success, archive_message, archived_id = archive_file_in_drive(
                old_file_id,
                old_filename,
                client_id,
                member_name
            )
            if archive_success:
                logger.info(f"Archived old policy file: {old_file_id} -> {archived_id}")
            else:
                logger.warning(f"Could not archive old file: {archive_message}")

        # Upload new paid policy file to Google Drive
        file_details, upload_error = upload_paid_policy_file(
            paid_file,
            policy_id,
            client_id,
            member_name
        )

        if not file_details:
            return False, f"Failed to upload new file: {upload_error}", None

        # Prepare update data
        update_data = {
            "file_path": file_details['name'],
            "drive_file_id": file_details['id'],
            "drive_url": file_details['webViewLink'],
            "drive_path": file_details['drive_path'],
            "payment_date": datetime.now().date().isoformat(),  # Use existing payment_date column
            "last_reminder_sent": None,
            "renewed_at": None
        }

        # Add optional fields if provided
        if new_expiry_date:
            update_data["policy_to"] = new_expiry_date

        if new_policy_number:
            update_data["policy_number"] = new_policy_number

        # Update policy in database
        update_result = (
            supabase.table("policies")
            .update(update_data)
            .eq("policy_id", policy_id)
            .execute()
        )

        if not update_result.data:
            return False, "Failed to update policy in database", None

        updated_policy = update_result.data[0]

        logger.info(f"Successfully updated policy payment for policy {policy_id}")

        return True, "Policy payment processed successfully", updated_policy

    except Exception as e:
        logger.error(f"Error updating policy payment: {e}")
        return False, str(e), None


def upload_paid_policy_file(file, policy_id, client_id, member_name):
    """Upload paid policy file to Google Drive using client/member folder structure"""
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None, "Could not initialize Drive service"

        # Get root folder ID
        ROOT_FOLDER_ID = "0AOc3bRLhlrgzUk9PVA"

        # Step 1: Find or create client folder
        client_folder = find_or_create_folder(ROOT_FOLDER_ID, client_id)
        if not client_folder:
            return None, f"Could not create client folder: {client_id}"

        # Step 2: Find or create member subfolder
        member_folder = find_or_create_folder(client_folder['id'], member_name)
        if not member_folder:
            return None, f"Could not create member folder: {member_name}"

        # Step 3: Use original filename or generate clean filename
        file_extension = os.path.splitext(file.filename)[1]
        # Use original filename if it exists, otherwise generate clean filename
        if file.filename and file.filename.strip():
            new_filename = file.filename
        else:
            new_filename = f"{client_id} - {member_name} - Policy{file_extension}"

        # Step 4: Upload file to member folder
        file_metadata = {
            "name": new_filename,
            "parents": [member_folder['id']]
        }

        # Read file content
        file_content = file.read()

        # Upload file
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=file.mimetype,
            resumable=True
        )

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size, createdTime",
            supportsAllDrives=True
        ).execute()

        drive_path = f"{client_id}/{member_name}/{new_filename}"
        logger.info(f"Successfully uploaded paid policy file: {drive_path}")

        return {
            "id": uploaded_file.get("id"),
            "name": uploaded_file.get("name"),
            "webViewLink": uploaded_file.get("webViewLink"),
            "size": uploaded_file.get("size"),
            "createdTime": uploaded_file.get("createdTime"),
            "drive_path": drive_path
        }, None

    except Exception as e:
        logger.error(f"Error uploading paid policy file: {e}")
        return None, str(e)


def send_payment_confirmation_email(customer_email, customer_name, policy, paid_file_details):
    """Send confirmation email when policy payment is processed"""
    try:
        from email_service import send_email

        subject = f"Payment Confirmation - {policy['product_name']} Insurance Policy"

        # Format expiry date to Indian format
        expiry_date = policy.get('policy_to', 'N/A')
        if expiry_date and expiry_date != 'N/A':
            try:
                from datetime import datetime
                if isinstance(expiry_date, str) and '-' in expiry_date:
                    parts = expiry_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:
                        expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except:
                pass

        body = f"""Dear {customer_name},

Thank you for your payment! We are pleased to confirm that your insurance policy has been successfully processed and updated.

Policy Details:
• Insurance Type: {policy['product_name']}
• Insurance Company: {policy['insurance_company']}
• Policy Number: {policy.get('policy_number', 'Will be updated shortly')}
• New Expiry Date: {expiry_date}

Your updated policy document has been processed and is now active. The updated policy document is attached to this email.

For any queries or assistance, please feel free to contact us.

Thank you for choosing our services.

Best regards,
Insta Insurance Consultancy Portal"""

        # Download the policy file temporarily for email attachment
        temp_file_path = None
        if policy.get('drive_url'):
            try:
                from whatsapp_bot import extract_file_id_from_url, download_file_from_drive
                file_id = extract_file_id_from_url(policy.get('drive_url'))
                if file_id:
                    filename = f"{policy.get('insurance_company', 'Policy')}_{policy.get('product_name', 'Document')}.pdf".replace(' ', '_')
                    temp_file_path = download_file_from_drive(file_id, filename)
            except Exception as e:
                logger.warning(f"Could not download file for email attachment: {e}")
        
        # Send email with policy document attachment
        if temp_file_path:
            # Prepare policy data for the new template-based function
            from email_service import indian_date_filter
            policy_data = {
                'client_name': customer_name,
                'policy_type': policy.get('product_name', 'Insurance'),
                'policy_no': policy.get('policy_number', 'N/A'),
                'asset': policy.get('remarks', 'N/A'),
                'start_date': indian_date_filter(policy.get('policy_from')),
                'expiry_date': indian_date_filter(policy.get('policy_to'))
            }
            
            result = send_policy_email(customer_email, policy_data, temp_file_path)
            # Clean up temp file
            try:
                import os
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass
            return result
        else:
            # Fallback to text-only email if no attachment available
            from email_service import send_email
            return send_email(customer_email, subject, body, customer_name=customer_name)

    except Exception as e:
        logger.error(f"Error sending payment confirmation email: {e}")
        return False, str(e)


def send_payment_confirmation_whatsapp(phone, customer_name, policy):
    """Send confirmation via WhatsApp when policy payment is processed"""
    try:
        from whatsapp_bot import send_whatsapp_message

        # Format expiry date to Indian format
        expiry_date = policy.get('policy_to', 'N/A')
        if expiry_date and expiry_date != 'N/A':
            try:
                if isinstance(expiry_date, str) and '-' in expiry_date:
                    parts = expiry_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:
                        expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except:
                pass

        message = f"""Dear {customer_name},

✅ *Payment Confirmed*

Thank you for your payment! Your insurance policy has been successfully updated.

*Policy Details:*
• Insurance: {policy['product_name']}
• Company: {policy['insurance_company']}
• Policy Number: {policy.get('policy_number', 'Will be updated shortly')}
• New Expiry Date: {expiry_date}

Your updated policy document is now active.

Reply with *HI* anytime to access your documents.

Thank you for choosing our services!

- Insta Insurance Consultancy Portal"""

        result = send_whatsapp_message(phone, message)
        return bool(result and not result.get('error')), "WhatsApp sent successfully"

    except Exception as e:
        logger.error(f"Error sending payment confirmation WhatsApp: {e}")
        return False, str(e)


def send_renewal_confirmation_email(customer_email, customer_name, policy, renewed_file_details):
    """Send confirmation email when policy is renewed with document attachment"""
    try:
        from email_service import send_policy_email

        subject = f"Policy Renewal Confirmation - {policy['product_name']} Insurance"

        # Format expiry date to Indian format
        expiry_date = policy.get('policy_to', 'N/A')
        if expiry_date and expiry_date != 'N/A':
            try:
                if isinstance(expiry_date, str) and '-' in expiry_date:
                    parts = expiry_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:
                        expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except:
                pass

        body = f"""Dear {customer_name},

Congratulations! Your insurance policy has been successfully renewed.

Renewal Details:
• Insurance Type: {policy['product_name']}
• Insurance Company: {policy['insurance_company']}
• Policy Number: {policy.get('policy_number', 'Will be updated shortly')}
• New Expiry Date: {expiry_date}

Your renewed policy document has been processed and is now active. The updated policy document is attached to this email.

Thank you for continuing to trust us with your insurance needs.

For any queries or assistance, please feel free to contact us.

Best regards,
Insta Insurance Consultancy Portal"""

        # Download the policy file temporarily for email attachment
        temp_file_path = None
        if policy.get('drive_url'):
            try:
                from whatsapp_bot import extract_file_id_from_url, download_file_from_drive
                file_id = extract_file_id_from_url(policy.get('drive_url'))
                if file_id:
                    filename = f"{policy.get('insurance_company', 'Policy')}_{policy.get('product_name', 'Document')}.pdf".replace(' ', '_')
                    temp_file_path = download_file_from_drive(file_id, filename)
            except Exception as e:
                logger.warning(f"Could not download file for email attachment: {e}")
        
        # Send email with policy document attachment
        if temp_file_path:
            # Prepare policy data for the new template-based function
            from email_service import indian_date_filter
            policy_data = {
                'client_name': customer_name,
                'policy_type': policy.get('product_name', 'Insurance'),
                'policy_no': policy.get('policy_number', 'N/A'),
                'asset': policy.get('remarks', 'N/A'),
                'start_date': indian_date_filter(policy.get('policy_from')),
                'expiry_date': indian_date_filter(policy.get('policy_to'))
            }
            
            result = send_policy_email(customer_email, policy_data, temp_file_path)
            # Clean up temp file
            try:
                import os
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass
            return result
        else:
            # Fallback to text-only email if no attachment available
            from email_service import send_email
            return send_email(customer_email, subject, body, customer_name=customer_name)

    except Exception as e:
        logger.error(f"Error sending renewal confirmation email: {e}")
        return False, str(e)