#!/usr/bin/env python3
"""
Debug User Status
Quick script to check current user session status
"""

from flask import Flask, jsonify
from flask_login import LoginManager, current_user
from dynamic_config import Config
from models import User
from auth import auth_bp

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.get_or_create(user_id)
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

app.register_blueprint(auth_bp)

@app.route('/debug-user')
def debug_user():
    """Debug current user status"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'email': current_user.email,
            'name': current_user.name,
            'role': getattr(current_user, 'role', 'unknown'),
            'is_admin': current_user.is_admin,
            'user_id': current_user.user_id
        })
    else:
        return jsonify({
            'authenticated': False,
            'message': 'User not logged in'
        })

if __name__ == '__main__':
    print("🔍 Debug server running on http://127.0.0.1:5051/debug-user")
    app.run(debug=True, port=5051)
