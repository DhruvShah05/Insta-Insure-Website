from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from supabase import create_client
from dynamic_config import Config
from datetime import datetime, timedelta
import math

dashboard_bp = Blueprint("dashboard", __name__)

supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@dashboard_bp.route("/")
@login_required
def index():
    """
    Dashboard showing policies expiring in the next 30 days and expired within last 30 days
    """
    today = datetime.today().strftime("%Y-%m-%d")
    next_month = (datetime.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    last_month = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Check if we should show hidden policies
    show_hidden = request.args.get("show_hidden", "false").lower() == "true"

    try:
        # Get policies expiring soon OR expired within last 30 days (exclude pending renewals)
        query = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .eq("is_pending_renewal", False)  # Exclude pending renewals from dashboard
            .gte("policy_to", last_month)  # Include policies expired within last 30 days
            .lte("policy_to", next_month)
            .order("policy_to", desc=False)
        )
        
        # Filter out hidden policies unless show_hidden is true
        if not show_hidden:
            query = query.eq("is_hidden_from_renewals", False)
        
        policies_result = query.execute()

        policies = policies_result.data

        # Flatten the customer data for easier template access
        for policy in policies:
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

        print(f"Found {len(policies)} policies between {last_month} and {next_month}")

        # Get total active policies count
        total_policies_result = supabase.table("policies").select("policy_id", count="exact").execute()
        total_active_policies = total_policies_result.count if total_policies_result.count else 0

        # Get pending policies count
        pending_policies_result = supabase.table("pending_policies").select("pending_id", count="exact").execute()
        total_pending_policies = pending_policies_result.count if pending_policies_result.count else 0

        # --- NEW: Get total claims count ---
        claims_result = supabase.table("claims").select("claim_id", count="exact").execute()
        total_claims = claims_result.count or 0

        print(f"Total active policies: {total_active_policies}")
        print(f"Total pending policies: {total_pending_policies}")

    except Exception as e:
        print(f"Error fetching policies: {e}")
        policies = []
        total_active_policies = 0
        total_pending_policies = 0
        total_claims = 0

    return render_template("dashboard.html", 
                         policies=policies, 
                         total_active_policies=total_active_policies,
                         total_pending_policies=total_pending_policies,
                         total_claims=total_claims,
                         show_hidden=show_hidden,
                         current_user=current_user)


@dashboard_bp.route("/toggle_policy_visibility/<int:policy_id>", methods=["POST"])
@login_required
def toggle_policy_visibility(policy_id):
    """
    Toggle the hidden status of a policy for renewals
    """
    from flask import jsonify
    
    try:
        # Get current policy state
        policy_result = supabase.table("policies").select("is_hidden_from_renewals").eq("policy_id", policy_id).single().execute()
        
        if not policy_result.data:
            return jsonify({"success": False, "error": "Policy not found"}), 404
        
        # Toggle the hidden state
        current_hidden = policy_result.data.get("is_hidden_from_renewals", False)
        new_hidden = not current_hidden
        
        # Update the policy
        update_result = supabase.table("policies").update({"is_hidden_from_renewals": new_hidden}).eq("policy_id", policy_id).execute()
        
        action = "hidden" if new_hidden else "unhidden"
        return jsonify({
            "success": True, 
            "message": f"Policy has been {action}",
            "is_hidden": new_hidden
        })
        
    except Exception as e:
        print(f"Error toggling policy visibility: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/view_all_policies")
