from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from supabase import create_client, Client
from config import Config
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from datetime import datetime, date
import os

# Initialize Supabase client
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Google Drive setup
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "my-first-project-7fb14-715c168d62d2.json"

# Initialize Google Drive service
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

drive_service = get_drive_service()
ROOT_FOLDER_ID = "1BdQZhqJNJxFYzKJJmJxJJxJJxJJxJJxJ"  # Replace with your actual root folder ID

claims_bp = Blueprint('claims', __name__, url_prefix='/claims')

def find_or_create_folder(parent_folder_id, folder_name):
    """Find existing folder or create new one"""
    try:
        # Search for existing folder
        query = f"name='{folder_name}' and parents in '{parent_folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            return folders[0]
        else:
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'parents': [parent_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = drive_service.files().create(
                body=folder_metadata,
                supportsAllDrives=True
            ).execute()
            
            return folder
            
    except Exception as e:
        print(f"Error in find_or_create_folder: {e}")
        raise

def upload_claim_document(file, client_id, member_name, claim_id, document_type):
    """Upload claim document to Google Drive in organized folder structure"""
    print(f"\nUploading claim document: {file.filename}")
    print(f"   Client ID: {client_id}")
    print(f"   Member Name: {member_name}")
    print(f"   Claim ID: {claim_id}")
    print(f"   Document Type: {document_type}")

    try:
        # Step 1: Find or create client folder
        client_folder = find_or_create_folder(ROOT_FOLDER_ID, str(client_id))
        client_folder_id = client_folder['id']

        # Step 2: Find or create member subfolder
        member_folder = find_or_create_folder(client_folder_id, member_name)
        member_folder_id = member_folder['id']

        # Step 3: Find or create Claims folder
        claims_folder = find_or_create_folder(member_folder_id, "Claims")
        claims_folder_id = claims_folder['id']

        # Step 4: Find or create specific claim folder
        claim_folder_name = f"Claim_{claim_id}"
        claim_folder = find_or_create_folder(claims_folder_id, claim_folder_name)
        claim_folder_id = claim_folder['id']

        # Step 5: Find or create document type folder
        doc_type_folder = find_or_create_folder(claim_folder_id, document_type)
        doc_type_folder_id = doc_type_folder['id']

        # Step 6: Generate filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{client_id}_{member_name}_{document_type}_{timestamp}.{file_extension}"

        # Step 7: Upload file
        file_metadata = {"name": new_filename, "parents": [doc_type_folder_id]}
        file_content = file.read()

        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=file.mimetype, resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size",
            supportsAllDrives=True
        ).execute()

        drive_path = f"{client_id}/{member_name}/Claims/Claim_{claim_id}/{document_type}/{new_filename}"

        print(f"Claim document uploaded successfully!")
        print(f"   Drive Path: {drive_path}")
        print(f"   Drive URL: {uploaded_file.get('webViewLink')}")

        return {
            "id": uploaded_file.get("id"),
            "webViewLink": uploaded_file.get("webViewLink"),
            "drive_path": drive_path,
            "file_size": uploaded_file.get("size")
        }

    except Exception as e:
        print(f"Error uploading claim document: {e}")
        raise

@claims_bp.route('/')
def index():
    """View all claims"""
    try:
        # Get all claims with policy and client information
        result = (
            supabase.table("claims")
            .select("*, policies(policy_number, clients(name), members(member_name))")
            .order("created_at", desc=True)
            .execute()
        )
        
        claims = result.data if result.data else []
        
        # Get claims statistics
        stats = {
            'total': len(claims),
            'pending': len([c for c in claims if c['status'] == 'PENDING']),
            'processing': len([c for c in claims if c['status'] == 'PROCESSING']),
            'approved': len([c for c in claims if c['status'] == 'APPROVED']),
            'settled': len([c for c in claims if c['status'] == 'SETTLED']),
            'rejected': len([c for c in claims if c['status'] == 'REJECTED'])
        }
        
        return render_template('claims.html', claims=claims, stats=stats)
        
    except Exception as e:
        print(f"Error fetching claims: {e}")
        flash(f"Error loading claims: {str(e)}", "error")
        return render_template('claims.html', claims=[], stats={})

