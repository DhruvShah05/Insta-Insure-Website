from flask import Blueprint, redirect, url_for, session, render_template, request, jsonify
from flask_login import login_user, logout_user, current_user
from config import Config
from models import User
import requests
import logging

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


def verify_clerk_session(session_token):
    """
    Verify Clerk session token and return user data
    """
    try:
        headers = {
            'Authorization': f'Bearer {Config.CLERK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }

        # Get the session details - correct endpoint (no /verify)
        response = requests.get(
            f'https://api.clerk.com/v1/sessions/{session_token}',
            headers=headers
        )

        if response.status_code == 200:
            session_data = response.json()
            user_id = session_data.get('user_id')

            if not user_id:
                logger.error("No user_id in session data")
                return None

            # Get user details
            user_response = requests.get(
                f'https://api.clerk.com/v1/users/{user_id}',
                headers=headers
            )

            if user_response.status_code == 200:
                return user_response.json()
            else:
                logger.error(f"Failed to get user details: {user_response.status_code} - {user_response.text}")
                return None
        else:
            logger.error(f"Failed to verify session: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error verifying Clerk session: {e}")
        return None


# ----------------- Routes -----------------

@auth_bp.route("/login")
def login():
    """
    Show login page with Clerk sign-in
    """
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@auth_bp.route("/auth/callback", methods=['POST'])
def auth_callback():
    """
    Clerk authentication callback
    This endpoint receives the session token from the frontend
    """
    try:
        data = request.get_json()
        session_token = data.get('session_token')

        logger.info(f"Auth callback received, session_token present: {bool(session_token)}")

        if not session_token:
            logger.error("No session token provided")
            return jsonify({'error': 'No session token provided'}), 400

        # Verify session with Clerk
        user_data = verify_clerk_session(session_token)

        if not user_data:
            logger.error("verify_clerk_session returned None - Invalid session")
            return jsonify({'error': 'Invalid session'}), 401

        # Extract user info
        email_addresses = user_data.get('email_addresses', [])
        primary_email = None

        for email_obj in email_addresses:
            if email_obj.get('id') == user_data.get('primary_email_address_id'):
                primary_email = email_obj.get('email_address')
                break

        if not primary_email:
            logger.error("No primary email found in user data")
            return jsonify({'error': 'No email found'}), 400

        logger.info(f"Authentication attempt for email: {primary_email}")

        # Check if user is admin
        if primary_email not in Config.ADMIN_EMAILS:
            logger.warning(f"Unauthorized access attempt by {primary_email}")
            return jsonify({'error': 'Unauthorized - Admin access only'}), 403

        # Get user name
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        name = f"{first_name} {last_name}".strip() or primary_email

        # Get profile picture
        picture = user_data.get('image_url', '')

        # Create or get user object
        user = User.get_or_create(email=primary_email, name=name, picture=picture)
        login_user(user, remember=True)

        # Store Clerk session info
        session['clerk_session_token'] = session_token
        session['clerk_user_id'] = user_data.get('id')

        logger.info(f"User {primary_email} ({name}) logged in successfully via Clerk")

        return jsonify({
            'success': True,
            'redirect': url_for('dashboard.index')
        })

    except Exception as e:
        logger.error(f"Clerk callback error: {e}", exc_info=True)
        return jsonify({'error': 'Authentication failed'}), 500


@auth_bp.route("/logout")
def logout():
    """
    Logout route - clears Flask-Login session and Clerk session
    """
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/verify")
def verify_auth():
    """
    Endpoint to verify current authentication status
    Used by frontend to check if user is still logged in
    """
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'email': current_user.email,
                'name': current_user.name,
                'picture': current_user.picture
            }
        })

    return jsonify({'authenticated': False}), 401