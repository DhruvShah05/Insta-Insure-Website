"""
Windows-Compatible Multi-User Deployment Script
Handles deployment with all scaling components (no emojis for Windows console)
"""
import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Setup logging without emojis for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class WindowsMultiUserDeployer:
    """Handles multi-user deployment process for Windows"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / 'venv'
        self.requirements_file = self.project_root / 'requirements_production.txt'
        
    def check_python_version(self):
        """Check Python version compatibility"""
        logger.info("Checking Python version...")
        
        if sys.version_info < (3, 8):
            logger.error("Python 3.8 or higher is required")
            return False
        
        logger.info(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return True
    
    def create_virtual_environment(self):
        """Create virtual environment if it doesn't exist"""
        logger.info("Setting up virtual environment...")
        
        if self.venv_path.exists():
            logger.info("[OK] Virtual environment already exists")
            return True
        
        try:
            subprocess.run([
                sys.executable, '-m', 'venv', str(self.venv_path)
            ], check=True)
            
            logger.info("[OK] Virtual environment created")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[ERROR] Failed to create virtual environment: {e}")
            return False
    
    def get_pip_path(self):
        """Get pip executable path"""
        return self.venv_path / 'Scripts' / 'pip.exe'
    
    def get_python_path(self):
        """Get Python executable path"""
        return self.venv_path / 'Scripts' / 'python.exe'
    
    def install_dependencies(self):
        """Install production dependencies"""
        logger.info("Installing dependencies...")
        
        pip_path = self.get_pip_path()
        
        if not pip_path.exists():
            logger.error("[ERROR] Pip not found in virtual environment")
            return False
        
        try:
            # Upgrade pip first
            subprocess.run([
                str(pip_path), 'install', '--upgrade', 'pip'
            ], check=True)
            
            # Install requirements
            subprocess.run([
                str(pip_path), 'install', '-r', str(self.requirements_file)
            ], check=True)
            
            logger.info("[OK] Dependencies installed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[ERROR] Failed to install dependencies: {e}")
            return False
    
    def check_environment_variables(self):
        """Check required environment variables"""
        logger.info("Checking environment variables...")
        
        required_vars = [
            'SUPABASE_URL',
            'SUPABASE_KEY',
            'CLERK_SECRET_KEY',
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN',
            'GOOGLE_CREDENTIALS_FILE'
        ]
        
        optional_vars = [
            'REDIS_URL',
            'WHATSAPP_TOKEN',
            'WHATSAPP_PHONE_ID',
            'VERIFY_TOKEN'
        ]
        
        missing_required = []
        missing_optional = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
        
        for var in optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)
        
        if missing_required:
            logger.error(f"[ERROR] Missing required environment variables: {', '.join(missing_required)}")
            logger.info("Please set these environment variables before continuing:")
            for var in missing_required:
                logger.info(f"  set {var}=your_value_here")
            logger.info("Or create a .env file with these variables")
            return False
        
        if missing_optional:
            logger.warning(f"[WARNING] Missing optional environment variables: {', '.join(missing_optional)}")
            logger.warning("Some features may be limited")
        
        logger.info("[OK] Environment variables checked")
        return True
    
    def create_directories(self):
        """Create necessary directories"""
        logger.info("Creating directories...")
        
        directories = [
            'logs',
            'static/renewals',
            'static/uploads',
            'temp'
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("[OK] Directories created")
        return True
    
    def create_env_file_template(self):
        """Create .env file template if it doesn't exist"""
        logger.info("Creating .env file template...")
        
        env_file = self.project_root / '.env'
        
        if env_file.exists():
            logger.info("[OK] .env file already exists")
            return True
        
        env_template = """# Database Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here

# Authentication
CLERK_SECRET_KEY=your_clerk_secret_key_here
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key_here
CLERK_FRONTEND_API=your_clerk_frontend_api_here

# Google Drive
GOOGLE_CREDENTIALS_FILE=credentials.json
ROOT_FOLDER_ID=your_root_folder_id_here

# Twilio
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Optional: Redis (recommended for production)
# REDIS_URL=redis://localhost:6379/0

# Optional: WhatsApp Business API
# WHATSAPP_TOKEN=your_whatsapp_token_here
# WHATSAPP_PHONE_ID=your_phone_id_here
# VERIFY_TOKEN=your_verify_token_here

# Application Settings
FLASK_ENV=production
SECRET_KEY=your_secret_key_here
PORT=5050
APP_BASE_URL=http://localhost:5050
"""
        
        try:
            with open(env_file, 'w') as f:
                f.write(env_template)
            
            logger.info(f"[OK] .env template created: {env_file}")
            logger.info("Please edit the .env file with your actual values")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to create .env template: {e}")
            return False
    
    def test_basic_imports(self):
        """Test basic imports without database connection"""
        logger.info("Testing basic imports...")
        
        try:
            python_path = self.get_python_path()
            
            test_script = """
import sys
sys.path.insert(0, '.')

try:
    import flask
    print("[OK] Flask imported successfully")
except ImportError as e:
    print(f"[ERROR] Flask import failed: {e}")
    sys.exit(1)

try:
    import supabase
    print("[OK] Supabase imported successfully")
except ImportError as e:
    print(f"[ERROR] Supabase import failed: {e}")
    sys.exit(1)

try:
    import twilio
    print("[OK] Twilio imported successfully")
except ImportError as e:
    print(f"[ERROR] Twilio import failed: {e}")
    sys.exit(1)

try:
    from cache_manager import cache_manager
    print("[OK] Cache manager imported successfully")
except ImportError as e:
    print(f"[ERROR] Cache manager import failed: {e}")

try:
    from task_queue import task_queue
    print("[OK] Task queue imported successfully")
except ImportError as e:
    print(f"[ERROR] Task queue import failed: {e}")

print("[OK] Basic imports test completed")
"""
            
            result = subprocess.run([
                str(python_path), '-c', test_script
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                logger.info("[OK] Basic imports test passed")
                for line in result.stdout.strip().split('\n'):
                    if line:
                        logger.info(f"  {line}")
                return True
            else:
                logger.error("[ERROR] Basic imports test failed")
                for line in result.stderr.strip().split('\n'):
                    if line:
                        logger.error(f"  {line}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Basic imports test error: {e}")
            return False
    
    def create_startup_script(self):
        """Create Windows startup script"""
        logger.info("Creating startup script...")
        
        script_content = f"""@echo off
echo Starting Insurance Portal Multi-User Application...

cd /d "{self.project_root}"

REM Check if virtual environment exists
if not exist "venv\\Scripts\\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run deploy_multiuser_windows.py first.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call "venv\\Scripts\\activate.bat"

REM Check if .env file exists
if not exist ".env" (
    echo [WARNING] .env file not found. Please create it with your configuration.
    echo You can use the .env template that was created during deployment.
    pause
)

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "static\\renewals" mkdir static\\renewals
if not exist "static\\uploads" mkdir static\\uploads
if not exist "temp" mkdir temp

REM Start application
echo.
echo ========================================
echo  Insurance Portal Multi-User Server
echo ========================================
echo.
echo Starting server...
echo Access the application at: http://localhost:5050
echo Press Ctrl+C to stop the server
echo.

REM Try to start with Waitress (Windows WSGI server)
python -c "
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

try:
    from waitress import serve
    from app_multiuser import app
    print('[OK] Starting with Waitress WSGI server...')
    print('[OK] Server running at: http://localhost:5050')
    print('[OK] Health check: http://localhost:5050/health')
    print('[OK] Metrics: http://localhost:5050/metrics')
    print('')
    serve(app, host='0.0.0.0', port=5050, threads=20)
except ImportError:
    print('[WARNING] Waitress not available, starting with Flask dev server...')
    from app_multiuser import app
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True)
except Exception as e:
    print(f'[ERROR] Error starting server: {{e}}')
    import sys
    sys.exit(1)
"

if errorlevel 1 (
    echo.
    echo Trying fallback startup method...
    python app_multiuser.py
)

echo.
echo Server stopped.
pause"""
        
        script_file = self.project_root / 'start_multiuser.bat'
        
        try:
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            logger.info(f"[OK] Startup script created: {script_file}")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to create startup script: {e}")
            return False
    
    def deploy(self):
        """Run complete deployment process"""
        logger.info("Starting multi-user deployment for Windows...")
        
        steps = [
            ("Check Python version", self.check_python_version),
            ("Create virtual environment", self.create_virtual_environment),
            ("Install dependencies", self.install_dependencies),
            ("Create directories", self.create_directories),
            ("Create .env template", self.create_env_file_template),
            ("Test basic imports", self.test_basic_imports),
            ("Create startup script", self.create_startup_script),
        ]
        
        failed_steps = []
        
        for step_name, step_func in steps:
            logger.info(f"\n{'='*50}")
            logger.info(f"Step: {step_name}")
            logger.info(f"{'='*50}")
            
            try:
                if not step_func():
                    failed_steps.append(step_name)
                    logger.error(f"[ERROR] Step failed: {step_name}")
                else:
                    logger.info(f"[OK] Step completed: {step_name}")
            except Exception as e:
                failed_steps.append(step_name)
                logger.error(f"[ERROR] Step error: {step_name} - {e}")
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("DEPLOYMENT SUMMARY")
        logger.info(f"{'='*60}")
        
        if failed_steps:
            logger.error(f"[ERROR] Deployment completed with {len(failed_steps)} failed steps:")
            for step in failed_steps:
                logger.error(f"  - {step}")
            logger.error("\nPlease fix the issues and run deployment again.")
            
            # Provide specific guidance
            if "Install dependencies" in failed_steps:
                logger.info("\nTo fix dependency issues:")
                logger.info("1. Make sure you have Python 3.8+ installed")
                logger.info("2. Try running: pip install --upgrade pip")
                logger.info("3. Install dependencies manually: pip install -r requirements_production.txt")
            
            return False
        else:
            logger.info("[OK] Deployment completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Edit the .env file with your actual configuration values")
            logger.info("2. Make sure you have your Google credentials.json file")
            logger.info("3. Start the application: start_multiuser.bat")
            logger.info("\n[OK] Your multi-user insurance portal is ready!")
            return True

def main():
    """Main deployment function"""
    deployer = WindowsMultiUserDeployer()
    success = deployer.deploy()
    
    if success:
        print("\n" + "="*60)
        print("DEPLOYMENT SUCCESSFUL!")
        print("="*60)
        print("To start your multi-user insurance portal:")
        print("1. Edit the .env file with your configuration")
        print("2. Double-click start_multiuser.bat")
        print("3. Open http://localhost:5050 in your browser")
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("DEPLOYMENT FAILED!")
        print("="*60)
        print("Please check the error messages above and fix the issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()
