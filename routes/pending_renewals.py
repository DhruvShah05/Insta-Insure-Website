# routes/pending_renewals.py
# Simplified pending renewals - tracks policies where payment received but company hasn't issued new policy yet
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from supabase import create_client
from dynamic_config import Config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

pending_renewals_bp = Blueprint("pending_renewals", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@pending_renewals_bp.route("/pending_renewals")
@login_required
def list_pending_renewals():
    """View all policies marked as pending renewal (payment received, waiting for company to issue policy)"""
    try:
        logger.info("=== PENDING RENEWALS PAGE ACCESSED ===")
        logger.info(f"Current user: {current_user.email if hasattr(current_user, 'email') else 'Unknown'}")
        
        # Query policies where is_pending_renewal = TRUE
        result = (
            supabase.table("policies")
            .select("*, clients!policies_client_id_fkey(*), members!policies_member_id_fkey(*)")
            .eq("is_pending_renewal", True)
            .order("policy_to", desc=True)
            .execute()
        )

        logger.info(f"Query executed successfully. Raw result count: {len(result.data) if result.data else 0}")
        if result.data:
            logger.info(f"First record sample: Policy ID={result.data[0].get('policy_id')}, Client ID={result.data[0].get('client_id')}")
        else:
            logger.warning("⚠️ No pending renewals found in database!")
        
        pending_renewals = result.data

        # Flatten data for template
        for renewal in pending_renewals:
            logger.info(f"Processing renewal: Policy ID {renewal.get('policy_id')}")
            if renewal.get("clients"):
                renewal["client_name"] = renewal["clients"]["name"]
                renewal["customer_email"] = renewal["clients"]["email"]
                renewal["customer_phone"] = renewal["clients"].get("phone", "")
                logger.info(f"  Client: {renewal['client_name']}")
            else:
                logger.warning(f"  ⚠️ No client data for policy {renewal.get('policy_id')}")
            
            if renewal.get("members"):
                renewal["member_name"] = renewal["members"].get("member_name", "")
                logger.info(f"  Member: {renewal['member_name']}")
            else:
                logger.warning(f"  ⚠️ No member data for policy {renewal.get('policy_id')}")

        logger.info(f"✓ Returning {len(pending_renewals)} pending renewals to template")
        return render_template("pending_renewals.html", pending_renewals=pending_renewals, current_user=current_user)

    except Exception as e:
        logger.error(f"❌ Error fetching pending renewals: {e}", exc_info=True)
        flash(f"Error loading pending renewals: {str(e)}", "error")
        return render_template("pending_renewals.html", pending_renewals=[], current_user=current_user)


@pending_renewals_bp.route("/complete_pending_renewal/<int:policy_id>")
@login_required
def complete_pending_renewal(policy_id):
    """Redirect to renewal page to complete the pending renewal"""
    # Simply redirect to the renewal page where user can upload PDF and edit all details
    return redirect(url_for('renewal.renewal_page', policy_id=policy_id))


@pending_renewals_bp.route("/remove_from_pending/<int:policy_id>", methods=["POST"])
@login_required
def remove_from_pending(policy_id):
    """Remove a policy from pending renewals (cancel pending status)"""
    try:
        supabase.table("policies").update({"is_pending_renewal": False}).eq("policy_id", policy_id).execute()
        flash("Policy removed from pending renewals", "success")
    except Exception as e:
        logger.error(f"Error removing policy from pending: {e}")
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("pending_renewals.list_pending_renewals"))