@login_required
def view_all_policies():
    """
    View all policies with search functionality and pagination
    Shows 100 policies per page with member names instead of client names
    """
    try:
        # Get search and pagination parameters
        search_query = request.args.get("search", "").strip()
        page = int(request.args.get("page", 1))
        per_page = 100
        offset = (page - 1) * per_page

        # Base query to get policies with member and client information
        query = supabase.table("policies").select("*, clients(*), members(*)")

        # Apply search filter if provided
        if search_query:
            # Search in member name, insurance company, product name, or policy number
            search_lower = search_query.lower()
            
            # Get all policies first, then filter in Python (since Supabase doesn't support complex OR queries easily)
            all_policies_result = query.execute()
            all_policies = all_policies_result.data
            
            filtered_policies = []
            for policy in all_policies:
                member_name = policy.get("members", {}).get("member_name", "") if policy.get("members") else ""
                insurance_company = policy.get("insurance_company", "")
                product_name = policy.get("product_name", "")
                policy_number = policy.get("policy_number", "")
                
                if (search_lower in member_name.lower() or 
                    search_lower in insurance_company.lower() or 
                    search_lower in product_name.lower() or 
                    search_lower in str(policy_number).lower()):
                    filtered_policies.append(policy)
            
            total_policies = len(filtered_policies)
            # Apply pagination to filtered results
            policies = filtered_policies[offset:offset + per_page]
        else:
            # Get total count for pagination
            count_result = supabase.table("policies").select("policy_id", count="exact").execute()
            total_policies = count_result.count or 0
            
            # Get paginated policies
            policies_result = (query
                             .order("policy_id", desc=True)
                             .range(offset, offset + per_page - 1)
                             .execute())
            policies = policies_result.data

        # Process policies to flatten customer and member data
        for policy in policies:
            if policy.get("clients"):
                policy["customer_name"] = policy["clients"]["name"]
                policy["customer_email"] = policy["clients"]["email"]
                policy["customer_phone"] = policy["clients"].get("phone", "")
            else:
                policy["customer_name"] = "Unknown"
                policy["customer_email"] = ""
                policy["customer_phone"] = ""
                
            if policy.get("members"):
                policy["member_name"] = policy["members"].get("member_name", "")
            else:
                policy["member_name"] = "Unknown Member"

        # Calculate pagination info
        total_pages = math.ceil(total_policies / per_page)
        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None

        # Calculate page range for pagination display
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        page_range = list(range(start_page, end_page + 1))

        print(f"Found {len(policies)} policies on page {page} of {total_pages}")
        print(f"Total policies: {total_policies}, Search query: '{search_query}'")

        return render_template("view_all_policies.html",
                             policies=policies,
                             current_search=search_query,
                             page=page,
                             total_pages=total_pages,
                             total_policies=total_policies,
                             has_prev=has_prev,
                             has_next=has_next,
                             prev_page=prev_page,
                             next_page=next_page,
                             page_range=page_range,
                             per_page=per_page,
                             current_user=current_user)

    except Exception as e:
        print(f"Error fetching policies: {e}")
        return render_template("view_all_policies.html",
                             policies=[],
                             current_search=search_query,
                             page=1,
                             total_pages=0,
                             total_policies=0,
                             has_prev=False,
                             has_next=False,
                             prev_page=None,
                             next_page=None,
                             page_range=[],
                             per_page=per_page,
                             current_user=current_user,
                             error=str(e))


