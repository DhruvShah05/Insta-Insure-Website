"""
WhatsApp Service for logging and tracking message status
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from supabase import create_client
from config import Config
from twilio.rest import Client as TwilioClient

# Set up logging
logger = logging.getLogger(__name__)

# Initialize clients
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
twilio_client = TwilioClient(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN) if (Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN) else None


class WhatsAppService:
    """Service for managing WhatsApp message logs and status tracking"""
    
    @staticmethod
    def log_message(
        message_sid: str,
        phone_number: str,
        message_type: str,
        message_content: str = None,
        media_url: str = None,
        policy_id: int = None,
        client_id: int = None,
        created_by: str = None,
        status: str = 'queued'
    ) -> bool:
        """Log a WhatsApp message to the database"""
        try:
            log_data = {
                'message_sid': message_sid,
                'phone_number': phone_number,
                'message_type': message_type,
                'message_content': message_content,
                'media_url': media_url,
                'policy_id': policy_id,
                'client_id': client_id,
                'status': status,
                'created_by': created_by,
                'sent_at': datetime.now().isoformat(),
                'last_status_check': datetime.now().isoformat()
            }
            
            result = supabase.table('whatsapp_logs').insert(log_data).execute()
            
            if result.data:
                logger.info(f"WhatsApp message logged: {message_sid}")
                return True
            else:
                logger.error(f"Failed to log WhatsApp message: {message_sid}")
                return False
                
        except Exception as e:
            logger.error(f"Error logging WhatsApp message {message_sid}: {e}")
            return False
    
    @staticmethod
    def get_message_status_from_twilio(message_sid: str) -> Dict:
        """Fetch current message status from Twilio API"""
        if not twilio_client:
            return {"error": "Twilio client not configured"}
        
        try:
            message = twilio_client.messages(message_sid).fetch()
            
            status_data = {
                'sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                'date_updated': message.date_updated.isoformat() if message.date_updated else None,
                'price': str(message.price) if message.price else None,
                'price_unit': message.price_unit,
                'direction': message.direction,
                'num_segments': message.num_segments
            }
            
            return status_data
            
        except Exception as e:
            logger.error(f"Error fetching message status from Twilio for {message_sid}: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def update_message_status(message_sid: str, status_data: Dict) -> bool:
        """Update message status in database"""
        try:
            update_data = {
                'status': status_data.get('status'),
                'error_code': status_data.get('error_code'),
                'error_message': status_data.get('error_message'),
                'last_status_check': datetime.now().isoformat()
            }
            
            # Set delivered_at timestamp if status is delivered
            if status_data.get('status') == 'delivered' and status_data.get('date_updated'):
                update_data['delivered_at'] = status_data.get('date_updated')
            
            # Set read_at timestamp if status is read
            if status_data.get('status') == 'read' and status_data.get('date_updated'):
                update_data['read_at'] = status_data.get('date_updated')
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            result = supabase.table('whatsapp_logs').update(update_data).eq('message_sid', message_sid).execute()
            
            if result.data:
                logger.info(f"Message status updated: {message_sid} -> {status_data.get('status')}")
                return True
            else:
                logger.error(f"Failed to update message status: {message_sid}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating message status {message_sid}: {e}")
            return False
    
    @staticmethod
    def refresh_message_status(message_sid: str) -> bool:
        """Refresh a single message status from Twilio"""
        status_data = WhatsAppService.get_message_status_from_twilio(message_sid)
        
        if 'error' in status_data:
            logger.error(f"Failed to fetch status for {message_sid}: {status_data['error']}")
            return False
        
        return WhatsAppService.update_message_status(message_sid, status_data)
    
    @staticmethod
    def refresh_all_pending_statuses() -> Tuple[int, int]:
        """Refresh status for all messages that are not in final state"""
        try:
            # Get messages that might need status updates (not delivered, read, failed, or undelivered)
            pending_statuses = ['queued', 'sending', 'sent']
            
            result = supabase.table('whatsapp_logs').select('message_sid').in_('status', pending_statuses).execute()
            
            if not result.data:
                return 0, 0
            
            total_messages = len(result.data)
            updated_count = 0
            
            for log in result.data:
                if WhatsAppService.refresh_message_status(log['message_sid']):
                    updated_count += 1
            
            logger.info(f"Refreshed {updated_count}/{total_messages} message statuses")
            return updated_count, total_messages
            
        except Exception as e:
            logger.error(f"Error refreshing all message statuses: {e}")
            return 0, 0
    
    @staticmethod
    def get_logs_with_filters(
        limit: int = 50,
        offset: int = 0,
        status_filter: str = None,
        message_type_filter: str = None,
        phone_filter: str = None,
        date_from: str = None,
        date_to: str = None
    ) -> Dict:
        """Get WhatsApp logs with optional filters"""
        try:
            query = supabase.table('whatsapp_logs').select(
                'log_id, message_sid, phone_number, message_type, status, '
                'error_code, error_message, sent_at, delivered_at, read_at, '
                'last_status_check, created_by, '
                'policies(policy_number, product_name, insurance_company), '
                'clients(name, email)'
            )
            
            # Apply filters
            if status_filter and status_filter != 'all':
                query = query.eq('status', status_filter)
            
            if message_type_filter and message_type_filter != 'all':
                query = query.eq('message_type', message_type_filter)
            
            if phone_filter:
                query = query.ilike('phone_number', f'%{phone_filter}%')
            
            if date_from:
                query = query.gte('sent_at', date_from)
            
            if date_to:
                query = query.lte('sent_at', date_to)
            
            # Order by sent_at desc and apply pagination
            query = query.order('sent_at', desc=True).range(offset, offset + limit - 1)
            
            result = query.execute()
            
            # Get total count for pagination
            count_query = supabase.table('whatsapp_logs').select('log_id', count='exact')
            
            if status_filter and status_filter != 'all':
                count_query = count_query.eq('status', status_filter)
            if message_type_filter and message_type_filter != 'all':
                count_query = count_query.eq('message_type', message_type_filter)
            if phone_filter:
                count_query = count_query.ilike('phone_number', f'%{phone_filter}%')
            if date_from:
                count_query = count_query.gte('sent_at', date_from)
            if date_to:
                count_query = count_query.lte('sent_at', date_to)
            
            count_result = count_query.execute()
            total_count = count_result.count if count_result.count is not None else 0
            
            return {
                'logs': result.data or [],
                'total_count': total_count,
                'has_next': offset + limit < total_count,
                'has_prev': offset > 0
            }
            
        except Exception as e:
            logger.error(f"Error fetching WhatsApp logs: {e}")
            return {
                'logs': [],
                'total_count': 0,
                'has_next': False,
                'has_prev': False
            }
    
    @staticmethod
    def get_status_summary() -> Dict:
        """Get summary statistics of message statuses"""
        try:
            result = supabase.table('whatsapp_logs').select('status').execute()
            
            if not result.data:
                return {
                    'total_messages': 0,
                    'status_counts': {},
                    'success_rate': 0
                }
            
            status_counts = {}
            for log in result.data:
                status = log['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate success rate
            total_messages = len(result.data)
            successful_messages = status_counts.get('delivered', 0) + status_counts.get('read', 0)
            success_rate = (successful_messages / total_messages * 100) if total_messages > 0 else 0
            
            return {
                'total_messages': total_messages,
                'status_counts': status_counts,
                'success_rate': round(success_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting status summary: {e}")
            return {
                'total_messages': 0,
                'status_counts': {},
                'success_rate': 0
            }
