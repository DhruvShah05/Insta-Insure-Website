from flask import Flask, request, jsonify, render_template, session
from flask_login import LoginManager
from datetime import timedelta
from dynamic_config import Config
from auth import auth_bp  # Remove create_oauth import
from routes.dashboard import dashboard_bp
from routes.policies import policies_bp
from routes.pending_policies import pending_policies_bp
from routes.existing_policies import existing_policies_bp
from routes.whatsapp_routes import whatsapp_bp
from routes.whatsapp_logs_routes import whatsapp_logs_bp
from routes.renewal_routes import renewal_bp
from routes.client_export import client_export_bp
from routes.claims import claims_bp
from routes.settings_routes import settings_bp
import os
import logging
import threading
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Import WhatsApp bot functionality
from whatsapp_bot import setup_whatsapp_webhook
from realtime_cleanup_service import start_realtime_cleanup_service

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

# Configure session to last until browser closes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Fallback timeout
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SECURE'] = Config.FLASK_ENV == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# Production-ready secret key
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# Session configuration for production multi-user environment
if Config.FLASK_ENV == "development":
    # Development: Relaxed cookie settings for local testing
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=None,  # Allow cross-origin for ngrok
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Fallback timeout
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
else:
    # Production: Secure but ngrok-compatible settings
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Keep False for HTTP ngrok
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=None,  # Allow cross-origin for ngrok access
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Fallback timeout
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

# Setup logger for use in functions
logger = logging.getLogger(__name__)

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
    
    # TEMPORARY FIX: Always load fresh from database to fix admin role issue
    # TODO: Re-enable caching after role issue is resolved
    try:
        from supabase import create_client
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        result = supabase.table('users').select('*').eq('email', user_id).execute()
        if result.data:
            user_data = result.data[0]
            user = User(
                email=user_data['email'],
                name=user_data.get('name'),
                picture=user_data.get('picture'),
                user_id=user_data.get('id'),
                password_hash=user_data.get('password_hash'),
                role=user_data.get('role', 'member')  # Include role parameter
            )
            logger.info(f"User loaded: {user.email} with role: {user.role} (is_admin: {user.is_admin})")
            return user
    except Exception as e:
        logger.error(f"Error loading user: {e}")
    return None


# Make config available in templates
@app.context_processor
def inject_config():
    return {
        'config': {
            'PORTAL_NAME': Config.PORTAL_NAME,
            'PORTAL_TITLE': Config.PORTAL_TITLE,
            'LOGO_PATH': Config.LOGO_PATH,
            'COMPANY_NAME': Config.COMPANY_NAME
        }
    }


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

# Custom filter for standardized N/A display
@app.template_filter('display_value')
def display_value_filter(value, default='N/A'):
    """Standardized display for values - shows default (N/A) for empty/null values"""
    if value is None or value == '' or value == 0:
        return default
    return str(value)

# Custom filter for currency display
@app.template_filter('currency')
def currency_filter(value):
    """Format currency values with proper display"""
    if value is None or value == '' or value == 0:
        return 'N/A'
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

# Custom filter for policy status
@app.template_filter('policy_status')
def policy_status_filter(policy):
    """Determine policy status based on expiry date and payment status"""
    from datetime import datetime, timedelta
    
    # If no payment date, it's pending payment
    if not policy.get('payment_date'):
        return {'status': 'pending', 'label': 'Pending Payment', 'class': 'pending'}
    
    # If policy has expired
    policy_to = policy.get('policy_to')
    if policy_to:
        try:
            # Handle different date formats
            if isinstance(policy_to, str):
                if '-' in policy_to:
                    expiry_date = datetime.strptime(policy_to, '%Y-%m-%d').date()
                else:
                    expiry_date = datetime.strptime(policy_to, '%d/%m/%Y').date()
            else:
                expiry_date = policy_to
            
            today = datetime.today().date()
            days_until_expiry = (expiry_date - today).days
            
            # Policy has expired
            if days_until_expiry < 0:
                return {'status': 'expired', 'label': 'Expired', 'class': 'expired'}
            
            # Policy expiring within 30 days
            elif days_until_expiry <= 30:
                return {'status': 'expiring_soon', 'label': 'Expiring Soon', 'class': 'expiring-soon'}
            
            # Policy is active (more than 30 days until expiry)
            else:
                return {'status': 'active', 'label': 'Active', 'class': 'active'}
                
        except (ValueError, TypeError):
            pass
    
    # Default fallback
    return {'status': 'unknown', 'label': 'Unknown', 'class': 'unknown'}

# Security headers middleware
@app.after_request
def after_request(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# Session management middleware
@app.before_request
def manage_session():
    """Ensure sessions are properly managed and non-permanent"""
    # Force all sessions to be non-permanent
    session.permanent = False
    
    # Clear session if it's somehow marked as permanent
    if hasattr(session, '_permanent') and session._permanent:
        session.clear()
        session.permanent = False


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
app.register_blueprint(whatsapp_logs_bp)  # WhatsApp logs
app.register_blueprint(renewal_bp)
app.register_blueprint(client_export_bp)  # Renewal routes
app.register_blueprint(claims_bp)  
app.register_blueprint(settings_bp)

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


# Test PDF route for WhatsApp template testing
@app.route('/test-policy.pdf')
def serve_test_pdf():
    """Serve test PDF for WhatsApp template validation"""
    from flask import send_file
    import os
    
    pdf_path = os.path.join(app.root_path, 'static', 'test_policy_document.pdf')
    
    # Create test PDF if it doesn't exist
    if not os.path.exists(pdf_path):
        try:
            from create_test_pdf import create_test_pdf
            create_test_pdf()
        except ImportError:
            # Fallback: create a simple text file if reportlab is not available
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            with open(pdf_path.replace('.pdf', '.txt'), 'w') as f:
                f.write("Test Policy Document\n\nThis is a test file for WhatsApp template validation.\n\nInsta Insurance Consultancy")
            return "Test PDF creation requires reportlab. Please install: pip install reportlab", 500
    
    return send_file(pdf_path, 
                     as_attachment=False, 
                     download_name='test_policy_document.pdf',
                     mimetype='application/pdf')

# Route to serve renewal documents
@app.route('/static/renewals/<filename>')
def serve_renewal_document(filename):
    """Serve renewal documents for WhatsApp"""
    from flask import send_from_directory
    import os
    
    renewals_dir = os.path.join(app.root_path, 'static', 'renewals')
    
    if not os.path.exists(os.path.join(renewals_dir, filename)):
        return "File not found", 404
    
    return send_from_directory(renewals_dir, filename, mimetype='application/pdf')

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

    # Check authentication configuration
    print("✅ Simple authentication enabled")
    print(f"📝 Admin emails: {', '.join(Config.ADMIN_EMAILS)}")

    print("🚀 Starting Insurance Portal with Full Integration...")
    print("📱 WhatsApp webhook: http://localhost:5050/webhook")
    print("📊 Excel sync: Real-time database → Google Drive")
    print("🌐 Web portal: http://localhost:5050/")
    print("🔐 Authentication: Email/Password")

    # Production settings
    port = int(os.environ.get("PORT", 5050))
    
    # Start real-time cleanup service
    print("🚀 Starting real-time file cleanup service...")
    start_realtime_cleanup_service(check_interval_seconds=60)
    print("✅ Real-time cleanup service started (checks every 60 seconds)")
    
    if Config.FLASK_ENV == "development":
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