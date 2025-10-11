from flask import Flask, request, jsonify, render_template
from flask_login import LoginManager
from config import Config
from auth import auth_bp, create_oauth
from routes.dashboard import dashboard_bp
from routes.policies import policies_bp
from routes.pending_policies import pending_policies_bp
from routes.existing_policies import existing_policies_bp
from routes.whatsapp_routes import whatsapp_bp
from routes.renewal_routes import renewal_bp
import os
import logging
import threading
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Import WhatsApp bot functionality
from whatsapp_bot import setup_whatsapp_webhook

# Try to import Excel routes
try:
    from routes.excel_routes import excel_bp
    excel_routes_available = True
except ImportError as e:
    print(f"Excel routes not available: {e}")
    excel_routes_available = False
    excel_bp = None

# Create Flask app with production settings
app = Flask(__name__)
app.config.from_object(Config)

# Production-ready secret key
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# Session configuration for production multi-user environment
if Config.FLASK_ENV == "development":
   # Development: Relaxed cookie settings for local testing
   app.config.update(
       SESSION_COOKIE_SECURE=False,
       SESSION_COOKIE_HTTPONLY=True,
       SESSION_COOKIE_SAMESITE=None,  # Allow cross-origin for ngrok
       PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
       MAX_CONTENT_LENGTH=50 * 1024 * 1024,
   )
else:
   # Production: Secure but ngrok-compatible settings
   app.config.update(
       SESSION_COOKIE_SECURE=False,  # Keep False for HTTP ngrok
       SESSION_COOKIE_HTTPONLY=True,
       SESSION_COOKIE_SAMESITE=None,  # Allow cross-origin for ngrok access
       PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
       MAX_CONTENT_LENGTH=50 * 1024 * 1024,
   )
  
   # Multi-user optimization settings for production
   app.config.update(
       SESSION_REFRESH_EACH_REQUEST=True,  # Keep sessions active
       SEND_FILE_MAX_AGE_DEFAULT=timedelta(hours=1),  # Cache static files
      
       # Performance settings
       JSON_SORT_KEYS=False,  # Faster JSON responses
       JSONIFY_PRETTYPRINT_REGULAR=False,  # Compact JSON in production
   )


# Setup logging for production
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler('logs/insurance_portal.log', 
                                     maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Insurance Portal startup')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

from models import User


@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    return User.get_or_create(user_id)


# Initialize OAuth
create_oauth(app)

# Custom Jinja2 filter for Indian date format (DD/MM/YYYY)
@app.template_filter('indian_date')
def indian_date_filter(date_string):
    """Convert date from YYYY-MM-DD to DD/MM/YYYY format"""
    if not date_string:
        return 'N/A'
    
    try:
        # Handle different date formats
        if isinstance(date_string, str):
            # If it's already in DD/MM/YYYY format, return as is
            if '/' in date_string and len(date_string.split('/')) == 3:
                parts = date_string.split('/')
                if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                    return date_string
            
            # If it's in YYYY-MM-DD format, convert to DD/MM/YYYY
            if '-' in date_string and len(date_string.split('-')) == 3:
                parts = date_string.split('-')
                if len(parts[0]) == 4:  # YYYY-MM-DD format
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
                elif len(parts[2]) == 4:  # DD-MM-YYYY format
                    return f"{parts[0]}/{parts[1]}/{parts[2]}"
        
        # Try to parse as datetime object
        if hasattr(date_string, 'strftime'):
            return date_string.strftime('%d/%m/%Y')
            
        # Try to parse string as date
        try:
            date_obj = datetime.strptime(str(date_string), '%Y-%m-%d')
            return date_obj.strftime('%d/%m/%Y')
        except ValueError:
            try:
                date_obj = datetime.strptime(str(date_string), '%d/%m/%Y')
                return date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass
        
        return str(date_string)
    except Exception as e:
        print(f"Error formatting date {date_string}: {e}")
        return str(date_string)

# Security headers middleware
@app.after_request
def after_request(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Request monitoring and rate limiting
request_counts = {}
request_lock = threading.Lock()

@app.before_request
def monitor_requests():
    """Monitor requests and implement basic rate limiting"""
    client_ip = request.remote_addr
    current_time = time.time()
    
    # Clean old entries (older than 1 minute)
    with request_lock:
        request_counts[client_ip] = [
            timestamp for timestamp in request_counts.get(client_ip, [])
            if current_time - timestamp < 60
        ]
        
        # Add current request
        request_counts[client_ip].append(current_time)
        
        # Rate limiting: max 120 requests per minute per IP
        if len(request_counts[client_ip]) > 120:
            app.logger.warning(f'Rate limit exceeded for IP: {client_ip}')
            return jsonify({'error': 'Rate limit exceeded'}), 429
    
    # Log request information for monitoring
    if not app.debug:
        app.logger.info(f'{client_ip} - {request.method} {request.url} - Active users: {len(request_counts)}')

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(policies_bp)
app.register_blueprint(pending_policies_bp)
app.register_blueprint(existing_policies_bp)
app.register_blueprint(whatsapp_bp)  # WhatsApp routes
app.register_blueprint(renewal_bp)  # Renewal routes

# Register Excel blueprint if available
if excel_routes_available and excel_bp:
    app.register_blueprint(excel_bp)
    
    # Initialize Excel sync service in background
    try:
        from excel_sync_service import initialize_excel_sync
        initialize_excel_sync()
        app.logger.info("Excel sync service initialized")
    except Exception as e:
        app.logger.warning(f"Excel sync service not available: {e}")

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         error='Page Not Found', 
                         message='The requested page could not be found.'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Server Error: {error}')
    return render_template('error.html', 
                         error='Internal Server Error', 
                         message='An internal server error occurred.'), 500

@app.errorhandler(413)
def too_large(error):
    return render_template('error.html', 
                         error='File Too Large', 
                         message='The uploaded file is too large. Maximum size is 50MB.'), 413

# Setup WhatsApp webhook
setup_whatsapp_webhook(app)

if __name__ == "__main__":
    # Check required environment variables
    required_vars = ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID', 'VERIFY_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠️  Warning: Missing WhatsApp variables: {', '.join(missing_vars)}")
        print("WhatsApp functionality will be disabled.")
    else:
        print("✅ WhatsApp integration enabled")

    # Check Excel functionality
    if excel_routes_available:
        print("✅ Excel integration enabled")
    else:
        print("⚠️  Excel functionality disabled - install: pip install pandas openpyxl numpy")

    print("🚀 Starting Insurance Portal with Full Integration...")
    print("📱 WhatsApp webhook: http://localhost:5050/webhook")
    print("📊 Excel sync: Real-time database → Google Drive")
    print("🌐 Web portal: http://localhost:5050/")

    # Production settings
    port = int(os.getenv('PORT', 5050))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    # Production server configuration for multi-user access
    if debug:
        # Development mode
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True,
            use_reloader=True
        )
    else:
        # Production mode - optimized for concurrent users
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,
            processes=1,  # Use threading, not multiprocessing for shared state
            use_reloader=False,
            # Performance optimizations
            request_handler=None,  # Use default optimized handler
        )
