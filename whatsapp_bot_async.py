"""
Async WhatsApp Bot for Multi-User Concurrent Operations
Handles multiple WhatsApp messages simultaneously using task queue system
"""
from flask import request, jsonify
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import existing WhatsApp functionality
from whatsapp_bot import (
    send_whatsapp_message, send_content_template_message, 
    get_customer_policies, normalize_phone, format_whatsapp_address,
    is_duplicate_message, processed_messages, MESSAGE_EXPIRY,
    user_sessions, send_policy_document_whatsapp
)

# Import task queue system
from task_queue import (
    task_queue, send_whatsapp_async, send_policy_async, 
    send_batch_whatsapp_async, Task
)

# Import database pool
from database_pool import execute_query, get_client_by_phone, batch_insert

logger = logging.getLogger(__name__)

class WhatsAppBotAsync:
    """Async WhatsApp Bot for handling concurrent users"""
    
    def __init__(self):
        self.active_sessions = {}  # Track active user sessions
        self.session_lock = threading.Lock()
        self.greeting_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="WhatsAppGreeting")
        
    def handle_greeting_async(self, phone: str) -> str:
        """Handle greeting message asynchronously"""
        try:
            # Check for duplicate processing
            message_id = f"greeting_{phone}_{int(time.time())}"
            if is_duplicate_message(message_id):
                logger.info(f"Duplicate greeting ignored for {phone}")
                return "duplicate"
            
            # Submit greeting task to executor
            future = self.greeting_executor.submit(self._process_greeting, phone)
            
            # Don't wait for completion, return immediately
            logger.info(f"Greeting task queued for {phone}")
            return "queued"
            
        except Exception as e:
            logger.error(f"Error queuing greeting for {phone}: {e}")
            return "error"
    
    def _process_greeting(self, phone: str) -> bool:
        """Process greeting and send policies"""
        try:
            # Get customer and policies using database pool
            client_result = get_client_by_phone(phone)
            if not client_result or not client_result.data:
                # Send welcome message for new users
                welcome_msg = """👋 Welcome to Insta Insurance Consultancy!

We don't have your details in our system yet. Please contact our team to get started with your insurance needs.

📞 Contact us for assistance with:
• Health Insurance
• Motor Insurance  
• Life Insurance
• General Insurance

Thank you for your interest!"""
                
                send_whatsapp_async(phone, welcome_msg, priority=2)
                return True
            
            client = client_result.data
            client_id = client['client_id']
            
            # Get policies for client
            policies_result = execute_query(
                'policies',
                'select',
                columns='*',
                filters={'client_id_eq': client_id}
            )
            
            policies = policies_result.data if policies_result.data else []
            
            if not policies:
                # No policies found
                no_policies_msg = f"""Hello {client['name']}! 👋

We don't have any active policies for you in our system yet.

Please contact our team if you'd like to:
• Purchase new insurance
• Check policy status
• Get insurance quotes

Thank you for choosing Insta Insurance Consultancy!"""
                
                send_whatsapp_async(phone, no_policies_msg, priority=2)
                return True
            
            # Send greeting message
            greeting_msg = f"""Hello {client['name']}! 👋

Welcome to Insta Insurance Consultancy Portal. I'll send you all your policy documents right away.

📄 Found {len(policies)} active policies for you."""
            
            send_whatsapp_async(phone, greeting_msg, priority=1)
            
            # Send each policy document asynchronously
            for i, policy in enumerate(policies):
                # Small delay between policies to avoid rate limiting
                time.sleep(1 + i * 0.5)
                
                send_policy_async(
                    phone=phone,
                    policy=policy,
                    send_email=False,  # Skip email for greeting response
                    priority=1
                )
            
            # Send final message
            final_msg = f"""✅ All {len(policies)} policy documents have been sent!

You can reply with *HI* anytime to receive your documents again.

For any assistance, please contact our team.

Thank you for choosing Insta Insurance Consultancy! 🙏"""
            
            # Delay final message to ensure it comes after all policies
            time.sleep(len(policies) * 0.5 + 2)
            send_whatsapp_async(phone, final_msg, priority=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing greeting for {phone}: {e}")
            
            # Send error message to user
            error_msg = """Sorry, we're experiencing technical difficulties. Please try again in a few minutes or contact our support team.

Thank you for your patience! 🙏"""
            
            send_whatsapp_async(phone, error_msg, priority=1)
            return False
    
    def send_bulk_reminders_async(self, reminder_data: List[Dict]) -> str:
        """Send renewal reminders to multiple customers asynchronously"""
        try:
            # Prepare batch WhatsApp messages
            whatsapp_messages = []
            
            for reminder in reminder_data:
                phone = reminder.get('phone')
                customer_name = reminder.get('customer_name', 'Customer')
                policy = reminder.get('policy', {})
                
                if not phone or not policy:
                    continue
                
                # Format expiry date
                expiry_date = policy.get('policy_to', 'N/A')
                if expiry_date and expiry_date != 'N/A':
                    try:
                        if isinstance(expiry_date, str) and '-' in expiry_date:
                            parts = expiry_date.split('-')
                            if len(parts) == 3 and len(parts[0]) == 4:
                                expiry_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    except:
                        pass
                
                # Create reminder message
                reminder_message = f"""🔔 *Policy Renewal Reminder*

Dear {customer_name},

Your insurance policy is expiring soon:

📋 *Policy Details:*
• Insurance: {policy.get('product_name', 'Insurance Policy')}
• Company: {policy.get('insurance_company', '')}
• Policy Number: {policy.get('policy_number', 'N/A')}
• Expiry Date: {expiry_date}

Please contact us to renew your policy and avoid any coverage gaps.

📞 Contact our team for renewal assistance.

Thank you!
- Insta Insurance Consultancy"""
                
                whatsapp_messages.append({
                    'phone': phone,
                    'message': reminder_message
                })
            
            if whatsapp_messages:
                # Send batch WhatsApp messages
                task_id = send_batch_whatsapp_async(
                    messages=whatsapp_messages,
                    priority=2,
                    callback=self._bulk_reminder_callback
                )
                
                logger.info(f"Bulk reminder task queued: {task_id} for {len(whatsapp_messages)} customers")
                return task_id
            else:
                logger.warning("No valid reminder data provided")
                return "no_data"
                
        except Exception as e:
            logger.error(f"Error queuing bulk reminders: {e}")
            return "error"
    
    def _bulk_reminder_callback(self, task: Task, success: bool, error: str = None):
        """Callback for bulk reminder completion"""
        if success:
            logger.info(f"Bulk reminder task {task.task_id} completed successfully")
        else:
            logger.error(f"Bulk reminder task {task.task_id} failed: {error}")
    
    def send_bulk_policy_notifications_async(self, notification_data: List[Dict]) -> str:
        """Send policy issued notifications to multiple customers asynchronously"""
        try:
            # Process notifications in batches
            batch_size = 10
            task_ids = []
            
            for i in range(0, len(notification_data), batch_size):
                batch = notification_data[i:i + batch_size]
                
                # Prepare batch messages
                whatsapp_messages = []
                
                for notification in batch:
                    phone = notification.get('phone')
                    customer_name = notification.get('customer_name', 'Customer')
                    policy = notification.get('policy', {})
                    
                    if not phone or not policy:
                        continue
                    
                    # Format dates
                    coverage_start = policy.get('policy_from', 'N/A')
                    expiry_date = policy.get('policy_to', 'N/A')
                    
                    for date_field in [coverage_start, expiry_date]:
                        if date_field and date_field != 'N/A':
                            try:
                                if isinstance(date_field, str) and '-' in date_field:
                                    parts = date_field.split('-')
                                    if len(parts) == 3 and len(parts[0]) == 4:
                                        date_field = f"{parts[2]}/{parts[1]}/{parts[0]}"
                            except:
                                pass
                    
                    # Create notification message
                    notification_message = f"""🎉 *Policy Issued Successfully!*

Dear {customer_name},

Congratulations! Your new insurance policy has been issued.

📋 *Policy Details:*
• Insurance: {policy.get('product_name', 'Insurance Policy')}
• Company: {policy.get('insurance_company', '')}
• Policy Number: {policy.get('policy_number', 'N/A')}
• Coverage Start: {coverage_start}
• Expiry Date: {expiry_date}

Your policy document will be sent separately.

Reply with *HI* anytime to view all your policies.

Thank you for choosing Insta Insurance Consultancy! 🙏"""
                    
                    whatsapp_messages.append({
                        'phone': phone,
                        'message': notification_message
                    })
                
                if whatsapp_messages:
                    # Send batch
                    task_id = send_batch_whatsapp_async(
                        messages=whatsapp_messages,
                        priority=1,
                        callback=self._bulk_notification_callback
                    )
                    task_ids.append(task_id)
                    
                    # Small delay between batches
                    time.sleep(2)
            
            logger.info(f"Bulk notification tasks queued: {len(task_ids)} batches for {len(notification_data)} customers")
            return f"queued_{len(task_ids)}_batches"
            
        except Exception as e:
            logger.error(f"Error queuing bulk notifications: {e}")
            return "error"
    
    def _bulk_notification_callback(self, task: Task, success: bool, error: str = None):
        """Callback for bulk notification completion"""
        if success:
            logger.info(f"Bulk notification task {task.task_id} completed successfully")
        else:
            logger.error(f"Bulk notification task {task.task_id} failed: {error}")
    
    def get_session_info(self, phone: str) -> Dict:
        """Get session information for a user"""
        with self.session_lock:
            return self.active_sessions.get(phone, {})
    
    def update_session(self, phone: str, data: Dict):
        """Update session data for a user"""
        with self.session_lock:
            if phone not in self.active_sessions:
                self.active_sessions[phone] = {}
            self.active_sessions[phone].update(data)
            self.active_sessions[phone]['last_activity'] = datetime.now()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old sessions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.session_lock:
            expired_sessions = [
                phone for phone, session in self.active_sessions.items()
                if session.get('last_activity', datetime.min) < cutoff_time
            ]
            
            for phone in expired_sessions:
                del self.active_sessions[phone]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

# Global async WhatsApp bot instance
whatsapp_bot_async = WhatsAppBotAsync()

# Enhanced webhook handler for concurrent processing
def handle_whatsapp_webhook_async(webhook_data):
    """Handle WhatsApp webhook with async processing"""
    try:
        # Extract message data
        if 'messages' not in webhook_data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
            return jsonify({'status': 'no_messages'}), 200
        
        messages = webhook_data['entry'][0]['changes'][0]['value']['messages']
        
        # Process each message asynchronously
        for message in messages:
            message_id = message.get('id')
            from_number = message.get('from')
            message_type = message.get('type')
            
            # Check for duplicate
            if is_duplicate_message(message_id):
                continue
            
            # Handle text messages
            if message_type == 'text':
                text_body = message.get('text', {}).get('body', '').strip().upper()
                
                if text_body in ['HI', 'HELLO', 'START', 'POLICIES']:
                    # Handle greeting asynchronously
                    whatsapp_bot_async.handle_greeting_async(from_number)
                else:
                    # Handle other messages
                    response_msg = """Thank you for your message! 

For policy documents, reply with *HI*
For assistance, please contact our team.

- Insta Insurance Consultancy"""
                    
                    send_whatsapp_async(from_number, response_msg, priority=3)
        
        return jsonify({'status': 'processed'}), 200
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Utility functions for multi-user operations
def send_reminders_to_multiple_customers(customers_data: List[Dict]) -> Dict:
    """Send renewal reminders to multiple customers"""
    try:
        task_id = whatsapp_bot_async.send_bulk_reminders_async(customers_data)
        
        return {
            'success': True,
            'task_id': task_id,
            'message': f'Bulk reminders queued for {len(customers_data)} customers'
        }
    except Exception as e:
        logger.error(f"Error sending bulk reminders: {e}")
        return {
            'success': False,
            'message': str(e)
        }

def notify_multiple_policy_issued(notifications_data: List[Dict]) -> Dict:
    """Notify multiple customers about policy issuance"""
    try:
        result = whatsapp_bot_async.send_bulk_policy_notifications_async(notifications_data)
        
        return {
            'success': True,
            'result': result,
            'message': f'Bulk notifications queued for {len(notifications_data)} customers'
        }
    except Exception as e:
        logger.error(f"Error sending bulk notifications: {e}")
        return {
            'success': False,
            'message': str(e)
        }

def get_queue_status() -> Dict:
    """Get current task queue status"""
    return task_queue.get_queue_stats()
