"""
Settings Routes - Admin-only settings management
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user
from auth_decorators import admin_required, settings_access_required
from settings_service import settings, SettingsService
from models import User
import logging
import json

logger = logging.getLogger(__name__)
settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@settings_access_required
def index():
    """Settings dashboard page"""
    try:
        all_settings = settings.get_all_settings()
        users = User.get_all_users()
        
        return render_template('settings/index.html', 
                             settings=all_settings, 
                             users=users,
                             current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading settings page: {e}")
        flash('Error loading settings page', 'error')
        return redirect(url_for('dashboard.index'))

@settings_bp.route('/api/get/<category>')
@admin_required
def get_category_settings(category):
    """Get settings for a specific category"""
    try:
        category_settings = settings.get_category_with_metadata(category)
        logger.info(f"Retrieved settings for category '{category}': {len(category_settings) if category_settings else 0} items")
        
        # If no settings exist for this category, create default ones
        if not category_settings:
            logger.info(f"No settings found for category '{category}', creating defaults")
            _create_default_settings_for_category(category)
            category_settings = settings.get_category_with_metadata(category)
        
        logger.debug(f"Settings data for '{category}': {category_settings}")
        
        return jsonify({
            'success': True,
            'settings': category_settings
        })
    except Exception as e:
        logger.error(f"Error getting category settings for '{category}': {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _create_default_settings_for_category(category):
    """Create default settings for a category if none exist"""
    try:
        default_settings = {
            'company': {
                'name': ('Insta Insurance Consultancy', 'Company name displayed in the application'),
                'portal_name': ('Insta Insurance Consultancy Portal', 'Portal name displayed in navigation bar'),
                'portal_title': ('Insta Insurances Portal', 'Portal title shown in browser tab'),
                'logo_path': ('ico.png', 'Path to logo file in static folder'),
                'address': ('', 'Company address'),
                'email': ('', 'Company email address'),
                'phone': ('', 'Company phone number'),
                'website': ('', 'Company website URL'),
                'logo_url': ('', 'URL to company logo image')
            },
            'email': {
                'smtp_server': ('', 'SMTP server hostname'),
                'smtp_port': ('587', 'SMTP server port'),
                'smtp_username': ('', 'SMTP username'),
                'smtp_password': ('', 'SMTP password'),
                'from_email': ('', 'From email address'),
                'use_tls': ('true', 'Use TLS encryption')
            },
            'whatsapp': {
                'token': ('', 'WhatsApp API token'),
                'phone_id': ('', 'WhatsApp phone number ID'),
                'webhook_url': ('', 'WhatsApp webhook URL'),
                'verify_token': ('', 'WhatsApp webhook verify token')
            },
            'twilio': {
                'account_sid': ('', 'Twilio Account SID'),
                'auth_token': ('', 'Twilio Auth Token'),
                'whatsapp_number': ('', 'Twilio WhatsApp number')
            },
            'google_drive': {
                'credentials_file': ('credentials.json', 'Google Drive credentials file name'),
                'credentials_json': ('{}', 'Google Drive service account credentials'),
                'root_folder_id': ('', 'Google Drive root folder ID for policy uploads'),
                'folder_id': ('', 'Google Drive folder ID'),
                'archive_folder_id': ('', 'Google Drive archive folder ID')
            },
            'app': {
                'base_url': ('http://localhost:5050', 'Application base URL'),
                'environment': ('development', 'Application environment'),
                'debug': ('true', 'Debug mode enabled')
            },
            'business': {
                'default_gst': ('18', 'Default GST percentage'),
                'default_commission': ('10', 'Default commission percentage'),
                'reminder_days': ('30', 'Days before expiry to send reminders')
            }
        }
        
        if category in default_settings:
            for key, (value, description) in default_settings[category].items():
                # Determine data type
                if key in ['use_tls', 'debug']:
                    data_type = 'boolean'
                elif key in ['smtp_port', 'default_gst', 'default_commission', 'reminder_days']:
                    data_type = 'number'
                elif key == 'credentials_json':
                    data_type = 'json'
                else:
                    data_type = 'string'
                
                # Create the setting
                settings.create(
                    category=category,
                    key=key,
                    value=value,
                    description=description,
                    is_sensitive=key in ['smtp_password', 'token', 'auth_token', 'credentials_json'],
                    updated_by='system'
                )
            
            logger.info(f"Created {len(default_settings[category])} default settings for category '{category}'")
        
    except Exception as e:
        logger.error(f"Error creating default settings for category '{category}': {e}")

@settings_bp.route('/api/update', methods=['POST'])
@admin_required
def update_settings():
    """Update multiple settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        updated_count = 0
        errors = []
        
        for category, category_settings in data.items():
            for key, value in category_settings.items():
                if settings.set(category, key, value, current_user.email):
                    updated_count += 1
                else:
                    errors.append(f"Failed to update {category}.{key}")
        
        if errors:
            logger.warning(f"Some settings failed to update: {errors}")
            return jsonify({
                'success': False,
                'error': f"Updated {updated_count} settings, but {len(errors)} failed",
                'errors': errors
            }), 207  # Multi-status
        
        logger.info(f"Settings updated successfully by {current_user.email}: {updated_count} settings")
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} settings'
        })
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/create', methods=['POST'])
@admin_required
def create_setting():
    """Create a new setting"""
    try:
        data = request.get_json()
        
        required_fields = ['category', 'key', 'value']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        success = settings.create(
            category=data['category'],
            key=data['key'],
            value=data['value'],
            description=data.get('description', ''),
            is_sensitive=data.get('is_sensitive', False),
            updated_by=current_user.email
        )
        
        if success:
            logger.info(f"Setting {data['category']}.{data['key']} created by {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Setting created successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create setting'
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating setting: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/delete', methods=['POST'])
@admin_required
def delete_setting():
    """Delete a setting"""
    try:
        data = request.get_json()
        
        if 'category' not in data or 'key' not in data:
            return jsonify({
                'success': False,
                'error': 'Category and key are required'
            }), 400
        
        success = settings.delete(data['category'], data['key'])
        
        if success:
            logger.info(f"Setting {data['category']}.{data['key']} deleted by {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Setting deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete setting'
            }), 500
            
    except Exception as e:
        logger.error(f"Error deleting setting: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/export')
@admin_required
def export_settings():
    """Export settings for backup"""
    try:
        include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
        exported_settings = settings.export_settings(include_sensitive)
        
        logger.info(f"Settings exported by {current_user.email} (include_sensitive: {include_sensitive})")
        return jsonify({
            'success': True,
            'settings': exported_settings
        })
        
    except Exception as e:
        logger.error(f"Error exporting settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/import', methods=['POST'])
@admin_required
def import_settings():
    """Import settings from backup"""
    try:
        data = request.get_json()
        
        if 'settings' not in data:
            return jsonify({
                'success': False,
                'error': 'Settings data is required'
            }), 400
        
        success = settings.bulk_update(data['settings'], current_user.email)
        
        if success:
            logger.info(f"Settings imported successfully by {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Settings imported successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Some settings failed to import'
            }), 207
            
    except Exception as e:
        logger.error(f"Error importing settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# User Management Routes
@settings_bp.route('/api/users')
@admin_required
def get_users():
    """Get all users"""
    try:
        users = User.get_all_users()
        return jsonify({
            'success': True,
            'users': users
        })
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/users/create', methods=['POST'])
@admin_required
def create_user():
    """Create a new user"""
    try:
        data = request.get_json()
        
        required_fields = ['email', 'name', 'password', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        success, message = User.create_user_with_password(
            email=data['email'],
            name=data['name'],
            password=data['password'],
            role=data['role'],
            created_by=current_user.email
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/users/update-role', methods=['POST'])
@admin_required
def update_user_role():
    """Update user role"""
    try:
        data = request.get_json()
        
        if 'email' not in data or 'role' not in data:
            return jsonify({
                'success': False,
                'error': 'Email and role are required'
            }), 400
        
        # Prevent admin from changing their own role
        if data['email'] == current_user.email:
            return jsonify({
                'success': False,
                'error': 'You cannot change your own role'
            }), 400
        
        success, message = User.update_user_role(
            email=data['email'],
            new_role=data['role'],
            updated_by=current_user.email
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/users/delete', methods=['POST'])
@admin_required
def delete_user():
    """Delete a user"""
    try:
        data = request.get_json()
        
        if 'email' not in data:
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
        
        # Prevent admin from deleting themselves
        if data['email'] == current_user.email:
            return jsonify({
                'success': False,
                'error': 'You cannot delete your own account'
            }), 400
        
        success, message = User.delete_user(
            email=data['email'],
            deleted_by=current_user.email
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@settings_bp.route('/api/users/reset-password', methods=['POST'])
@admin_required
def reset_user_password():
    """Reset user password"""
    try:
        data = request.get_json()
        
        if 'email' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        success, message = User.reset_user_password(
            email=data['email'],
            new_password=data['password'],
            reset_by=current_user.email
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
