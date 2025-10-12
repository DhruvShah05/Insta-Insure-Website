from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from supabase import create_client
from config import Config
from database_pool import execute_query
from email_service import send_renewal_reminder_email, indian_date_filter
from renewal_service import (
    renew_policy,
    get_policy_renewal_history,
    update_policy_payment,
    send_payment_confirmation_email,
    send_payment_confirmation_whatsapp
)
import logging
import os


def convert_date_format(date_string):
    """Convert DD/MM/YYYY to YYYY-MM-DD for database storage"""
    if not date_string or date_string.strip() == '':
        return None
    
    date_string = date_string.strip()
    
    try:
        from datetime import datetime
        
        # If already in YYYY-MM-DD format, validate and return
        if '-' in date_string and len(date_string.split('-')[0]) == 4:
            # Validate the date
            datetime.strptime(date_string, '%Y-%m-%d')
            return date_string
            
        # Convert DD/MM/YYYY to YYYY-MM-DD
        if '/' in date_string:
            parts = date_string.split('/')
            if len(parts) == 3:
                day, month, year = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                
                # Validate the date before converting
                datetime.strptime(f"{day}/{month}/{year}", '%d/%m/%Y')
                
                return f"{year}-{month}-{day}"
                
        # Try to parse other common formats
        for fmt in ['%d-%m-%Y', '%Y/%m/%d', '%m/%d/%Y']:
            try:
                parsed_date = datetime.strptime(date_string, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
                
        # If no format matches, return None to avoid database errors
        logger.warning(f"Could not parse date format: {date_string}")
        return None
        
    except Exception as e:
        logger.error(f"Error converting date {date_string}: {e}")
        return None

# Set up logging
logger = logging.getLogger(__name__)

renewal_bp = Blueprint("renewal", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@renewal_bp.route('/api/renew_policy', methods=['POST'])
@login_required
def renew_policy_api():
    """API endpoint to renew a policy with new PDF"""
    try:
        # Input validation
        policy_id = request.form.get('policy_id')
        renewed_file = request.files.get('renewed_file')
        new_expiry_date = request.form.get('new_expiry_date')
        new_policy_number = request.form.get('new_policy_number')

        if not policy_id:
            logger.error("Renewal attempt without policy ID")
            return jsonify({'success': False, 'message': 'Policy ID is required'}), 400

        if not policy_id.isdigit():
            logger.error(f"Invalid policy ID format: {policy_id}")
            return jsonify({'success': False, 'message': 'Invalid policy ID format'}), 400

        if not renewed_file:
            logger.error(f"Renewal attempt for policy {policy_id} without file")
            return jsonify({'success': False, 'message': 'Renewed policy file is required'}), 400

        # Validate file type and size
        if not renewed_file.filename:
            return jsonify({'success': False, 'message': 'Invalid file - no filename'}), 400
            
        if not renewed_file.filename.lower().endswith('.pdf'):
            logger.error(f"Invalid file type for policy {policy_id}: {renewed_file.filename}")
            return jsonify({'success': False, 'message': 'Only PDF files are allowed'}), 400

        # Check file size (max 50MB)
        renewed_file.seek(0, 2)  # Seek to end
        file_size = renewed_file.tell()
        renewed_file.seek(0)  # Reset to beginning
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            logger.error(f"File too large for policy {policy_id}: {file_size} bytes")
            return jsonify({'success': False, 'message': 'File size must be less than 50MB'}), 400

        if file_size == 0:
            logger.error(f"Empty file for policy {policy_id}")
            return jsonify({'success': False, 'message': 'File cannot be empty'}), 400

        # Get policy details with comprehensive error handling
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
            return jsonify({'success': False, 'message': 'Database error - please try again'}), 500

        if not policy_result.data:
            logger.error(f"Policy not found: {policy_id}")
            return jsonify({'success': False, 'message': 'Policy not found'}), 404

        policy = policy_result.data
        client = policy.get('clients', {})
        member = policy.get('members', {})
        
        if not client:
            logger.error(f"No client data found for policy {policy_id}")
            return jsonify({'success': False, 'message': 'Client information not found'}), 404
            
        if not member:
            logger.error(f"No member data found for policy {policy_id}")
            return jsonify({'success': False, 'message': 'Member information not found'}), 404

        # Renew the policy
        success, message, updated_policy = renew_policy(
            policy_id=int(policy_id),
            renewed_file=renewed_file,
            new_expiry_date=new_expiry_date if new_expiry_date else None,
            new_policy_number=new_policy_number if new_policy_number else None
        )

        if success:
            logger.info(f"Policy {policy_id} renewed successfully")
            
            # Send confirmation with the actual renewed policy document
            notification_results = []
            
            if client.get('email') or client.get('phone'):
                # Send via WhatsApp if phone available
                if client.get('phone'):
                    try:
                        from whatsapp_bot import send_policy_to_customer
                        whatsapp_success, whatsapp_msg = send_policy_to_customer(
                            client['phone'], 
                            updated_policy
                        )
                        if whatsapp_success:
                            notification_results.append("WhatsApp: ✅ Policy sent")
                            logger.info(f"WhatsApp notification sent for policy {policy_id}")
                        else:
                            notification_results.append(f"WhatsApp: ❌ {whatsapp_msg}")
                            logger.warning(f"WhatsApp failed for policy {policy_id}: {whatsapp_msg}")
                    except Exception as whatsapp_error:
                        error_msg = f"WhatsApp: ❌ Service error"
                        notification_results.append(error_msg)
                        logger.error(f"WhatsApp error for policy {policy_id}: {whatsapp_error}")
                
                # Send via Email if email available
                if client.get('email'):
                    try:
                        from renewal_service import send_renewal_confirmation_email
                        email_success, email_message = send_renewal_confirmation_email(
                            client['email'],
                            client['name'],
                            updated_policy,
                            {'name': renewed_file.filename}
                        )
                        if email_success:
                            notification_results.append("Email: ✅ Policy sent")
                            logger.info(f"Email notification sent for policy {policy_id}")
                        else:
                            notification_results.append(f"Email: ❌ {email_message}")
                            logger.warning(f"Email failed for policy {policy_id}: {email_message}")
                    except Exception as email_error:
                        error_msg = f"Email: ❌ Service error"
                        notification_results.append(error_msg)
                        logger.error(f"Email error for policy {policy_id}: {email_error}")
            
            # Combine results
            if notification_results:
                message += " | " + " | ".join(notification_results)
            else:
                message += " | No contact information available for notifications"

            return jsonify({
                'success': True,
                'message': message,
                'policy': updated_policy
            })
        else:
            return jsonify({'success': False, 'message': message}), 500

    except Exception as e:
        logger.error(f"Error in renew_policy_api: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@renewal_bp.route('/api/get_renewal_history/<int:policy_id>')
@login_required
def get_renewal_history_api(policy_id):
    """API endpoint to get renewal history for a policy"""
    try:
        history = get_policy_renewal_history(policy_id)

        if history:
            return jsonify({'success': True, 'history': history})
        else:
            return jsonify({'success': False, 'message': 'Could not retrieve renewal history'}), 404

    except Exception as e:
        logger.error(f"Error getting renewal history: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@renewal_bp.route('/renewal_page/<int:policy_id>')
@login_required
def renewal_page(policy_id):
    """Page for renewing a specific policy with full details editing"""
    try:
        # Get policy details
        policy_result = (
            supabase.table("policies")
            .select("*, clients!policies_client_id_fkey(client_id, name, email, phone), members!policies_member_id_fkey(member_name)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        if not policy_result.data:
            flash("Policy not found", "error")
            return redirect(url_for("existing_policies.list_all"))

        policy = policy_result.data
        client = policy.get('clients', {})
        member = policy.get('members', {})

        # Get health insurance details if exists
        health_details = None
        health_members = []
        try:
            health_result = supabase.table("health_insurance_details").select("*").eq("policy_id", policy_id).execute()
            if health_result.data:
                health_details = health_result.data[0]
                health_id = health_details['health_id']
                
                # Get health insured members
                members_result = supabase.table("health_insured_members").select("*").eq("health_id", health_id).execute()
                health_members = members_result.data
        except Exception as e:
            logger.warning(f"No health insurance details found for policy {policy_id}: {e}")

        # Get factory insurance details if exists
        factory_details = None
        try:
            factory_result = supabase.table("factory_insurance_details").select("*").eq("policy_id", policy_id).execute()
            if factory_result.data:
                factory_details = factory_result.data[0]
        except Exception as e:
            logger.warning(f"No factory insurance details found for policy {policy_id}: {e}")

        # Get renewal history
        history = get_policy_renewal_history(policy_id)

        return render_template("renewal_page.html",
                               policy=policy,
                               client=client,
                               member=member,
                               health_details=health_details,
                               health_members=health_members,
                               factory_details=factory_details,
                               history=history)

    except Exception as e:
        logger.error(f"Error loading renewal page: {e}")
        flash("Error loading policy details", "error")
        return redirect(url_for("existing_policies.list_all"))


@renewal_bp.route('/api/update_policy_details', methods=['POST'])
@login_required
def update_policy_details_api():
    """API endpoint to update policy details during renewal"""
    try:
        data = request.get_json()
        policy_id = data.get('policy_id')
        
        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID is required'}), 400
        
        # Update basic policy details
        policy_updates = {}
        if 'insurance_company' in data:
            policy_updates['insurance_company'] = data['insurance_company']
        if 'product_name' in data:
            policy_updates['product_name'] = data['product_name']
        if 'agent_name' in data:
            policy_updates['agent_name'] = data['agent_name']
        if 'sum_insured' in data:
            policy_updates['sum_insured'] = data['sum_insured']
        if 'net_premium' in data:
            policy_updates['net_premium'] = data['net_premium']
        if 'gross_premium' in data:
            policy_updates['gross_premium'] = data['gross_premium']
        if 'tp_tr_premium' in data:
            policy_updates['tp_tr_premium'] = data['tp_tr_premium']
        if 'business_type' in data:
            policy_updates['business_type'] = data['business_type']
        if 'group_name' in data:
            policy_updates['group_name'] = data['group_name']
        if 'subgroup_name' in data:
            policy_updates['subgroup_name'] = data['subgroup_name']
        if 'remarks' in data:
            policy_updates['remarks'] = data['remarks']
        if 'policy_from' in data and data['policy_from']:
            converted_date = convert_date_format(data['policy_from'])
            if converted_date is None:
                return jsonify({'success': False, 'message': f'Invalid policy start date format: {data["policy_from"]}. Please use DD/MM/YYYY format.'}), 400
            policy_updates['policy_from'] = converted_date
        if 'policy_to' in data and data['policy_to']:
            converted_date = convert_date_format(data['policy_to'])
            if converted_date is None:
                return jsonify({'success': False, 'message': f'Invalid policy end date format: {data["policy_to"]}. Please use DD/MM/YYYY format.'}), 400
            policy_updates['policy_to'] = converted_date
        if 'payment_date' in data and data['payment_date']:
            converted_date = convert_date_format(data['payment_date'])
            if converted_date is None:
                return jsonify({'success': False, 'message': f'Invalid payment date format: {data["payment_date"]}. Please use DD/MM/YYYY format.'}), 400
            policy_updates['payment_date'] = converted_date
        
        # Update policy table
        if policy_updates:
            supabase.table("policies").update(policy_updates).eq("policy_id", policy_id).execute()
        
        # Handle health insurance details
        if 'health_details' in data:
            health_data = data['health_details']
            
            # Check if health insurance details exist
            health_result = supabase.table("health_insurance_details").select("*").eq("policy_id", policy_id).execute()
            
            if health_result.data:
                # Update existing health details
                health_id = health_result.data[0]['health_id']
                health_updates = {}
                if 'plan_type' in health_data:
                    health_updates['plan_type'] = health_data['plan_type']
                
                if health_updates:
                    supabase.table("health_insurance_details").update(health_updates).eq("health_id", health_id).execute()
                
                # Handle health members
                if 'members' in health_data:
                    # Delete existing members
                    supabase.table("health_insured_members").delete().eq("health_id", health_id).execute()
                    
                    # Insert new members
                    for member in health_data['members']:
                        if member.get('member_name'):  # Only insert if name is provided
                            member_data = {
                                'health_id': health_id,
                                'member_name': member['member_name'],
                                'sum_insured': member.get('sum_insured', ''),
                                'bonus': member.get('bonus', '')
                            }
                            supabase.table("health_insured_members").insert(member_data).execute()
            
            elif health_data.get('plan_type'):  # Create new health insurance if plan_type is provided
                # Insert new health insurance details
                health_insert = {
                    'policy_id': policy_id,
                    'plan_type': health_data['plan_type']
                }
                health_result = supabase.table("health_insurance_details").insert(health_insert).execute()
                health_id = health_result.data[0]['health_id']
                
                # Insert health members
                if 'members' in health_data:
                    for member in health_data['members']:
                        if member.get('member_name'):  # Only insert if name is provided
                            member_data = {
                                'health_id': health_id,
                                'member_name': member['member_name'],
                                'sum_insured': member.get('sum_insured', ''),
                                'bonus': member.get('bonus', '')
                            }
                            supabase.table("health_insured_members").insert(member_data).execute()
        
        # Handle factory insurance details
        if 'factory_details' in data:
            factory_data = data['factory_details']
            
            # Check if factory insurance details exist
            factory_result = supabase.table("factory_insurance_details").select("*").eq("policy_id", policy_id).execute()
            
            factory_updates = {}
            if 'building' in factory_data:
                factory_updates['building'] = factory_data['building']
            if 'plant_machinery' in factory_data:
                factory_updates['plant_machinery'] = factory_data['plant_machinery']
            if 'furniture_fittings' in factory_data:
                factory_updates['furniture_fittings'] = factory_data['furniture_fittings']
            if 'stocks' in factory_data:
                factory_updates['stocks'] = factory_data['stocks']
            if 'electrical_installations' in factory_data:
                factory_updates['electrical_installations'] = factory_data['electrical_installations']
            
            if factory_result.data:
                # Update existing factory details
                if factory_updates:
                    supabase.table("factory_insurance_details").update(factory_updates).eq("policy_id", policy_id).execute()
            elif any(factory_updates.values()):  # Create new factory insurance if any value is provided
                # Insert new factory insurance details
                factory_updates['policy_id'] = policy_id
                supabase.table("factory_insurance_details").insert(factory_updates).execute()
        
        return jsonify({'success': True, 'message': 'Policy details updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating policy details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@renewal_bp.route('/api/update_policy_payment', methods=['POST'])
@login_required
def update_policy_payment_api():
    """API endpoint to update policy when payment is received"""
    try:
        policy_id = request.form.get('policy_id')
        paid_file = request.files.get('paid_file')
        new_expiry_date = request.form.get('new_expiry_date')
        new_policy_number = request.form.get('new_policy_number')
        send_confirmation = request.form.get('send_confirmation') == 'yes'

        # Get customer data if confirmation is requested
        customer_phone = request.form.get('customer_phone', '')
        customer_email = request.form.get('customer_email', '')
        customer_name = request.form.get('customer_name', '')

        if not policy_id:
            return jsonify({'success': False, 'message': 'Policy ID required'}), 400

        if not paid_file:
            return jsonify({'success': False, 'message': 'Paid policy file required'}), 400

        # Validate file type
        if not paid_file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'message': 'Only PDF files are allowed'}), 400

        # Get policy details
        policy_result = (
            supabase.table("policies")
            .select("*, clients!policies_client_id_fkey(client_id, name, email, phone), members!policies_member_id_fkey(member_name)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        if not policy_result.data:
            return jsonify({'success': False, 'message': 'Policy not found'}), 404

        policy = policy_result.data
        client = policy.get('clients', {})
        member = policy.get('members', {})

        # Update the policy with payment
        success, message, updated_policy = update_policy_payment(
            policy_id=int(policy_id),
            paid_file=paid_file,
            new_expiry_date=new_expiry_date if new_expiry_date else None,
            new_policy_number=new_policy_number if new_policy_number else None
        )

        if success:
            confirmation_messages = []

            # Send confirmations if checkbox was ticked
            if send_confirmation:
                # Send WhatsApp confirmation with document if phone is available
                if customer_phone:
                    try:
                        from whatsapp_bot import normalize_phone, send_policy_to_customer
                        normalized_phone = normalize_phone(customer_phone)
                        
                        # Send the actual policy document via WhatsApp
                        whatsapp_success, whatsapp_msg = send_policy_to_customer(
                            normalized_phone,
                            updated_policy
                        )

                        if whatsapp_success:
                            confirmation_messages.append("Policy document sent via WhatsApp")
                        else:
                            confirmation_messages.append(f"WhatsApp failed: {whatsapp_msg}")
                    except Exception as e:
                        logger.warning(f"Could not send WhatsApp confirmation: {e}")
                        confirmation_messages.append("WhatsApp confirmation failed")

                # Send Email confirmation if email is available
                if customer_email:
                    try:
                        email_success, email_message = send_payment_confirmation_email(
                            customer_email,
                            customer_name or client.get('name', 'Customer'),
                            updated_policy,
                            {'name': paid_file.filename}
                        )

                        if email_success:
                            confirmation_messages.append("Email confirmation sent")
                        else:
                            confirmation_messages.append(f"Email failed: {email_message}")
                    except Exception as e:
                        logger.warning(f"Could not send email confirmation: {e}")
                        confirmation_messages.append("Email confirmation failed")

                if confirmation_messages:
                    message += " | " + " | ".join(confirmation_messages)

            return jsonify({
                'success': True,
                'message': message,
                'policy': updated_policy
            })
        else:
            return jsonify({'success': False, 'message': message}), 500

    except Exception as e:
        logger.error(f"Error in update_policy_payment_api: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@renewal_bp.route("/send_renewal_reminder/<policy_id>", methods=['POST'])
@login_required
def send_reminder(policy_id):
    """Send a renewal reminder for a specific policy."""
    try:
        # 1. Fetch the policy details from the database
        policy_response = execute_query('policies', 'select', filters={'policy_id': policy_id}, single=True)
        if not policy_response.data:
            return jsonify({'success': False, 'message': 'Policy not found'}), 404
        policy = policy_response.data

        # 2. Fetch the client details
        client_response = execute_query('clients', 'select', filters={'client_id': policy['client_id']}, single=True)
        if not client_response.data:
            return jsonify({'success': False, 'message': 'Client not found for this policy'}), 404
        client = client_response.data
        
        # 3. Check if the client has an email address
        if not client.get('email'):
             return jsonify({'success': False, 'message': 'Client does not have an email address on file.'}), 400

        # 4. Create the data dictionary with the exact keys the HTML template needs
        renewal_data = {
            'client_name': client.get('name', 'Valued Customer'),
            'policy_no': policy.get('policy_number', 'N/A'), # The official policy number
            'asset': policy.get('remarks', 'N/A'),            # Using the 'remarks' field as requested
            'company': policy.get('insurance_company', 'N/A'),# The insurance company name
            'expiry_date': indian_date_filter(policy.get('policy_to'))
        }

        # 5. Call the email function with the data dictionary
        # (Assuming no file attachment for a reminder)
        success, message = send_renewal_reminder_email(
            client.get('email'),
            renewal_data,
            file_path=None 
        )

        if success:
            return jsonify({'success': True, 'message': f"Renewal reminder sent successfully to {client.get('email')}"})
        else:
            return jsonify({'success': False, 'message': f"Failed to send email: {message}"}), 500

    except Exception as e:
        print(f"Error in send_reminder route: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500