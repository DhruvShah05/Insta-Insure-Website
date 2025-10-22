"""
System Monitoring Service
Tracks CPU, RAM, disk usage, concurrent users, and active sessions
"""

import psutil
import time
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Singleton class to monitor system metrics and user activity"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.active_users = {}  # {user_id: {'email': str, 'last_activity': datetime, 'ip': str}}
        self.user_lock = Lock()
        self.metrics_history = defaultdict(list)  # Store last 60 data points (1 minute at 1s intervals)
        self.max_history = 60
        
    def get_system_metrics(self):
        """Get current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024 ** 3)
            memory_total_gb = memory.total / (1024 ** 3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            # Process info
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024 ** 2)  # MB
            process_cpu = process.cpu_percent(interval=0.1)
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': round(cpu_percent, 2),
                    'count': cpu_count,
                    'frequency': round(cpu_freq.current, 2) if cpu_freq else 0
                },
                'memory': {
                    'percent': round(memory_percent, 2),
                    'used_gb': round(memory_used_gb, 2),
                    'total_gb': round(memory_total_gb, 2),
                    'available_gb': round(memory.available / (1024 ** 3), 2)
                },
                'disk': {
                    'percent': round(disk_percent, 2),
                    'used_gb': round(disk_used_gb, 2),
                    'total_gb': round(disk_total_gb, 2),
                    'free_gb': round(disk.free / (1024 ** 3), 2)
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                },
                'process': {
                    'memory_mb': round(process_memory, 2),
                    'cpu_percent': round(process_cpu, 2),
                    'threads': process.num_threads()
                }
            }
            
            # Store in history
            self._add_to_history(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _add_to_history(self, metrics):
        """Add metrics to history, keeping only last max_history points"""
        timestamp = metrics['timestamp']
        
        self.metrics_history['cpu_percent'].append({
            'time': timestamp,
            'value': metrics['cpu']['percent']
        })
        self.metrics_history['memory_percent'].append({
            'time': timestamp,
            'value': metrics['memory']['percent']
        })
        self.metrics_history['disk_percent'].append({
            'time': timestamp,
            'value': metrics['disk']['percent']
        })
        
        # Trim history
        for key in self.metrics_history:
            if len(self.metrics_history[key]) > self.max_history:
                self.metrics_history[key] = self.metrics_history[key][-self.max_history:]
    
    def get_metrics_history(self):
        """Get historical metrics for charts"""
        return dict(self.metrics_history)
    
    def track_user_activity(self, user_id, email, ip_address):
        """Track user activity"""
        with self.user_lock:
            self.active_users[user_id] = {
                'email': email,
                'last_activity': datetime.now(),
                'ip': ip_address
            }
            self._cleanup_inactive_users()
    
    def _cleanup_inactive_users(self):
        """Remove users inactive for more than 5 minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=5)
        inactive_users = [
            user_id for user_id, data in self.active_users.items()
            if data['last_activity'] < cutoff_time
        ]
        for user_id in inactive_users:
            del self.active_users[user_id]
    
    def get_active_users(self):
        """Get list of currently active users"""
        with self.user_lock:
            self._cleanup_inactive_users()
            return [
                {
                    'user_id': user_id,
                    'email': data['email'],
                    'last_activity': data['last_activity'].isoformat(),
                    'ip': data['ip'],
                    'active_duration': str(datetime.now() - data['last_activity']).split('.')[0]
                }
                for user_id, data in self.active_users.items()
            ]
    
    def get_concurrent_users_count(self):
        """Get count of concurrent active users"""
        with self.user_lock:
            self._cleanup_inactive_users()
            return len(self.active_users)
    
    def get_full_status(self):
        """Get complete system status including metrics and users"""
        metrics = self.get_system_metrics()
        active_users = self.get_active_users()
        
        return {
            'metrics': metrics,
            'active_users': active_users,
            'concurrent_users': len(active_users),
            'history': self.get_metrics_history()
        }

# Global instance
monitor = SystemMonitor()