@claims_bp.route('/add', methods=['GET', 'POST'])
def add_claim():
    """Add new claim"""
    if request.method == 'POST':
        try:
            # Get form data
            policy_number = request.form.get('policy_number')
            member_name = request.form.get('member_name')
            claim_type = request.form.get('claim_type')
            diagnosis = request.form.get('diagnosis')
            hospital_name = request.form.get('hospital_name')
            admission_date = request.form.get('admission_date')
            discharge_date = request.form.get('discharge_date')
            claimed_amount = request.form.get('claimed_amount')
            settled_amount = request.form.get('settled_amount')
            settlement_date = request.form.get('settlement_date')
            utr_no = request.form.get('utr_no')
            status = request.form.get('status', 'PENDING')
            remarks = request.form.get('remarks')

            # Validate required fields
            if not policy_number or not member_name or not claim_type:
                flash("Policy number, member name, and claim type are required", "error")
                return redirect(url_for('claims.add_claim'))

            # Find policy
            policy_result = supabase.table("policies").select("policy_id, client_id, clients(name)").eq("policy_number", policy_number).execute()
            
            if not policy_result.data:
                flash("Policy not found", "error")
                return redirect(url_for('claims.add_claim'))
            
            policy = policy_result.data[0]
            policy_id = policy['policy_id']
            client_id = policy['client_id']
            client_name = policy['clients']['name']

            # Convert date strings to proper format
            def convert_date(date_str):
                if date_str:
                    try:
                        # Handle DD/MM/YYYY format
                        if '/' in date_str:
                            day, month, year = date_str.split('/')
                            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        return date_str
                    except:
                        return None
                return None

            # Prepare claim data
            claim_data = {
                "policy_id": policy_id,
                "member_name": member_name,
                "claim_type": claim_type,
                "diagnosis": diagnosis,
                "hospital_name": hospital_name,
                "status": status,
                "remarks": remarks
            }

            # Add optional fields
            if admission_date:
                claim_data["admission_date"] = convert_date(admission_date)
            if discharge_date:
                claim_data["discharge_date"] = convert_date(discharge_date)
            if claimed_amount:
                claim_data["claimed_amount"] = float(claimed_amount)
            if settled_amount:
                claim_data["settled_amount"] = float(settled_amount)
            if settlement_date:
                claim_data["settlement_date"] = convert_date(settlement_date)
            if utr_no:
                claim_data["utr_no"] = utr_no

            # Insert claim
            result = supabase.table("claims").insert(claim_data).execute()
            claim = result.data[0]
            claim_id = claim["claim_id"]

            print(f"Claim created successfully: {result.data}")

            # Handle document uploads
            uploaded_files = request.files.getlist('claim_documents')
            document_types = request.form.getlist('document_types')

            if uploaded_files and uploaded_files[0].filename:
                for i, file in enumerate(uploaded_files):
                    if file and file.filename:
                        try:
                            # Get document type for this file
                            doc_type = document_types[i] if i < len(document_types) else 'OTHER'
                            
                            # Upload to Google Drive
                            drive_file = upload_claim_document(file, client_id, member_name, claim_id, doc_type)
                            
                            # Save document record
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
                            print(f"Document uploaded: {file.filename}")
                            
                        except Exception as e:
                            print(f"Error uploading document {file.filename}: {e}")
                            flash(f"Error uploading document {file.filename}: {str(e)}", "warning")

            flash("Claim added successfully!", "success")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))

        except Exception as e:
            print(f"Error adding claim: {e}")
            flash(f"Error adding claim: {str(e)}", "error")
            return redirect(url_for('claims.add_claim'))

    return render_template('add_claim.html')

