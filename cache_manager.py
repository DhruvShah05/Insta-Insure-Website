"""
Redis Cache Manager for Multi-User Session Management and Rate Limiting
Handles caching, session storage, and rate limiting for concurrent users
"""
import os
import json
import time
import logging
import threading
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from functools import wraps
import hashlib

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

class CacheManager:
    """Redis-based cache manager with fallback to in-memory storage"""
    
    def __init__(self, redis_url=None, fallback_to_memory=True):
        self.redis_client = None
        self.fallback_to_memory = fallback_to_memory
        self.memory_cache = {}
        self.memory_cache_lock = threading.Lock()
        
        # Rate limiting storage
        self.rate_limits = {}
        self.rate_limits_lock = threading.Lock()
        
        # Session storage
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        
        # Initialize Redis if available
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache manager initialized successfully")
                
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                if not fallback_to_memory:
                    raise
                logger.info("Falling back to in-memory cache")
                self.redis_client = None
        else:
            if not REDIS_AVAILABLE:
                logger.warning("Redis not available, using in-memory cache")
            else:
                logger.info("Redis URL not provided, using in-memory cache")
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        elif isinstance(value, (int, float, bool)):
            return str(value)
        else:
            return str(value)
    
    def _deserialize_value(self, value: str, value_type: str = 'auto') -> Any:
        """Deserialize value from storage"""
        if not value:
            return None
        
        if value_type == 'json':
            try:
                return json.loads(value)
            except:
                return value
        elif value_type == 'int':
            try:
                return int(value)
            except:
                return 0
        elif value_type == 'float':
            try:
                return float(value)
            except:
                return 0.0
        else:
            # Auto-detect type
            try:
                return json.loads(value)
            except:
                try:
                    return int(value)
                except:
                    try:
                        return float(value)
                    except:
                        return value
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a value in cache with optional TTL (seconds)"""
        try:
            serialized_value = self._serialize_value(value)
            
            if self.redis_client:
                if ttl:
                    return self.redis_client.setex(key, ttl, serialized_value)
                else:
                    return self.redis_client.set(key, serialized_value)
            else:
                # Fallback to memory
                with self.memory_cache_lock:
                    expiry = datetime.now() + timedelta(seconds=ttl) if ttl else None
                    self.memory_cache[key] = {
                        'value': serialized_value,
                        'expiry': expiry
                    }
                return True
                
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def get(self, key: str, default: Any = None, value_type: str = 'auto') -> Any:
        """Get a value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value is not None:
                    return self._deserialize_value(value, value_type)
            else:
                # Fallback to memory
                with self.memory_cache_lock:
                    cached_item = self.memory_cache.get(key)
                    if cached_item:
                        # Check expiry
                        if cached_item['expiry'] and datetime.now() > cached_item['expiry']:
                            del self.memory_cache[key]
                            return default
                        return self._deserialize_value(cached_item['value'], value_type)
            
            return default
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                # Fallback to memory
                with self.memory_cache_lock:
                    if key in self.memory_cache:
                        del self.memory_cache[key]
                        return True
                return False
                
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(key))
            else:
                # Fallback to memory
                with self.memory_cache_lock:
                    cached_item = self.memory_cache.get(key)
                    if cached_item:
                        # Check expiry
                        if cached_item['expiry'] and datetime.now() > cached_item['expiry']:
                            del self.memory_cache[key]
                            return False
                        return True
                return False
                
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1, ttl: int = None) -> int:
        """Increment a counter in cache"""
        try:
            if self.redis_client:
                if ttl and not self.redis_client.exists(key):
                    # Set initial value with TTL
                    self.redis_client.setex(key, ttl, 0)
                
                result = self.redis_client.incr(key, amount)
                
                # Set TTL if key was just created
                if ttl and result == amount:
                    self.redis_client.expire(key, ttl)
                
                return result
            else:
                # Fallback to memory
                with self.memory_cache_lock:
                    cached_item = self.memory_cache.get(key)
                    
                    if cached_item:
                        # Check expiry
                        if cached_item['expiry'] and datetime.now() > cached_item['expiry']:
                            del self.memory_cache[key]
                            cached_item = None
                    
                    if not cached_item:
                        expiry = datetime.now() + timedelta(seconds=ttl) if ttl else None
                        self.memory_cache[key] = {
                            'value': str(amount),
                            'expiry': expiry
                        }
                        return amount
                    else:
                        current_value = int(cached_item['value']) + amount
                        cached_item['value'] = str(current_value)
                        return current_value
                        
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
    
    def get_keys_pattern(self, pattern: str) -> List[str]:
        """Get keys matching a pattern"""
        try:
            if self.redis_client:
                return self.redis_client.keys(pattern)
            else:
                # Fallback to memory - simple pattern matching
                import fnmatch
                with self.memory_cache_lock:
                    return [key for key in self.memory_cache.keys() if fnmatch.fnmatch(key, pattern)]
                    
        except Exception as e:
            logger.error(f"Cache keys pattern error for {pattern}: {e}")
            return []
    
    def clear_expired(self):
        """Clear expired items from memory cache"""
        if not self.redis_client:
            with self.memory_cache_lock:
                now = datetime.now()
                expired_keys = [
                    key for key, item in self.memory_cache.items()
                    if item['expiry'] and now > item['expiry']
                ]
                
                for key in expired_keys:
                    del self.memory_cache[key]
                
                if expired_keys:
                    logger.info(f"Cleared {len(expired_keys)} expired cache items")

