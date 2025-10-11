"""
Production Integration Script
Ensures all production optimizations are properly integrated
"""

import os
import sys
import importlib.util

def check_production_files():
    """Check if all production optimization files exist"""
    required_files = {
        'database.py': 'Database connection manager with pooling',
        'static/js/performance.js': 'Frontend performance optimizations',
        'combined_app.py': 'Production-optimized Flask application',
        'deploy_production.py': 'Automated deployment script'
    }
    
    missing_files = []
    for file_path, description in required_files.items():
        if not os.path.exists(file_path):
            missing_files.append(f"{file_path} - {description}")
    
    return missing_files

def integrate_database_manager():
    """Integrate database manager into the application"""
    try:
        # Check if database.py exists and can be imported
        if os.path.exists('database.py'):
            spec = importlib.util.spec_from_file_location("database", "database.py")
            database_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(database_module)
            
            # Test database manager initialization
            db_manager = database_module.db_manager
            print("✅ Database manager successfully integrated")
            return True
        else:
            print("❌ database.py not found")
            return False
    except Exception as e:
        print(f"❌ Database manager integration failed: {e}")
        return False

def check_performance_js_integration():
    """Check if performance.js is included in templates"""
    template_files = ['templates/dashboard.html', 'templates/base.html']
    integrated = False
    
    for template_file in template_files:
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'performance.js' in content:
                    print(f"✅ performance.js integrated in {template_file}")
                    integrated = True
                    break
    
    if not integrated:
        print("❌ performance.js not integrated in templates")
    
    return integrated

def validate_production_setup():
    """Validate the complete production setup"""
    print("🔍 PRODUCTION SETUP VALIDATION")
    print("=" * 50)
    
    # Check required files
    missing_files = check_production_files()
    if missing_files:
        print("❌ Missing production files:")
        for file in missing_files:
            print(f"   - {file}")
    else:
        print("✅ All production files present")
    
    # Check database integration
    db_integrated = integrate_database_manager()
    
    # Check performance.js integration
    perf_integrated = check_performance_js_integration()
    
    # Check environment variables
    required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
    missing_env_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_env_vars.append(var)
    
    if missing_env_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_env_vars)}")
    else:
        print("✅ All required environment variables set")
    
    # Overall status
    print("\n" + "=" * 50)
    if not missing_files and db_integrated and perf_integrated and not missing_env_vars:
        print("🚀 PRODUCTION READY - All optimizations integrated!")
        return True
    else:
        print("⚠️  PRODUCTION SETUP INCOMPLETE - Some optimizations missing")
        return False

if __name__ == "__main__":
    validate_production_setup()
