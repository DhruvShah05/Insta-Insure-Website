"""
Authentication and Authorization Decorators
Provides role-based access control for routes
"""

from functools import wraps
from flask import redirect, url_for, flash, jsonify, request
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

def login_required(f):
    """Decorator to require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require user to be an admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_admin:
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role != required_role:
                if request.is_json:
                    return jsonify({'error': f'{required_role.title()} access required'}), 403
                flash(f'You need {required_role} privileges to access this page.', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def any_role_required(allowed_roles):
    """Decorator to require any of the specified roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in allowed_roles:
                if request.is_json:
                    return jsonify({'error': 'Insufficient privileges'}), 403
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_user_permissions(required_permission=None):
    """Check if current user has required permissions"""
    if not current_user.is_authenticated:
        return False, 'Authentication required'
    
    if required_permission == 'admin' and not current_user.is_admin:
        return False, 'Admin access required'
    
    if required_permission == 'member' and current_user.role not in ['admin', 'member']:
        return False, 'Member access required'
    
    return True, 'Access granted'

def log_access_attempt(route_name, required_role=None):
    """Log access attempts for security monitoring"""
    user_info = f"{current_user.email} ({current_user.role})" if current_user.is_authenticated else "Anonymous"
    
    if current_user.is_authenticated and (not required_role or current_user.role == required_role or current_user.is_admin):
        logger.info(f"Access granted to {route_name} for user {user_info}")
    else:
        logger.warning(f"Access denied to {route_name} for user {user_info}. Required role: {required_role}")

# Convenience decorators for common use cases
def settings_access_required(f):
    """Decorator specifically for settings page access (admin only)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        log_access_attempt('settings', 'admin')
        return admin_required(f)(*args, **kwargs)
    return decorated_function

def user_management_required(f):
    """Decorator for user management functions (admin only)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        log_access_attempt('user_management', 'admin')
        return admin_required(f)(*args, **kwargs)
    return decorated_function