class RateLimiter:
    """Rate limiter using cache manager"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    def is_rate_limited(self, identifier: str, limit: int, window: int) -> bool:
        """
        Check if identifier is rate limited
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit: Maximum requests allowed
            window: Time window in seconds
        
        Returns:
            True if rate limited, False otherwise
        """
        key = f"rate_limit:{identifier}:{window}"
        
        try:
            current_count = self.cache.increment(key, 1, window)
            return current_count > limit
            
        except Exception as e:
            logger.error(f"Rate limit check error for {identifier}: {e}")
            return False
    
    def get_rate_limit_info(self, identifier: str, window: int) -> Dict:
        """Get current rate limit information"""
        key = f"rate_limit:{identifier}:{window}"
        
        try:
            current_count = self.cache.get(key, 0, 'int')
            
            return {
                'current_count': current_count,
                'window': window,
                'key': key
            }
            
        except Exception as e:
            logger.error(f"Rate limit info error for {identifier}: {e}")
            return {'current_count': 0, 'window': window, 'key': key}

class SessionManager:
    """Session manager using cache manager"""
    
    def __init__(self, cache_manager: CacheManager, default_ttl: int = 3600):
        self.cache = cache_manager
        self.default_ttl = default_ttl
    
    def create_session(self, session_id: str, user_data: Dict, ttl: int = None) -> bool:
        """Create a new session"""
        key = f"session:{session_id}"
        session_data = {
            'user_data': user_data,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        }
        
        return self.cache.set(key, session_data, ttl or self.default_ttl)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data"""
        key = f"session:{session_id}"
        return self.cache.get(key, value_type='json')
    
    def update_session(self, session_id: str, user_data: Dict, extend_ttl: bool = True) -> bool:
        """Update session data"""
        key = f"session:{session_id}"
        session_data = self.get_session(session_id)
        
        if not session_data:
            return False
        
        session_data['user_data'].update(user_data)
        session_data['last_activity'] = datetime.now().isoformat()
        
        ttl = self.default_ttl if extend_ttl else None
        return self.cache.set(key, session_data, ttl)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        key = f"session:{session_id}"
        return self.cache.delete(key)
    
    def extend_session(self, session_id: str, ttl: int = None) -> bool:
        """Extend session TTL"""
        session_data = self.get_session(session_id)
        if session_data:
            session_data['last_activity'] = datetime.now().isoformat()
            return self.cache.set(f"session:{session_id}", session_data, ttl or self.default_ttl)
        return False

# Initialize cache manager
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
cache_manager = CacheManager(redis_url=redis_url, fallback_to_memory=True)

# Initialize rate limiter and session manager
rate_limiter = RateLimiter(cache_manager)
session_manager = SessionManager(cache_manager, default_ttl=7200)  # 2 hours

# Decorators for easy use
def rate_limit(limit: int, window: int = 60, key_func=None):
    """Rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            # Determine identifier
            if key_func:
                identifier = key_func(*args, **kwargs)
            else:
                identifier = request.remote_addr
            
            if rate_limiter.is_rate_limited(identifier, limit, window):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'limit': limit,
                    'window': window
                }), 429
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def cache_result(ttl: int = 300, key_func=None):
    """Cache function result decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Generate key from function name and arguments
                arg_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"cache:{func.__name__}:{hashlib.md5(arg_str.encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key, value_type='json')
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# Utility functions
def cache_user_policies(user_id: str, policies: List[Dict], ttl: int = 600):
    """Cache user policies"""
    key = f"user_policies:{user_id}"
    return cache_manager.set(key, policies, ttl)

def get_cached_user_policies(user_id: str) -> Optional[List[Dict]]:
    """Get cached user policies"""
    key = f"user_policies:{user_id}"
    return cache_manager.get(key, value_type='json')

def cache_client_data(phone: str, client_data: Dict, ttl: int = 1800):
    """Cache client data by phone"""
    key = f"client_data:{phone}"
    return cache_manager.set(key, client_data, ttl)

def get_cached_client_data(phone: str) -> Optional[Dict]:
    """Get cached client data by phone"""
    key = f"client_data:{phone}"
    return cache_manager.get(key, value_type='json')

def clear_user_cache(user_id: str):
    """Clear all cache entries for a user"""
    patterns = [
        f"user_policies:{user_id}",
        f"session:{user_id}*",
        f"rate_limit:{user_id}*"
    ]
    
    for pattern in patterns:
        keys = cache_manager.get_keys_pattern(pattern)
        for key in keys:
            cache_manager.delete(key)

def get_cache_stats() -> Dict:
    """Get cache statistics"""
    try:
        if cache_manager.redis_client:
            info = cache_manager.redis_client.info()
            return {
                'type': 'redis',
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'total_commands_processed': info.get('total_commands_processed', 0)
            }
        else:
            with cache_manager.memory_cache_lock:
                return {
                    'type': 'memory',
                    'total_keys': len(cache_manager.memory_cache),
                    'memory_usage': 'N/A'
                }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'type': 'error', 'message': str(e)}
