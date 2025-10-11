"""
WSGI Configuration for Production Multi-User Deployment
Optimized for concurrent user handling with proper worker management
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Add the application directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set production environment
os.environ.setdefault('FLASK_ENV', 'production')

# Configure logging for production
if not os.path.exists('logs'):
    os.makedirs('logs')

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        RotatingFileHandler('logs/production.log', maxBytes=50*1024*1024, backupCount=10),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

try:
    from app import app as application
    logger.info("WSGI application loaded successfully")
    
    # Validate critical environment variables
    required_vars = [
        'SUPABASE_URL', 'SUPABASE_KEY', 'CLERK_SECRET_KEY',
        'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("All critical environment variables are set")
    
    # Initialize database pool
    from database_pool import check_database_health
    db_healthy, db_message = check_database_health()
    if db_healthy:
        logger.info(f"Database connection pool initialized: {db_message}")
    else:
        logger.error(f"Database initialization failed: {db_message}")
    
except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise

if __name__ == "__main__":
    application.run()
