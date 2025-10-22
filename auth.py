from flask import Blueprint, redirect, url_for, session, render_template, request, jsonify, flash
from flask_login import login_user, logout_user, current_user
from dynamic_config import Config
from models import User
import logging

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@auth_bp.route("/login", methods=['GET', 'POST'])
def login():
    """
    Show login page and handle login form submission
    """
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please provide both email and password', 'error')
            return render_template("login.html")

        # Authenticate user
        user = User.authenticate(email, password)
        
        if user:
            # Login successful - session lasts until browser closes
            login_user(user, remember=False)  # Session cookie only, no remember me
            logger.info(f"User {email} logged in successfully")
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            # Login failed
            flash('Invalid email or password', 'error')
            logger.warning(f"Failed login attempt for email: {email}")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """
    Logout route - clears Flask-Login session and forces session expiry
    """
    if current_user.is_authenticated:
        logger.info(f"User {current_user.email} logged out")
    
    # Clear Flask-Login session
    logout_user()
    
    # Clear all session data
    session.clear()
    
    flash('You have been logged out successfully', 'info')
    
    # Create response and clear session cookie
    response = redirect(url_for("auth.login"))
    response.set_cookie('session', '', expires=0, httponly=True, secure=False, samesite='Lax')
    
    return response


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