@claims_bp.route('/<int:claim_id>')
def view_claim(claim_id):
    """View claim details"""
    try:
        # Get claim with policy and client information
        claim_result = (
            supabase.table("claims")
            .select("*, policies(policy_number, clients(name, client_id), members(member_name))")
            .eq("claim_id", claim_id)
            .single()
            .execute()
        )
        
        if not claim_result.data:
            flash("Claim not found", "error")
            return redirect(url_for('claims.index'))
        
        claim = claim_result.data
        
        # Get claim documents
        docs_result = (
            supabase.table("claim_documents")
            .select("*")
            .eq("claim_id", claim_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        
        documents = docs_result.data if docs_result.data else []
        
        return render_template('view_claim.html', claim=claim, documents=documents)
        
    except Exception as e:
        print(f"Error fetching claim: {e}")
        flash(f"Error loading claim: {str(e)}", "error")
        return redirect(url_for('claims.index'))

@claims_bp.route('/api/policy-lookup')
def policy_lookup():
    """API endpoint to lookup policy by policy number"""
    try:
        policy_number = request.args.get('policy_number')
        if not policy_number:
            return jsonify({'error': 'Policy number is required'}), 400
        
        # Get policy with health insurance members
        policy_result = (
            supabase.table("policies")
            .select("policy_id, policy_number, client_id, member_id, clients(name), members(member_name)")
            .eq("policy_number", policy_number)
            .execute()
        )
        
        if not policy_result.data:
            return jsonify({'error': 'Policy not found'}), 404
        
        policy = policy_result.data[0]
        
        # Get health insurance members for this policy
        health_members = []
        try:
            health_result = (
                supabase.table("health_insurance_details")
                .select("health_id")
                .eq("policy_id", policy['policy_id'])
                .execute()
            )
            
            if health_result.data:
                health_id = health_result.data[0]['health_id']
                members_result = (
                    supabase.table("health_insured_members")
                    .select("member_name")
                    .eq("health_id", health_id)
                    .execute()
                )
                
                if members_result.data:
                    health_members = [m['member_name'] for m in members_result.data]
        except:
            pass  # Health insurance details might not exist
        
        # If no health members, use the main policy member
        if not health_members and policy.get('members'):
            health_members = [policy['members']['member_name']]
        
        return jsonify({
            'policy_id': policy['policy_id'],
            'policy_number': policy['policy_number'],
            'client_name': policy['clients']['name'],
            'client_id': policy['client_id'],
            'members': health_members
        })
        
    except Exception as e:
        print(f"Error in policy lookup: {e}")
        return jsonify({'error': str(e)}), 500

@claims_bp.route('/<int:claim_id>/update-status', methods=['POST'])
def update_claim_status(claim_id):
    """Update claim status"""
    try:
        new_status = request.form.get('status')
        remarks = request.form.get('remarks', '')
        
        if not new_status:
            flash("Status is required", "error")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
        update_data = {
            "status": new_status,
            "remarks": remarks
        }
        
        # If status is SETTLED, update settlement date
        if new_status == 'SETTLED':
            settlement_date = request.form.get('settlement_date')
            settled_amount = request.form.get('settled_amount')
            utr_no = request.form.get('utr_no')
            
            if settlement_date:
                update_data["settlement_date"] = settlement_date
            if settled_amount:
                update_data["settled_amount"] = float(settled_amount)
            if utr_no:
                update_data["utr_no"] = utr_no
        
        supabase.table("claims").update(update_data).eq("claim_id", claim_id).execute()
        
        flash("Claim status updated successfully!", "success")
        return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
    except Exception as e:
        print(f"Error updating claim status: {e}")
        flash(f"Error updating claim status: {str(e)}", "error")
        return redirect(url_for('claims.view_claim', claim_id=claim_id))

@claims_bp.route('/<int:claim_id>/upload-document', methods=['POST'])
def upload_document(claim_id):
    """Upload additional document to existing claim"""
    try:
        # Get claim details
        claim_result = (
            supabase.table("claims")
            .select("*, policies(client_id)")
            .eq("claim_id", claim_id)
            .single()
            .execute()
        )
        
        if not claim_result.data:
            flash("Claim not found", "error")
            return redirect(url_for('claims.index'))
        
        claim = claim_result.data
        client_id = claim['policies']['client_id']
        member_name = claim['member_name']
        
        file = request.files.get('document')
        document_type = request.form.get('document_type', 'OTHER')
        
        if not file or not file.filename:
            flash("Please select a file to upload", "error")
            return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
        # Upload to Google Drive
        drive_file = upload_claim_document(file, client_id, member_name, claim_id, document_type)
        
        # Save document record
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
        return redirect(url_for('claims.view_claim', claim_id=claim_id))
        
    except Exception as e:
        print(f"Error uploading document: {e}")
        flash(f"Error uploading document: {str(e)}", "error")
        return redirect(url_for('claims.view_claim', claim_id=claim_id))
