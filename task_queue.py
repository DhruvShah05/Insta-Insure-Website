"""
Task Queue System for Multi-User Concurrent Operations
Handles WhatsApp messaging, email sending, and file operations asynchronously
"""
import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Task definition for queue processing"""
    task_id: str
    task_type: str  # 'whatsapp', 'email', 'file_upload', 'policy_send'
    priority: int  # 1=high, 2=medium, 3=low
    data: Dict[Any, Any]
    callback: Optional[Callable] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class TaskQueue:
    """Thread-safe task queue with priority handling and retry logic"""
    
    def __init__(self, max_workers=None, max_queue_size=None):
        # Use optimized config if available
        if os.getenv('USE_OPTIMIZED_CONFIG'):
            from config_optimized import OptimizedConfig
            max_workers = max_workers or OptimizedConfig.TASK_QUEUE_MAX_WORKERS
            max_queue_size = max_queue_size or OptimizedConfig.TASK_QUEUE_MAX_SIZE
        else:
            max_workers = max_workers or 10
            max_queue_size = max_queue_size or 1000
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        # Priority queues (1=high, 2=medium, 3=low)
        self.queues = {
            1: Queue(maxsize=max_queue_size),
            2: Queue(maxsize=max_queue_size),
            3: Queue(maxsize=max_queue_size)
        }
        
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="TaskWorker")
        self.running = True
        self.workers = []
        self.task_results = {}
        self.failed_tasks = Queue()
        
        # Statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_workers': 0
        }
        
        # Start worker threads
        self._start_workers()
        
        logger.info(f"Task queue initialized with {max_workers} workers")
    
    def _start_workers(self):
        """Start worker threads for processing tasks"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        """Main worker loop for processing tasks"""
        while self.running:
            try:
                task = self._get_next_task()
                if task:
                    self.stats['active_workers'] += 1
                    try:
                        self._process_task(task)
                        self.stats['completed_tasks'] += 1
                    except Exception as e:
                        logger.error(f"Task {task.task_id} failed: {e}")
                        self._handle_failed_task(task, str(e))
                    finally:
                        self.stats['active_workers'] -= 1
                else:
                    time.sleep(0.1)  # No tasks available, sleep briefly
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1)
    
    def _get_next_task(self) -> Optional[Task]:
        """Get next task from priority queues (high priority first)"""
        for priority in [1, 2, 3]:
            try:
                return self.queues[priority].get_nowait()
            except Empty:
                continue
        return None
    
    def _process_task(self, task: Task):
        """Process a single task based on its type"""
        logger.info(f"Processing task {task.task_id} of type {task.task_type}")
        
        try:
            if task.task_type == 'whatsapp':
                self._process_whatsapp_task(task)
            elif task.task_type == 'email':
                self._process_email_task(task)
            elif task.task_type == 'file_upload':
                self._process_file_upload_task(task)
            elif task.task_type == 'policy_send':
                self._process_policy_send_task(task)
            elif task.task_type == 'batch_whatsapp':
                self._process_batch_whatsapp_task(task)
            elif task.task_type == 'batch_email':
                self._process_batch_email_task(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            # Store success result
            self.task_results[task.task_id] = {
                'status': 'completed',
                'completed_at': datetime.now(),
                'result': 'Success'
            }
            
            # Call callback if provided
            if task.callback:
                task.callback(task, True, None)
                
        except Exception as e:
            logger.error(f"Task {task.task_id} processing failed: {e}")
            raise
    
    def _process_whatsapp_task(self, task: Task):
        """Process WhatsApp message task"""
        from whatsapp_bot import send_whatsapp_message
        
        phone = task.data.get('phone')
        message = task.data.get('message')
        
        if not phone or not message:
            raise ValueError("WhatsApp task missing phone or message")
        
        result = send_whatsapp_message(phone, message)
        if result.get('error'):
            raise Exception(f"WhatsApp send failed: {result['error']}")
        
        logger.info(f"WhatsApp message sent to {phone}: {result.get('sid')}")
    
    def _process_email_task(self, task: Task):
        """Process email sending task"""
        from email_service import send_email
        
        email = task.data.get('email')
        subject = task.data.get('subject')
        body = task.data.get('body')
        attachments = task.data.get('attachments', [])
        customer_name = task.data.get('customer_name', 'Customer')
        
        if not email or not subject or not body:
            raise ValueError("Email task missing required fields")
        
        success, message = send_email(email, subject, body, attachments, customer_name)
        if not success:
            raise Exception(f"Email send failed: {message}")
        
        logger.info(f"Email sent to {email}")
    
    def _process_file_upload_task(self, task: Task):
        """Process file upload to Google Drive"""
        from renewal_service import upload_renewed_policy_file
        
        file_data = task.data.get('file')
        policy_id = task.data.get('policy_id')
        client_id = task.data.get('client_id')
        member_name = task.data.get('member_name')
        
        if not all([file_data, policy_id, client_id, member_name]):
            raise ValueError("File upload task missing required fields")
        
        result, error = upload_renewed_policy_file(file_data, policy_id, client_id, member_name)
        if error:
            raise Exception(f"File upload failed: {error}")
        
        logger.info(f"File uploaded for policy {policy_id}")
    
    def _process_policy_send_task(self, task: Task):
        """Process sending policy document to customer"""
        from whatsapp_bot import send_policy_to_customer
        
        phone = task.data.get('phone')
        policy = task.data.get('policy')
        send_email = task.data.get('send_email', True)
        
        if not phone or not policy:
            raise ValueError("Policy send task missing phone or policy")
        
        success, message = send_policy_to_customer(phone, policy, send_email)
        if not success:
            raise Exception(f"Policy send failed: {message}")
        
        logger.info(f"Policy sent to {phone}")
    
    def _process_batch_whatsapp_task(self, task: Task):
        """Process batch WhatsApp messages"""
        from whatsapp_bot import send_whatsapp_message
        
        messages = task.data.get('messages', [])
        results = []
        
        for msg_data in messages:
            try:
                phone = msg_data.get('phone')
                message = msg_data.get('message')
                
                if phone and message:
                    result = send_whatsapp_message(phone, message)
                    results.append({
                        'phone': phone,
                        'success': not result.get('error'),
                        'message': result.get('sid') or result.get('error')
                    })
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Batch WhatsApp message failed for {msg_data.get('phone')}: {e}")
                results.append({
                    'phone': msg_data.get('phone'),
                    'success': False,
                    'message': str(e)
                })
        
        logger.info(f"Batch WhatsApp completed: {len(results)} messages processed")
        return results
    
    def _process_batch_email_task(self, task: Task):
        """Process batch email sending"""
        from email_service import send_email
        
        emails = task.data.get('emails', [])
        results = []
        
        for email_data in emails:
            try:
                email = email_data.get('email')
                subject = email_data.get('subject')
                body = email_data.get('body')
                attachments = email_data.get('attachments', [])
                customer_name = email_data.get('customer_name', 'Customer')
                
                if email and subject and body:
                    success, message = send_email(email, subject, body, attachments, customer_name)
                    results.append({
                        'email': email,
                        'success': success,
                        'message': message
                    })
                    
                    # Small delay to avoid rate limiting
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Batch email failed for {email_data.get('email')}: {e}")
                results.append({
                    'email': email_data.get('email'),
                    'success': False,
                    'message': str(e)
                })
        
        logger.info(f"Batch email completed: {len(results)} emails processed")
        return results
    
    def _handle_failed_task(self, task: Task, error_message: str):
        """Handle failed task with retry logic"""
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            # Retry with exponential backoff
            delay = min(2 ** task.retry_count, 60)  # Max 60 seconds
            logger.warning(f"Retrying task {task.task_id} in {delay} seconds (attempt {task.retry_count}/{task.max_retries})")
            
            # Schedule retry
            threading.Timer(delay, lambda: self.add_task(task)).start()
        else:
            # Max retries exceeded
            logger.error(f"Task {task.task_id} failed permanently after {task.max_retries} retries")
            self.stats['failed_tasks'] += 1
            self.failed_tasks.put(task)
            
            # Store failure result
            self.task_results[task.task_id] = {
                'status': 'failed',
                'failed_at': datetime.now(),
                'error': error_message,
                'retry_count': task.retry_count
            }
            
            # Call callback if provided
            if task.callback:
                task.callback(task, False, error_message)
    
    def add_task(self, task: Task) -> bool:
        """Add task to appropriate priority queue"""
        try:
            if task.priority not in self.queues:
                task.priority = 2  # Default to medium priority
            
            self.queues[task.priority].put_nowait(task)
            self.stats['total_tasks'] += 1
            
            logger.debug(f"Task {task.task_id} added to queue (priority {task.priority})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add task {task.task_id}: {e}")
            return False
    
    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """Get result of a completed task"""
        return self.task_results.get(task_id)
    
    def get_queue_stats(self) -> Dict:
        """Get current queue statistics"""
        queue_sizes = {
            priority: queue.qsize() 
            for priority, queue in self.queues.items()
        }
        
        return {
            **self.stats,
            'queue_sizes': queue_sizes,
            'total_queue_size': sum(queue_sizes.values()),
            'failed_queue_size': self.failed_tasks.qsize()
        }
    
    def shutdown(self):
        """Gracefully shutdown the task queue"""
        logger.info("Shutting down task queue...")
        self.running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=30)
        
        self.executor.shutdown(wait=True)
        logger.info("Task queue shutdown complete")

# Global task queue instance
# Use optimized config if available
if os.getenv('USE_OPTIMIZED_CONFIG'):
    from config_optimized import OptimizedConfig
    task_queue = TaskQueue(
        max_workers=OptimizedConfig.TASK_QUEUE_MAX_WORKERS,
        max_queue_size=OptimizedConfig.TASK_QUEUE_MAX_SIZE
    )
else:
    task_queue = TaskQueue(max_workers=15, max_queue_size=2000)

# Convenience functions for common operations
def send_whatsapp_async(phone: str, message: str, priority: int = 2, callback: Callable = None) -> str:
    """Send WhatsApp message asynchronously"""
    task_id = f"whatsapp_{int(time.time() * 1000)}"
    task = Task(
        task_id=task_id,
        task_type='whatsapp',
        priority=priority,
        data={'phone': phone, 'message': message},
        callback=callback
    )
    
    if task_queue.add_task(task):
        return task_id
    else:
        raise Exception("Failed to queue WhatsApp task")

def send_email_async(email: str, subject: str, body: str, attachments: List = None, 
                    customer_name: str = 'Customer', priority: int = 2, callback: Callable = None) -> str:
    """Send email asynchronously"""
    task_id = f"email_{int(time.time() * 1000)}"
    task = Task(
        task_id=task_id,
        task_type='email',
        priority=priority,
        data={
            'email': email,
            'subject': subject,
            'body': body,
            'attachments': attachments or [],
            'customer_name': customer_name
        },
        callback=callback
    )
    
    if task_queue.add_task(task):
        return task_id
    else:
        raise Exception("Failed to queue email task")

def send_policy_async(phone: str, policy: Dict, send_email: bool = True, 
                     priority: int = 1, callback: Callable = None) -> str:
    """Send policy document asynchronously"""
    task_id = f"policy_{int(time.time() * 1000)}"
    task = Task(
        task_id=task_id,
        task_type='policy_send',
        priority=priority,
        data={
            'phone': phone,
            'policy': policy,
            'send_email': send_email
        },
        callback=callback
    )
    
    if task_queue.add_task(task):
        return task_id
    else:
        raise Exception("Failed to queue policy send task")

def send_batch_whatsapp_async(messages: List[Dict], priority: int = 2, callback: Callable = None) -> str:
    """Send multiple WhatsApp messages asynchronously"""
    task_id = f"batch_whatsapp_{int(time.time() * 1000)}"
    task = Task(
        task_id=task_id,
        task_type='batch_whatsapp',
        priority=priority,
        data={'messages': messages},
        callback=callback
    )
    
    if task_queue.add_task(task):
        return task_id
    else:
        raise Exception("Failed to queue batch WhatsApp task")

def send_batch_email_async(emails: List[Dict], priority: int = 2, callback: Callable = None) -> str:
    """Send multiple emails asynchronously"""
    task_id = f"batch_email_{int(time.time() * 1000)}"
    task = Task(
        task_id=task_id,
        task_type='batch_email',
        priority=priority,
        data={'emails': emails},
        callback=callback
    )
    
    if task_queue.add_task(task):
        return task_id
    else:
        raise Exception("Failed to queue batch email task")

def get_queue_status() -> Dict:
    """Get current queue status and statistics"""
    try:
        stats = task_queue.get_queue_stats()
        return {
            'status': 'healthy',
            'stats': stats,
            'message': 'Task queue is running normally'
        }
    except Exception as e:
        return {
            'status': 'error',
            'stats': {},
            'message': f'Task queue error: {str(e)}'
        }
