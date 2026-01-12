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
    """View all clients with their members and policies in hierarchical structure
    
    OPTIMIZED: Uses batch queries (3 total) instead of N+1 queries (200+)
    """
    try:
        import time
        start_time = time.time()
        
        # Get search parameter
        search_query = request.args.get("search", "").strip()

        # BATCH QUERY 1: Fetch ALL clients
        clients_result = supabase.table("clients").select("*").order("client_id").execute()
        all_clients = clients_result.data
        
        # BATCH QUERY 2: Fetch ALL members
        members_result = supabase.table("members").select("*").order("member_name").execute()
        all_members = members_result.data
        
        # BATCH QUERY 3: Fetch ALL policies (only essential fields for listing)
        policies_result = supabase.table("policies").select(
            "policy_id, member_id, client_id, insurance_company, product_name, policy_number, policy_from, policy_to, gross_premium"
        ).order("policy_to", desc=True).execute()
        all_policies = policies_result.data
        
        query_time = time.time() - start_time
        print(f"[OPTIMIZED] 3 batch queries completed in {query_time:.2f}s")
        
        # BUILD LOOKUP TABLES (in-memory joins)
        # Create member_id -> policies[] lookup
        policies_by_member = {}
        for policy in all_policies:
            member_id = policy.get('member_id')
            if member_id:
                if member_id not in policies_by_member:
                    policies_by_member[member_id] = []
                policies_by_member[member_id].append(policy)
        
        # Create client_id -> members[] lookup
        members_by_client = {}
        for member in all_members:
            client_id = member.get('client_id')
            if client_id:
                if client_id not in members_by_client:
                    members_by_client[client_id] = []
                members_by_client[client_id].append(member)
        
        # BUILD HIERARCHICAL STRUCTURE
        clients_data = []
        search_lower = search_query.lower() if search_query else None
        
        for client in all_clients:
            client_id = client['client_id']
            
            # Get members for this client from lookup
            client_members = members_by_client.get(client_id, [])
            
            # Build members with their policies
            members_with_policies = []
            total_client_policies = 0
            
            for member in client_members:
                member_id = member['member_id']
                
                # Get policies for this member from lookup
                member_policies = policies_by_member.get(member_id, [])
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
            if search_lower:
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

        total_time = time.time() - start_time
        print(f"[OPTIMIZED] Found {len(clients_data)} clients (filtered from {len(all_clients)} total) in {total_time:.2f}s")
        print(f"[OPTIMIZED] Stats: {len(all_clients)} clients, {len(all_members)} members, {len(all_policies)} policies")
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
            policy["customer_alternate_email"] = policy["clients"].get("alternate_email", "")
            policy["customer_alternate_phone"] = policy["clients"].get("alternate_phone", "")
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