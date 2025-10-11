"""
Optimized Server Startup for 2-4 Users
Configured for i3 2nd gen, 4GB RAM
"""
import os
import sys
import psutil
import gc

# Set encoding for Windows console
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Import optimized configuration
from config_optimized import OptimizedConfig

def check_system_resources():
    """Check if system has sufficient resources"""
    print('[INFO] Checking system resources...')
    
    # Check available RAM
    memory = psutil.virtual_memory()
    available_gb = memory.available / (1024**3)
    
    print(f'[INFO] Available RAM: {available_gb:.1f} GB')
    print(f'[INFO] CPU Count: {psutil.cpu_count()} cores')
    
    if available_gb < 1.0:
        print('[WARNING] Low available RAM detected!')
        print('[WARNING] Consider closing other applications for better performance')
    
    return True

def optimize_python_settings():
    """Optimize Python settings for low-resource environment"""
    print('[INFO] Applying Python optimizations...')
    
    # Set garbage collection thresholds for better memory management
    gc.set_threshold(500, 8, 8)
    
    # Disable debug mode
    os.environ['PYTHONOPTIMIZE'] = '1'
    
    # Set smaller buffer sizes
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    print('[OK] Python optimizations applied')

def start_optimized_server():
    """Start the server with optimized settings for 2-4 users"""
    
    print('='*60)
    print('INSURANCE PORTAL - OPTIMIZED FOR 2-4 USERS')
    print('='*60)
    print(f'[INFO] Optimized for: i3 2nd gen, 4GB RAM')
    print(f'[INFO] Target users: 2-4 concurrent users')
    print(f'[INFO] Configuration: Resource-optimized')
    print('')
    
    # Check system resources
    if not check_system_resources():
        return False
    
    # Apply Python optimizations
    optimize_python_settings()
    
    print('[INFO] Starting optimized multi-user server...')
    print('[INFO] Server will be available at: http://localhost:5050')
    print('[INFO] Health check: http://localhost:5050/health')
    print('[INFO] Metrics: http://localhost:5050/metrics')
    print('')
    
    try:
        from waitress import serve
        
        # Import app with optimized config
        os.environ['USE_OPTIMIZED_CONFIG'] = '1'
        from app_multiuser import app
        
        # Get optimized Waitress configuration
        waitress_config = OptimizedConfig.get_waitress_config()
        
        print('[OK] Starting with Waitress WSGI server (optimized)...')
        print(f'[OK] Threads: {waitress_config["threads"]}')
        print(f'[OK] Connection limit: {waitress_config["connection_limit"]}')
        print(f'[OK] Database pool: {OptimizedConfig.DATABASE_POOL_SIZE} connections')
        print(f'[OK] Task workers: {OptimizedConfig.TASK_QUEUE_MAX_WORKERS} workers')
        print(f'[OK] File workers: {OptimizedConfig.FILE_MANAGER_MAX_WORKERS} workers')
        print('')
        print('[OK] Press Ctrl+C to stop the server')
        print('')
        
        # Start server with optimized settings
        serve(
            app,
            host=waitress_config['host'],
            port=waitress_config['port'],
            threads=waitress_config['threads'],
            connection_limit=waitress_config['connection_limit'],
            cleanup_interval=waitress_config['cleanup_interval'],
            channel_timeout=waitress_config['channel_timeout'],
            max_request_body_size=waitress_config['max_request_body_size'],
            expose_tracebacks=waitress_config['expose_tracebacks'],
            ident=waitress_config['ident']
        )
        
    except ImportError as e:
        print(f'[WARNING] Waitress not available: {e}')
        print('[INFO] Falling back to Flask development server...')
        
        try:
            os.environ['USE_OPTIMIZED_CONFIG'] = '1'
            from app_multiuser import app
            
            print('[WARNING] Using Flask dev server (not recommended for production)')
            print('[INFO] Consider installing Waitress: pip install waitress')
            
            app.run(
                host='0.0.0.0',
                port=5050,
                debug=False,
                threaded=True,
                use_reloader=False,
                processes=1  # Single process for low RAM
            )
        except Exception as e:
            print(f'[ERROR] Flask server failed: {e}')
            return False
            
    except Exception as e:
        print(f'[ERROR] Server startup failed: {e}')
        
        # Check for common issues
        if 'Address already in use' in str(e) or 'WinError 10048' in str(e):
            print('[ERROR] Port 5050 is already in use!')
            print('[FIX] Stop other applications using port 5050')
            print('[FIX] Or change PORT in .env file')
        
        elif 'Permission denied' in str(e):
            print('[ERROR] Permission denied!')
            print('[FIX] Try running as administrator')
        
        elif 'Memory' in str(e) or 'RAM' in str(e):
            print('[ERROR] Insufficient memory!')
            print('[FIX] Close other applications to free up RAM')
            print('[FIX] Consider increasing virtual memory/page file')
        
        else:
            print('[ERROR] Unknown error occurred')
            print('[FIX] Check the logs for more details')
        
        return False
    
    return True

def monitor_resources():
    """Monitor system resources during startup"""
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024*1024)
        cpu_percent = process.cpu_percent()
        
        print(f'[INFO] App memory usage: {memory_mb:.1f} MB')
        if memory_mb > OptimizedConfig.MAX_MEMORY_USAGE_MB:
            print(f'[WARNING] High memory usage detected!')
        
        return True
    except Exception as e:
        print(f'[WARNING] Could not monitor resources: {e}')
        return True

if __name__ == "__main__":
    try:
        success = start_optimized_server()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print('\n[INFO] Server stopped by user')
        
        # Show final resource usage
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024*1024)
            print(f'[INFO] Final memory usage: {memory_mb:.1f} MB')
        except:
            pass
        
        sys.exit(0)
    except Exception as e:
        print(f'[ERROR] Unexpected error: {e}')
        sys.exit(1)
