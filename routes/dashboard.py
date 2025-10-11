from flask import Blueprint, render_template
from flask_login import login_required
from supabase import create_client
from config import Config
from datetime import datetime, timedelta

dashboard_bp = Blueprint("dashboard", __name__)

supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@dashboard_bp.route("/")
@login_required
def index():
    """
    Dashboard showing policies expiring in the next 30 days and statistics
    """
    today = datetime.today().strftime("%Y-%m-%d")
    next_month = (datetime.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    try:
        # Get policies expiring soon with customer information
        policies_result = (
            supabase.table("policies")
            .select("*, clients(*), members(*)")
            .gte("policy_to", today)
            .lte("policy_to", next_month)
            .order("policy_to", desc=False)
            .execute()
        )

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

        print(f"Found {len(policies)} policies expiring between {today} and {next_month}")

        # Get total active policies count
        total_policies_result = supabase.table("policies").select("policy_id", count="exact").execute()
        total_active_policies = total_policies_result.count if total_policies_result.count else 0

        # Get pending policies count
        pending_policies_result = supabase.table("pending_policies").select("pending_id", count="exact").execute()
        total_pending_policies = pending_policies_result.count if pending_policies_result.count else 0

        print(f"Total active policies: {total_active_policies}")
        print(f"Total pending policies: {total_pending_policies}")

    except Exception as e:
        print(f"Error fetching policies: {e}")
        policies = []
        total_active_policies = 0
        total_pending_policies = 0

    return render_template("dashboard.html", 
                         policies=policies, 
                         total_active_policies=total_active_policies,
                         total_pending_policies=total_pending_policies)