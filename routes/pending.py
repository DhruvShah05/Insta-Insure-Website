# routes/pending.py
# Unified pending page - combines pending policies and pending renewals
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from supabase import create_client
from dynamic_config import Config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

pending_bp = Blueprint("pending", __name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


@pending_bp.route("/pending")
@login_required
def list_pending():
    """View all pending items (both pending policies and pending renewals)"""
    try:
        logger.info("=== UNIFIED PENDING PAGE ACCESSED ===")
        logger.info(f"Current user: {current_user.email if hasattr(current_user, 'email') else 'Unknown'}")
        
        # Get filter from query params (default to 'all')
        filter_type = request.args.get('filter', 'all')
        
        pending_policies = []
        pending_renewals = []
        
        # Fetch pending policies if filter allows
        if filter_type in ['all', 'policies']:
            try:
                policies_result = (
                    supabase.table("pending_policies")
                    .select("*, clients(*), members(*)")
                    .order("created_at", desc=True)
                    .execute()
                )
                
                pending_policies = policies_result.data
                
                # Flatten customer data
                for policy in pending_policies:
                    policy['item_type'] = 'policy'  # Mark as policy type
                    if policy.get("clients"):
                        policy["client_name"] = policy["clients"]["name"]
                        policy["customer_email"] = policy["clients"]["email"]
                        policy["customer_phone"] = policy["clients"].get("phone", "")
                        policy["customer_alternate_email"] = policy["clients"].get("alternate_email", "")
                        policy["customer_alternate_phone"] = policy["clients"].get("alternate_phone", "")
                    if policy.get("members"):
                        policy["member_name"] = policy["members"].get("member_name", "")
                        policy["customer_name"] = policy["members"].get("member_name", "")
                    else:
                        policy["client_name"] = "Unknown"
                        policy["customer_name"] = "Unknown"
                        policy["customer_email"] = ""
                        policy["customer_phone"] = ""
                        policy["customer_alternate_email"] = ""
                        policy["customer_alternate_phone"] = ""
                
                logger.info(f"Found {len(pending_policies)} pending policies")
            except Exception as e:
                logger.error(f"Error fetching pending policies: {e}")
                flash(f"Error loading pending policies: {str(e)}", "error")
        
        # Fetch pending renewals if filter allows
        if filter_type in ['all', 'renewals']:
            try:
                renewals_result = (
                    supabase.table("policies")
                    .select("*, clients!policies_client_id_fkey(*), members!policies_member_id_fkey(*)")
                    .eq("is_pending_renewal", True)
                    .order("policy_to", desc=True)
                    .execute()
                )
                
                pending_renewals = renewals_result.data
                
                # Flatten data for template
                for renewal in pending_renewals:
                    renewal['item_type'] = 'renewal'  # Mark as renewal type
                    if renewal.get("clients"):
                        renewal["client_name"] = renewal["clients"]["name"]
                        renewal["customer_email"] = renewal["clients"]["email"]
                        renewal["customer_phone"] = renewal["clients"].get("phone", "")
                        renewal["customer_alternate_email"] = renewal["clients"].get("alternate_email", "")
                        renewal["customer_alternate_phone"] = renewal["clients"].get("alternate_phone", "")
                    else:
                        logger.warning(f"No client data for policy {renewal.get('policy_id')}")
                    
                    if renewal.get("members"):
                        renewal["member_name"] = renewal["members"].get("member_name", "")
                    else:
                        logger.warning(f"No member data for policy {renewal.get('policy_id')}")
                
                logger.info(f"Found {len(pending_renewals)} pending renewals")
            except Exception as e:
                logger.error(f"Error fetching pending renewals: {e}")
                flash(f"Error loading pending renewals: {str(e)}", "error")
        
        # Combine both lists
        all_pending = pending_policies + pending_renewals
        
        logger.info(f"✓ Returning {len(all_pending)} total pending items to template")
        return render_template(
            "pending.html", 
            pending_items=all_pending,
            pending_policies_count=len(pending_policies),
            pending_renewals_count=len(pending_renewals),
            filter_type=filter_type,
            current_user=current_user
        )

    except Exception as e:
        logger.error(f"❌ Error in unified pending page: {e}", exc_info=True)
        flash(f"Error loading pending items: {str(e)}", "error")
        return render_template(
            "pending.html", 
            pending_items=[],
            pending_policies_count=0,
            pending_renewals_count=0,
            filter_type='all',
            current_user=current_user
        )


@pending_bp.route("/complete_pending_item/<item_type>/<int:item_id>")
@login_required
def complete_pending_item(item_type, item_id):
    """Forward to appropriate completion page based on item type"""
    if item_type == 'policy':
        # Forward to pending policy completion
        return redirect(url_for('pending_policies.complete_pending', pending_id=item_id))
    elif item_type == 'renewal':
        # Forward to renewal page
        return redirect(url_for('renewal.renewal_page', policy_id=item_id))
    else:
        flash("Invalid item type", "error")
        return redirect(url_for('pending.list_pending'))


@pending_bp.route("/remove_pending_item/<item_type>/<int:item_id>", methods=["POST"])
@login_required
def remove_pending_item(item_type, item_id):
    """Remove a pending item based on type"""
    try:
        if item_type == 'policy':
            # Delete pending policy
            supabase.table("pending_policies").delete().eq("pending_id", item_id).execute()
            flash("Pending policy deleted successfully", "success")
        elif item_type == 'renewal':
            # Remove pending renewal flag
            supabase.table("policies").update({"is_pending_renewal": False}).eq("policy_id", item_id).execute()
            flash("Policy removed from pending renewals", "success")
        else:
            flash("Invalid item type", "error")
    except Exception as e:
        logger.error(f"Error removing pending item: {e}")
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("pending.list_pending"))