@dashboard_bp.route("/api/global_search")
@login_required
def global_search():
    """
    Global search API endpoint for searching policies, clients, members, claims, and pending items.
    Returns JSON with categorized results.
    Uses server-side filtering with ilike for efficient searching across all records.
    """
    query = request.args.get("q", "").strip()
    query_lower = query.lower()
    
    if len(query) < 2:
        return jsonify({"policies": [], "clients": [], "members": [], "claims": [], "pending": []})
    
    results = {"policies": [], "clients": [], "members": [], "claims": [], "pending": []}
    search_pattern = f"%{query}%"
    
    try:
        # Search clients first (using ilike for server-side filtering)
        clients_result = (supabase.table("clients")
                         .select("*")
                         .or_(f"name.ilike.{search_pattern},client_id.ilike.{search_pattern},phone.ilike.{search_pattern},email.ilike.{search_pattern}")
                         .limit(5)
                         .execute())
        
        for client in clients_result.data:
            results["clients"].append({
                "client_id": client.get("client_id", ""),
                "name": client.get("name", ""),
                "phone": client.get("phone", ""),
                "email": client.get("email", ""),
                "url": f"/existing_policies?search={client.get('name', '')}"
            })
        
        # Search members (using ilike for server-side filtering)
        members_result = (supabase.table("members")
                         .select("*, clients(*)")
                         .ilike("member_name", search_pattern)
                         .limit(5)
                         .execute())
        
        for member in members_result.data:
            client_name = member.get("clients", {}).get("name", "") if member.get("clients") else ""
            results["members"].append({
                "member_id": member.get("member_id"),
                "member_name": member.get("member_name", ""),
                "client_name": client_name,
                "client_id": member.get("client_id", ""),
                "url": f"/existing_policies?search={member.get('member_name', '')}"
            })
        
        # Get member_ids that match the search to find associated policies
        matching_member_ids = [m["member_id"] for m in members_result.data]
        
        # Get client_ids that match the search to find associated policies
        matching_client_ids = [c.get("client_id", "") for c in clients_result.data]
        
        # Search policies - use multiple strategies for comprehensive results
        # Strategy 1: Search by policy fields directly
        policies_by_fields = (supabase.table("policies")
                             .select("*, clients(*), members(*)")
                             .or_(f"insurance_company.ilike.{search_pattern},product_name.ilike.{search_pattern},policy_number.ilike.{search_pattern}")
                             .limit(5)
                             .execute())
        
        policy_ids_added = set()
        
        for policy in policies_by_fields.data:
            policy_id = policy["policy_id"]
            if policy_id not in policy_ids_added:
                member_name = policy.get("members", {}).get("member_name", "") if policy.get("members") else ""
                client_name = policy.get("clients", {}).get("name", "") if policy.get("clients") else ""
                
                results["policies"].append({
                    "policy_id": policy_id,
                    "member_name": member_name or client_name,
                    "client_id": policy.get("clients", {}).get("client_id", "") if policy.get("clients") else "",
                    "insurance_company": policy.get("insurance_company", ""),
                    "product_name": policy.get("product_name", ""),
                    "policy_number": str(policy.get("policy_number", "")),
                    "url": f"/view_policy/{policy_id}"
                })
                policy_ids_added.add(policy_id)
        
        # Strategy 2: Search policies by matching members
        if matching_member_ids and len(results["policies"]) < 5:
            for member_id in matching_member_ids[:5]:
                if len(results["policies"]) >= 5:
                    break
                policies_by_member = (supabase.table("policies")
                                     .select("*, clients(*), members(*)")
                                     .eq("member_id", member_id)
                                     .limit(5 - len(results["policies"]))
                                     .execute())
                
                for policy in policies_by_member.data:
                    policy_id = policy["policy_id"]
                    if policy_id not in policy_ids_added:
                        member_name = policy.get("members", {}).get("member_name", "") if policy.get("members") else ""
                        client_name = policy.get("clients", {}).get("name", "") if policy.get("clients") else ""
                        
                        results["policies"].append({
                            "policy_id": policy_id,
                            "member_name": member_name or client_name,
                            "client_id": policy.get("clients", {}).get("client_id", "") if policy.get("clients") else "",
                            "insurance_company": policy.get("insurance_company", ""),
                            "product_name": policy.get("product_name", ""),
                            "policy_number": str(policy.get("policy_number", "")),
                            "url": f"/view_policy/{policy_id}"
                        })
                        policy_ids_added.add(policy_id)
        
        # Strategy 3: Search policies by matching clients
        if matching_client_ids and len(results["policies"]) < 5:
            for client_id in matching_client_ids[:5]:
                if len(results["policies"]) >= 5:
                    break
                policies_by_client = (supabase.table("policies")
                                     .select("*, clients(*), members(*)")
                                     .eq("client_id", client_id)
                                     .limit(5 - len(results["policies"]))
                                     .execute())
                
                for policy in policies_by_client.data:
                    policy_id = policy["policy_id"]
                    if policy_id not in policy_ids_added:
                        member_name = policy.get("members", {}).get("member_name", "") if policy.get("members") else ""
                        client_name = policy.get("clients", {}).get("name", "") if policy.get("clients") else ""
                        
                        results["policies"].append({
                            "policy_id": policy_id,
                            "member_name": member_name or client_name,
                            "client_id": policy.get("clients", {}).get("client_id", "") if policy.get("clients") else "",
                            "insurance_company": policy.get("insurance_company", ""),
                            "product_name": policy.get("product_name", ""),
                            "policy_number": str(policy.get("policy_number", "")),
                            "url": f"/view_policy/{policy_id}"
                        })
                        policy_ids_added.add(policy_id)
        
        # Search claims (with server-side filtering where possible)
        claims_result = (supabase.table("claims")
                        .select("*, policies(*, clients(*), members(*))")
                        .or_(f"claim_number.ilike.{search_pattern},member_name.ilike.{search_pattern}")
                        .limit(10)
                        .execute())
        
        for claim in claims_result.data:
            if len(results["claims"]) >= 5:
                break
            policy = claim.get("policies", {}) or {}
            client_name = policy.get("clients", {}).get("name", "") if policy.get("clients") else ""
            member_name = policy.get("members", {}).get("member_name", "") if policy.get("members") else ""
            
            results["claims"].append({
                "claim_id": claim.get("claim_id"),
                "claim_number": claim.get("claim_number", ""),
                "status": claim.get("status", ""),
                "client_name": client_name or member_name,
                "policy_id": claim.get("policy_id"),
                "url": f"/claims/{claim.get('claim_id')}"
            })
        
        # Search pending items (pending policies) with server-side filtering
        # Note: pending_policies doesn't have customer_name - it uses client_id/member_id foreign keys
        pending_result = (supabase.table("pending_policies")
                         .select("*, clients(*), members(*)")
                         .or_(f"insurance_company.ilike.{search_pattern},product_name.ilike.{search_pattern}")
                         .limit(10)
                         .execute())
        
        for pending in pending_result.data:
            client_name = pending.get("clients", {}).get("name", "") if pending.get("clients") else ""
            member_name = pending.get("members", {}).get("member_name", "") if pending.get("members") else ""
            display_name = member_name or client_name
            
            results["pending"].append({
                "pending_id": pending.get("pending_id"),
                "customer_name": display_name,
                "insurance_company": pending.get("insurance_company", ""),
                "product_name": pending.get("product_name", ""),
                "url": f"/pending/{pending.get('pending_id')}"
            })
        
    except Exception as e:
        print(f"Error in global search: {e}")
        import traceback
        traceback.print_exc()
    
    return jsonify(results)