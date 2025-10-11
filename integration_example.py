"""
Integration Example: Multi-User Operations
Demonstrates how to use all scaling components together
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict
import time

# Import all scaling components
from database_pool import execute_query, batch_insert, DatabaseTransaction
from cache_manager import cache_manager, rate_limiter, session_manager
from task_queue import (
    send_whatsapp_async, send_email_async, send_batch_whatsapp_async, 
    send_batch_email_async, task_queue
)
from batch_file_operations import batch_file_manager, upload_multiple_policy_files
from whatsapp_bot_async import whatsapp_bot_async
from monitoring import metrics_collector

logger = logging.getLogger(__name__)

class MultiUserInsurancePortal:
    """
    Example integration of all multi-user scaling components
    Demonstrates real-world usage patterns
    """
    
    def __init__(self):
        self.active_sessions = {}
        
    def handle_bulk_policy_issuance(self, policies_data: List[Dict]) -> Dict:
        """
        Handle bulk policy issuance with all scaling features
        
        Example of processing multiple policies simultaneously:
        - Database operations with connection pooling
        - File uploads with batch processing
        - Notifications with async messaging
        - Caching for performance
        """
        logger.info(f"Processing bulk policy issuance for {len(policies_data)} policies")
        
        try:
            # Step 1: Validate and cache client data
            client_cache_tasks = []
            for policy_data in policies_data:
                client_phone = policy_data.get('client_phone')
                if client_phone:
                    # Check cache first
                    cached_client = cache_manager.get(f"client:{client_phone}", value_type='json')
                    if not cached_client:
                        # Load from database and cache
                        client_result = execute_query(
                            'clients', 'select', 
                            columns='*', 
                            filters={'phone_eq': client_phone}
                        )
                        if client_result.data:
                            cache_manager.set(f"client:{client_phone}", client_result.data[0], ttl=1800)
            
            # Step 2: Batch insert policies with transaction
            with DatabaseTransaction() as transaction:
                # Prepare policy records
                policy_records = []
                for policy_data in policies_data:
                    policy_record = {
                        'client_id': policy_data['client_id'],
                        'member_id': policy_data['member_id'],
                        'insurance_company': policy_data['insurance_company'],
                        'product_name': policy_data['product_name'],
                        'policy_number': policy_data['policy_number'],
                        'policy_from': policy_data['policy_from'],
                        'policy_to': policy_data['policy_to'],
                        'sum_insured': policy_data['sum_insured'],
                        'net_premium': policy_data['net_premium'],
                        'created_at': datetime.now().isoformat()
                    }
                    policy_records.append(policy_record)
                
                # Batch insert policies
                inserted_policies = batch_insert('policies', policy_records, batch_size=50)
                
                if not inserted_policies:
                    raise Exception("Failed to insert policies")
            
            # Step 3: Batch file uploads (if files provided)
            file_upload_batch_id = None
            if any('policy_file' in policy for policy in policies_data):
                upload_requests = []
                for i, policy_data in enumerate(policies_data):
                    if 'policy_file' in policy_data:
                        upload_requests.append({
                            'file': policy_data['policy_file'],
                            'filename': f"{policy_data['insurance_company']}_{policy_data['product_name']}.pdf",
                            'client_id': policy_data['client_id'],
                            'member_name': policy_data['member_name'],
                            'policy_id': inserted_policies[i]['policy_id'] if i < len(inserted_policies) else None,
                            'parent_folder_id': 'your_root_folder_id'
                        })
                
                if upload_requests:
                    file_upload_batch_id = upload_multiple_policy_files(
                        upload_requests, 
                        callback=self._file_upload_callback
                    )
            
            # Step 4: Send notifications asynchronously
            notification_tasks = []
            
            # Prepare WhatsApp notifications
            whatsapp_messages = []
            email_notifications = []
            
            for policy_data in policies_data:
                client_phone = policy_data.get('client_phone')
                client_email = policy_data.get('client_email')
                client_name = policy_data.get('client_name', 'Customer')
                
                if client_phone:
                    message = f"""🎉 *Policy Issued Successfully!*

