"""
Monitoring and Health Check System for Multi-User Environment
Tracks system performance, user activity, and service health
"""
import os
import time
import threading
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    active_connections: int
    active_threads: int

@dataclass
class ServiceHealth:
    """Service health status"""
    service_name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str] = None

class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, collection_interval=30, max_history=1000):
        self.collection_interval = collection_interval
        self.max_history = max_history
        
        # Metrics storage
        self.system_metrics = deque(maxlen=max_history)
        self.service_health = {}
        self.user_activity = defaultdict(list)
        self.request_metrics = deque(maxlen=max_history)
        
        # Counters
        self.counters = defaultdict(int)
        self.counters_lock = threading.Lock()
        
        # Collection thread
        self.collecting = True
        self.collector_thread = threading.Thread(target=self._collect_metrics, daemon=True)
        self.collector_thread.start()
        
        logger.info(f"Metrics collector started with {collection_interval}s interval")
    
    def _collect_metrics(self):
        """Background thread for collecting metrics"""
        while self.collecting:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Get process info
                process = psutil.Process()
                connections = len(process.connections())
                threads = process.num_threads()
                
                metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_gb=memory.used / (1024**3),
                    memory_total_gb=memory.total / (1024**3),
                    disk_percent=disk.percent,
                    disk_used_gb=disk.used / (1024**3),
                    disk_total_gb=disk.total / (1024**3),
                    active_connections=connections,
                    active_threads=threads
                )
                
                self.system_metrics.append(metrics)
                
                # Check service health
                self._check_service_health()
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                time.sleep(self.collection_interval)
    
    def _check_service_health(self):
        """Check health of various services"""
        services_to_check = [
            ('database', self._check_database_health),
            ('cache', self._check_cache_health),
            ('task_queue', self._check_task_queue_health),
            ('file_manager', self._check_file_manager_health)
        ]
        
        for service_name, check_func in services_to_check:
            try:
                start_time = time.time()
                status, error = check_func()
                response_time = (time.time() - start_time) * 1000
                
                self.service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    status=status,
                    last_check=datetime.now(),
                    response_time_ms=response_time,
                    error_message=error
                )
                
            except Exception as e:
                self.service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    status='unhealthy',
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message=str(e)
                )
    
    def _check_database_health(self) -> tuple:
        """Check database connection health"""
        try:
            from database_pool import check_database_health
            healthy, message = check_database_health()
            return ('healthy' if healthy else 'unhealthy', message if not healthy else None)
        except Exception as e:
            return ('unhealthy', str(e))
    
    def _check_cache_health(self) -> tuple:
        """Check cache system health"""
        try:
            from cache_manager import cache_manager
            # Simple cache operation test
            test_key = 'health_check'
            cache_manager.set(test_key, 'test', 10)
            value = cache_manager.get(test_key)
            cache_manager.delete(test_key)
            
            if value == 'test':
                return ('healthy', None)
            else:
                return ('degraded', 'Cache read/write test failed')
        except Exception as e:
            return ('unhealthy', str(e))
    
    def _check_task_queue_health(self) -> tuple:
        """Check task queue health"""
        try:
            from task_queue import task_queue
            stats = task_queue.get_queue_stats()
            
            # Check if queue is not overloaded
            total_queue_size = stats.get('total_queue_size', 0)
            if total_queue_size > 1000:
                return ('degraded', f'Queue overloaded: {total_queue_size} tasks')
            
            return ('healthy', None)
        except Exception as e:
            return ('unhealthy', str(e))
    
    def _check_file_manager_health(self) -> tuple:
        """Check file manager health"""
        try:
            from batch_file_operations import batch_file_manager
            stats = batch_file_manager.get_stats()
            
            # Check if too many failed operations
            failed_ratio = stats.get('failed_operations', 0) / max(stats.get('total_operations', 1), 1)
            if failed_ratio > 0.1:  # More than 10% failure rate
                return ('degraded', f'High failure rate: {failed_ratio:.2%}')
            
            return ('healthy', None)
        except Exception as e:
            return ('unhealthy', str(e))
    
    def increment_counter(self, counter_name: str, amount: int = 1):
        """Increment a counter"""
        with self.counters_lock:
            self.counters[counter_name] += amount
    
    def record_request(self, method: str, endpoint: str, status_code: int, 
                      response_time_ms: float, user_id: str = None):
        """Record request metrics"""
        request_data = {
            'timestamp': datetime.now(),
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_time_ms': response_time_ms,
            'user_id': user_id
        }
        
        self.request_metrics.append(request_data)
        
        # Update counters
        self.increment_counter('total_requests')
        self.increment_counter(f'requests_{status_code}')
        
        if status_code >= 400:
            self.increment_counter('error_requests')
    
    def record_user_activity(self, user_id: str, activity: str, metadata: Dict = None):
        """Record user activity"""
        activity_data = {
            'timestamp': datetime.now(),
            'activity': activity,
            'metadata': metadata or {}
        }
        
        # Keep only last 100 activities per user
        if len(self.user_activity[user_id]) >= 100:
            self.user_activity[user_id].pop(0)
        
        self.user_activity[user_id].append(activity_data)
    
    def get_current_metrics(self) -> Dict:
        """Get current system metrics"""
        if not self.system_metrics:
            return {}
        
        latest = self.system_metrics[-1]
        return asdict(latest)
    
    def get_service_health_summary(self) -> Dict:
        """Get service health summary"""
        summary = {}
        for service_name, health in self.service_health.items():
            summary[service_name] = {
                'status': health.status,
                'last_check': health.last_check.isoformat(),
                'response_time_ms': health.response_time_ms,
                'error_message': health.error_message
            }
        return summary
    
    def get_performance_summary(self, minutes: int = 60) -> Dict:
        """Get performance summary for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        # Filter recent metrics
        recent_metrics = [m for m in self.system_metrics if m.timestamp > cutoff_time]
        recent_requests = [r for r in self.request_metrics if r['timestamp'] > cutoff_time]
        
        if not recent_metrics:
            return {}
        
        # Calculate averages
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        
        # Request statistics
        total_requests = len(recent_requests)
        error_requests = len([r for r in recent_requests if r['status_code'] >= 400])
        
        if recent_requests:
            avg_response_time = sum(r['response_time_ms'] for r in recent_requests) / len(recent_requests)
            max_response_time = max(r['response_time_ms'] for r in recent_requests)
        else:
            avg_response_time = 0
            max_response_time = 0
        
        return {
            'time_period_minutes': minutes,
            'system': {
                'avg_cpu_percent': round(avg_cpu, 2),
                'avg_memory_percent': round(avg_memory, 2),
                'current_connections': recent_metrics[-1].active_connections,
                'current_threads': recent_metrics[-1].active_threads
            },
            'requests': {
                'total_requests': total_requests,
                'error_requests': error_requests,
                'error_rate': round(error_requests / max(total_requests, 1), 4),
                'avg_response_time_ms': round(avg_response_time, 2),
                'max_response_time_ms': round(max_response_time, 2),
                'requests_per_minute': round(total_requests / minutes, 2)
            }
        }
    
    def get_user_activity_summary(self, hours: int = 24) -> Dict:
        """Get user activity summary"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        active_users = set()
        activity_counts = defaultdict(int)
        
        for user_id, activities in self.user_activity.items():
            recent_activities = [a for a in activities if a['timestamp'] > cutoff_time]
            
            if recent_activities:
                active_users.add(user_id)
                
                for activity in recent_activities:
                    activity_counts[activity['activity']] += 1
        
        return {
            'time_period_hours': hours,
            'active_users': len(active_users),
            'activity_breakdown': dict(activity_counts),
            'total_activities': sum(activity_counts.values())
        }
    
    def get_alerts(self) -> List[Dict]:
        """Get system alerts based on thresholds"""
        alerts = []
        
        if not self.system_metrics:
            return alerts
        
        latest = self.system_metrics[-1]
        
        # CPU alert
        if latest.cpu_percent > 80:
            alerts.append({
                'type': 'cpu_high',
                'severity': 'warning' if latest.cpu_percent < 90 else 'critical',
                'message': f'High CPU usage: {latest.cpu_percent:.1f}%',
                'timestamp': latest.timestamp.isoformat()
            })
        
        # Memory alert
        if latest.memory_percent > 85:
            alerts.append({
                'type': 'memory_high',
                'severity': 'warning' if latest.memory_percent < 95 else 'critical',
                'message': f'High memory usage: {latest.memory_percent:.1f}%',
                'timestamp': latest.timestamp.isoformat()
            })
        
        # Disk alert
        if latest.disk_percent > 90:
            alerts.append({
                'type': 'disk_high',
                'severity': 'critical',
                'message': f'High disk usage: {latest.disk_percent:.1f}%',
                'timestamp': latest.timestamp.isoformat()
            })
        
        # Service health alerts
        for service_name, health in self.service_health.items():
            if health.status == 'unhealthy':
                alerts.append({
                    'type': 'service_unhealthy',
                    'severity': 'critical',
                    'message': f'Service {service_name} is unhealthy: {health.error_message}',
                    'timestamp': health.last_check.isoformat()
                })
            elif health.status == 'degraded':
                alerts.append({
                    'type': 'service_degraded',
                    'severity': 'warning',
                    'message': f'Service {service_name} is degraded: {health.error_message}',
                    'timestamp': health.last_check.isoformat()
                })
        
        return alerts
    
    def export_metrics(self, filename: str = None) -> str:
        """Export metrics to JSON file"""
        if not filename:
            filename = f"metrics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'system_metrics': [asdict(m) for m in self.system_metrics],
            'service_health': self.get_service_health_summary(),
            'counters': dict(self.counters),
            'performance_summary': self.get_performance_summary(),
            'user_activity_summary': self.get_user_activity_summary()
        }
        
        # Convert datetime objects to strings for JSON serialization
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=serialize_datetime)
        
        logger.info(f"Metrics exported to {filename}")
        return filename
    
    def stop_collecting(self):
        """Stop metrics collection"""
        self.collecting = False
        if self.collector_thread.is_alive():
            self.collector_thread.join(timeout=5)
        logger.info("Metrics collection stopped")

