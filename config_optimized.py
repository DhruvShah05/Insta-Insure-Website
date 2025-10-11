"""
Optimized Configuration for 2-4 Concurrent Users
Tuned for i3 2nd gen, 4GB RAM system
"""
import os
from config import Config

class OptimizedConfig(Config):
    """Optimized configuration for small-scale deployment (2-4 users)"""
    
    # Database Connection Pool - Reduced for 2-4 users
    DATABASE_POOL_SIZE = 3  # Down from 15
    DATABASE_MAX_OVERFLOW = 2  # Down from 30
    DATABASE_TIMEOUT = 30  # Down from 45
    DATABASE_RETRY_ATTEMPTS = 2  # Down from 3
    
    # Task Queue - Optimized for small workload
    TASK_QUEUE_MAX_WORKERS = 3  # Down from 15
    TASK_QUEUE_MAX_SIZE = 100  # Down from 1000
    TASK_PRIORITY_LEVELS = 3  # Keep all priority levels
    
    # File Operations - Reduced concurrent uploads
    FILE_MANAGER_MAX_WORKERS = 2  # Down from 10
    FILE_BATCH_SIZE = 5  # Down from 50
    FILE_UPLOAD_TIMEOUT = 60  # Keep reasonable timeout
    
    # Cache Settings - Keep Redis but optimize
    CACHE_DEFAULT_TTL = 600  # 10 minutes (down from 1800)
    CACHE_SESSION_TTL = 1800  # 30 minutes for sessions
    CACHE_USER_TTL = 900  # 15 minutes for user data
    
    # Rate Limiting - Relaxed for small user base
    RATE_LIMIT_API = 50  # Down from 100 per minute
    RATE_LIMIT_GENERAL = 100  # Down from 200 per minute
    RATE_LIMIT_WEBHOOK = 200  # Down from 1000 per minute
    
    # Monitoring - Less frequent checks
    MONITORING_INTERVAL = 60  # Every minute instead of real-time
    PERFORMANCE_WINDOW = 300  # 5 minutes instead of 15
    METRICS_RETENTION = 3600  # 1 hour instead of 24 hours
    
    # Session Management
    SESSION_PERMANENT_LIFETIME = 14400  # 4 hours instead of 8
    SESSION_REFRESH_EACH_REQUEST = False  # Reduce overhead
    
    # Flask App Settings - Optimized for small scale
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25MB instead of 50MB
    SEND_FILE_MAX_AGE_DEFAULT = 1800  # 30 minutes instead of 1 hour
    
    # WSGI Server Settings (Waitress for Windows)
    WAITRESS_THREADS = 4  # Down from 20
    WAITRESS_CONNECTION_LIMIT = 100  # Down from 1000
    WAITRESS_CLEANUP_INTERVAL = 60  # More frequent cleanup
    WAITRESS_CHANNEL_TIMEOUT = 60  # Shorter timeout
    
    # Background Task Settings
    WHATSAPP_BATCH_SIZE = 5  # Down from 10
    EMAIL_BATCH_SIZE = 3  # Down from 10
    EXCEL_SYNC_BATCH_SIZE = 10  # Down from 50
    
    # Memory Management
    PYTHON_GC_THRESHOLD = (500, 8, 8)  # More aggressive garbage collection
    MAX_MEMORY_USAGE_MB = 800  # Alert if app uses more than 800MB
    
    # Excel Sync Optimization
    EXCEL_SYNC_CHUNK_SIZE = 50  # Process 50 records at a time
    EXCEL_SYNC_DELAY = 0.1  # Small delay between chunks
    EXCEL_MAX_RETRIES = 2  # Fewer retries
    
    @classmethod
    def get_database_config(cls):
        """Get optimized database configuration"""
        return {
            'pool_size': cls.DATABASE_POOL_SIZE,
            'max_overflow': cls.DATABASE_MAX_OVERFLOW,
            'pool_timeout': cls.DATABASE_TIMEOUT,
            'pool_recycle': 1800,  # 30 minutes
            'pool_pre_ping': True,
            'echo': False  # Disable SQL logging for performance
        }
    
    @classmethod
    def get_task_queue_config(cls):
        """Get optimized task queue configuration"""
        return {
            'max_workers': cls.TASK_QUEUE_MAX_WORKERS,
            'max_queue_size': cls.TASK_QUEUE_MAX_SIZE,
            'worker_timeout': 300,  # 5 minutes
            'retry_delay': 5,  # 5 seconds between retries
            'max_retries': 2
        }
    
    @classmethod
    def get_cache_config(cls):
        """Get optimized cache configuration"""
        return {
            'default_ttl': cls.CACHE_DEFAULT_TTL,
            'session_ttl': cls.CACHE_SESSION_TTL,
            'user_ttl': cls.CACHE_USER_TTL,
            'max_memory_mb': 100,  # Limit Redis memory to 100MB
            'eviction_policy': 'allkeys-lru'  # Remove least recently used
        }
    
    @classmethod
    def get_waitress_config(cls):
        """Get optimized Waitress server configuration"""
        return {
            'host': '0.0.0.0',
            'port': 5050,
            'threads': cls.WAITRESS_THREADS,
            'connection_limit': cls.WAITRESS_CONNECTION_LIMIT,
            'cleanup_interval': cls.WAITRESS_CLEANUP_INTERVAL,
            'channel_timeout': cls.WAITRESS_CHANNEL_TIMEOUT,
            'max_request_body_size': cls.MAX_CONTENT_LENGTH,
            'expose_tracebacks': False,  # Security
            'ident': 'Insurance Portal'
        }
