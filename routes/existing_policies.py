# routes/existing_policies.py - Now handles client-centric view
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from supabase import create_client
from dynamic_config import Config

existing_policies_bp = Blueprint("existing_policies", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@existing_policies_bp.route("/existing_policies")
@login_required
def list_all():
    """View all clients with their members and policies in hierarchical structure"""
    try:
        # Get search parameter
        search_query = request.args.get("search", "").strip()

        # Fetch all clients with their data
        clients_result = supabase.table("clients").select("*").order("client_id").execute()
        all_clients = clients_result.data

        # Build hierarchical structure: Clients -> Members -> Policies
        clients_data = []
        
        for client in all_clients:
            client_id = client['client_id']
            
            # Get all members for this client
            members_result = supabase.table("members").select("*").eq("client_id", client_id).order("member_name").execute()
            client_members = members_result.data
            
            # For each member, get their policies
            members_with_policies = []
            total_client_policies = 0
            
            for member in client_members:
                member_id = member['member_id']
                
                # Get all policies for this member
                policies_result = (
                    supabase.table("policies")
                    .select("*")
                    .eq("member_id", member_id)
                    .order("policy_to", desc=True)
                    .execute()
                )
                
                member_policies = policies_result.data
                total_client_policies += len(member_policies)
                
                # Add policies to member data
                member['policies'] = member_policies
                member['policy_count'] = len(member_policies)
                members_with_policies.append(member)
            
            # Add member data to client
            client['members'] = members_with_policies
            client['total_policies'] = total_client_policies
            client['member_count'] = len(members_with_policies)
            
            # Apply search filter if provided
            if search_query:
                search_lower = search_query.lower()
                # Search in client name, client ID, member names, or policy details
                client_matches = (
                    search_lower in client['name'].lower() or
                    search_lower in client['client_id'].lower() or
                    any(search_lower in member['member_name'].lower() for member in members_with_policies) or
                    any(
                        any(
                            search_lower in str(policy.get('insurance_company', '')).lower() or
                            search_lower in str(policy.get('product_name', '')).lower() or
                            search_lower in str(policy.get('policy_number', '')).lower()
                            for policy in member['policies']
                        )
                        for member in members_with_policies
                    )
                )
                
                if client_matches:
                    clients_data.append(client)
            else:
                clients_data.append(client)

        print(f"Found {len(clients_data)} clients (filtered from {len(all_clients)} total)")
        print(f"Search query: '{search_query}'")

        return render_template(
            "view_all_clients.html",
            clients=clients_data,
            current_search=search_query,
            total_clients=len(clients_data),
            current_user=current_user
        )

    except Exception as e:
        print(f"Error fetching clients: {e}")
        flash(f"Error loading clients: {str(e)}", "error")
        return render_template("view_all_clients.html", clients=[], current_search="", total_clients=0, current_user=current_user)


@existing_policies_bp.route("/view_policy/<int:policy_id>")
@login_required
def view_policy(policy_id):
    """View detailed information about a specific policy"""
    try:
        result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("policy_id", policy_id)
            .single()
            .execute()
        )

        policy = result.data

        # Flatten customer data
        if policy.get("clients"):
            policy["customer_name"] = policy["clients"]["name"]
            policy["customer_email"] = policy["clients"]["email"]
            policy["customer_phone"] = policy["clients"].get("phone", "")
        if policy.get("members"):
            policy["member_name"] = policy["members"].get("member_name", "")

        return render_template("view_policy.html", policy=policy, current_user=current_user)

    except Exception as e:
        print(f"Error fetching policy: {e}")
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("existing_policies.list_all"))


@existing_policies_bp.route("/delete_policy/<int:policy_id>", methods=["POST"])
@login_required
def delete_policy(policy_id):
    """Delete a policy"""
    try:
        supabase.table("policies").delete().eq("policy_id", policy_id).execute()
        flash("Policy deleted successfully", "success")
    except Exception as e:
        print(f"Error deleting policy: {e}")
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("existing_policies.list_all"))