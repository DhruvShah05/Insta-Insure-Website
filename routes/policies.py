# routes/policies.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import datetime, io, os, tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from supabase import create_client
from dynamic_config import Config

# Import WhatsApp functionality
from whatsapp_bot import send_policy_to_customer, normalize_phone

# Import PDF conversion utility
from utils.pdf_converter import convert_pdf_for_twilio


def convert_date_format(date_string):
    """Convert DD/MM/YYYY to YYYY-MM-DD for database storage"""
    if not date_string:
        return None
    try:
        # If already in YYYY-MM-DD format, return as is
        if '-' in date_string and len(date_string.split('-')[0]) == 4:
            return date_string
        # Convert DD/MM/YYYY to YYYY-MM-DD
        if '/' in date_string:
            parts = date_string.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_string
    except:
        return date_string

def _is_factory_insurance(product_name):
    """Check if a product is a factory-type insurance that requires factory details"""
    if not product_name:
        return False
    
    product_upper = product_name.upper()
    return (
        "FACTORY" in product_upper or
        "BHARAT GRIHA RAKSHA" in product_upper or
        "BHARAT SOOKSHMA UDYAM SURAKSHA" in product_upper or
        "BHARAT LAGHU UDYAM SURAKSHA" in product_upper
    )

policies_bp = Blueprint("policies", __name__)

# Initialize Supabase
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Google Drive setup
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "my-first-project-7fb14-715c168d62d2.json"


def get_drive_service():
    """Initialize and return Google Drive service with comprehensive SSL error handling"""
    try:
        import ssl
        import httplib2
        from google.auth.transport.requests import Request
        
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        
        # Try multiple connection methods
        connection_methods = [
            ("Standard SSL", lambda: build("drive", "v3", credentials=creds)),
            ("Disabled SSL Cert Validation", lambda: build("drive", "v3", credentials=creds, 
                http=httplib2.Http(disable_ssl_certificate_validation=True))),
            ("Custom SSL Context", lambda: build_with_custom_ssl(creds))
        ]
        
        for method_name, method_func in connection_methods:
            try:
                print(f"Attempting Google Drive connection using: {method_name}")
                service = method_func()
                print(f"✅ Google Drive connected successfully using: {method_name}")
                return service
            except Exception as method_error:
                print(f"❌ {method_name} failed: {method_error}")
                continue
        
        print("❌ All Google Drive connection methods failed")
        return None
            
    except Exception as e:
        print(f"Error initializing Google Drive service: {e}")
        return None

def build_with_custom_ssl(creds):
    """Build Google Drive service with custom SSL context"""
    import ssl
    import httplib2
    
    # Create custom SSL context with relaxed settings
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Create HTTP with custom SSL context
    http = httplib2.Http()
    
    return build("drive", "v3", credentials=creds, http=http)


# Initialize drive service
drive_service = get_drive_service()

# Root folder in Google Drive where month folders exist
# Now loaded from settings/config instead of hardcoded
ROOT_FOLDER_ID = Config.ROOT_FOLDER_ID or "0AOc3bRLhlrgzUk9PVA"  # Fallback to old value if not set


def test_drive_connection():
    """Test function to verify Drive API connection and folder access"""
    print("\n" + "=" * 50)
    print("GOOGLE DRIVE CONNECTION TEST")
    print("=" * 50)

    try:
        print("\nGoogle Drive API connection successful")

        print(f"\n--- Testing access to folder ID: {ROOT_FOLDER_ID} ---")
        try:
            folder = drive_service.files().get(
                fileId=ROOT_FOLDER_ID,
                fields="id, name, mimeType, capabilities",
                supportsAllDrives=True
            ).execute()
            print(f"Folder found: '{folder['name']}'")
            print(f"   Type: {folder['mimeType']}")

            capabilities = folder.get('capabilities', {})
            can_edit = capabilities.get('canEdit', False)
            can_add_children = capabilities.get('canAddChildren', False)
            print(f"   Can Edit: {can_edit}")
            print(f"   Can Add Children: {can_add_children}")

            if not can_add_children:
                print("\nWARNING: Service account doesn't have permission to add files!")
                print("   Change permissions from 'Viewer' to 'Editor'")

            print(f"\n--- Contents of '{folder['name']}' ---")
            query = f"'{ROOT_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            items = results.get('files', [])
            print(f"Found {len(items)} month folders:")
            for item in items:
                print(f"  {item['name']} (ID: {item['id']})")

            if len(items) == 0:
                print("\nWARNING: No folders found!")

        except Exception as e:
            print(f"Cannot access folder: {e}")

    except Exception as e:
        print(f"Drive API connection failed: {e}")

    print("\n" + "=" * 50 + "\n")


