from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required
from whatsapp_bot import (
    send_policy_to_customer,
    send_renewal_reminder,
    normalize_phone
)
from email_service import send_policy_email, send_renewal_reminder_email
from supabase import create_client
from config import Config
import io
from googleapiclient.http import MediaIoBaseDownload
from whatsapp_bot import get_drive_service
import tempfile
import os

whatsapp_bp = Blueprint("whatsapp", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@whatsapp_bp.route('/api/send_policy_whatsapp', methods=['POST'])
@login_required
def send_policy_whatsapp():
    """Send a policy document to customer via WhatsApp"""
    try:
        data = request.json
        policy_id = data.get('policy_id')

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

        if not customer or not customer.get('phone'):
            return jsonify({'success': False, 'message': 'No phone number found for customer'}), 400

        phone = normalize_phone(customer['phone'])
        success, message = send_policy_to_customer(phone, policy)

        return jsonify({'success': success, 'message': message})

    except Exception as e:
        print(f"Error sending policy via WhatsApp: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_policy_email', methods=['POST'])
@login_required
def send_policy_email_api():
    """Send a policy document to customer via email only"""
    try:
        data = request.json
        policy_id = data.get('policy_id')

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

        if not customer or not customer.get('email'):
            return jsonify({'success': False, 'message': 'No email address found for customer'}), 400

        # Download file from Google Drive
        from whatsapp_bot import extract_file_id_from_url, download_file_from_drive, delete_temp_file
        
        file_id = extract_file_id_from_url(policy.get('drive_url'))
        if not file_id:
            return jsonify({'success': False, 'message': 'No drive URL found'}), 400

        filename = f"{policy.get('insurance_company','')}_{policy.get('product_name','')}.pdf".replace(' ', '_')
        temp_file_path = download_file_from_drive(file_id, filename)

        if not temp_file_path:
            return jsonify({'success': False, 'message': 'Could not download file'}), 400

        # Send email
        success, message = send_policy_email(
            customer['email'], 
            customer['name'], 
            policy, 
            temp_file_path
        )

        # Clean up temp file
        delete_temp_file(temp_file_path)

        return jsonify({'success': success, 'message': message})

    except Exception as e:
        print(f"Error sending policy via email: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_renewal_reminder_email', methods=['POST'])
@login_required
def send_renewal_reminder_email_api():
    """Send renewal reminder via email only"""
    try:
        policy_id = request.form.get('policy_id')
        payment_link = request.form.get('payment_link', '')
        renewal_file = request.files.get('renewal_file')

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

        if not customer or not customer.get('email'):
            return jsonify({'success': False, 'message': 'No email address found'}), 400

        # Handle renewal file if provided
        file_path = None
        if renewal_file:
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, renewal_file.filename)
            renewal_file.save(file_path)

        success, message = send_renewal_reminder_email(
            customer['email'],
            customer['name'],
            policy,
            file_path=file_path,
            payment_link=payment_link if payment_link else None
        )

        # Clean up temp file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({'success': success, 'message': message})

    except Exception as e:
        print(f"Error sending renewal reminder via email: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@whatsapp_bp.route('/api/send_renewal_reminder', methods=['POST'])
@login_required
def send_renewal_reminder_api():
    """Send renewal reminder via WhatsApp"""
    try:
        policy_id = request.form.get('policy_id')
        payment_link = request.form.get('payment_link', '')
        renewal_file = request.files.get('renewal_file')

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

        if not customer or not customer.get('phone'):
            return jsonify({'success': False, 'message': 'No phone number found'}), 400

        phone = normalize_phone(customer['phone'])

        # Handle renewal file if provided - save directly to static/renewals
        renewal_filename = None
        if renewal_file:
            # Ensure static renewals directory exists
            static_renewals_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'renewals')
            os.makedirs(static_renewals_dir, exist_ok=True)
            
            # Save with original filename directly to static/renewals
            renewal_filename = renewal_file.filename
            static_file_path = os.path.join(static_renewals_dir, renewal_filename)
            renewal_file.save(static_file_path)
            
            print(f"Renewal file saved: {static_file_path}")

        success, message = send_renewal_reminder(
            phone,
            policy,
            renewal_filename=renewal_filename,
            payment_link=payment_link if payment_link else None
        )

        return jsonify({'success': success, 'message': message})

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
        
        # Add additional headers for better compatibility
        response.headers['Content-Type'] = final_mime_type
        response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        response.headers['Access-Control-Allow-Origin'] = '*'  # Allow cross-origin access
        
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
        from config import Config
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