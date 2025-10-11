"""
Windows Server Startup Script
Handles starting the multi-user application with proper error handling
"""
import os
import sys

# Set encoding for Windows console
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

def start_server():
    """Start the multi-user server with fallback options"""
    
    print('[INFO] Starting Insurance Portal Multi-User Server...')
    print('[INFO] Server will be available at: http://localhost:5050')
    print('[INFO] Health check: http://localhost:5050/health')
    print('[INFO] Metrics: http://localhost:5050/metrics')
    print('')
    
    # Try Waitress first (recommended for Windows)
    try:
        from waitress import serve
        from app_multiuser import app
        
        print('[OK] Starting with Waitress WSGI server...')
        print('[OK] Multi-user scaling features enabled')
        print('[OK] Press Ctrl+C to stop the server')
        print('')
        
        # Start server with Waitress
        serve(
            app, 
            host='0.0.0.0', 
            port=5050, 
            threads=20,
            connection_limit=1000,
            cleanup_interval=30,
            channel_timeout=120
        )
        
    except ImportError as e:
        print(f'[WARNING] Waitress not available: {e}')
        print('[INFO] Falling back to Flask development server...')
        
        try:
            from app_multiuser import app
            app.run(
                host='0.0.0.0', 
                port=5050, 
                debug=False, 
                threaded=True,
                use_reloader=False
            )
        except Exception as e:
            print(f'[ERROR] Flask server failed: {e}')
            return False
            
    except Exception as e:
        print(f'[ERROR] Server startup failed: {e}')
        print('[INFO] Checking for common issues...')
        
        # Check for common issues
        if 'Address already in use' in str(e) or 'WinError 10048' in str(e):
            print('[ERROR] Port 5050 is already in use!')
            print('[FIX] Try stopping other applications using port 5050')
            print('[FIX] Or change the port in the .env file')
        
        elif 'Permission denied' in str(e):
            print('[ERROR] Permission denied!')
            print('[FIX] Try running as administrator')
        
        else:
            print('[ERROR] Unknown error occurred')
            print('[FIX] Check the logs for more details')
        
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = start_server()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print('\n[INFO] Server stopped by user')
        sys.exit(0)
    except Exception as e:
        print(f'[ERROR] Unexpected error: {e}')
        sys.exit(1)