def get_month_folder_id(root_folder_id, month_name):
    """Search for a subfolder by name inside the root folder"""
    print(f"\n=== Searching for folder: '{month_name}' ===")
    print(f"Root folder ID: {root_folder_id}")

    all_folders_query = (
        f"mimeType='application/vnd.google-apps.folder' and "
        f"'{root_folder_id}' in parents and trashed=false"
    )
    all_folders_result = drive_service.files().list(
        q=all_folders_query,
        spaces='drive',
        fields='files(id, name)'
    ).execute()

    all_folders = all_folders_result.get('files', [])
    print(f"\nAll folders found in root folder ({len(all_folders)} total):")
    for folder in all_folders:
        print(f"  - '{folder['name']}' (ID: {folder['id']})")

    query = (
        f"mimeType='application/vnd.google-apps.folder' and "
        f"name='{month_name}' and '{root_folder_id}' in parents and trashed=false"
    )
    results = drive_service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, webViewLink)'
    ).execute()

    files = results.get('files', [])
    if not files:
        print(f"\nERROR: Folder '{month_name}' not found!")
        print(f"Available folder names: {[f['name'] for f in all_folders]}")
        raise ValueError(
            f"Folder '{month_name}' not found in root folder. Available folders: {[f['name'] for f in all_folders]}")

    print(f"Found folder: '{files[0]['name']}' (ID: {files[0]['id']})\n")
    return files[0]


def find_month_folder(root_folder_id, month_name):
    query = f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='{month_name}'"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    folders = results.get("files", [])

    if folders:
        print(f"Found {month_name} folder with ID: {folders[0]['id']}")
        return folders[0]
    else:
        raise Exception(f"{month_name} folder not found")


def find_or_create_folder(parent_folder_id, folder_name):
    """Find existing folder or create new one in parent folder"""
    print(f"Looking for folder '{folder_name}' in parent {parent_folder_id}")

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
        print(f"Found existing folder: {folders[0]['name']} (ID: {folders[0]['id']})")
        return folders[0]
    else:
        # Create new folder
        print(f"Creating new folder: {folder_name}")
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

        print(f"Created folder: {created_folder['name']} (ID: {created_folder['id']})")
        return created_folder


def upload_policy_file(file, client_id, member_name):
    """Upload file to Google Drive in client/member folder structure with PDF conversion"""
    print(f"\nUploading file: {file.filename}")
    print(f"   Client ID: {client_id}")
    print(f"   Member Name: {member_name}")

    # Step 1: Find or create client folder
    client_folder = find_or_create_folder(ROOT_FOLDER_ID, client_id)
    client_folder_id = client_folder['id']

    # Step 2: Find or create member subfolder
    member_folder = find_or_create_folder(client_folder_id, member_name)
    member_folder_id = member_folder['id']

    # Step 3: Generate filename with format: Client ID - Member Name - File.PDF
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
    new_filename = f"{client_id} - {member_name} - {file.filename}"

    # Step 4: Convert PDF to Twilio-compatible format before uploading
    file_content = None
    converted_path = None
    
    try:
        if file_extension.lower() == 'pdf':
            print("   Converting PDF to Twilio-compatible format...")
            
            # Convert PDF using print-to-PDF approach
            success, converted_path, error = convert_pdf_for_twilio(file)
            
            if success and converted_path:
                # Read converted file
                with open(converted_path, 'rb') as f:
                    file_content = f.read()
                print("   ✓ PDF converted successfully")
            else:
                print(f"   ⚠ PDF conversion failed: {error}, using original file")
                file.seek(0)
                file_content = file.read()
        else:
            # Not a PDF, use original content
            file_content = file.read()
    except Exception as e:
        print(f"   ⚠ Error during PDF conversion: {e}, using original file")
        file.seek(0)
        file_content = file.read()
    finally:
        # Clean up temporary converted file
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except:
                pass

    # Step 5: Upload file to member folder
    file_metadata = {"name": new_filename, "parents": [member_folder_id]}

    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf', resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True
    ).execute()

    drive_path = f"{client_id}/{member_name}/{new_filename}"

    print(f"File uploaded successfully!")
    print(f"   Drive Path: {drive_path}")
    print(f"   Drive URL: {uploaded_file.get('webViewLink')}")

    return {
        "id": uploaded_file.get("id"),
        "webViewLink": uploaded_file.get("webViewLink"),
        "drive_path": drive_path
    }