Dear {client_name},

Your new insurance policy has been issued:

📋 *Policy Details:*
• Insurance: {policy_data['product_name']}
• Company: {policy_data['insurance_company']}
• Policy Number: {policy_data['policy_number']}
• Sum Insured: ₹{policy_data['sum_insured']}

Your policy document will be sent separately.

Thank you for choosing our services! 🙏"""
                    
                    whatsapp_messages.append({
                        'phone': client_phone,
                        'message': message
                    })
                
                if client_email:
                    email_notifications.append({
                        'email': client_email,
                        'subject': f"Policy Issued - {policy_data['product_name']}",
                        'body': f"""Dear {client_name},

Congratulations! Your insurance policy has been successfully issued.

Policy Details:
- Insurance Type: {policy_data['product_name']}
- Insurance Company: {policy_data['insurance_company']}
- Policy Number: {policy_data['policy_number']}
- Sum Insured: ₹{policy_data['sum_insured']}
- Premium: ₹{policy_data['net_premium']}

Your policy document is attached to this email.

Thank you for choosing our services.

Best regards,
Insta Insurance Consultancy""",
                        'customer_name': client_name
                    })
            
            # Send batch notifications
            whatsapp_task_id = None
            email_task_id = None
            
            if whatsapp_messages:
                whatsapp_task_id = send_batch_whatsapp_async(
                    whatsapp_messages, 
                    priority=1,
                    callback=self._notification_callback
                )
            
            if email_notifications:
                email_task_id = send_batch_email_async(
                    email_notifications,
                    priority=1,
                    callback=self._notification_callback
                )
            
            # Step 5: Update metrics and cache
            metrics_collector.increment_counter('bulk_policies_processed', len(policies_data))
            metrics_collector.record_user_activity(
                'system',
                'bulk_policy_issuance',
                {'policies_count': len(policies_data)}
            )
            
            # Cache policy counts for quick dashboard access
            total_policies_today = cache_manager.get('policies_today_count', 0, 'int')
            cache_manager.set('policies_today_count', total_policies_today + len(policies_data), ttl=86400)
            
            return {
                'success': True,
                'policies_processed': len(policies_data),
                'inserted_policies': len(inserted_policies),
                'file_upload_batch_id': file_upload_batch_id,
                'whatsapp_task_id': whatsapp_task_id,
                'email_task_id': email_task_id,
                'message': f'Successfully processed {len(policies_data)} policies'
            }
            
        except Exception as e:
            logger.error(f"Bulk policy issuance failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Bulk policy issuance failed'
            }
    
    def handle_bulk_renewal_reminders(self, renewal_data: List[Dict]) -> Dict:
        """
        Handle bulk renewal reminders with rate limiting and caching
        """
        logger.info(f"Processing bulk renewal reminders for {len(renewal_data)} policies")
        
        try:
            # Step 1: Check rate limits
            if rate_limiter.is_rate_limited('bulk_reminders', 100, 3600):  # Max 100 per hour
                return {
                    'success': False,
                    'error': 'Rate limit exceeded for bulk reminders',
                    'message': 'Please wait before sending more reminders'
                }
            
            # Step 2: Filter policies that haven't been reminded recently
            filtered_renewals = []
            for renewal in renewal_data:
                policy_id = renewal.get('policy_id')
                last_reminder_key = f"last_reminder:{policy_id}"
                
                last_reminder = cache_manager.get(last_reminder_key, value_type='int')
                current_time = int(time.time())
                
                # Only send reminder if last one was more than 24 hours ago
                if not last_reminder or (current_time - last_reminder) > 86400:
                    filtered_renewals.append(renewal)
                    cache_manager.set(last_reminder_key, current_time, ttl=86400)
            
            if not filtered_renewals:
                return {
                    'success': True,
                    'reminders_sent': 0,
                    'message': 'No policies eligible for reminders'
                }
            
            # Step 3: Use async WhatsApp bot for bulk reminders
            task_id = whatsapp_bot_async.send_bulk_reminders_async(filtered_renewals)
            
            # Step 4: Update database with reminder timestamps
            for renewal in filtered_renewals:
                execute_query(
                    'policies',
                    'update',
                    data={'last_reminder_sent': datetime.now().isoformat()},
                    filters={'policy_id': renewal['policy_id']}
                )
            
            # Step 5: Update metrics
            metrics_collector.increment_counter('bulk_reminders_sent', len(filtered_renewals))
            
            return {
                'success': True,
                'reminders_sent': len(filtered_renewals),
                'task_id': task_id,
                'message': f'Sent reminders for {len(filtered_renewals)} policies'
            }
            
        except Exception as e:
            logger.error(f"Bulk renewal reminders failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Bulk renewal reminders failed'
            }
    
    def handle_concurrent_user_requests(self, user_requests: List[Dict]) -> Dict:
        """
        Handle multiple user requests concurrently
        Demonstrates session management and concurrent processing
        """
        logger.info(f"Processing {len(user_requests)} concurrent user requests")
        
        results = []
        
        for request in user_requests:
            user_id = request.get('user_id')
            request_type = request.get('type')
            
            try:
                # Step 1: Manage user session
                session_data = session_manager.get_session(user_id)
                if not session_data:
                    # Create new session
                    session_manager.create_session(
                        user_id,
                        {'user_id': user_id, 'login_time': datetime.now().isoformat()}
                    )
                else:
                    # Extend existing session
                    session_manager.extend_session(user_id)
                
                # Step 2: Process request based on type
                if request_type == 'get_policies':
                    result = self._handle_get_policies_request(user_id, request)
                elif request_type == 'send_whatsapp':
                    result = self._handle_whatsapp_request(user_id, request)
                elif request_type == 'upload_file':
                    result = self._handle_file_upload_request(user_id, request)
                else:
                    result = {'success': False, 'error': f'Unknown request type: {request_type}'}
                
                results.append({
                    'user_id': user_id,
                    'request_type': request_type,
                    **result
                })
                
                # Record user activity
                metrics_collector.record_user_activity(
                    user_id, 
                    request_type, 
                    {'success': result.get('success', False)}
                )
                
            except Exception as e:
                logger.error(f"Request failed for user {user_id}: {e}")
                results.append({
                    'user_id': user_id,
                    'request_type': request_type,
                    'success': False,
                    'error': str(e)
                })
        
        successful_requests = sum(1 for r in results if r.get('success'))
        
        return {
            'total_requests': len(user_requests),
            'successful_requests': successful_requests,
            'failed_requests': len(user_requests) - successful_requests,
            'results': results
        }
    
    def _handle_get_policies_request(self, user_id: str, request: Dict) -> Dict:
        """Handle get policies request with caching"""
        try:
            # Check cache first
            cache_key = f"user_policies:{user_id}"
            cached_policies = cache_manager.get(cache_key, value_type='json')
            
            if cached_policies:
                return {
                    'success': True,
                    'policies': cached_policies,
                    'source': 'cache'
                }
            
            # Load from database
            policies_result = execute_query(
                'policies',
                'select',
                columns='*',
                filters={'client_id_eq': request.get('client_id')}
            )
            
            policies = policies_result.data if policies_result.data else []
            
            # Cache for future requests
            cache_manager.set(cache_key, policies, ttl=600)  # 10 minutes
            
            return {
                'success': True,
                'policies': policies,
                'source': 'database'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_whatsapp_request(self, user_id: str, request: Dict) -> Dict:
        """Handle WhatsApp message request"""
        try:
            phone = request.get('phone')
            message = request.get('message')
            
            if not phone or not message:
                return {'success': False, 'error': 'Phone and message required'}
            
            # Send asynchronously
            task_id = send_whatsapp_async(phone, message, priority=2)
            
            return {
                'success': True,
                'task_id': task_id,
                'message': 'WhatsApp message queued'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_file_upload_request(self, user_id: str, request: Dict) -> Dict:
        """Handle file upload request"""
        try:
            file_data = request.get('file')
            client_id = request.get('client_id')
            member_name = request.get('member_name')
            
            if not all([file_data, client_id, member_name]):
                return {'success': False, 'error': 'File, client_id, and member_name required'}
            
            # Use batch file manager for single file
            upload_requests = [{
                'file': file_data,
                'filename': request.get('filename', 'uploaded_file.pdf'),
                'client_id': client_id,
                'member_name': member_name,
                'policy_id': request.get('policy_id'),
                'parent_folder_id': 'your_root_folder_id'
            }]
            
            batch_id = upload_multiple_policy_files(upload_requests)
            
            return {
                'success': True,
                'batch_id': batch_id,
                'message': 'File upload queued'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _file_upload_callback(self, batch_id: str, success: bool, results):
        """Callback for file upload completion"""
        if success:
            logger.info(f"File upload batch {batch_id} completed successfully")
            metrics_collector.increment_counter('file_uploads_completed')
        else:
            logger.error(f"File upload batch {batch_id} failed")
            metrics_collector.increment_counter('file_uploads_failed')
    
    def _notification_callback(self, task, success: bool, error: str = None):
        """Callback for notification completion"""
        if success:
            logger.info(f"Notification task {task.task_id} completed successfully")
            metrics_collector.increment_counter('notifications_sent')
        else:
            logger.error(f"Notification task {task.task_id} failed: {error}")
            metrics_collector.increment_counter('notifications_failed')
    
    def get_system_health(self) -> Dict:
        """Get comprehensive system health status"""
        return {
            'database': {
                'pool_size': 15,  # From database_pool configuration
                'active_connections': 'Available via health check'
            },
            'cache': {
                'type': 'Redis' if hasattr(cache_manager, 'redis_client') and cache_manager.redis_client else 'Memory',
                'status': 'Available via health check'
            },
            'task_queue': task_queue.get_queue_stats(),
            'file_manager': batch_file_manager.get_stats(),
            'metrics': {
                'performance': metrics_collector.get_performance_summary(60),
                'user_activity': metrics_collector.get_user_activity_summary(24),
                'alerts': metrics_collector.get_alerts()
            }
        }

# Example usage
def example_usage():
    """Example of how to use the multi-user portal"""
    
    portal = MultiUserInsurancePortal()
    
    # Example 1: Bulk policy issuance
    policies_data = [
        {
            'client_id': 'C001',
            'member_id': 'M001',
            'client_phone': '+919876543210',
            'client_email': 'customer1@example.com',
            'client_name': 'John Doe',
            'insurance_company': 'HDFC ERGO',
            'product_name': 'Health Insurance',
            'policy_number': 'POL001',
            'policy_from': '2024-01-01',
            'policy_to': '2025-01-01',
            'sum_insured': '500000',
            'net_premium': '15000',
            'member_name': 'John Doe'
        },
        # Add more policies...
    ]
    
    result = portal.handle_bulk_policy_issuance(policies_data)
    print(f"Bulk policy issuance result: {result}")
    
    # Example 2: Concurrent user requests
    user_requests = [
        {
            'user_id': 'user1',
            'type': 'get_policies',
            'client_id': 'C001'
        },
        {
            'user_id': 'user2',
            'type': 'send_whatsapp',
            'phone': '+919876543210',
            'message': 'Hello from insurance portal!'
        }
    ]
    
    result = portal.handle_concurrent_user_requests(user_requests)
    print(f"Concurrent requests result: {result}")
    
    # Example 3: System health check
    health = portal.get_system_health()
    print(f"System health: {health}")

if __name__ == "__main__":
    example_usage()
