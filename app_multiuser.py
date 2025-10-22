"""
Multi-User Scaled Flask Application
Integrates all scaling components for concurrent user handling
"""
from flask import Flask, request, jsonify, render_template, g, session
from flask_login import LoginManager
from datetime import timedelta
from dynamic_config import Config
from auth import auth_bp
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
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Import multi-user scaling components
from database_pool import db_pool, check_database_health
from cache_manager import cache_manager, rate_limiter, session_manager, rate_limit
from task_queue import task_queue, get_queue_status
from batch_file_operations import batch_file_manager
from monitoring import metrics_collector, monitor_requests, create_health_check_blueprint
from whatsapp_bot_async import whatsapp_bot_async, handle_whatsapp_webhook_async
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

# Configure session to last until browser closes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Fallback timeout
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SECURE'] = Config.FLASK_ENV == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# Production-ready secret key
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# Multi-user session configuration
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Fallback timeout
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB max file size
    
    # Performance optimizations for multi-user
    SESSION_REFRESH_EACH_REQUEST=True,
    SEND_FILE_MAX_AGE_DEFAULT=timedelta(hours=1),
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=False,
    
    # Connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS={
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 30
    }
)

# Setup enhanced logging for multi-user environment
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler('logs/multiuser_app.log', maxBytes=50*1024*1024, backupCount=10),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Flask-Login setup with session management
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
    user = User.get_or_create(user_id)
    if user:
        logger.info(f"User loaded: {user.email} with role: {user.role} (is_admin: {user.is_admin})")
    
    return user

# Make config available in templates
@app.context_processor
def inject_config():
    return {
        'config': {
            'CLERK_PUBLISHABLE_KEY': Config.CLERK_PUBLISHABLE_KEY,
            'CLERK_FRONTEND_API': Config.CLERK_FRONTEND_API,
            'PORTAL_NAME': Config.PORTAL_NAME,
            'PORTAL_TITLE': Config.PORTAL_TITLE,
            'LOGO_PATH': Config.LOGO_PATH,
            'COMPANY_NAME': Config.COMPANY_NAME
        }
    }

# Custom Jinja2 filter for Indian date format
@app.template_filter('indian_date')
def indian_date_filter(date_string):
    """Convert date from YYYY-MM-DD to DD/MM/YYYY format"""
    if not date_string:
        return 'N/A'
    
    try:
        if isinstance(date_string, str):
            if '/' in date_string and len(date_string.split('/')) == 3:
                parts = date_string.split('/')
                if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                    return date_string
            
            if '-' in date_string and len(date_string.split('-')) == 3:
                parts = date_string.split('-')
                if len(parts[0]) == 4:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
                elif len(parts[2]) == 4:
                    return f"{parts[0]}/{parts[1]}/{parts[2]}"
        
        if hasattr(date_string, 'strftime'):
            return date_string.strftime('%d/%m/%Y')
        
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
        logger.error(f"Error formatting date {date_string}: {e}")
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

# Enhanced security headers for multi-user environment
@app.after_request
def after_request(response):
    """Add security headers and performance optimizations"""
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Performance headers
    if request.endpoint and request.endpoint.startswith('static'):
        response.headers['Cache-Control'] = 'public, max-age=3600'
    
    # CORS headers for API endpoints
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    return response

# Session management middleware
@app.before_request
def manage_session():
    """Ensure sessions are properly managed"""
    # Allow Flask-Login to manage session permanence
    pass


# Enhanced rate limiting middleware
@app.before_request
def enhanced_rate_limiting():
    """Enhanced rate limiting with different limits for different endpoints"""
    client_ip = request.remote_addr
    endpoint = request.endpoint or request.path
    
    # Different rate limits for different endpoint types
    if endpoint and endpoint.startswith('api.'):
        # API endpoints: 100 requests per minute
        if rate_limiter.is_rate_limited(f"api_{client_ip}", 100, 60):
            metrics_collector.increment_counter('rate_limit_api_exceeded')
            return jsonify({'error': 'API rate limit exceeded'}), 429
    
    elif request.path.startswith('/webhook'):
        # Webhook endpoints: 1000 requests per minute (for WhatsApp)
        if rate_limiter.is_rate_limited(f"webhook_{client_ip}", 1000, 60):
            metrics_collector.increment_counter('rate_limit_webhook_exceeded')
            return jsonify({'error': 'Webhook rate limit exceeded'}), 429
    
    else:
        # General endpoints: 200 requests per minute
        if rate_limiter.is_rate_limited(f"general_{client_ip}", 200, 60):
            metrics_collector.increment_counter('rate_limit_general_exceeded')
            return jsonify({'error': 'Rate limit exceeded'}), 429
    
    # Record request start time for monitoring
    g.request_start_time = time.time()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(policies_bp)