def archive_policy_file(file_id, client_id, member_name, filename):
    """Move file to archive with year-based folder structure"""
    import datetime

    current_year = datetime.datetime.now().year
    # Financial year format: 2024-25, 2025-26, etc.
    if datetime.datetime.now().month >= 4:  # April onwards is new financial year
        financial_year = f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        financial_year = f"{current_year - 1}-{str(current_year)[-2:]}"

    print(f"\nArchiving file: {filename}")
    print(f"   Financial Year: {financial_year}")
    print(f"   Client ID: {client_id}")
    print(f"   Member Name: {member_name}")

    # Assume ARCHIVE_FOLDER_ID is defined (you'll need to set this)
    # For now, we'll create archive folder in root if it doesn't exist
    archive_folder = find_or_create_folder(ROOT_FOLDER_ID, "Archive")
    archive_folder_id = archive_folder['id']

    # Step 1: Find or create financial year folder
    year_folder = find_or_create_folder(archive_folder_id, financial_year)
    year_folder_id = year_folder['id']

    # Step 2: Find or create client folder in year folder
    client_folder = find_or_create_folder(year_folder_id, client_id)
    client_folder_id = client_folder['id']

    # Step 3: Find or create member folder in client folder
    member_folder = find_or_create_folder(client_folder_id, member_name)
    member_folder_id = member_folder['id']

    # Step 4: Move file to archive location
    try:
        # Update file's parent to move it to archive
        drive_service.files().update(
            fileId=file_id,
            addParents=member_folder_id,
            removeParents=ROOT_FOLDER_ID,  # Remove from current location
            supportsAllDrives=True
        ).execute()

        archive_path = f"Archive/{financial_year}/{client_id}/{member_name}/{filename}"
        print(f"File archived successfully to: {archive_path}")
        return archive_path

    except Exception as e:
        print(f"Error archiving file: {e}")
        return None


@policies_bp.route("/test_drive")
@login_required
def test_drive():
    """Test endpoint to check Google Drive connection"""
    test_drive_connection()
    return "<pre>Check your console/terminal for detailed output</pre>"


@policies_bp.route("/list_all_folders")
@login_required
def list_all_folders():
    """List all folders accessible by the service account"""
    print("\n" + "=" * 50)
    print("LISTING ALL ACCESSIBLE FOLDERS")
    print("=" * 50 + "\n")

    try:
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name, parents, webViewLink)',
            pageSize=100
        ).execute()

        folders = results.get('files', [])
        print(f"Found {len(folders)} folders:\n")

        for folder in folders:
            print(f"{folder['name']}")
            print(f"   ID: {folder['id']}")
            print(f"   Link: {folder.get('webViewLink', 'N/A')}")
            print()

        if len(folders) == 0:
            print("WARNING: No folders found!")

    except Exception as e:
        print(f"Error: {e}")

    print("=" * 50 + "\n")
    return "<pre>Check your console/terminal for the list of folders</pre>"


@policies_bp.route("/get_clients")
@login_required
def get_clients():
    """API endpoint to get all existing clients"""
    try:
        result = supabase.table("clients").select("client_id, name, email, phone").execute()
        return jsonify(result.data)
    except Exception as e:
        print(f"Error fetching clients: {e}")
        return jsonify({"error": str(e)}), 500


@policies_bp.route("/get_members")
@login_required
def get_members():
    """Get members for a client"""
    try:
        client_id = request.args.get("client_id")  # Remove int() conversion since client_id is now a string
        result = supabase.table("members").select("member_id, member_name").eq("client_id", client_id).order("member_id").execute()
        return jsonify(result.data)
    except Exception as e:
        print(f"Error fetching members: {e}")
        return jsonify({"error": str(e)}), 500


@policies_bp.route("/create_member", methods=["POST"])
@login_required
def create_member():
    """Create a new member for a client"""
    try:
        client_id = request.json.get("client_id")  # Remove int() conversion since client_id is now a string
        member_name = request.json.get("member_name")
        if not member_name:
            return jsonify({"error": "member_name required"}), 400
        result = supabase.table("members").insert({
            "client_id": client_id,
            "member_name": member_name
        }).execute()
        return jsonify(result.data[0])
    except Exception as e:
        print(f"Error creating member: {e}")
        return jsonify({"error": str(e)}), 500


@policies_bp.route("/test_backend")
@login_required
def test_backend():
    """Test endpoint to verify backend is working"""
    return jsonify({
        "status": "success",
        "message": "Backend is working properly",
        "timestamp": datetime.datetime.now().isoformat()
    })

@policies_bp.route("/test_drive_connection")
@login_required
def test_drive_connection_endpoint():
    """Test Google Drive connectivity"""
    try:
        global drive_service
        if not drive_service:
            drive_service = get_drive_service()
        
        if drive_service:
            # Try a simple API call
            results = drive_service.files().list(pageSize=1).execute()
            return jsonify({
                "status": "success",
                "message": "Google Drive connection successful",
                "files_accessible": len(results.get('files', []))
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Could not establish Google Drive connection"
            }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Google Drive test failed: {str(e)}"
        }), 500

