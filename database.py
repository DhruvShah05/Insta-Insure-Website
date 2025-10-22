"""
Centralized Database Connection Manager for Insurance Portal
Optimized for multi-user concurrent access with connection pooling
"""

import threading
import logging
from supabase import create_client, Client
from dynamic_config import Config
from typing import Optional
import time

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Thread-safe Supabase client manager with connection pooling"""
    
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure single database manager instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database manager with connection pooling"""
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self._client: Optional[Client] = None
        self._client_lock = threading.Lock()
        self._connection_count = 0
        self._max_retries = 3
        self._retry_delay = 1.0
        
        logger.info("Database manager initialized")
    
    def get_client(self) -> Client:
        """Get thread-safe Supabase client with automatic retry"""
        with self._client_lock:
            if self._client is None:
                self._create_client()
            
            self._connection_count += 1
            return self._client
    
    def _create_client(self):
        """Create new Supabase client with retry logic"""
        for attempt in range(self._max_retries):
            try:
                self._client = create_client(
                    Config.SUPABASE_URL, 
                    Config.SUPABASE_KEY
                )
                logger.info(f"Supabase client created successfully (attempt {attempt + 1})")
                return
                
            except Exception as e:
                logger.error(f"Failed to create Supabase client (attempt {attempt + 1}): {e}")
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                else:
                    raise Exception(f"Failed to create Supabase client after {self._max_retries} attempts")
    
    def execute_query(self, operation_name: str, query_func, max_retries: int = 2):
        """Execute database query with automatic retry and error handling"""
        client = self.get_client()
        
        for attempt in range(max_retries + 1):
            try:
                result = query_func(client)
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on retry {attempt}")
                return result
                
            except Exception as e:
                logger.error(f"{operation_name} failed (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries:
                    # Recreate client on connection errors
                    if "connection" in str(e).lower() or "timeout" in str(e).lower():
                        with self._client_lock:
                            self._client = None
                        time.sleep(self._retry_delay)
                    else:
                        time.sleep(0.5)  # Shorter delay for non-connection errors
                else:
                    logger.error(f"{operation_name} failed permanently after {max_retries + 1} attempts")
                    raise e
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics for monitoring"""
        return {
            'connection_count': self._connection_count,
            'client_active': self._client is not None,
            'max_retries': self._max_retries
        }
    
    def health_check(self) -> bool:
        """Perform database health check"""
        try:
            def check_query(client):
                return client.table("users").select("count", count="exact").execute()
            
            result = self.execute_query("health_check", check_query, max_retries=1)
            logger.info("Database health check passed")
            return True
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()

def get_supabase() -> Client:
    """Get thread-safe Supabase client instance"""
    return db_manager.get_client()

def execute_db_operation(operation_name: str, query_func, max_retries: int = 2):
    """Execute database operation with retry logic"""
    return db_manager.execute_query(operation_name, query_func, max_retries)

# Convenience functions for common operations
def safe_select(table_name: str, columns: str = "*", filters: dict = None):
    """Safely execute SELECT query with error handling"""
    def query_func(client):
        query = client.table(table_name).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        return query.execute()
    
    return execute_db_operation(f"select_{table_name}", query_func)

def safe_insert(table_name: str, data: dict):
    """Safely execute INSERT query with error handling"""
    def query_func(client):
        return client.table(table_name).insert(data).execute()
    
    return execute_db_operation(f"insert_{table_name}", query_func)

def safe_update(table_name: str, data: dict, filters: dict):
    """Safely execute UPDATE query with error handling"""
    def query_func(client):
        query = client.table(table_name).update(data)
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.execute()
    
    return execute_db_operation(f"update_{table_name}", query_func)

def safe_delete(table_name: str, filters: dict):
    """Safely execute DELETE query with error handling"""
    def query_func(client):
        query = client.table(table_name).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.execute()
    
    return execute_db_operation(f"delete_{table_name}", query_func)