app.register_blueprint(pending_policies_bp)
app.register_blueprint(existing_policies_bp)
app.register_blueprint(whatsapp_bp)
app.register_blueprint(whatsapp_logs_bp)
app.register_blueprint(renewal_bp)
app.register_blueprint(client_export_bp)
app.register_blueprint(claims_bp)
app.register_blueprint(settings_bp)

# Register health check blueprint
health_bp = create_health_check_blueprint()
app.register_blueprint(health_bp)

# Register Excel blueprint if available
if excel_routes_available and excel_bp:
    app.register_blueprint(excel_bp)

# Setup Twilio WhatsApp webhook (for existing Twilio integration)
setup_whatsapp_webhook(app)

# Enhanced WhatsApp webhook with async processing
@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """Enhanced WhatsApp webhook with async processing"""
    if request.method == 'GET':
        # Webhook verification
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if verify_token == os.getenv('VERIFY_TOKEN'):
            return challenge
        else:
            return 'Invalid verification token', 403
    
    elif request.method == 'POST':
        # Process webhook data asynchronously
        try:
            webhook_data = request.get_json()
            if webhook_data:
                # Use async webhook handler
                return handle_whatsapp_webhook_async(webhook_data)
            else:
                return jsonify({'status': 'no_data'}), 400
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

# Multi-user API endpoints
@app.route('/api/system/status')
@rate_limit(limit=10, window=60)  # 10 requests per minute
def system_status():
    """Get system status for monitoring"""
    try:
        # Get various system metrics
        db_healthy, db_message = check_database_health()
        queue_stats = get_queue_status()
        cache_stats = cache_manager.get_cache_stats() if hasattr(cache_manager, 'get_cache_stats') else {}
        file_manager_stats = batch_file_manager.get_stats()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': {
                    'healthy': db_healthy,
                    'message': db_message,
                    'pool_size': db_pool.active_connections
                },
                'task_queue': {
                    'healthy': True,
                    'stats': queue_stats
                },
                'cache': {
                    'healthy': True,
                    'stats': cache_stats
                },
                'file_manager': {
                    'healthy': True,
                    'stats': file_manager_stats
                }
            },
            'performance': metrics_collector.get_performance_summary(15),
            'alerts': metrics_collector.get_alerts()
        })
    except Exception as e:
        logger.error(f"System status error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bulk/send-reminders', methods=['POST'])
@rate_limit(limit=5, window=300)  # 5 requests per 5 minutes
def bulk_send_reminders():
    """Send renewal reminders to multiple customers"""
    try:
        data = request.get_json()
        customers = data.get('customers', [])
        
        if not customers:
            return jsonify({'error': 'No customers provided'}), 400
        
        # Use async WhatsApp bot for bulk operations
        from whatsapp_bot_async import send_reminders_to_multiple_customers
        result = send_reminders_to_multiple_customers(customers)
        
        metrics_collector.increment_counter('bulk_reminders_sent', len(customers))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Bulk reminders error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk/notify-policy-issued', methods=['POST'])
@rate_limit(limit=5, window=300)  # 5 requests per 5 minutes
def bulk_notify_policy_issued():
    """Notify multiple customers about policy issuance"""
    try:
        data = request.get_json()
        notifications = data.get('notifications', [])
        
        if not notifications:
            return jsonify({'error': 'No notifications provided'}), 400
        
        # Use async WhatsApp bot for bulk operations
        from whatsapp_bot_async import notify_multiple_policy_issued
        result = notify_multiple_policy_issued(notifications)
        
        metrics_collector.increment_counter('bulk_notifications_sent', len(notifications))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Bulk notifications error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/batch-upload', methods=['POST'])
@rate_limit(limit=3, window=300)  # 3 requests per 5 minutes
def batch_file_upload():
    """Handle batch file uploads"""
    try:
        files = request.files.getlist('files')
        metadata = request.form.get('metadata', '{}')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        # Parse metadata
        import json
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
        
        # Prepare upload requests
        upload_requests = []
        for i, file in enumerate(files):
            upload_requests.append({
                'file': file,
                'filename': file.filename,
                'mimetype': file.mimetype,
                'client_id': metadata.get('client_id'),
                'member_name': metadata.get('member_name'),
                'policy_id': metadata.get('policy_ids', [None])[i] if i < len(metadata.get('policy_ids', [])) else None,
                'parent_folder_id': Config.ROOT_FOLDER_ID
            })
        
        # Use batch file manager
        from batch_file_operations import upload_multiple_policy_files
        batch_id = upload_multiple_policy_files(upload_requests)
        
        metrics_collector.increment_counter('batch_uploads_initiated')
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'message': f'Batch upload started for {len(files)} files'
        })
        
    except Exception as e:
        logger.error(f"Batch upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/batch-status/<batch_id>')
def batch_operation_status(batch_id):
    """Get status of batch file operation"""
    try:
        result = batch_file_manager.get_batch_result(batch_id)
        
        if result:
            return jsonify({
                'success': True,
                'batch_id': batch_id,
                'result': result
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Batch operation not found or still in progress'
            }), 404
            
    except Exception as e:
        logger.error(f"Batch status error: {e}")
        return jsonify({'error': str(e)}), 500

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

# Error handlers with enhanced logging
@app.errorhandler(404)
def not_found_error(error):
    metrics_collector.increment_counter('error_404')
    return render_template('error.html',
                          error='Page Not Found',
                          message='The requested page could not be found.'), 404

@app.errorhandler(500)
def internal_error(error):
    metrics_collector.increment_counter('error_500')
    logger.error(f'Server Error: {error}')
    return render_template('error.html',
                          error='Internal Server Error',
                          message='An internal server error occurred.'), 500

@app.errorhandler(413)
def too_large(error):
    metrics_collector.increment_counter('error_413')
    return render_template('error.html',
                          error='File Too Large',
                          message='The uploaded file is too large. Maximum size is 50MB.'), 413

@app.errorhandler(429)
def rate_limit_exceeded(error):
    metrics_collector.increment_counter('error_429')
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.'
    }), 429

