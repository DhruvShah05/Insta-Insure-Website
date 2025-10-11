"""
Multi-User Deployment Script
Handles deployment with all scaling components
"""
import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class MultiUserDeployer:
    """Handles multi-user deployment process"""
    
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
        
        logger.info(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return True
    
    def create_virtual_environment(self):
        """Create virtual environment if it doesn't exist"""
        logger.info("Setting up virtual environment...")
        
        if self.venv_path.exists():
            logger.info("✅ Virtual environment already exists")
            return True
        
        try:
            subprocess.run([
                sys.executable, '-m', 'venv', str(self.venv_path)
            ], check=True)
            
            logger.info("✅ Virtual environment created")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to create virtual environment: {e}")
            return False
    
    def get_pip_path(self):
        """Get pip executable path"""
        if os.name == 'nt':  # Windows
            return self.venv_path / 'Scripts' / 'pip.exe'
        else:  # Unix/Linux/macOS
            return self.venv_path / 'bin' / 'pip'
    
    def get_python_path(self):
        """Get Python executable path"""
        if os.name == 'nt':  # Windows
            return self.venv_path / 'Scripts' / 'python.exe'
        else:  # Unix/Linux/macOS
            return self.venv_path / 'bin' / 'python'
    
    def install_dependencies(self):
        """Install production dependencies"""
        logger.info("Installing dependencies...")
        
        pip_path = self.get_pip_path()
        
        if not pip_path.exists():
            logger.error("❌ Pip not found in virtual environment")
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
            
            logger.info("✅ Dependencies installed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies: {e}")
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
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_required)}")
            return False
        
        if missing_optional:
            logger.warning(f"⚠️ Missing optional environment variables: {', '.join(missing_optional)}")
            logger.warning("Some features may be limited")
        
        logger.info("✅ Environment variables checked")
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
        
        logger.info("✅ Directories created")
        return True
    
    def test_database_connection(self):
        """Test database connection"""
        logger.info("Testing database connection...")
        
        try:
            python_path = self.get_python_path()
            
            # Test script
            test_script = """
import sys
sys.path.insert(0, '.')
from database_pool import check_database_health

healthy, message = check_database_health()
if healthy:
    print("✅ Database connection successful")
    sys.exit(0)
else:
    print(f"❌ Database connection failed: {message}")
    sys.exit(1)
"""
            
            result = subprocess.run([
                str(python_path), '-c', test_script
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                logger.info("✅ Database connection test passed")
                return True
            else:
                logger.error(f"❌ Database connection test failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Database connection test error: {e}")
            return False
    
    def test_services(self):
        """Test various services"""
        logger.info("Testing services...")
        
        try:
            python_path = self.get_python_path()
            
            # Service test script
            test_script = """
import sys
sys.path.insert(0, '.')

# Test cache manager
try:
    from cache_manager import cache_manager
    cache_manager.set('test', 'ok', 10)
    if cache_manager.get('test') == 'ok':
        print("✅ Cache manager working")
    else:
        print("⚠️ Cache manager degraded")
except Exception as e:
    print(f"❌ Cache manager error: {e}")

# Test task queue
try:
    from task_queue import task_queue
    stats = task_queue.get_queue_stats()
    print(f"✅ Task queue ready: {stats}")
except Exception as e:
    print(f"❌ Task queue error: {e}")

# Test file manager
try:
    from batch_file_operations import batch_file_manager
    stats = batch_file_manager.get_stats()
    print(f"✅ File manager ready: {stats}")
except Exception as e:
    print(f"❌ File manager error: {e}")
"""
            
            result = subprocess.run([
                str(python_path), '-c', test_script
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            logger.info("Service test output:")
            for line in result.stdout.strip().split('\n'):
                if line:
                    logger.info(f"  {line}")
            
            if result.stderr:
                logger.warning("Service test warnings:")
                for line in result.stderr.strip().split('\n'):
                    if line:
                        logger.warning(f"  {line}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Service test error: {e}")
            return False
    
    def create_systemd_service(self):
        """Create systemd service file for Linux deployment"""
        if os.name == 'nt':
            logger.info("Skipping systemd service creation on Windows")
            return True
        
        logger.info("Creating systemd service file...")
        
        service_content = f"""[Unit]
Description=Insurance Portal Multi-User Application
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory={self.project_root}
Environment=PATH={self.venv_path}/bin
ExecStart={self.venv_path}/bin/gunicorn -c gunicorn_config.py wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.project_root / 'insurance-portal.service'
        
        try:
            with open(service_file, 'w') as f:
                f.write(service_content)
            
            logger.info(f"✅ Systemd service file created: {service_file}")
            logger.info("To install the service:")
            logger.info(f"  sudo cp {service_file} /etc/systemd/system/")
            logger.info("  sudo systemctl daemon-reload")
            logger.info("  sudo systemctl enable insurance-portal")
            logger.info("  sudo systemctl start insurance-portal")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create systemd service: {e}")
            return False
    
    def create_nginx_config(self):
        """Create nginx configuration"""
        logger.info("Creating nginx configuration...")
        
        nginx_config = """server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;
    
    # Static files
    location /static/ {
        alias /path/to/your/app/static/;  # Replace with actual path
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
    
    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running operations
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Webhook endpoints (higher rate limit)
    location /webhook {
        limit_req zone=general burst=100 nodelay;
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # General application
    location / {
        limit_req zone=general burst=50 nodelay;
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5050;
        access_log off;
    }
}

# HTTPS redirect (uncomment when SSL is configured)
# server {
#     listen 80;
#     server_name your-domain.com;
#     return 301 https://$server_name$request_uri;
# }
"""
        
        nginx_file = self.project_root / 'nginx.conf'
        
        try:
            with open(nginx_file, 'w') as f:
                f.write(nginx_config)
            
            logger.info(f"✅ Nginx configuration created: {nginx_file}")
            logger.info("To install nginx configuration:")
            logger.info(f"  sudo cp {nginx_file} /etc/nginx/sites-available/insurance-portal")
            logger.info("  sudo ln -s /etc/nginx/sites-available/insurance-portal /etc/nginx/sites-enabled/")
            logger.info("  sudo nginx -t")
            logger.info("  sudo systemctl reload nginx")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create nginx config: {e}")
            return False
    
    def create_startup_script(self):
        """Create startup script"""
        logger.info("Creating startup script...")
        
        if os.name == 'nt':
            # Windows batch script
            script_content = f"""@echo off
echo Starting Insurance Portal Multi-User Application...

cd /d "{self.project_root}"

REM Activate virtual environment
call "{self.venv_path}\\Scripts\\activate.bat"

REM Start application
echo Starting with Gunicorn...
"{self.venv_path}\\Scripts\\gunicorn.exe" -c gunicorn_config.py wsgi:application

pause
"""
            script_file = self.project_root / 'start_multiuser.bat'
        else:
            # Unix shell script
            script_content = f"""#!/bin/bash
echo "Starting Insurance Portal Multi-User Application..."

cd "{self.project_root}"

# Activate virtual environment
source "{self.venv_path}/bin/activate"

# Start application
echo "Starting with Gunicorn..."
"{self.venv_path}/bin/gunicorn" -c gunicorn_config.py wsgi:application
"""
            script_file = self.project_root / 'start_multiuser.sh'
        
        try:
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            if os.name != 'nt':
                os.chmod(script_file, 0o755)
            
            logger.info(f"✅ Startup script created: {script_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create startup script: {e}")
            return False
    
    def deploy(self):
        """Run complete deployment process"""
        logger.info("🚀 Starting multi-user deployment...")
        
        steps = [
            ("Check Python version", self.check_python_version),
            ("Create virtual environment", self.create_virtual_environment),
            ("Install dependencies", self.install_dependencies),
            ("Check environment variables", self.check_environment_variables),
            ("Create directories", self.create_directories),
            ("Test database connection", self.test_database_connection),
            ("Test services", self.test_services),
            ("Create systemd service", self.create_systemd_service),
            ("Create nginx config", self.create_nginx_config),
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
                    logger.error(f"❌ Step failed: {step_name}")
                else:
                    logger.info(f"✅ Step completed: {step_name}")
            except Exception as e:
                failed_steps.append(step_name)
                logger.error(f"❌ Step error: {step_name} - {e}")
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("DEPLOYMENT SUMMARY")
        logger.info(f"{'='*60}")
        
        if failed_steps:
            logger.error(f"❌ Deployment completed with {len(failed_steps)} failed steps:")
            for step in failed_steps:
                logger.error(f"  - {step}")
            logger.error("\nPlease fix the issues and run deployment again.")
            return False
        else:
            logger.info("✅ Deployment completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Configure your domain in nginx.conf")
            logger.info("2. Set up SSL certificate")
            logger.info("3. Configure Redis (optional but recommended)")
            logger.info("4. Start the application:")
            
            if os.name == 'nt':
                logger.info("   ./start_multiuser.bat")
            else:
                logger.info("   ./start_multiuser.sh")
            
            logger.info("\n🎉 Your multi-user insurance portal is ready!")
            return True

def main():
    """Main deployment function"""
    deployer = MultiUserDeployer()
    success = deployer.deploy()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
