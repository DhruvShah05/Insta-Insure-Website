#!/usr/bin/env python3
"""
Production Deployment Script for Insurance Portal
Optimized for multi-user concurrent access
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if all required dependencies are installed"""
    logger.info("Checking requirements...")
    
    required_packages = [
        'flask', 'flask-login', 'supabase', 'python-dotenv',
        'twilio', 'pandas', 'openpyxl', 'numpy', 'google-api-python-client',
        'google-auth', 'google-auth-oauthlib', 'google-auth-httplib2'
    ]
    
    missing_packages = []
    
    try:
        import pkg_resources
        installed_packages = {pkg.key for pkg in pkg_resources.working_set}
        
        for package in required_packages:
            # Handle package name variations
            pkg_name = package.lower().replace('_', '-')
            if pkg_name in installed_packages or any(pkg.startswith(pkg_name) for pkg in installed_packages):
                logger.info(f"✓ {package} is installed")
            else:
                missing_packages.append(package)
                logger.error(f"✗ {package} is missing")
                
    except Exception as e:
        logger.warning(f"Could not check all packages: {e}")
        # Fallback to import check if pkg_resources fails
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                logger.info(f"✓ {package} is installed")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"✗ {package} is missing")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Install missing packages with: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_environment():
    """Check if all required environment variables are set"""
    logger.info("Checking environment variables...")
    
    required_env_vars = [
        'SUPABASE_URL', 'SUPABASE_KEY', 'GOOGLE_CLIENT_ID', 
        'GOOGLE_CLIENT_SECRET', 'GOOGLE_CREDENTIALS_FILE'
    ]
    
    optional_env_vars = [
        'WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID', 'VERIFY_TOKEN',
        'SMTP_SERVER', 'SMTP_USERNAME', 'SMTP_PASSWORD'
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_required.append(var)
            logger.error(f"✗ Required: {var} is not set")
        else:
            logger.info(f"✓ Required: {var} is set")
    
    for var in optional_env_vars:
        if not os.getenv(var):
            missing_optional.append(var)
            logger.warning(f"⚠ Optional: {var} is not set")
        else:
            logger.info(f"✓ Optional: {var} is set")
    
    if missing_required:
        logger.error(f"Missing required environment variables: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        logger.warning(f"Missing optional variables (some features may be disabled): {', '.join(missing_optional)}")
    
    return True

def check_files():
    """Check if all required files exist"""
    logger.info("Checking required files...")
    
    required_files = [
        '.env',
        'config.py',
        'combined_app.py',
        'database.py',
        'models.py',
        'auth.py'
    ]
    
    google_creds = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    if google_creds:
        required_files.append(google_creds)
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            logger.info(f"✓ {file_path} exists")
        else:
            missing_files.append(file_path)
            logger.error(f"✗ {file_path} is missing")
    
    if missing_files:
        logger.error(f"Missing files: {', '.join(missing_files)}")
        return False
    
    return True

def setup_directories():
    """Create necessary directories"""
    logger.info("Setting up directories...")
    
    directories = ['logs', 'temp', 'uploads']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"✓ Created directory: {directory}")
        else:
            logger.info(f"✓ Directory exists: {directory}")

def test_database_connection():
    """Test database connection"""
    logger.info("Testing database connection...")
    
    try:
        from database import db_manager
        
        # Perform health check
        if db_manager.health_check():
            logger.info("✓ Database connection successful")
            
            # Get connection stats
            stats = db_manager.get_connection_stats()
            logger.info(f"Database stats: {stats}")
            return True
        else:
            logger.error("✗ Database health check failed")
            return False
            
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False

def run_pre_deployment_tests():
    """Run basic tests before deployment"""
    logger.info("Running pre-deployment tests...")
    
    try:
        # Test imports
        import combined_app
        logger.info("✓ Main application imports successfully")
        
        # Test Flask app creation
        app = combined_app.app
        with app.test_client() as client:
            # Test basic routes
            response = client.get('/login')
            if response.status_code in [200, 302]:  # 302 for redirects
                logger.info("✓ Login route accessible")
            else:
                logger.error(f"✗ Login route failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Pre-deployment test failed: {e}")
        return False

def start_production_server():
    """Start the production server"""
    logger.info("Starting production server...")
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    
    try:
        # Import and run the application
        from combined_app import app
        
        logger.info("🚀 Insurance Portal starting in PRODUCTION mode...")
        logger.info("📊 Multi-user optimization: ENABLED")
        logger.info("🔒 Security features: ENABLED")
        logger.info("📝 Logging: ENABLED")
        logger.info("🌐 Server: http://0.0.0.0:5050")
        
        # Run the application
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 5050)),
            debug=False,
            threaded=True,
            use_reloader=False
        )
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

def main():
    """Main deployment function"""
    logger.info("=" * 60)
    logger.info("INSURANCE PORTAL - PRODUCTION DEPLOYMENT")
    logger.info(f"Deployment started at: {datetime.now()}")
    logger.info("=" * 60)
    
    # Run all checks
    checks = [
        ("Requirements", check_requirements),
        ("Environment", check_environment),
        ("Files", check_files),
        ("Database", test_database_connection),
        ("Pre-deployment tests", run_pre_deployment_tests)
    ]
    
    for check_name, check_func in checks:
        logger.info(f"\n--- {check_name} Check ---")
        if not check_func():
            logger.error(f"❌ {check_name} check failed. Deployment aborted.")
            sys.exit(1)
        logger.info(f"✅ {check_name} check passed")
    
    # Setup directories
    logger.info("\n--- Setup ---")
    setup_directories()
    
    # Start server
    logger.info("\n--- Starting Server ---")
    logger.info("✅ All checks passed. Starting production server...")
    start_production_server()

if __name__ == "__main__":
    main()
