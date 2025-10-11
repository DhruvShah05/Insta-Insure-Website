"""
Gunicorn Configuration for Multi-User Production Deployment
Optimized for handling concurrent users with proper worker management
"""
import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5050')}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1  # Recommended formula
worker_class = "gevent"  # Async worker for better concurrency
worker_connections = 1000
max_requests = 1000  # Restart workers after handling this many requests
max_requests_jitter = 100  # Add randomness to prevent thundering herd

# Timeout settings
timeout = 120  # Worker timeout in seconds
keepalive = 5  # Keep-alive connections
graceful_timeout = 30

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "insurance_portal"

# Server mechanics
daemon = False
pidfile = "logs/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

# Application
wsgi_module = "wsgi:application"

# Worker process management
preload_app = True  # Load application code before forking workers
enable_stdio_inheritance = True

# Memory management
max_worker_memory = 200 * 1024 * 1024  # 200MB per worker

def when_ready(server):
    """Called just after the server is started"""
    server.log.info("Insurance Portal server is ready. Accepting connections.")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal"""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked"""
    server.log.info(f"Worker {worker.pid} is being forked")

def post_fork(server, worker):
    """Called just after a worker has been forked"""
    server.log.info(f"Worker {worker.pid} has been forked")
    
    # Initialize worker-specific resources here
    from database_pool import check_database_health
    try:
        db_healthy, db_message = check_database_health()
        if db_healthy:
            worker.log.info(f"Worker {worker.pid} database connection verified")
        else:
            worker.log.error(f"Worker {worker.pid} database connection failed: {db_message}")
    except Exception as e:
        worker.log.error(f"Worker {worker.pid} database check error: {e}")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal"""
    worker.log.info(f"Worker {worker.pid} received SIGABRT signal")

def pre_exec(server):
    """Called just before a new master process is forked"""
    server.log.info("Forked child, re-executing.")

def pre_request(worker, req):
    """Called just before a worker processes the request"""
    worker.log.debug(f"Worker {worker.pid} processing {req.method} {req.path}")

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request"""
    # Log slow requests
    if hasattr(req, 'start_time'):
        duration = time.time() - req.start_time
        if duration > 5:  # Log requests taking more than 5 seconds
            worker.log.warning(f"Slow request: {req.method} {req.path} took {duration:.2f}s")

# Environment variables for workers
raw_env = [
    f"FLASK_ENV=production",
    f"PYTHONPATH={os.getcwd()}",
]

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