# Add request monitoring middleware
monitor_requests(app)

# Startup health checks
def perform_startup_checks():
    """Perform startup health checks"""
    logger.info("Performing startup health checks...")
    
    # Check database connection
    db_healthy, db_message = check_database_health()
    if db_healthy:
        logger.info(f"✅ Database: {db_message}")
    else:
        logger.error(f"❌ Database: {db_message}")
    
    # Check cache system
    try:
        cache_manager.set('startup_test', 'ok', 10)
        if cache_manager.get('startup_test') == 'ok':
            logger.info("✅ Cache system: Working")
        else:
            logger.warning("⚠️ Cache system: Degraded")
    except Exception as e:
        logger.error(f"❌ Cache system: {e}")
    
    # Check task queue
    try:
        stats = task_queue.get_queue_stats()
        logger.info(f"✅ Task queue: {stats['total_tasks']} total tasks processed")
    except Exception as e:
        logger.error(f"❌ Task queue: {e}")
    
    # Check file manager
    try:
        stats = batch_file_manager.get_stats()
        logger.info(f"✅ File manager: Ready with {stats['active_workers']} workers")
    except Exception as e:
        logger.error(f"❌ File manager: {e}")

if __name__ == "__main__":
    # Perform startup checks
    perform_startup_checks()
    
    # Check required environment variables
    required_vars = ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID', 'VERIFY_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"⚠️ Missing WhatsApp variables: {', '.join(missing_vars)}")
        logger.warning("WhatsApp functionality will be limited.")
    else:
        logger.info("✅ WhatsApp integration: Fully configured")
    
    # Check Excel functionality
    if excel_routes_available:
        logger.info("✅ Excel integration: Available")
    else:
        logger.warning("⚠️ Excel functionality: Disabled")
    
    logger.info("✅ Clerk authentication: Enabled")
    logger.info(f"📝 Clerk Frontend: {Config.CLERK_FRONTEND_API}")
    
    logger.info("🚀 Starting Multi-User Insurance Portal...")
    logger.info("📱 WhatsApp webhook: /webhook")
    logger.info("📊 System status: /api/system/status")
    logger.info("🏥 Health check: /health")
    logger.info("📈 Metrics: /metrics")
    
    # Production settings
    port = int(os.getenv('PORT', 5050))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    if debug:
        logger.info("🔧 Running in DEVELOPMENT mode")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True,
            use_reloader=False  # Disable reloader to prevent duplicate processes
        )
    else:
        logger.info("🏭 Running in PRODUCTION mode")
        logger.info("💡 Use Gunicorn for production deployment:")
        logger.info(f"   gunicorn -c gunicorn_config.py wsgi:application")
        
        # For direct execution, use a simple WSGI server
        try:
            from waitress import serve
            logger.info("🍽️ Using Waitress WSGI server")
            serve(app, host='0.0.0.0', port=port, threads=20)
        except ImportError:
            logger.warning("Waitress not available, using Flask dev server")
            app.run(
                host='0.0.0.0',
                port=port,
                debug=False,
                threaded=True
            )
