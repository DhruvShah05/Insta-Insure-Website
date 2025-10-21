"""
Excel Management Routes for Insurance Portal
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
import logging
import os
from datetime import datetime
# Try to import excel sync service, but don't fail if dependencies are missing
excel_sync = None
try:
    from excel_sync_service import get_excel_sync, initialize_excel_sync
    excel_sync = get_excel_sync()
    if excel_sync is None:
        excel_sync = initialize_excel_sync()
except ImportError as e:
    # Excel dependencies not installed yet
    import logging
    logging.getLogger(__name__).warning(f"Excel sync service not available: {e}")
    excel_sync = None

logger = logging.getLogger(__name__)
excel_bp = Blueprint("excel", __name__)


@excel_bp.route('/excel')
@login_required
def excel_dashboard():
    """Excel management dashboard"""
    try:
        if excel_sync is None:
            # Show setup page when dependencies are missing
            return render_template('excel_setup.html')
            
        # Get file information
        file_info = excel_sync.get_drive_file_info()
        shareable_link = excel_sync.get_shareable_link()
        
        return render_template('excel_dashboard.html', 
                             file_info=file_info,
                             shareable_link=shareable_link)
    except Exception as e:
        logger.error(f"Error loading Excel dashboard: {e}")
        # Show setup page on any error
        return render_template('excel_setup.html')


@excel_bp.route('/api/excel/export', methods=['POST'])
@login_required
def export_to_excel():
    """Export current database data to Excel in Google Drive"""
    try:
        if excel_sync is None:
            return jsonify({
                'success': False,
                'message': 'Excel service is not available. Please install required dependencies.'
            }), 500
            
        logger.info(f"Excel export requested by user: {current_user.email}")
        
        # Trigger manual sync
        excel_sync.manual_sync()
        success, message = True, "Excel file updated successfully"
        
        if success:
            logger.info(f"Excel export successful for user: {current_user.email}")
            return jsonify({
                'success': True,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"Excel export failed for user {current_user.email}: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 500
            
    except Exception as e:
        logger.error(f"Excel export error for user {current_user.email}: {e}")
        return jsonify({
            'success': False,
            'message': f"Export failed: {str(e)}"
        }), 500


@excel_bp.route('/api/excel/download', methods=['POST'])
@login_required
def download_excel():
    """Download Excel file (local file available)"""
    try:
        if excel_sync is None:
            return jsonify({
                'success': False,
                'message': 'Excel service is not available. Please install required dependencies.'
            }), 500
            
        logger.info(f"Excel download requested by user: {current_user.email}")
        
        # Check if local file exists
        if os.path.exists(excel_sync.local_excel_path):
            logger.info(f"Excel download successful for user: {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Excel file is available for download',
                'local_path': excel_sync.local_excel_path,
                'timestamp': datetime.now().isoformat()
            })
        else:
            # Trigger sync to create file
            excel_sync.manual_sync()
            return jsonify({
                'success': True,
                'message': 'Excel file created and available for download',
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Excel download error for user {current_user.email}: {e}")
        return jsonify({
            'success': False,
            'message': f"Download failed: {str(e)}"
        }), 500


@excel_bp.route('/api/excel/info', methods=['GET'])
@login_required
def get_excel_info():
    """Get Excel file information"""
    try:
        if excel_sync is None:
            return jsonify({
                'success': False,
                'message': 'Excel service is not available. Please install required dependencies.'
            }), 500
            
        file_info = excel_sync.get_drive_file_info()
        shareable_link = excel_sync.get_shareable_link()
        
        if file_info:
            return jsonify({
                'success': True,
                'file_info': file_info,
                'shareable_link': shareable_link,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': "Could not retrieve file information"
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting Excel info: {e}")
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 500


@excel_bp.route('/api/excel/refresh', methods=['POST'])
@login_required
def refresh_excel_data():
    """Refresh Excel file with latest database data"""
    try:
        logger.info(f"Excel refresh requested by user: {current_user.email}")
        
        # Trigger manual sync
        excel_sync.manual_sync()
        
        # Get updated file info
        file_info = excel_sync.get_drive_file_info()
        shareable_link = excel_sync.get_shareable_link()
        
        success = True
        
        if success:
            logger.info(f"Excel refresh successful for user: {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Excel file refreshed with latest data',
                'file_info': file_info,
                'shareable_link': shareable_link,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"Excel refresh failed for user {current_user.email}: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 500
            
    except Exception as e:
        logger.error(f"Excel refresh error for user {current_user.email}: {e}")
        return jsonify({
            'success': False,
            'message': f"Refresh failed: {str(e)}"
        }), 500


@excel_bp.route('/api/excel/policy-history-report', methods=['POST'])
@login_required
def generate_policy_history_report():
    """Generate a detailed policy history Excel report"""
    try:
        if excel_sync is None:
            return jsonify({
                'success': False,
                'message': 'Excel service is not available. Please install required dependencies.'
            }), 500
        
        # Get filter parameters from request
        data = request.get_json() or {}
        policy_id = data.get('policy_id')
        client_id = data.get('client_id')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        logger.info(f"Policy history report requested by user: {current_user.email}")
        logger.info(f"Filters - Policy ID: {policy_id}, Client ID: {client_id}, Date range: {date_from} to {date_to}")
        
        # Generate the report
        report_path = excel_sync.export_policy_history_report(
            policy_id=policy_id,
            client_id=client_id,
            date_from=date_from,
            date_to=date_to
        )
        
        if os.path.exists(report_path):
            logger.info(f"Policy history report generated successfully for user: {current_user.email}")
            return jsonify({
                'success': True,
                'message': 'Policy history report generated successfully',
                'report_path': report_path,
                'filename': os.path.basename(report_path),
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"Policy history report file not found: {report_path}")
            return jsonify({
                'success': False,
                'message': 'Report generation failed - file not created'
            }), 500
            
    except Exception as e:
        logger.error(f"Policy history report error for user {current_user.email}: {e}")
        return jsonify({
            'success': False,
            'message': f"Report generation failed: {str(e)}"
        }), 500


@excel_bp.route('/api/excel/download-history-report/<filename>')
@login_required
def download_history_report(filename):
    """Download a generated policy history report"""
    try:
        # Security check - ensure filename is safe
        if not filename.endswith('.xlsx') or '..' in filename or '/' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400
        
        report_path = os.path.join(os.getcwd(), filename)
        
        if not os.path.exists(report_path):
            return jsonify({
                'success': False,
                'message': 'Report file not found'
            }), 404
        
        logger.info(f"Policy history report download: {filename} by user: {current_user.email}")
        
        from flask import send_file
        return send_file(
            report_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Policy history report download error: {e}")
        return jsonify({
            'success': False,
            'message': f"Download failed: {str(e)}"
        }), 500
