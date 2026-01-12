from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required
from whatsapp_bot import (
    send_policy_to_customer,
    send_renewal_reminder,
    normalize_phone
)
from email_service import send_policy_email, send_renewal_reminder_email, indian_date_filter
from supabase import create_client
from dynamic_config import Config
import io
from googleapiclient.http import MediaIoBaseDownload
from whatsapp_bot import get_drive_service
import tempfile
import os
from utils.pdf_converter import convert_pdf_for_twilio
import re

whatsapp_bp = Blueprint("whatsapp", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@whatsapp_bp.route('/api/send_policy_whatsapp', methods=['POST'])
@login_required
def send_policy_whatsapp():
    """Send a policy document to customer via WhatsApp and/or Email with contact selection"""
    try:
        data = request.json
        policy_id = data.get('policy_id')
        
        # Contact selection options (default to primary)
        use_primary_phone = data.get('use_primary_phone', True)
        use_alternate_phone = data.get('use_alternate_phone', False)
        use_primary_email = data.get('use_primary_email', True)
        use_alternate_email = data.get('use_alternate_email', False)

        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID required'}), 400

        # Fetch policy and customer info
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        policy = result.data
        customer = policy.get('clients')
        
        if not customer:
            return jsonify({'success': False, 'message': 'No customer found for policy'}), 400

        messages = []
        overall_success = False
        
        # Build phone list based on selection
        phones_to_send = []
        if use_primary_phone and customer.get('phone'):
            phones_to_send.append(('primary', normalize_phone(customer['phone'])))
        if use_alternate_phone and customer.get('alternate_phone'):
            phones_to_send.append(('alternate', normalize_phone(customer['alternate_phone'])))
        
        # Send WhatsApp to selected phones
        for contact_type, phone in phones_to_send:
            success, message = send_policy_to_customer(phone, policy, send_email=False)
            messages.append(f"WhatsApp ({contact_type}): {message}")
            if success:
                overall_success = True
        
        # Build email list based on selection
        emails_to_send = []
        if use_primary_email and customer.get('email'):
            emails_to_send.append(('primary', customer['email']))
        if use_alternate_email and customer.get('alternate_email'):
            emails_to_send.append(('alternate', customer['alternate_email']))
        
        # Send email to selected addresses
        if emails_to_send:
            from whatsapp_bot import extract_file_id_from_url, download_file_from_drive, delete_temp_file
            
            file_id = extract_file_id_from_url(policy.get('drive_url'))
            if file_id:
                filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
                temp_file_path = download_file_from_drive(file_id, filename)
                
                if temp_file_path:
                    member = policy.get('members')
                    member_name = member.get('member_name', '') if member else ''
                    display_name = member_name if member_name else customer['name']
                    
                    policy_data = {
                        'member_name': display_name,
                        'policy_type': policy.get('product_name', 'Insurance'),
                        'policy_no': policy.get('policy_number', 'N/A'),
                        'asset': policy.get('remarks', 'N/A'),
                        'start_date': indian_date_filter(policy.get('policy_from')),
                        'expiry_date': indian_date_filter(policy.get('policy_to'))
                    }
                    
                    for contact_type, email in emails_to_send:
                        success, message = send_policy_email(email, policy_data, temp_file_path)
                        messages.append(f"Email ({contact_type}): {message}")
                        if success:
                            overall_success = True
                    
                    delete_temp_file(temp_file_path)
                else:
                    messages.append("Email: Failed to download policy document")
            else:
                messages.append("Email: No drive URL found")
        
        if not phones_to_send and not emails_to_send:
            return jsonify({'success': False, 'message': 'No contacts selected for sending'}), 400

        return jsonify({'success': overall_success, 'message': ' | '.join(messages)})

    except Exception as e:
        print(f"Error sending policy: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_policy_email', methods=['POST'])
@login_required
def send_policy_email_api():
    """Send a policy document to customer via email only with contact selection"""
    try:
        data = request.json
        policy_id = data.get('policy_id')
        
        # Contact selection options (default to primary)
        use_primary_email = data.get('use_primary_email', True)
        use_alternate_email = data.get('use_alternate_email', False)

        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID required'}), 400

        # Fetch policy and customer info
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        policy = result.data
        customer = policy.get('clients')

        if not customer:
            return jsonify({'success': False, 'message': 'No customer found for policy'}), 400
        
        # Build email list based on selection
        emails_to_send = []
        if use_primary_email and customer.get('email'):
            emails_to_send.append(('primary', customer['email']))
        if use_alternate_email and customer.get('alternate_email'):
            emails_to_send.append(('alternate', customer['alternate_email']))
        
        if not emails_to_send:
            return jsonify({'success': False, 'message': 'No email addresses selected or available'}), 400

        # Download file from Google Drive
        from whatsapp_bot import extract_file_id_from_url, download_file_from_drive, delete_temp_file
        
        file_id = extract_file_id_from_url(policy.get('drive_url'))
        if not file_id:
            return jsonify({'success': False, 'message': 'No drive URL found'}), 400

        filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
        temp_file_path = download_file_from_drive(file_id, filename)

        if not temp_file_path:
            return jsonify({'success': False, 'message': 'Could not download file'}), 400

        # Get member name (use member name instead of client name)
        member = policy.get('members')
        member_name = member.get('member_name', '') if member else ''
        display_name = member_name if member_name else customer['name']
        
        # Prepare policy data
        policy_data = {
            'member_name': display_name,
            'policy_type': policy.get('product_name', 'Insurance'),
            'policy_no': policy.get('policy_number', 'N/A'),
            'asset': policy.get('remarks', 'N/A'),
            'start_date': indian_date_filter(policy.get('policy_from')),
            'expiry_date': indian_date_filter(policy.get('policy_to'))
        }
        
        # Send email to selected addresses
        messages = []
        overall_success = False
        for contact_type, email in emails_to_send:
            success, message = send_policy_email(email, policy_data, temp_file_path)
            messages.append(f"Email ({contact_type}): {message}")
            if success:
                overall_success = True

        # Clean up temp file
        delete_temp_file(temp_file_path)

        return jsonify({'success': overall_success, 'message': ' | '.join(messages)})

    except Exception as e:
        print(f"Error sending policy via email: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_renewal_reminder_email', methods=['POST'])
@login_required
def send_renewal_reminder_email_api():
    """Send renewal reminder via email only with contact selection"""
    try:
        policy_id = request.form.get('policy_id')
        renewal_premium = request.form.get('renewal_premium', '')
        renewal_file = request.files.get('renewal_file')
        
        # Contact selection options (default to primary)
        use_primary_email = request.form.get('use_primary_email', 'true').lower() == 'true'
        use_alternate_email = request.form.get('use_alternate_email', 'false').lower() == 'true'

        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID required'}), 400

        # Fetch policy and customer info
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        policy = result.data
        customer = policy.get('clients')

        if not customer:
            return jsonify({'success': False, 'message': 'No customer found'}), 400
        
        # Build email list based on selection
        emails_to_send = []
        if use_primary_email and customer.get('email'):
            emails_to_send.append(('primary', customer['email']))
        if use_alternate_email and customer.get('alternate_email'):
            emails_to_send.append(('alternate', customer['alternate_email']))
        
        if not emails_to_send:
            return jsonify({'success': False, 'message': 'No email addresses selected or available'}), 400

        # Handle renewal file if provided
        file_path = None
        if renewal_file:
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, renewal_file.filename)
            renewal_file.save(file_path)

        # Get member name
        member = policy.get('members')
        member_name = member.get('member_name', '') if member else ''
        display_name = member_name if member_name else customer['name']
        
        # Prepare renewal data
        renewal_data = {
            'member_name': display_name,
            'policy_no': policy.get('policy_number', policy.get('policy_id', 'N/A')),
            'asset': policy.get('remarks', 'N/A'),
            'company': policy.get('insurance_company', 'N/A'),
            'expiry_date': policy.get('policy_to', 'N/A'),
            'renewal_premium': renewal_premium if renewal_premium else None
        }
        
        # Send to selected emails
        messages = []
        overall_success = False
        for contact_type, email in emails_to_send:
            success, message = send_renewal_reminder_email(email, renewal_data, file_path=file_path)
            messages.append(f"Email ({contact_type}): {message}")
            if success:
                overall_success = True

        # Clean up temp file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({'success': overall_success, 'message': ' | '.join(messages)})

    except Exception as e:
        print(f"Error sending renewal reminder via email: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_renewal_reminder', methods=['POST'])
@login_required
def send_renewal_reminder_api():
    """Send renewal reminder via WhatsApp with contact selection"""
    try:
        policy_id = request.form.get('policy_id')
        renewal_premium = request.form.get('renewal_premium', '')
        renewal_file = request.files.get('renewal_file')
        
        # Contact selection options (default to primary)
        use_primary_phone = request.form.get('use_primary_phone', 'true').lower() == 'true'
        use_alternate_phone = request.form.get('use_alternate_phone', 'false').lower() == 'true'

        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID required'}), 400
        
        # Require file upload for renewal reminders
        if not renewal_file:
            return jsonify({'success': False, 'message': 'Renewal document is required'}), 400

        # Fetch policy and customer info
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        policy = result.data
        customer = policy.get('clients')

        if not customer:
            return jsonify({'success': False, 'message': 'No customer found'}), 400
        
        # Build phone list based on selection
        phones_to_send = []
        if use_primary_phone and customer.get('phone'):
            phones_to_send.append(('primary', normalize_phone(customer['phone'])))
        if use_alternate_phone and customer.get('alternate_phone'):
            phones_to_send.append(('alternate', normalize_phone(customer['alternate_phone'])))
        
        # Debug logging
        print(f"[DEBUG] Contact selection - Primary: {use_primary_phone}, Alternate: {use_alternate_phone}")
        print(f"[DEBUG] Customer data - Phone: {customer.get('phone')}, Alt Phone: {customer.get('alternate_phone')}")
        print(f"[DEBUG] Phones to send: {phones_to_send}")
        
        if not phones_to_send:
            return jsonify({'success': False, 'message': 'No phone numbers selected or available'}), 400

        # Handle renewal file - convert and save to static/renewals
        renewal_filename = None
        converted_path = None
        try:
            # Ensure static renewals directory exists
            static_renewals_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'renewals')
            os.makedirs(static_renewals_dir, exist_ok=True)
            
            # Sanitize filename per Twilio guidelines
            original_filename = renewal_file.filename
            name_parts = original_filename.rsplit('.', 1)
            base_name = name_parts[0] if len(name_parts) > 1 else original_filename
            extension = name_parts[1] if len(name_parts) > 1 else 'pdf'
            
            safe_base = re.sub(r'[^a-zA-Z0-9\-_]', '_', base_name)
            safe_base = re.sub(r'_+', '_', safe_base)
            safe_base = safe_base.strip('_')
            if len(safe_base) > 20:
                safe_base = safe_base[:20]
            
            safe_filename = f"{safe_base}.{extension}"
            renewal_filename = safe_filename
            static_file_path = os.path.join(static_renewals_dir, safe_filename)
            
            # Convert PDF to Twilio-compatible format
            file_content = None
            if extension.lower() == 'pdf':
                print(f"Converting renewal PDF: {safe_filename}")
                success, converted_path, error = convert_pdf_for_twilio(renewal_file)
                
                if success and converted_path:
                    with open(converted_path, 'rb') as f:
                        file_content = f.read()
                    print(f"✓ Renewal PDF converted: {safe_filename}")
                else:
                    print(f"⚠ PDF conversion failed: {error}, using original")
                    renewal_file.seek(0)
                    file_content = renewal_file.read()
            else:
                file_content = renewal_file.read()
            
            with open(static_file_path, 'wb') as f:
                f.write(file_content)
            
            print(f"Renewal file saved: {static_file_path}")
            
        except Exception as e:
            print(f"Error processing renewal file: {e}")
            renewal_file.seek(0)
            static_file_path = os.path.join(static_renewals_dir, safe_filename)
            renewal_file.save(static_file_path)
        finally:
            if converted_path and os.path.exists(converted_path):
                try:
                    os.remove(converted_path)
                except:
                    pass

        # Send to selected phones
        messages = []
        overall_success = False
        for contact_type, phone in phones_to_send:
            success, message = send_renewal_reminder(
                phone,
                policy,
                renewal_filename=renewal_filename,
                renewal_premium=renewal_premium if renewal_premium else None
            )
            messages.append(f"WhatsApp ({contact_type}): {message}")
            if success:
                overall_success = True

        return jsonify({'success': overall_success, 'message': ' | '.join(messages)})

    except Exception as e:
        print(f"Error sending renewal reminder: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/media/drive/<file_id>/<path:filename>', methods=['GET'])
def serve_drive_media(file_id, filename):
    """Proxy a Google Drive file as a public URL for Twilio media_url.
    
    This endpoint serves files from Google Drive with proper HTTPS access
    and content-type headers required by Twilio WhatsApp API.
    """
    try:
        service = get_drive_service()
        if not service:
            print(f"Google Drive service not available for file_id: {file_id}")
            return jsonify({'error': 'Drive service unavailable'}), 500

        # Get file metadata to determine proper content type
        try:
            file_metadata = service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType', 'application/octet-stream')
            
            # Map Google Drive MIME types to standard MIME types for WhatsApp
            mime_type_mapping = {
                'application/vnd.google-apps.document': 'application/pdf',
                'application/vnd.google-apps.spreadsheet': 'application/pdf',
                'application/vnd.google-apps.presentation': 'application/pdf',
                'application/pdf': 'application/pdf',
                'image/jpeg': 'image/jpeg',
                'image/png': 'image/png',
                'image/jpg': 'image/jpeg'
            }
            
            # Use mapped MIME type or default to PDF for documents
            final_mime_type = mime_type_mapping.get(mime_type, 'application/pdf')
            
        except Exception as e:
            print(f"Could not get file metadata for {file_id}: {e}")
            final_mime_type = 'application/pdf'  # Default fallback

        # Download the file content
        request_obj = service.files().get_media(fileId=file_id)
        mem = io.BytesIO()
        downloader = MediaIoBaseDownload(mem, request_obj)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        mem.seek(0)
        
        # Ensure filename has proper extension for the MIME type
        if final_mime_type == 'application/pdf' and not filename.lower().endswith('.pdf'):
            filename = f"{filename}.pdf"
        
        print(f"Serving file {filename} with MIME type {final_mime_type} for Twilio")
        
        # Return file with proper headers for Twilio
        response = send_file(
            mem, 
            mimetype=final_mime_type,
            download_name=filename,
            as_attachment=False
        )
        
        # Add Content-Disposition header (required by Twilio spec)
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        
        # Ensure Content-Type is explicitly set
        response.headers['Content-Type'] = final_mime_type
        
        # Add cache control headers to prevent Cloudflare issues
        # Use no-cache to ensure Twilio always gets fresh headers
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # Allow cross-origin access for Twilio
        response.headers['Access-Control-Allow-Origin'] = '*'
        
        return response
        
    except Exception as e:
        print(f"Error serving drive media {file_id}/{filename}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to serve media file',
            'message': str(e),
            'file_id': file_id,
            'filename': filename
        }), 500


@whatsapp_bp.route('/media/health', methods=['GET'])
def media_health_check():
    """Health check endpoint to verify media serving is working"""
    try:
        from dynamic_config import Config
        return jsonify({
            'status': 'healthy',
            'base_url': Config.APP_BASE_URL,
            'https_enabled': Config.APP_BASE_URL.startswith('https://'),
            'drive_service': get_drive_service() is not None,
            'message': 'Media serving endpoint is operational'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500