@policies_bp.route("/add_policy", methods=["GET", "POST"])
@login_required
def add_policy():
    if request.method == "POST":
        print("\n" + "="*50)
        print("ADD POLICY FORM SUBMITTED")
        print("="*50)
        print(f"Form data received: {dict(request.form)}")
        print(f"Files received: {list(request.files.keys())}")
        
        # Basic validation to catch issues early
        required_fields = ['customer_type', 'insurance_company', 'policy_number']
        missing_fields = []
        for field in required_fields:
            if not request.form.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for("policies.add_policy"))
        
        if 'policy_file' not in request.files:
            print("❌ No policy file uploaded")
            flash("Please upload a policy file", "error")
            return redirect(url_for("policies.add_policy"))
        
        print("✅ Basic validation passed, processing...")
        try:
            customer_type = request.form.get("customer_type")
            insurance_company = request.form.get("insurance_company")
            product_name = request.form.get("product_name")
            policy_number = request.form.get("policy_number")
            payment_date = request.form.get("payment_date")
            agent_name = request.form.get("agent_name")
            policy_from = request.form.get("policy_from")
            policy_to = request.form.get("policy_to")
            one_time_insurance = True if request.form.get("one_time_insurance") in ["on", "true", "1"] else False
            payment_details = request.form.get("payment_details")
            net_premium = request.form.get("net_premium")
            addon_premium = request.form.get("addon_premium")  # NEW
            tp_tr_premium = request.form.get("tp_tr_premium")
            gst_percentage = request.form.get("gst_percentage")  # NEW
            gross_premium = request.form.get("gross_premium")  # This will be auto-calculated
            commission_percentage = request.form.get("commission_percentage")
            commission_amount = request.form.get("commission_amount")  # NEW
            commission_received = True if request.form.get("commission_received") in ["on", "true", "1"] else False
            business_type = request.form.get("business_type")
            group_name = request.form.get("group_name")
            subgroup_name = request.form.get("subgroup_name")
            remarks = request.form.get("remarks")
            file = request.files.get("policy_file")
            send_via_whatsapp = request.form.get("send_via_whatsapp") == "yes"  # NEW
            sum_insured = request.form.get("sum_insured")
            
            # Health insurance specific fields
            health_plan_type = request.form.get("health_plan_type")
            health_member_names = request.form.getlist("health_member_name[]")
            health_member_sum_insureds = request.form.getlist("health_member_sum_insured[]")
            health_member_bonuses = request.form.getlist("health_member_bonus[]")
            health_member_deductibles = request.form.getlist("health_member_deductible[]")
            
            # Floater-specific fields (single sum_insured, bonus, and deductible for entire policy)
            floater_sum_insured = request.form.get("floater_sum_insured")
            floater_bonus = request.form.get("floater_bonus")
            floater_deductible = request.form.get("floater_deductible")
            
            # Factory insurance specific fields
            factory_building = request.form.get("factory_building")
            factory_plant_machinery = request.form.get("factory_plant_machinery")
            factory_furniture_fittings = request.form.get("factory_furniture_fittings")
            factory_stocks = request.form.get("factory_stocks")
            factory_electrical_installations = request.form.get("factory_electrical_installations")

            if not file:
                flash("Please upload a file", "error")
                return redirect(url_for("policies.add_policy"))

            if not policy_number:
                flash("Policy number is required", "error")
                return redirect(url_for("policies.add_policy"))

            # Handle client/member creation or selection
            client_id = None
            member_id = None
            customer_phone = None  # used for WhatsApp

            if customer_type == "new":
                customer_name = request.form.get("customer_name")
                customer_email = request.form.get("customer_email")
                customer_phone = request.form.get("customer_phone")  # NEW
                client_prefix = request.form.get("client_prefix")  # NEW
                member_name = request.form.get("member_name") or customer_name

                if not customer_name:
                    flash("Customer name is required", "error")
                    return redirect(url_for("policies.add_policy"))

                if not client_prefix:
                    flash("Client prefix is required", "error")
                    return redirect(url_for("policies.add_policy"))

                # Create client (auto identity with prefix)
                client_result = supabase.table("clients").insert({
                    "prefix": client_prefix.upper(),
                    "name": customer_name,
                    "email": customer_email,
                    "phone": customer_phone
                }).execute()

                client_id = client_result.data[0]["client_id"]
                print(f"Created new client with id: {client_id}")

                # Create member for the client
                member_result = supabase.table("members").insert({
                    "client_id": client_id,
                    "member_name": member_name
                }).execute()
                member_id = member_result.data[0]["member_id"]
                print(f"Created new member with id: {member_id}")

            elif customer_type == "existing":
                client_id = request.form.get("existing_client_id")
                member_id = request.form.get("existing_member_id")
                new_member_name = request.form.get("new_member_name")

                if not client_id:
                    flash("Please select a client", "error")
                    return redirect(url_for("policies.add_policy"))

                # client_id is now a string (e.g., "DS01"), no need to convert to int

                # Ensure member exists; if not provided, create from new_member_name or default to client name
                if not member_id:
                    try:
                        client_row = supabase.table("clients").select("name, phone").eq("client_id", client_id).single().execute()
                        chosen_member_name = new_member_name if new_member_name else (client_row.data.get("name") if client_row and client_row.data else "Member")
                        customer_phone = client_row.data.get("phone") if client_row and client_row.data else None
                        member_result = supabase.table("members").insert({
                            "client_id": client_id,
                            "member_name": chosen_member_name
                        }).execute()
                        member_id = member_result.data[0]["member_id"]
                    except Exception as e:
                        print(f"Error creating default member: {e}")
                        flash("Could not create default member", "error")
                        return redirect(url_for("policies.add_policy"))
                else:
                    member_id = int(member_id)

                    # Fetch client phone for WhatsApp  # NEW
                    try:
                        client_result = supabase.table("clients").select("phone").eq("client_id",
                                                                                     client_id).single().execute()
                        customer_phone = client_result.data.get("phone")
                    except Exception as e:
                        print(f"Error fetching client phone: {e}")
                        customer_phone = None

                print(f"Using existing client {client_id} and member {member_id}")
            else:
                flash("Invalid customer type", "error")
                return redirect(url_for("policies.add_policy"))

            # Get client and member information for file upload
            try:
                # Get client info
                client_result = supabase.table("clients").select("client_id, name").eq("client_id", client_id).single().execute()
                client_data = client_result.data

                # Get member info
                member_result = supabase.table("members").select("member_name").eq("member_id", member_id).single().execute()
                member_data = member_result.data

                client_id_str = client_data['client_id']
                member_name_str = member_data['member_name']

            except Exception as e:
                print(f"Error getting client/member info: {e}")
                flash(f"Error retrieving client information: {str(e)}", "error")
                return redirect(url_for("policies.add_policy"))

            # Upload file to Google Drive with fallback
            print("Uploading file to Google Drive...")
            drive_file = None
            try:
                drive_file = upload_policy_file(file, client_id_str, member_name_str)
                print(f"File uploaded successfully: {drive_file}")
            except Exception as e:
                print(f"Drive upload error: {e}")
                
                # Fallback: Save file locally and continue with policy creation
                print("Attempting local file storage as fallback...")
                try:
                    import os
                    from werkzeug.utils import secure_filename
                    
                    # Create local storage directory
                    upload_folder = os.path.join(os.getcwd(), 'local_uploads', client_id_str, member_name_str)
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Save file locally
                    filename = secure_filename(file.filename)
                    local_path = os.path.join(upload_folder, filename)
                    file.seek(0)  # Reset file pointer
                    file.save(local_path)
                    
                    # Create fallback drive_file object
                    drive_file = {
                        "id": f"local_{client_id_str}_{member_name_str}_{filename}",
                        "webViewLink": f"file://{local_path}",
                        "drive_path": f"local/{client_id_str}/{member_name_str}/{filename}"
                    }
                    
                    print(f"File saved locally: {local_path}")
                    flash("File uploaded locally (Google Drive unavailable). Policy created successfully.", "warning")
                    
                except Exception as local_error:
                    print(f"Local storage also failed: {local_error}")
                    flash(f"Error uploading file: {str(e)}. Please try again or contact support.", "error")
                    return redirect(url_for("policies.add_policy"))

            # Insert policy metadata into Supabase
            print("Inserting policy into Supabase...")
            try:
                policy_data = {
                    "client_id": client_id,
                    "member_id": member_id,
                    "insurance_company": insurance_company,
                    "product_name": product_name,
                    "policy_number": policy_number,
                    "one_time_insurance": one_time_insurance,
                    "commission_received": commission_received,
                    "file_path": file.filename,
                    "drive_file_id": drive_file.get("id"),
                    "drive_path": drive_file.get("drive_path"),
                    "drive_url": drive_file.get("webViewLink")
                }

                # Add optional fields
                if payment_date:
                    policy_data["payment_date"] = convert_date_format(payment_date)
                if agent_name:
                    policy_data["agent_name"] = agent_name
                if policy_from:
                    policy_data["policy_from"] = convert_date_format(policy_from)
                if policy_to:
                    policy_data["policy_to"] = convert_date_format(policy_to)
                if payment_details:
                    policy_data["payment_details"] = payment_details
                if net_premium:
                    policy_data["net_premium"] = float(net_premium)
                if addon_premium:
                    policy_data["addon_premium"] = float(addon_premium)
                if tp_tr_premium:
                    policy_data["tp_tr_premium"] = float(tp_tr_premium)
                if gst_percentage:
                    policy_data["gst_percentage"] = float(gst_percentage)
                if gross_premium:
                    policy_data["gross_premium"] = float(gross_premium)
                if commission_percentage:
                    policy_data["commission_percentage"] = float(commission_percentage)
                if commission_amount:
                    policy_data["commission_amount"] = float(commission_amount)
                if business_type:
                    policy_data["business_type"] = business_type
                if group_name:
                    policy_data["group_name"] = group_name
                if subgroup_name:
                    policy_data["subgroup_name"] = subgroup_name
                if remarks:
                    policy_data["remarks"] = remarks
                if sum_insured:
                    policy_data["sum_insured"] = float(sum_insured)

                result = supabase.table("policies").insert(policy_data).execute()
                inserted_policy = result.data[0]
                policy_id = inserted_policy["policy_id"]
                print(f"Policy inserted successfully: {result.data}")
                
                # Handle health insurance details if applicable
                if product_name and "HEALTH" in product_name.upper() and health_plan_type:
                    try:
                        # Insert health insurance details
                        health_details = {
                            "policy_id": policy_id,
                            "plan_type": health_plan_type
                        }
                        
                        # Add floater-specific fields if it's a floater plan
                        if health_plan_type in ["FLOATER", "TOPUP_FLOATER"]:
                            if floater_sum_insured:
                                health_details["floater_sum_insured"] = float(floater_sum_insured)
                            if floater_bonus:
                                health_details["floater_bonus"] = float(floater_bonus)
                            if health_plan_type == "TOPUP_FLOATER" and floater_deductible:
                                health_details["floater_deductible"] = float(floater_deductible)
                        
                        health_result = supabase.table("health_insurance_details").insert(health_details).execute()
                        health_id = health_result.data[0]["health_id"]
                        
                        # Insert health insured members
                        if health_member_names:
                            for i, member_name in enumerate(health_member_names):
                                if member_name.strip():  # Only insert non-empty names
                                    member_data = {
                                        "health_id": health_id,
                                        "member_name": member_name.strip()
                                    }
                                    
                                    # For INDIVIDUAL plans, store sum_insured, bonus, and deductible per member
                                    # For FLOATER plans, only store member names (sum_insured, bonus, and deductible are in health_details)
                                    if health_plan_type in ["INDIVIDUAL", "TOPUP_INDIVIDUAL"]:
                                        if i < len(health_member_sum_insureds) and health_member_sum_insureds[i]:
                                            member_data["sum_insured"] = float(health_member_sum_insureds[i])
                                        if i < len(health_member_bonuses) and health_member_bonuses[i]:
                                            member_data["bonus"] = float(health_member_bonuses[i])
                                        if health_plan_type == "TOPUP_INDIVIDUAL" and i < len(health_member_deductibles) and health_member_deductibles[i]:
                                            member_data["deductible"] = float(health_member_deductibles[i])
                                    
                                    supabase.table("health_insured_members").insert(member_data).execute()
                        
                        print(f"Health insurance details saved for policy {policy_id} with plan type {health_plan_type}")
                    except Exception as e:
                        print(f"Error saving health insurance details: {e}")
                        # Don't fail the whole operation, just log the error
                
                # Handle factory insurance details if applicable
                elif product_name and _is_factory_insurance(product_name):
                    try:
                        factory_details = {"policy_id": policy_id}
                        
                        if factory_building:
                            factory_details["building"] = float(factory_building)
                        if factory_plant_machinery:
                            factory_details["plant_machinery"] = float(factory_plant_machinery)
                        if factory_furniture_fittings:
                            factory_details["furniture_fittings"] = float(factory_furniture_fittings)
                        if factory_stocks:
                            factory_details["stocks"] = float(factory_stocks)
                        if factory_electrical_installations:
                            factory_details["electrical_installations"] = float(factory_electrical_installations)
                        
                        # Only insert if we have at least one factory detail
                        if len(factory_details) > 1:  # More than just policy_id
                            supabase.table("factory_insurance_details").insert(factory_details).execute()
                            print(f"Factory insurance details saved for policy {policy_id}")
                    except Exception as e:
                        print(f"Error saving factory insurance details: {e}")
                        # Don't fail the whole operation, just log the error

                # NEW: Handle WhatsApp sending
                if send_via_whatsapp and customer_phone:
                    try:
                        phone = normalize_phone(customer_phone)
                        success, message = send_policy_to_customer(phone, inserted_policy)
                        if success:
                            flash("Policy added and sent via WhatsApp successfully!", "success")
                        else:
                            flash(f"Policy added but WhatsApp send failed: {message}", "warning")
                    except Exception as whatsapp_error:
                        print(f"WhatsApp error: {whatsapp_error}")
                        flash("Policy added but could not send via WhatsApp", "warning")
                elif send_via_whatsapp and not customer_phone:
                    flash("Policy added but customer has no phone number for WhatsApp", "warning")
                else:
                    flash("Policy added successfully!", "success")

                return redirect(url_for("dashboard.index"))

            except Exception as e:
                print(f"Database error: {e}")
                flash(f"Error saving policy to database: {str(e)}", "error")
                return redirect(url_for("policies.add_policy"))

        except Exception as e:
            print(f"General error: {e}")
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for("policies.add_policy"))

    # Get default GST percentage from settings
    default_gst = Config.DEFAULT_GST_PERCENTAGE
    return render_template("add_policy.html", current_user=current_user, default_gst=default_gst)


