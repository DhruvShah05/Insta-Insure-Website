"""
WhatsApp Logs Routes
Routes for viewing and managing WhatsApp message logs
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from whatsapp_service import WhatsAppService
from renewal_file_cleanup import RenewalFileCleanup
from realtime_cleanup_service import get_realtime_cleanup_service, start_realtime_cleanup_service, stop_realtime_cleanup_service
from datetime import datetime
import math

whatsapp_logs_bp = Blueprint("whatsapp_logs", __name__)


@whatsapp_logs_bp.app_template_filter('format_datetime')
def format_datetime(value):
    """Format datetime for display"""
    if not value:
        return '-'
    
    try:
        if isinstance(value, str):
            # Parse ISO format datetime
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = value
        
        # Format as DD/MM/YYYY HH:MM
        return dt.strftime('%d/%m/%Y %H:%M')
    except:
        return str(value) if value else '-'


@whatsapp_logs_bp.route('/whatsapp_logs')
@login_required
def whatsapp_logs():
    """Display WhatsApp message logs with filters and pagination"""
    try:
        # Get filter parameters
        status_filter = request.args.get('status_filter', 'all')
        message_type_filter = request.args.get('message_type_filter', 'all')
        phone_filter = request.args.get('phone_filter', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Pagination parameters
        page = int(request.args.get('page', 1))
        per_page = 25
        offset = (page - 1) * per_page
        
        # Get logs with filters
        result = WhatsAppService.get_logs_with_filters(
            limit=per_page,
            offset=offset,
            status_filter=status_filter if status_filter != 'all' else None,
            message_type_filter=message_type_filter if message_type_filter != 'all' else None,
            phone_filter=phone_filter if phone_filter else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None
        )
        
        logs = result['logs']
        total_count = result['total_count']
        has_next = result['has_next']
        has_prev = result['has_prev']
        
        # Calculate pagination info
        total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
        
        # Get status summary
        summary = WhatsAppService.get_status_summary()
        
        return render_template(
            'whatsapp_logs.html',
            logs=logs,
            summary=summary,
            page=page,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            total_count=total_count
        )
        
    except Exception as e:
        print(f"Error loading WhatsApp logs: {e}")
        return render_template(
            'whatsapp_logs.html',
            logs=[],
            summary={},
            page=1,
            total_pages=1,
            has_next=False,
            has_prev=False,
            total_count=0,
            error=str(e)
        )


@whatsapp_logs_bp.route('/api/whatsapp/refresh_all_statuses', methods=['POST'])
@login_required
def refresh_all_statuses():
    """Refresh status for all pending messages"""
    try:
        updated_count, total_count = WhatsAppService.refresh_all_pending_statuses()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'total_count': total_count,
            'message': f'Updated {updated_count} out of {total_count} messages'
        })
        
    except Exception as e:
        print(f"Error refreshing all statuses: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/refresh_status', methods=['POST'])
@login_required
def refresh_single_status():
    """Refresh status for a single message"""
    try:
        data = request.get_json()
        message_sid = data.get('message_sid')
        
        if not message_sid:
            return jsonify({
                'success': False,
                'message': 'Message SID is required'
            }), 400
        
        success = WhatsAppService.refresh_message_status(message_sid)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Status updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update status'
            }), 500
            
    except Exception as e:
        print(f"Error refreshing single status: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/message_details/<message_sid>')
@login_required
def get_message_details(message_sid):
    """Get detailed information about a specific message from Twilio"""
    try:
        status_data = WhatsAppService.get_message_status_from_twilio(message_sid)
        
        if 'error' in status_data:
            return jsonify({
                'success': False,
                'message': status_data['error']
            }), 500
        
        return jsonify({
            'success': True,
            'message': status_data
        })
        
    except Exception as e:
        print(f"Error getting message details: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/stats')
@login_required
def get_whatsapp_stats():
    """Get WhatsApp statistics for dashboard widgets"""
    try:
        summary = WhatsAppService.get_status_summary()
        
        return jsonify({
            'success': True,
            'stats': summary
        })
        
    except Exception as e:
        print(f"Error getting WhatsApp stats: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/cleanup_files', methods=['POST'])
@login_required
def cleanup_renewal_files():
    """Clean up renewal files based on WhatsApp delivery status"""
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        
        cleanup_service = RenewalFileCleanup()
        results = cleanup_service.run_full_cleanup(dry_run=dry_run)
        
        return jsonify({
            'success': True,
            'results': results,
            'message': results['summary']
        })
        
    except Exception as e:
        print(f"Error during file cleanup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/cleanup_preview')
@login_required
def preview_cleanup():
    """Preview which files would be cleaned up without actually deleting them"""
    try:
        cleanup_service = RenewalFileCleanup()
        
        # Get files ready for cleanup
        files_to_cleanup = cleanup_service.get_files_ready_for_cleanup()
        
        # Get orphaned files info
        orphaned_results = cleanup_service.cleanup_orphaned_files(dry_run=True)
        
        return jsonify({
            'success': True,
            'preview': {
                'status_based_files': files_to_cleanup,
                'orphaned_files': orphaned_results['deleted_orphaned'],
                'total_files': len(files_to_cleanup) + len(orphaned_results['deleted_orphaned']),
                'estimated_size_freed': sum(f.get('size', 0) for f in files_to_cleanup) + orphaned_results['total_size_freed']
            }
        })
        
    except Exception as e:
        print(f"Error previewing cleanup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/realtime_service_status')
@login_required
def get_realtime_service_status():
    """Get status of the real-time cleanup service"""
    try:
        service = get_realtime_cleanup_service()
        
        if service:
            status = service.get_status()
            return jsonify({
                'success': True,
                'service_running': status['running'],
                'check_interval_seconds': status['check_interval_seconds'],
                'thread_alive': status['thread_alive']
            })
        else:
            return jsonify({
                'success': True,
                'service_running': False,
                'check_interval_seconds': 0,
                'thread_alive': False
            })
        
    except Exception as e:
        print(f"Error getting service status: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/start_realtime_service', methods=['POST'])
@login_required
def start_realtime_service():
    """Start the real-time cleanup service"""
    try:
        data = request.get_json() or {}
        interval = data.get('interval_seconds', 60)
        
        service = start_realtime_cleanup_service(check_interval_seconds=interval)
        
        return jsonify({
            'success': True,
            'message': f'Real-time cleanup service started (checking every {interval} seconds)',
            'service_running': True
        })
        
    except Exception as e:
        print(f"Error starting real-time service: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_logs_bp.route('/api/whatsapp/stop_realtime_service', methods=['POST'])
@login_required
def stop_realtime_service_api():
    """Stop the real-time cleanup service"""
    try:
        stop_realtime_cleanup_service()
        
        return jsonify({
            'success': True,
            'message': 'Real-time cleanup service stopped',
            'service_running': False
        })
        
    except Exception as e:
        print(f"Error stopping real-time service: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
