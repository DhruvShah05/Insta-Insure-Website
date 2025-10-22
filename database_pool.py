"""
Database Connection Pool Manager for Multi-User Scaling
Handles concurrent database operations with connection pooling and retry logic
"""
import threading
import time
import logging
import os
from contextlib import contextmanager
from queue import Queue, Empty
from supabase import create_client, Client
import functools
from dynamic_config import Config

logger = logging.getLogger(__name__)

# Database connection pool configuration
# Check if optimized config should be used
if os.getenv('USE_OPTIMIZED_CONFIG'):
    from config_optimized import OptimizedConfig
    POOL_SIZE = OptimizedConfig.DATABASE_POOL_SIZE
    MAX_OVERFLOW = OptimizedConfig.DATABASE_MAX_OVERFLOW
    POOL_TIMEOUT = OptimizedConfig.DATABASE_TIMEOUT
    RETRY_ATTEMPTS = OptimizedConfig.DATABASE_RETRY_ATTEMPTS
else:
    POOL_SIZE = 15
    MAX_OVERFLOW = 30
    POOL_TIMEOUT = 45
    RETRY_ATTEMPTS = 3

class DatabasePool:
    """Thread-safe database connection pool for Supabase"""
    
    def __init__(self, pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW, timeout=POOL_TIMEOUT):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.timeout = timeout
        self.pool = Queue(maxsize=pool_size + max_overflow)
        self.active_connections = 0
        self.lock = threading.Lock()
        
        # Initialize pool with connections
        for _ in range(pool_size):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
                self.active_connections += 1
    
    def _create_connection(self):
        """Create a new Supabase client connection"""
        try:
            return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with automatic cleanup"""
        conn = None
        try:
            # Try to get connection from pool
            try:
                conn = self.pool.get(timeout=self.timeout)
            except Empty:
                # Pool is empty, try to create new connection if under limit
                with self.lock:
                    if self.active_connections < (self.pool_size + self.max_overflow):
                        conn = self._create_connection()
                        if conn:
                            self.active_connections += 1
                    
                if not conn:
                    raise Exception("Database pool exhausted - too many concurrent connections")
            
            yield conn
            
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            # Return connection to pool
            if conn:
                try:
                    self.pool.put_nowait(conn)
                except:
                    # Pool is full, connection will be garbage collected
                    with self.lock:
                        self.active_connections -= 1

# Global database pool instance
db_pool = DatabasePool(pool_size=15, max_overflow=30, timeout=45)

def with_db_retry(max_retries=3, delay=1):
    """Decorator for database operations with retry logic"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}")
            
            raise last_exception
        return wrapper
    return decorator

@with_db_retry(max_retries=3)
def execute_query(table_name, operation, **kwargs):
    """Execute database query with connection pooling and retry logic"""
    with db_pool.get_connection() as supabase:
        table = supabase.table(table_name)
        
        if operation == 'select':
            query = table.select(kwargs.get('columns', '*'))
            
            # Add filters
            for filter_key, filter_value in kwargs.get('filters', {}).items():
                if filter_key.endswith('_eq'):
                    query = query.eq(filter_key[:-3], filter_value)
                elif filter_key.endswith('_neq'):
                    query = query.neq(filter_key[:-4], filter_value)
                elif filter_key.endswith('_gt'):
                    query = query.gt(filter_key[:-3], filter_value)
                elif filter_key.endswith('_gte'):
                    query = query.gte(filter_key[:-4], filter_value)
                elif filter_key.endswith('_lt'):
                    query = query.lt(filter_key[:-3], filter_value)
                elif filter_key.endswith('_lte'):
                    query = query.lte(filter_key[:-4], filter_value)
                elif filter_key.endswith('_like'):
                    query = query.like(filter_key[:-5], filter_value)
                elif filter_key.endswith('_ilike'):
                    query = query.ilike(filter_key[:-6], filter_value)
                else:
                    query = query.eq(filter_key, filter_value)
            
            # Add ordering
            if 'order' in kwargs:
                order_by = kwargs['order']
                if isinstance(order_by, str):
                    query = query.order(order_by)
                elif isinstance(order_by, dict):
                    query = query.order(order_by['column'], desc=order_by.get('desc', False))
            
            # Add limit
            if 'limit' in kwargs:
                query = query.limit(kwargs['limit'])
            
            # Execute query
            if kwargs.get('single', False):
                return query.single().execute()
            else:
                return query.execute()
        
        elif operation == 'insert':
            data = kwargs.get('data')
            if isinstance(data, list):
                # Batch insert
                return table.insert(data).execute()
            else:
                return table.insert(data).execute()
        
        elif operation == 'update':
            query = table.update(kwargs.get('data'))
            
            # Add filters for update
            for filter_key, filter_value in kwargs.get('filters', {}).items():
                query = query.eq(filter_key, filter_value)
            
            return query.execute()
        
        elif operation == 'delete':
            query = table.delete()
            
            # Add filters for delete
            for filter_key, filter_value in kwargs.get('filters', {}).items():
                query = query.eq(filter_key, filter_value)
            
            return query.execute()
        
        else:
            raise ValueError(f"Unsupported operation: {operation}")

