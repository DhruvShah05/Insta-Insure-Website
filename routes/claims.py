from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from supabase import create_client, Client
from config import Config
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from datetime import datetime
import logging

# Set up logging for this blueprint
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Google Drive setup (using the same pattern as your other files)
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = Config.GOOGLE_CREDENTIALS_FILE
ROOT_FOLDER_ID = "0AOc3bRLhlrgzUk9PVA" # Your main root folder ID from policies.py

claims_bp = Blueprint('claims', __name__, url_prefix='/claims')

def get_drive_service():
    """Initializes and returns the Google Drive service object."""
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        return None

def find_or_create_folder(drive_service, parent_folder_id, folder_name):
    """Finds a folder by name within a parent folder, or creates it if it doesn't exist."""
    try:
        query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            return folders[0]['id']
        else:
            folder_metadata = {
                'name': folder_name,
                'parents': [parent_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(body=folder_metadata, supportsAllDrives=True, fields='id').execute()
            return folder['id']
            
    except Exception as e:
        logger.error(f"Error in find_or_create_folder for '{folder_name}': {e}")
        raise

def upload_claim_document(file, client_id, member_name, claim_id, document_type):
    """Uploads a claim document to a structured folder in Google Drive."""
    drive_service = get_drive_service()
    if not drive_service:
        raise Exception("Google Drive service could not be initialized.")

    try:
        # Build the folder structure: Client -> Member -> Claims -> Claim_ID -> Document_Type
        client_folder_id = find_or_create_folder(drive_service, ROOT_FOLDER_ID, str(client_id))
        member_folder_id = find_or_create_folder(drive_service, client_folder_id, member_name)
        claims_folder_id = find_or_create_folder(drive_service, member_folder_id, "Claims")
        claim_folder_id = find_or_create_folder(drive_service, claims_folder_id, f"Claim_{claim_id}")
        doc_type_folder_id = find_or_create_folder(drive_service, claim_folder_id, document_type)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        new_filename = f"{client_id}_{member_name}_{document_type}_{timestamp}.{file_extension}"

        file_metadata = {"name": new_filename, "parents": [doc_type_folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.mimetype, resumable=True)
        
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size",
            supportsAllDrives=True
        ).execute()

        drive_path = f"{client_id}/{member_name}/Claims/Claim_{claim_id}/{document_type}/{new_filename}"

        return {
            "id": uploaded_file.get("id"),
            "name": uploaded_file.get("name"),
            "webViewLink": uploaded_file.get("webViewLink"),
            "drive_path": drive_path,
            "file_size": uploaded_file.get("size")
        }
    except Exception as e:
        logger.error(f"Error uploading claim document to Drive: {e}")
        raise

@claims_bp.route('/')
@login_required
def index():
    """View all claims with optional filtering"""
    try:
        # Get filter parameters
        client_id = request.args.get('client_id')
        policy_number = request.args.get('policy_number')
        search_query = request.args.get('search', '').strip()
        
        # Build the query
        query = supabase.table("claims").select("*, policies(policy_number, client_id, clients(name, client_id))")
        
        # Apply filters
        if client_id:
            query = query.eq("policies.client_id", client_id)
        
        if policy_number:
            query = query.eq("policies.policy_number", policy_number)
        
        # Execute query
        result = query.order("created_at", desc=True).execute()
        claims = result.data or []
        
        # Apply text search if provided
        if search_query:
            search_lower = search_query.lower()
            filtered_claims = []
            for claim in claims:
                # Search in claim number, member name, client name, policy number
                if (search_lower in str(claim.get('claim_number', '')).lower() or
                    search_lower in str(claim.get('member_name', '')).lower() or
                    search_lower in str(claim['policies']['clients']['name']).lower() or
                    search_lower in str(claim['policies']['policy_number']).lower()):
                    filtered_claims.append(claim)
            claims = filtered_claims
        
        # Calculate stats
        stats = {
            'total': len(claims),
            'pending': len([c for c in claims if c['status'] == 'PENDING']),
            'processing': len([c for c in claims if c['status'] == 'PROCESSING']),
            'approved': len([c for c in claims if c['status'] == 'APPROVED']),
            'settled': len([c for c in claims if c['status'] == 'SETTLED']),
            'rejected': len([c for c in claims if c['status'] == 'REJECTED'])
        }
        
        # Get client name for display if filtering by client
        client_name = None
        if client_id:
            try:
                client_result = supabase.table("clients").select("name").eq("client_id", client_id).single().execute()
                if client_result.data:
                    client_name = client_result.data['name']
            except:
                pass
        
        return render_template('claims.html', 
                             claims=claims, 
                             stats=stats,
                             current_client_id=client_id,
                             current_policy_number=policy_number,
                             current_search=search_query,
                             client_name=client_name)
    except Exception as e:
        logger.error(f"Error fetching claims: {e}")
        flash(f"Error loading claims: {str(e)}", "error")
        return render_template('claims.html', claims=[], stats={}, 
                             current_client_id=None, current_policy_number=None, 
                             current_search="", client_name=None)

@claims_bp.route('/api/document-types')
@login_required
def get_document_types():
    """API endpoint to get all available document types."""
    try:
        result = supabase.table("custom_document_types").select("type_name").eq("is_active", True).order("type_name").execute()
        types = [item['type_name'] for item in result.data] if result.data else []
        return jsonify({'document_types': types})
    except Exception as e:
        logger.error(f"Error fetching document types: {e}")
        return jsonify({'error': 'Failed to fetch document types'}), 500

@claims_bp.route('/api/add-document-type', methods=['POST'])
@login_required
def add_document_type():
    """API endpoint to add a new custom document type."""
    try:
        data = request.get_json()
        type_name = data.get('type_name', '').strip().upper()
        
        if not type_name:
            return jsonify({'error': 'Document type name is required'}), 400
        
        # Check if it already exists
        existing = supabase.table("custom_document_types").select("id").eq("type_name", type_name).execute()
        if existing.data:
            return jsonify({'error': 'Document type already exists'}), 400
        
        # Add new document type
        result = supabase.table("custom_document_types").insert({"type_name": type_name}).execute()
        return jsonify({'success': True, 'type_name': type_name})
        
    except Exception as e:
        logger.error(f"Error adding document type: {e}")
        return jsonify({'error': 'Failed to add document type'}), 500

@claims_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_claim():
    """Handles the creation of a new claim."""
    if request.method == 'GET':
        # Get document types for the form
        try:
            result = supabase.table("custom_document_types").select("type_name").eq("is_active", True).order("type_name").execute()
            document_types = [item['type_name'] for item in result.data] if result.data else []
        except:
            document_types = ['MEDICAL_BILL', 'DISCHARGE_SUMMARY', 'PRESCRIPTION', 'LAB_REPORT', 'OTHER']
        
        return render_template('add_claim.html', document_types=document_types)
    
    if request.method == 'POST':
        try:
            policy_number = request.form.get('policy_number')
            member_name = request.form.get('member_name')
            claim_type = request.form.get('claim_type')
            claim_number = request.form.get('claim_number')

            if not all([policy_number, member_name, claim_type, claim_number]):
                flash("Policy Number, Member Name, Claim Type, and Claim Number are required.", "error")
                return redirect(url_for('claims.add_claim'))

            policy_result = supabase.table("policies").select("policy_id, client_id, clients(client_id)").eq("policy_number", policy_number).single().execute()
            if not policy_result.data:
                flash("Policy number not found.", "error")
                return redirect(url_for('claims.add_claim'))
            
            policy = policy_result.data
            client_id = policy['clients']['client_id']

            # Convert dates from DD/MM/YYYY to YYYY-MM-DD format for database
            def convert_date_format(date_str):
                if not date_str:
                    return None
                try:
                    # If it's already in YYYY-MM-DD format, return as is
                    if len(date_str.split('-')) == 3 and len(date_str.split('-')[0]) == 4:
                        return date_str
                    # Convert from DD/MM/YYYY to YYYY-MM-DD
                    day, month, year = date_str.split('/')
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    return None

            # Check if claim number already exists
            existing_claim = supabase.table("claims").select("claim_id").eq("claim_number", claim_number).execute()
            if existing_claim.data:
                flash(f"Claim number '{claim_number}' already exists. Please use a different claim number.", "error")
                return redirect(url_for('claims.add_claim'))

            claim_data = {
                "policy_id": policy['policy_id'],
                "member_name": member_name,
                "claim_type": claim_type,
                "claim_number": claim_number,
                "diagnosis": request.form.get('diagnosis'),
                "hospital_name": request.form.get('hospital_name'),
                "admission_date": convert_date_format(request.form.get('admission_date')),
                "discharge_date": convert_date_format(request.form.get('discharge_date')),
                "claimed_amount": float(request.form.get('claimed_amount')) if request.form.get('claimed_amount') else None,
                "status": "PENDING"
            }
            
            result = supabase.table("claims").insert(claim_data).execute()
            claim_id = result.data[0]["claim_id"]

            files = request.files.getlist('claim_documents[]')
            document_types = request.form.getlist('document_types[]')
            custom_document_types = request.form.getlist('custom_document_types[]')

            for i, file in enumerate(files):
                if file and file.filename:
                    try:
                        doc_type = document_types[i] if i < len(document_types) else 'OTHER'
                        
                        # If it's a custom type, use the custom name and save it to database
                        if doc_type == 'OTHER' and i < len(custom_document_types) and custom_document_types[i]:
                            custom_type = custom_document_types[i].strip().upper()
                            # Save custom type to database if it doesn't exist
                            try:
                                existing = supabase.table("custom_document_types").select("id").eq("type_name", custom_type).execute()
                                if not existing.data:
                                    supabase.table("custom_document_types").insert({"type_name": custom_type}).execute()
                                doc_type = custom_type
                            except:
                                pass  # If saving fails, just use the custom name
                        
                        drive_file = upload_claim_document(file, client_id, member_name, claim_id, doc_type)
                        doc_data = {
                            "claim_id": claim_id,
                            "document_name": file.filename,
                            "document_type": doc_type,
                            "drive_file_id": drive_file["id"],
                            "drive_url": drive_file["webViewLink"],
                            "drive_path": drive_file["drive_path"],
                            "file_size": drive_file.get("file_size")
                        }
                        supabase.table("claim_documents").insert(doc_data).execute()
                    except Exception as e:
                        logger.error(f"Failed to upload document '{file.filename}': {e}")
                        flash(f"Warning: Could not upload document '{file.filename}'.", "warning")

            flash(f"Claim added successfully! Claim Number: {claim_number}", "success")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))

        except Exception as e:
            logger.error(f"Error adding claim: {e}", exc_info=True)
            flash(f"An unexpected error occurred while adding the claim: {str(e)}", "error")
            return redirect(url_for('claims.add_claim'))

    return render_template('add_claim.html')

