from flask import Blueprint, render_template, request
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