# Global metrics collector
metrics_collector = MetricsCollector(collection_interval=30)

# Flask middleware for request monitoring
def monitor_requests(app):
    """Add request monitoring middleware to Flask app"""
    
    @app.before_request
    def before_request():
        from flask import g, request
        g.start_time = time.time()
        
        # Record user activity if authenticated
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                metrics_collector.record_user_activity(
                    current_user.get_id(),
                    'request',
                    {
                        'method': request.method,
                        'endpoint': request.endpoint,
                        'path': request.path
                    }
                )
        except:
            pass
    
    @app.after_request
    def after_request(response):
        from flask import g, request
        
        if hasattr(g, 'start_time'):
            response_time = (time.time() - g.start_time) * 1000
            
            # Get user ID if available
            user_id = None
            try:
                from flask_login import current_user
                if current_user and current_user.is_authenticated:
                    user_id = current_user.get_id()
            except:
                pass
            
            metrics_collector.record_request(
                method=request.method,
                endpoint=request.endpoint or request.path,
                status_code=response.status_code,
                response_time_ms=response_time,
                user_id=user_id
            )
        
        return response

# Health check endpoint function
def create_health_check_blueprint():
    """Create health check blueprint"""
    from flask import Blueprint, jsonify
    
    health_bp = Blueprint('health', __name__)
    
    @health_bp.route('/health')
    def health_check():
        """Basic health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        })
    
    @health_bp.route('/health/detailed')
    def detailed_health_check():
        """Detailed health check with service status"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': metrics_collector.get_service_health_summary(),
            'system': metrics_collector.get_current_metrics(),
            'alerts': metrics_collector.get_alerts()
        })
    
    @health_bp.route('/metrics')
    def metrics_endpoint():
        """Metrics endpoint for monitoring systems"""
        return jsonify({
            'system': metrics_collector.get_current_metrics(),
            'performance': metrics_collector.get_performance_summary(60),
            'user_activity': metrics_collector.get_user_activity_summary(24),
            'services': metrics_collector.get_service_health_summary()
        })
    
    return health_bp
