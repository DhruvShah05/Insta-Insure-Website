# routes/pending_policies.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from supabase import create_client
from config import Config
from datetime import datetime


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

pending_policies_bp = Blueprint("pending_policies", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

@pending_policies_bp.route("/test_pending_backend")
@login_required
def test_pending_backend():
    """Test endpoint to verify pending policies backend is working"""
    return jsonify({
        "status": "success",
        "message": "Pending policies backend is working properly",
        "timestamp": datetime.now().isoformat()
    })


@pending_policies_bp.route("/pending_policies")
@login_required
def list_pending():
    """View all pending policies"""
    try:
        result = (
            supabase.table("pending_policies")
            .select("*, clients(*), members(*)")
            .order("created_at", desc=True)
            .execute()
        )

        pending = result.data

        # Flatten customer data
        for policy in pending:
            if policy.get("clients"):
                policy["customer_name"] = policy["clients"]["name"]
                policy["customer_email"] = policy["clients"]["email"]
                policy["customer_phone"] = policy["clients"].get("phone", "")
            if policy.get("members"):
                policy["member_name"] = policy["members"].get("member_name", "")
            else:
                policy["customer_name"] = "Unknown"
                policy["customer_email"] = ""
                policy["customer_phone"] = ""

        print(f"Found {len(pending)} pending policies")
        return render_template("pending_policies.html", pending_policies=pending)

    except Exception as e:
        print(f"Error fetching pending policies: {e}")
        flash(f"Error loading pending policies: {str(e)}", "error")
        return render_template("pending_policies.html", pending_policies=[])


@pending_policies_bp.route("/add_pending", methods=["GET", "POST"])
@login_required
def add_pending():
    """Add a new pending policy"""
    if request.method == "POST":
        print("\n" + "="*50)
        print("ADD PENDING POLICY FORM SUBMITTED")
        print("="*50)
        print(f"Form data received: {dict(request.form)}")
        
        # Basic validation to catch issues early
        required_fields = ['customer_type', 'insurance_company', 'product_name']
        missing_fields = []
        for field in required_fields:
            if not request.form.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for("pending_policies.add_pending"))
        
        print("✅ Basic validation passed, processing...")
        try:
            customer_type = request.form.get("customer_type")
            insurance_company = request.form.get("insurance_company")
            product_name = request.form.get("product_name")
            agent_name = request.form.get("agent_name")
            remarks = request.form.get("remarks")
            policy_from = request.form.get("policy_from")
            policy_to = request.form.get("policy_to")
            payment_date = request.form.get("payment_date")
            net_premium = request.form.get("net_premium")
            gross_premium = request.form.get("gross_premium")
            tp_tr_premium = request.form.get("tp_tr_premium")
            commission_percentage = request.form.get("commission_percentage")
            business_type = request.form.get("business_type")
            group_name = request.form.get("group_name")
            subgroup_name = request.form.get("subgroup_name")
            payment_details = request.form.get("payment_details")
            one_time_insurance = True if request.form.get("one_time_insurance") in ["on", "true", "1"] else False
            commission_received = True if request.form.get("commission_received") in ["on", "true", "1"] else False
            sum_insured = request.form.get("sum_insured")
            
            # Health insurance specific fields
            health_plan_type = request.form.get("health_plan_type")
            health_member_names = request.form.getlist("health_member_name[]")
            health_member_sum_insureds = request.form.getlist("health_member_sum_insured[]")
            health_member_bonuses = request.form.getlist("health_member_bonus[]")
            
            # Factory insurance specific fields
            factory_building = request.form.get("factory_building")
            factory_plant_machinery = request.form.get("factory_plant_machinery")
            factory_furniture_fittings = request.form.get("factory_furniture_fittings")
            factory_stocks = request.form.get("factory_stocks")
            factory_electrical_installations = request.form.get("factory_electrical_installations")

            # Handle client/member creation or selection
            client_id = None
            member_id = None

            if customer_type == "new":
                customer_name = request.form.get("customer_name")
                customer_email = request.form.get("customer_email")
                customer_phone = request.form.get("customer_phone")
                client_prefix = request.form.get("client_prefix")
                member_name = request.form.get("member_name") or customer_name

                if not customer_name:
                    flash("Customer name is required", "error")
                    return redirect(url_for("pending_policies.add_pending"))
                
                if not client_prefix:
                    flash("Client prefix is required", "error")
                    return redirect(url_for("pending_policies.add_pending"))

                # Insert client with prefix
                client_result = supabase.table("clients").insert({
                    "prefix": client_prefix.upper(),
                    "name": customer_name,
                    "email": customer_email,
                    "phone": customer_phone
                }).execute()
                client_id = client_result.data[0]["client_id"]

                # Insert member
                member_result = supabase.table("members").insert({
                    "client_id": client_id,
                    "member_name": member_name
                }).execute()
                member_id = member_result.data[0]["member_id"]

            elif customer_type == "existing":
                client_id = request.form.get("existing_client_id")
                member_id = request.form.get("existing_member_id")
                new_member_name = request.form.get("new_member_name")
                if not client_id:
                    flash("Please select a client", "error")
                    return redirect(url_for("pending_policies.add_pending"))
                # client_id is now a string (e.g., "DS01"), no need to convert to int
                if member_id:
                    member_id = int(member_id)  # member_id is still an integer
                else:
                    # create new member using provided new_member_name or fallback to client name
                    client_row = supabase.table("clients").select("name").eq("client_id", client_id).single().execute()
                    chosen_member_name = new_member_name if new_member_name else (client_row.data.get("name") if client_row and client_row.data else "Member")
                    member_result = supabase.table("members").insert({
                        "client_id": client_id,  # Remove int() conversion since client_id is now a string
                        "member_name": chosen_member_name
                    }).execute()
                    member_id = member_result.data[0]["member_id"]
                print(f"Using existing client {client_id} and member {member_id}")
            else:
                flash("Invalid customer type", "error")
                return redirect(url_for("pending_policies.add_pending"))

            # Insert pending policy - ensure all fields are captured
            pending_data = {
                "client_id": client_id,
                "member_id": member_id,
                "insurance_company": insurance_company,
                "product_name": product_name,
                "one_time_insurance": one_time_insurance,
                "commission_received": commission_received
            }

            # Add optional fields
            if agent_name:
                pending_data["agent_name"] = agent_name
            if remarks:
                pending_data["remarks"] = remarks
            if policy_from:
                pending_data["policy_from"] = convert_date_format(policy_from)
            if policy_to:
                pending_data["policy_to"] = convert_date_format(policy_to)
            if payment_date:
                pending_data["payment_date"] = convert_date_format(payment_date)
            if payment_details:
                pending_data["payment_details"] = payment_details
            if net_premium:
                pending_data["net_premium"] = float(net_premium)
            if gross_premium:
                pending_data["gross_premium"] = float(gross_premium)
            if tp_tr_premium:
                pending_data["tp_tr_premium"] = float(tp_tr_premium)
            if commission_percentage:
                pending_data["commission_percentage"] = float(commission_percentage)
            if business_type:
                pending_data["business_type"] = business_type
            if group_name:
                pending_data["group_name"] = group_name
            if subgroup_name:
                pending_data["subgroup_name"] = subgroup_name
            if sum_insured:
                pending_data["sum_insured"] = float(sum_insured)

            result = supabase.table("pending_policies").insert(pending_data).execute()
            pending_policy = result.data[0]
            pending_id = pending_policy["pending_id"]
            print(f"Pending policy created: {result.data}")
            
            # Handle health insurance details if applicable
            if product_name and "HEALTH" in product_name.upper() and health_plan_type:
                try:
                    # Insert pending health insurance details
                    health_details = {
                        "pending_id": pending_id,
                        "plan_type": health_plan_type
                    }
                    health_result = supabase.table("pending_health_insurance_details").insert(health_details).execute()
                    pending_health_id = health_result.data[0]["pending_health_id"]
                    
                    # Insert health insured members
                    if health_member_names:
                        for i, member_name in enumerate(health_member_names):
                            if member_name.strip():  # Only insert non-empty names
                                member_data = {
                                    "pending_health_id": pending_health_id,
                                    "member_name": member_name.strip()
                                }
                                if i < len(health_member_sum_insureds) and health_member_sum_insureds[i]:
                                    member_data["sum_insured"] = float(health_member_sum_insureds[i])
                                if i < len(health_member_bonuses) and health_member_bonuses[i]:
                                    member_data["bonus"] = float(health_member_bonuses[i])
                                
                                supabase.table("pending_health_insured_members").insert(member_data).execute()
                    
                    print(f"Health insurance details saved for pending policy {pending_id}")
                except Exception as e:
                    print(f"Error saving health insurance details: {e}")
                    # Don't fail the whole operation, just log the error
            
            # Handle factory insurance details if applicable
            elif product_name and "FACTORY" in product_name.upper():
                try:
                    factory_details = {"pending_id": pending_id}
                    
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
                    if len(factory_details) > 1:  # More than just pending_id
                        supabase.table("pending_factory_insurance_details").insert(factory_details).execute()
                        print(f"Factory insurance details saved for pending policy {pending_id}")
                except Exception as e:
                    print(f"Error saving factory insurance details: {e}")
                    # Don't fail the whole operation, just log the error

            flash("Pending policy added successfully!", "success")
            return redirect(url_for("pending_policies.list_pending"))

        except Exception as e:
            print(f"Error adding pending policy: {e}")
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("pending_policies.add_pending"))

    return render_template("add_pending_policy.html")