def batch_insert(table_name, data_list, batch_size=100):
    """Insert multiple records in batches for better performance"""
    results = []
    
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        try:
            result = execute_query(table_name, 'insert', data=batch)
            results.extend(result.data if result.data else [])
            logger.info(f"Batch inserted {len(batch)} records to {table_name}")
        except Exception as e:
            logger.error(f"Batch insert failed for {table_name}: {e}")
            # Try individual inserts for failed batch
            for item in batch:
                try:
                    result = execute_query(table_name, 'insert', data=item)
                    if result.data:
                        results.extend(result.data)
                except Exception as item_error:
                    logger.error(f"Individual insert failed: {item_error}")
    
    return results

def get_policies_for_client(client_id):
    """Get all policies for a client using connection pool"""
    return execute_query(
        'policies',
        'select',
        columns='*',
        filters={'client_id_eq': client_id}
    )

def get_client_by_phone(phone):
    """Get client by phone number using connection pool"""
    # Try different phone formats
    phone_formats = [phone, phone.replace('+', ''), f'+{phone.replace("+", "")}']
    
    for phone_format in phone_formats:
        try:
            result = execute_query(
                'clients',
                'select',
                columns='*',
                filters={'phone_eq': phone_format},
                single=True
            )
            if result.data:
                return result
        except:
            continue
    
    return None

def update_policy_reminder(policy_id, reminder_time):
    """Update last reminder sent time for a policy"""
    return execute_query(
        'policies',
        'update',
        data={'last_reminder_sent': reminder_time},
        filters={'policy_id': policy_id}
    )

class DatabaseTransaction:
    """Context manager for database transactions"""
    
    def __init__(self):
        self.operations = []
        self.rollback_operations = []
    
    def add_operation(self, table_name, operation, rollback_op=None, **kwargs):
        """Add an operation to the transaction"""
        self.operations.append((table_name, operation, kwargs))
        if rollback_op:
            self.rollback_operations.append(rollback_op)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Execute rollback operations
            for rollback_op in reversed(self.rollback_operations):
                try:
                    rollback_op()
                except Exception as e:
                    logger.error(f"Rollback operation failed: {e}")
            return False
        
        # Execute all operations
        results = []
        try:
            for table_name, operation, kwargs in self.operations:
                result = execute_query(table_name, operation, **kwargs)
                results.append(result)
            return results
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            # Execute rollback operations
            for rollback_op in reversed(self.rollback_operations):
                try:
                    rollback_op()
                except Exception as rollback_error:
                    logger.error(f"Rollback operation failed: {rollback_error}")
            raise

# Health check for database pool
def check_database_health():
    """Check if database connections are healthy"""
    try:
        with db_pool.get_connection() as supabase:
            # Simple query to test connection
            result = supabase.table('clients').select('client_id').limit(1).execute()
            return True, f"Database healthy. Pool size: {db_pool.active_connections}"
    except Exception as e:
        return False, f"Database unhealthy: {e}"