@policies_bp.route("/edit_policy/<int:policy_id>", methods=["GET", "POST"])
@login_required
def edit_policy(policy_id):
    if request.method == "POST":
        print("\n" + "="*50)
        print(f"EDIT POLICY {policy_id} FORM SUBMITTED")
        print("="*50)
        print(f"Form data received: {dict(request.form)}")
        
        try:
            # Extract form data
            insurance_company = request.form.get("insurance_company")
            product_name = request.form.get("product_name")
            policy_number = request.form.get("policy_number")
            payment_date = request.form.get("payment_date")
            agent_name = request.form.get("agent_name")
            policy_from = request.form.get("policy_from")
            policy_to = request.form.get("policy_to")
            one_time_insurance = True if request.form.get("one_time_insurance") in ["on", "true", "1"] else False
            payment_details = request.form.get("payment_details")
            net_premium = request.form.get("net_premium")
            addon_premium = request.form.get("addon_premium")
            tp_tr_premium = request.form.get("tp_tr_premium")
            gst_percentage = request.form.get("gst_percentage")
            gross_premium = request.form.get("gross_premium")
            commission_percentage = request.form.get("commission_percentage")
            commission_amount = request.form.get("commission_amount")
            commission_received = True if request.form.get("commission_received") in ["on", "true", "1"] else False
            business_type = request.form.get("business_type")
            group_name = request.form.get("group_name")
            subgroup_name = request.form.get("subgroup_name")
            remarks = request.form.get("remarks")
            sum_insured = request.form.get("sum_insured")
            
            # Health insurance specific fields
            health_plan_type = request.form.get("health_plan_type")
            health_member_names = request.form.getlist("health_member_name[]")
            health_member_sum_insureds = request.form.getlist("health_member_sum_insured[]")
            health_member_bonuses = request.form.getlist("health_member_bonus[]")
            health_member_deductibles = request.form.getlist("health_member_deductible[]")
            
            # Floater-specific fields
            floater_sum_insured = request.form.get("floater_sum_insured")
            floater_bonus = request.form.get("floater_bonus")
            floater_deductible = request.form.get("floater_deductible")
            
            # Factory insurance specific fields
            factory_building = request.form.get("factory_building")
            factory_plant_machinery = request.form.get("factory_plant_machinery")
            factory_furniture_fittings = request.form.get("factory_furniture_fittings")
            factory_stocks = request.form.get("factory_stocks")
            factory_electrical_installations = request.form.get("factory_electrical_installations")

            # Build update data
            policy_data = {
                "insurance_company": insurance_company,
                "product_name": product_name,
                "policy_number": policy_number,
                "one_time_insurance": one_time_insurance,
                "commission_received": commission_received,
            }

            # Add optional fields
            if payment_date:
                policy_data["payment_date"] = convert_date_format(payment_date)
            if agent_name:
                policy_data["agent_name"] = agent_name
            if policy_from:
                policy_data["policy_from"] = convert_date_format(policy_from)
            if policy_to:
                policy_data["policy_to"] = convert_date_format(policy_to)
            if payment_details:
                policy_data["payment_details"] = payment_details
            if net_premium:
                policy_data["net_premium"] = float(net_premium)
            if addon_premium:
                policy_data["addon_premium"] = float(addon_premium)
            if tp_tr_premium:
                policy_data["tp_tr_premium"] = float(tp_tr_premium)
            if gst_percentage:
                policy_data["gst_percentage"] = float(gst_percentage)
            if gross_premium:
                policy_data["gross_premium"] = float(gross_premium)
            if commission_percentage:
                policy_data["commission_percentage"] = float(commission_percentage)
            if commission_amount:
                policy_data["commission_amount"] = float(commission_amount)
            if business_type:
                policy_data["business_type"] = business_type
            if group_name:
                policy_data["group_name"] = group_name
            if subgroup_name:
                policy_data["subgroup_name"] = subgroup_name
            if remarks:
                policy_data["remarks"] = remarks
            if sum_insured:
                policy_data["sum_insured"] = float(sum_insured)

            # Update policy in database
            result = supabase.table("policies").update(policy_data).eq("policy_id", policy_id).execute()
            print(f"Policy updated successfully: {result.data}")
            
            # Handle health insurance details if applicable
            if product_name and "HEALTH" in product_name.upper() and health_plan_type:
                try:
                    # Check if health details exist
                    health_check = supabase.table("health_insurance_details").select("health_id").eq("policy_id", policy_id).execute()
                    
                    health_details = {
                        "plan_type": health_plan_type
                    }
                    
                    # Add floater-specific fields if it's a floater plan
                    if health_plan_type in ["FLOATER", "TOPUP_FLOATER"]:
                        if floater_sum_insured:
                            health_details["floater_sum_insured"] = float(floater_sum_insured)
                        if floater_bonus:
                            health_details["floater_bonus"] = float(floater_bonus)
                        if health_plan_type == "TOPUP_FLOATER" and floater_deductible:
                            health_details["floater_deductible"] = float(floater_deductible)
                    
                    if health_check.data:
                        # Update existing health details
                        health_id = health_check.data[0]["health_id"]
                        supabase.table("health_insurance_details").update(health_details).eq("health_id", health_id).execute()
                        
                        # Delete existing members and re-insert
                        supabase.table("health_insured_members").delete().eq("health_id", health_id).execute()
                    else:
                        # Insert new health details
                        health_details["policy_id"] = policy_id
                        health_result = supabase.table("health_insurance_details").insert(health_details).execute()
                        health_id = health_result.data[0]["health_id"]
                    
                    # Insert health insured members
                    if health_member_names:
                        for i, member_name in enumerate(health_member_names):
                            if member_name.strip():
                                member_data = {
                                    "health_id": health_id,
                                    "member_name": member_name.strip()
                                }
                                
                                if health_plan_type in ["INDIVIDUAL", "TOPUP_INDIVIDUAL"]:
                                    if i < len(health_member_sum_insureds) and health_member_sum_insureds[i]:
                                        member_data["sum_insured"] = float(health_member_sum_insureds[i])
                                    if i < len(health_member_bonuses) and health_member_bonuses[i]:
                                        member_data["bonus"] = float(health_member_bonuses[i])
                                    if health_plan_type == "TOPUP_INDIVIDUAL" and i < len(health_member_deductibles) and health_member_deductibles[i]:
                                        member_data["deductible"] = float(health_member_deductibles[i])
                                
                                supabase.table("health_insured_members").insert(member_data).execute()
                    
                    print(f"Health insurance details updated for policy {policy_id}")
                except Exception as e:
                    print(f"Error updating health insurance details: {e}")
            
            # Handle factory insurance details if applicable
            elif product_name and _is_factory_insurance(product_name):
                try:
                    # Check if factory details exist
                    factory_check = supabase.table("factory_insurance_details").select("factory_id").eq("policy_id", policy_id).execute()
                    
                    factory_details = {}
                    
                    if factory_building:
                        factory_details["building"] = float(factory_building)
                    if factory_plant_machinery:
                        factory_details["plant_machinery"] = float(factory_plant_machinery)
                    if factory_furniture_fittings:
                        factory_details["furniture_fittings"] = float(factory_furniture_fittings)
                    if factory_stocks:
                        factory_details["stocks"] = float(factory_stocks)
                    if factory_electrical_installations:
                        factory_details["electrical_installations"] = float(factory_electrical_installations)
                    
                    if factory_check.data:
                        # Update existing factory details
                        factory_id = factory_check.data[0]["factory_id"]
                        if factory_details:
                            supabase.table("factory_insurance_details").update(factory_details).eq("factory_id", factory_id).execute()
                    else:
                        # Insert new factory details
                        if factory_details:
                            factory_details["policy_id"] = policy_id
                            supabase.table("factory_insurance_details").insert(factory_details).execute()
                    
                    print(f"Factory insurance details updated for policy {policy_id}")
                except Exception as e:
                    print(f"Error updating factory insurance details: {e}")

            flash("Policy updated successfully!", "success")
            return redirect(url_for("dashboard.view_all_policies"))

        except Exception as e:
            print(f"Error updating policy: {e}")
            flash(f"Error updating policy: {str(e)}", "error")
            return redirect(url_for("policies.edit_policy", policy_id=policy_id))

    # GET request - load policy data
    try:
        # Fetch policy with client and member info
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )
        
        policy = result.data
        
        # Fetch health insurance details if applicable
        health_details = None
        health_members = []
        if policy.get("product_name") and "HEALTH" in policy["product_name"].upper():
            health_result = supabase.table("health_insurance_details").select("*").eq("policy_id", policy_id).execute()
            if health_result.data:
                health_details = health_result.data[0]
                health_id = health_details["health_id"]
                
                # Fetch health insured members
                members_result = supabase.table("health_insured_members").select("*").eq("health_id", health_id).execute()
                health_members = members_result.data
        
        # Fetch factory insurance details if applicable
        factory_details = None
        if policy.get("product_name") and _is_factory_insurance(policy["product_name"]):
            factory_result = supabase.table("factory_insurance_details").select("*").eq("policy_id", policy_id).execute()
            if factory_result.data:
                factory_details = factory_result.data[0]
        
        # Get default GST percentage from settings
        default_gst = Config.DEFAULT_GST_PERCENTAGE
        
        return render_template(
            "edit_policy.html",
            policy=policy,
            health_details=health_details,
            health_members=health_members,
            factory_details=factory_details,
            current_user=current_user,
            default_gst=default_gst
        )
        
    except Exception as e:
        print(f"Error fetching policy: {e}")
        flash(f"Error loading policy: {str(e)}", "error")
        return redirect(url_for("dashboard.view_all_policies"))