@pending_policies_bp.route("/complete_pending/<int:pending_id>", methods=["GET", "POST"])
@login_required
def complete_pending(pending_id):
    """Complete a pending policy by uploading document and converting to active policy"""
    if request.method == "POST":
        try:
            from routes.policies import upload_policy_file

            file = request.files.get("policy_file")
            policy_number = request.form.get("policy_number")
            send_to_customer = request.form.get("send_to_customer") == "yes"  # NEW

            if not file:
                flash("Please upload a policy document", "error")
                return redirect(url_for("pending_policies.complete_pending", pending_id=pending_id))

            # Get pending policy data with customer info
            pending_result = (
                supabase.table("pending_policies")
                .select("*, clients(*), members(*)")
                .eq("pending_id", pending_id)
                .single()
                .execute()
            )
            pending = pending_result.data
            customer = pending.get("clients", {})
            
            # Get health insurance details if they exist
            health_details = None
            health_members = []
            try:
                health_result = supabase.table("pending_health_insurance_details").select("*").eq("pending_id", pending_id).execute()
                if health_result.data:
                    health_details = health_result.data[0]
                    # Get health members
                    members_result = supabase.table("pending_health_insured_members").select("*").eq("pending_health_id", health_details["pending_health_id"]).execute()
                    health_members = members_result.data
            except Exception as e:
                print(f"Error fetching health details: {e}")
            
            # Get factory insurance details if they exist
            factory_details = None
            try:
                factory_result = supabase.table("pending_factory_insurance_details").select("*").eq("pending_id", pending_id).execute()
                if factory_result.data:
                    factory_details = factory_result.data[0]
            except Exception as e:
                print(f"Error fetching factory details: {e}")

            # Get client and member information for file upload
            try:
                # Get client info
                client_result = supabase.table("clients").select("client_id, name").eq("client_id", pending["client_id"]).single().execute()
                client_data = client_result.data
                
                # Get member info  
                member_result = supabase.table("members").select("member_name").eq("member_id", pending["member_id"]).single().execute()
                member_data = member_result.data
                
                client_id_str = client_data['client_id']
                member_name_str = member_data['member_name']
                
            except Exception as e:
                print(f"Error getting client/member info: {e}")
                flash(f"Error retrieving client information: {str(e)}", "error")
                return redirect(url_for("pending_policies.complete_pending", pending_id=pending_id))

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
                    flash("File uploaded locally (Google Drive unavailable). Policy completed successfully.", "warning")
                    
                except Exception as local_error:
                    print(f"Local storage also failed: {local_error}")
                    flash(f"Error uploading file: {str(e)}. Please try again or contact support.", "error")
                    return redirect(url_for("pending_policies.complete_pending", pending_id=pending_id))

            # Create active policy
            policy_data = {
                "client_id": pending["client_id"],
                "member_id": pending["member_id"],
                "insurance_company": pending.get("insurance_company"),
                "product_name": pending.get("product_name"),
                "agent_name": pending.get("agent_name"),
                "payment_date": pending.get("payment_date"),
                "policy_from": pending.get("policy_from"),
                "policy_to": pending.get("policy_to"),
                "one_time_insurance": pending.get("one_time_insurance", False),
                "payment_details": pending.get("payment_details"),
                "net_premium": pending.get("net_premium"),
                "gross_premium": pending.get("gross_premium"),
                "tp_tr_premium": pending.get("tp_tr_premium"),
                "commission_percentage": pending.get("commission_percentage"),
                "commission_received": pending.get("commission_received", False),
                "business_type": pending.get("business_type"),
                "group_name": pending.get("group_name"),
                "subgroup_name": pending.get("subgroup_name"),
                "file_path": file.filename,
                "drive_file_id": drive_file.get("id"),
                "drive_path": drive_file.get("drive_path"),
                "drive_url": drive_file.get("webViewLink")
            }

            if policy_number:
                policy_data["policy_number"] = policy_number
            if pending.get("remarks"):
                policy_data["remarks"] = pending["remarks"]
            

            # Insert into policies table
            policy_result = supabase.table("policies").insert(policy_data).execute()
            inserted_policy = policy_result.data[0]
            new_policy_id = inserted_policy["policy_id"]
            print(f"Active policy created: {policy_result.data}")
            
            # Transfer health insurance details if they exist
            if health_details:
                try:
                    # Insert health insurance details for active policy
                    active_health_details = {
                        "policy_id": new_policy_id,
                        "plan_type": health_details["plan_type"]
                    }
                    active_health_result = supabase.table("health_insurance_details").insert(active_health_details).execute()
                    active_health_id = active_health_result.data[0]["health_id"]
                    
                    # Transfer health insured members
                    for member in health_members:
                        member_data = {
                            "health_id": active_health_id,
                            "member_name": member["member_name"]
                        }
                        if member.get("sum_insured"):
                            member_data["sum_insured"] = member["sum_insured"]
                        if member.get("bonus"):
                            member_data["bonus"] = member["bonus"]
                        
                        supabase.table("health_insured_members").insert(member_data).execute()
                    
                    print(f"Health insurance details transferred to active policy {new_policy_id}")
                except Exception as e:
                    print(f"Error transferring health insurance details: {e}")
            
            # Transfer factory insurance details if they exist
            if factory_details:
                try:
                    active_factory_details = {"policy_id": new_policy_id}
                    
                    if factory_details.get("building"):
                        active_factory_details["building"] = factory_details["building"]
                    if factory_details.get("plant_machinery"):
                        active_factory_details["plant_machinery"] = factory_details["plant_machinery"]
                    if factory_details.get("furniture_fittings"):
                        active_factory_details["furniture_fittings"] = factory_details["furniture_fittings"]
                    if factory_details.get("stocks"):
                        active_factory_details["stocks"] = factory_details["stocks"]
                    if factory_details.get("electrical_installations"):
                        active_factory_details["electrical_installations"] = factory_details["electrical_installations"]
                    
                    # Only insert if we have factory details beyond just policy_id
                    if len(active_factory_details) > 1:
                        supabase.table("factory_insurance_details").insert(active_factory_details).execute()
                        print(f"Factory insurance details transferred to active policy {new_policy_id}")
                except Exception as e:
                    print(f"Error transferring factory insurance details: {e}")

            # Remove pending policy and related details after completion
            try:
                # Delete health insurance details if they exist
                if health_details:
                    # Delete health members first (foreign key constraint)
                    supabase.table("pending_health_insured_members").delete().eq("pending_health_id", health_details["pending_health_id"]).execute()
                    # Delete health details
                    supabase.table("pending_health_insurance_details").delete().eq("pending_id", pending_id).execute()
                
                # Delete factory insurance details if they exist
                if factory_details:
                    supabase.table("pending_factory_insurance_details").delete().eq("pending_id", pending_id).execute()
                
                # Finally delete the pending policy
                supabase.table("pending_policies").delete().eq("pending_id", pending_id).execute()
                print(f"Pending policy {pending_id} and related details deleted")
            except Exception as e:
                print(f"Error deleting pending policy details: {e}")
                # Still try to delete the main pending policy
                supabase.table("pending_policies").delete().eq("pending_id", pending_id).execute()

            # NEW: Send to customer if checkbox was ticked
            if send_to_customer:
                messages = []

                # Send via WhatsApp if phone available
                if customer.get("phone"):
                    try:
                        from whatsapp_bot import send_policy_to_customer, normalize_phone
                        phone = normalize_phone(customer["phone"])
                        whatsapp_success, whatsapp_msg = send_policy_to_customer(phone, inserted_policy)

                        if whatsapp_success:
                            messages.append("WhatsApp: Sent successfully")
                        else:
                            messages.append(f"WhatsApp: {whatsapp_msg}")
                    except Exception as e:
                        print(f"WhatsApp error: {e}")
                        messages.append("WhatsApp: Failed to send")

                # Send via Email if email available
                if customer.get("email"):
                    try:
                        from whatsapp_bot import extract_file_id_from_url, download_file_from_drive, delete_temp_file
                        from email_service import send_policy_email

                        # Download file temporarily for email
                        file_id = extract_file_id_from_url(inserted_policy.get('drive_url'))
                        if file_id:
                            filename = f"{inserted_policy['insurance_company']}_{inserted_policy['product_name']}.pdf".replace(
                                ' ', '_')
                            temp_file_path = download_file_from_drive(file_id, filename)

                            if temp_file_path:
                                email_success, email_msg = send_policy_email(
                                    customer["email"],
                                    customer["name"],
                                    inserted_policy,
                                    temp_file_path
                                )

                                if email_success:
                                    messages.append("Email: Sent successfully")
                                else:
                                    messages.append(f"Email: {email_msg}")

                                # Clean up temp file
                                delete_temp_file(temp_file_path)
                    except Exception as e:
                        print(f"Email error: {e}")
                        messages.append("Email: Failed to send")

                if messages:
                    flash(f"Policy completed! Delivery status: {' | '.join(messages)}", "success")
                else:
                    flash("Policy completed but customer has no contact information", "warning")
            else:
                flash("Policy completed and moved to active policies!", "success")

            return redirect(url_for("pending_policies.list_pending"))

        except Exception as e:
            print(f"Error completing policy: {e}")
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("pending_policies.complete_pending", pending_id=pending_id))

    # GET request - show form
    try:
        result = (
            supabase.table("pending_policies")
            .select("*, clients(*), members(*)")
            .eq("pending_id", pending_id)
            .single()
            .execute()
        )
        pending = result.data

        # Flatten customer data
        if pending.get("clients"):
            pending["customer_name"] = pending["clients"]["name"]
            pending["customer_email"] = pending["clients"]["email"]
            pending["customer_phone"] = pending["clients"].get("phone", "")
        if pending.get("members"):
            pending["member_name"] = pending["members"].get("member_name", "")

        return render_template("complete_pending.html", pending=pending)

    except Exception as e:
        print(f"Error fetching pending policy: {e}")
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("pending_policies.list_pending"))


@pending_policies_bp.route("/delete_pending/<int:pending_id>", methods=["POST"])
@login_required
def delete_pending(pending_id):
    """Delete a pending policy"""
    try:
        supabase.table("pending_policies").delete().eq("pending_id", pending_id).execute()
        flash("Pending policy deleted successfully", "success")
    except Exception as e:
        print(f"Error deleting pending policy: {e}")
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("pending_policies.list_pending"))