@claims_bp.route('/<int:claim_id>')
@login_required
def view_claim(claim_id):
    """View claim details"""
    try:
        claim_result = supabase.table("claims").select("*, policies(policy_number, clients(name, client_id))").eq("claim_id", claim_id).single().execute()
        if not claim_result.data:
            flash("Claim not found", "error")
            return redirect(url_for('claims.index'))
        
        claim = claim_result.data
        docs_result = supabase.table("claim_documents").select("*").eq("claim_id", claim_id).order("uploaded_at", desc=True).execute()
        documents = docs_result.data or []
        
        return render_template('view_claim.html', claim=claim, documents=documents)
    except Exception as e:
        logger.error(f"Error fetching claim details for ID {claim_id}: {e}")
        flash(f"Error loading claim details: {str(e)}", "error")
        return redirect(url_for('claims.index'))

@claims_bp.route('/api/policy-lookup')
@login_required
def policy_lookup():
    """API endpoint to look up a policy and get its associated members."""
    policy_number = request.args.get('policy_number')
    if not policy_number:
        return jsonify({'error': 'Policy number is required'}), 400
        
    try:
        policy_result = supabase.table("policies").select("policy_id, product_name, clients(name)").eq("policy_number", policy_number).single().execute()
        if not policy_result.data:
            return jsonify({'error': 'Policy not found'}), 404
        
        policy = policy_result.data
        members = []

        if "HEALTH" in policy.get('product_name', '').upper():
            health_details_res = supabase.table("health_insurance_details").select("health_id").eq("policy_id", policy['policy_id']).single().execute()
            if health_details_res.data:
                health_id = health_details_res.data['health_id']
                members_res = supabase.table("health_insured_members").select("member_name").eq("health_id", health_id).execute()
                if members_res.data:
                    members = sorted([m['member_name'] for m in members_res.data])
        
        if not members:
            member_res = supabase.table("policies").select("members(member_name)").eq("policy_id", policy['policy_id']).single().execute()
            if member_res.data and member_res.data.get('members'):
                members = [member_res.data['members']['member_name']]

        return jsonify({
            'client_name': policy['clients']['name'],
            'members': members
        })
        
    except Exception as e:
        logger.error(f"Error in policy lookup API: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

@claims_bp.route('/api/search-clients')
@login_required
def search_clients():
    """API endpoint to search for clients by name."""
    search_term = request.args.get('search', '').strip()
    if len(search_term) < 2:
        return jsonify({'clients': []})
        
    try:
        # Search clients by name (case-insensitive)
        result = supabase.table("clients").select("client_id, name").ilike("name", f"%{search_term}%").order("name").limit(10).execute()
        clients = result.data or []
        
        return jsonify({'clients': clients})
        
    except Exception as e:
        logger.error(f"Error searching clients: {e}")
        return jsonify({'error': 'Failed to search clients'}), 500

@claims_bp.route('/api/client-policies')
@login_required
def get_client_policies():
    """API endpoint to get all policies for a specific client."""
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({'error': 'Client ID is required'}), 400
        
    try:
        # Get all policies for the client
        policies_result = supabase.table("policies").select("policy_id, policy_number, product_name, members(member_name)").eq("client_id", client_id).order("policy_number").execute()
        
        if not policies_result.data:
            return jsonify({'policies': []})
        
        policies = []
        for policy in policies_result.data:
            # Get members for health insurance policies
            members = []
            if "HEALTH" in policy.get('product_name', '').upper():
                health_details_res = supabase.table("health_insurance_details").select("health_id").eq("policy_id", policy['policy_id']).execute()
                if health_details_res.data:
                    health_id = health_details_res.data[0]['health_id']
                    members_res = supabase.table("health_insured_members").select("member_name").eq("health_id", health_id).execute()
                    if members_res.data:
                        members = sorted([m['member_name'] for m in members_res.data])
            
            # Fallback to regular members table
            if not members and policy.get('members'):
                members = [policy['members']['member_name']]
            
            policies.append({
                'policy_id': policy['policy_id'],
                'policy_number': policy['policy_number'],
                'product_name': policy['product_name'],
                'members': members
            })
        
        return jsonify({'policies': policies})
        
    except Exception as e:
        logger.error(f"Error fetching client policies: {e}")
        return jsonify({'error': 'Failed to fetch client policies'}), 500

@claims_bp.route('/<int:claim_id>/update-status', methods=['POST'])
@login_required
def update_claim_status(claim_id):
    """Handles status updates and adds settlement information."""
    try:
        new_status = request.form.get('status')
        if not new_status:
            flash("Status is required.", "error")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
        update_data = {
            "status": new_status,
            "remarks": request.form.get('remarks', '')
        }
        
        # Handle claim number update
        claim_number_update = request.form.get('claim_number', '').strip()
        if claim_number_update:
            # Check if this claim number is already used by another claim
            existing_claim = supabase.table("claims").select("claim_id").eq("claim_number", claim_number_update).neq("claim_id", claim_id).execute()
            if existing_claim.data:
                flash(f"Claim number '{claim_number_update}' is already used by another claim.", "error")
                return redirect(url_for('claims.view_claim', claim_id=claim_id))
            update_data["claim_number"] = claim_number_update
        
        # Handle approved amount for APPROVED status
        if new_status == 'APPROVED':
            approved_amount = request.form.get('approved_amount')
            update_data["approved_amount"] = float(approved_amount) if approved_amount else None
        
        # Handle settlement information for SETTLED status
        if new_status == 'SETTLED':
            settled_amount = request.form.get('settled_amount')
            settlement_date = request.form.get('settlement_date')
            settled_amount_float = float(settled_amount) if settled_amount else None
            
            update_data["settled_amount"] = settled_amount_float
            
            # If approved_amount is not set, set it to settled_amount (they should be the same)
            if settled_amount_float and not update_data.get("approved_amount"):
                # Check if approved_amount is already set in database
                current_claim = supabase.table("claims").select("approved_amount").eq("claim_id", claim_id).single().execute()
                if current_claim.data and not current_claim.data.get("approved_amount"):
                    update_data["approved_amount"] = settled_amount_float
            
            # Convert settlement date from DD/MM/YYYY to YYYY-MM-DD
            if settlement_date:
                try:
                    if '/' in settlement_date:
                        day, month, year = settlement_date.split('/')
                        update_data["settlement_date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        update_data["settlement_date"] = settlement_date
                except:
                    update_data["settlement_date"] = None
            else:
                update_data["settlement_date"] = None
                
            update_data["utr_no"] = request.form.get('utr_no')
        
        supabase.table("claims").update(update_data).eq("claim_id", claim_id).execute()
        flash("Claim status updated successfully!", "success")
        
    except Exception as e:
        logger.error(f"Error updating status for claim {claim_id}: {e}")
        flash(f"Error updating status: {str(e)}", "error")
        
    return redirect(url_for('claims.view_claim', claim_id=claim_id))

@claims_bp.route('/<int:claim_id>/upload-document', methods=['POST'])
@login_required
def upload_document(claim_id):
    """Upload additional document to an existing claim."""
    try:
        claim_result = supabase.table("claims").select("*, policies(clients(client_id))").eq("claim_id", claim_id).single().execute()
        if not claim_result.data:
            flash("Claim not found", "error")
            return redirect(url_for('claims.index'))
        
        claim = claim_result.data
        client_id = claim['policies']['clients']['client_id']
        member_name = claim['member_name']
        
        file = request.files.get('document')
        document_type = request.form.get('document_type', 'OTHER')
        custom_document_type = request.form.get('custom_document_type', '')
        
        # If it's a custom type, use the custom name and save it to database
        if document_type == 'OTHER' and custom_document_type:
            custom_type = custom_document_type.strip().upper()
            # Save custom type to database if it doesn't exist
            try:
                existing = supabase.table("custom_document_types").select("id").eq("type_name", custom_type).execute()
                if not existing.data:
                    supabase.table("custom_document_types").insert({"type_name": custom_type}).execute()
                document_type = custom_type
            except:
                document_type = custom_type  # Use custom name even if saving fails
        
        if not file or not file.filename:
            flash("Please select a file to upload.", "error")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
        drive_file = upload_claim_document(file, client_id, member_name, claim_id, document_type)
        
        doc_data = {
            "claim_id": claim_id,
            "document_name": file.filename,
            "document_type": document_type,
            "drive_file_id": drive_file["id"],
            "drive_url": drive_file["webViewLink"],
            "drive_path": drive_file["drive_path"],
            "file_size": drive_file.get("file_size")
        }
        supabase.table("claim_documents").insert(doc_data).execute()
        
        flash("Document uploaded successfully!", "success")
    except Exception as e:
        logger.error(f"Error uploading additional document for claim {claim_id}: {e}")
        flash(f"Error uploading document: {str(e)}", "error")
        
    return redirect(url_for('claims.view_claim', claim_id=claim_id))