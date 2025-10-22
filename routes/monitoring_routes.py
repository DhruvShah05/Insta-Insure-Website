"""
Monitoring Routes
API endpoints for system monitoring dashboard
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from auth_decorators import admin_required
from system_monitor import monitor
import logging

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/api/monitoring/metrics', methods=['GET'])
@login_required
@admin_required
def get_system_metrics():
    """Get current system metrics"""
    try:
        metrics = monitor.get_system_metrics()
        return jsonify({
            'success': True,
            'data': metrics
        })
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@monitoring_bp.route('/api/monitoring/active-users', methods=['GET'])
@login_required
@admin_required
def get_active_users():
    """Get list of currently active users"""
    try:
        active_users = monitor.get_active_users()
        concurrent_count = monitor.get_concurrent_users_count()
        
        return jsonify({
            'success': True,
            'data': {
                'active_users': active_users,
                'concurrent_count': concurrent_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting active users: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@monitoring_bp.route('/api/monitoring/full-status', methods=['GET'])
@login_required
@admin_required
def get_full_status():
    """Get complete system status including metrics, users, and history"""
    try:
        status = monitor.get_full_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"Error getting full status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@monitoring_bp.route('/api/monitoring/history', methods=['GET'])
@login_required
@admin_required
def get_metrics_history():
    """Get historical metrics for charts"""
    try:
        history = monitor.get_metrics_history()
        return jsonify({
            'success': True,
            'data': history
        })
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
