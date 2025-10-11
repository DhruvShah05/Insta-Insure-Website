"""
Batch File Operations for Multi-User Concurrent Google Drive Operations
Handles multiple file uploads, downloads, and operations simultaneously
"""
import os
import io
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import tempfile
from queue import Queue

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from config import Config
from database_pool import execute_query, batch_insert

logger = logging.getLogger(__name__)

@dataclass
class FileOperation:
    """File operation definition"""
    operation_id: str
    operation_type: str  # 'upload', 'download', 'move', 'delete'
    file_data: Any
    metadata: Dict
    callback: Optional[callable] = None
    priority: int = 2
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class BatchFileManager:
    """Manages batch file operations for Google Drive"""
    
    def __init__(self, max_workers=None, credentials_file=None):
        # Use optimized config if available
        if os.getenv('USE_OPTIMIZED_CONFIG'):
            from config_optimized import OptimizedConfig
            max_workers = max_workers or OptimizedConfig.FILE_MANAGER_MAX_WORKERS
        else:
            max_workers = max_workers or 8
        
        self.max_workers = max_workers
        self.credentials_file = credentials_file or Config.GOOGLE_CREDENTIALS_FILE
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="FileWorker")
        
        # Operation queues by priority
        self.operation_queues = {
            1: Queue(),  # High priority
            2: Queue(),  # Medium priority  
            3: Queue()   # Low priority
        }
        
        # Statistics
        self.stats = {
            'total_operations': 0,
            'completed_operations': 0,
            'failed_operations': 0,
            'active_workers': 0
        }
        
        # Results storage
        self.operation_results = {}
        self.failed_operations = Queue()
        
        # Thread safety
        self.stats_lock = threading.Lock()
        
        # Initialize Drive service pool
        self.drive_services = Queue(maxsize=max_workers)
        self._initialize_drive_services()
        
        logger.info(f"Batch file manager initialized with {max_workers} workers")
    
    def _initialize_drive_services(self):
        """Initialize pool of Google Drive service instances"""
        try:
            scopes = ['https://www.googleapis.com/auth/drive']
            
            for _ in range(self.max_workers):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file, scopes=scopes
                )
                service = build('drive', 'v3', credentials=credentials)
                self.drive_services.put(service)
                
            logger.info(f"Initialized {self.max_workers} Google Drive service instances")
            
        except Exception as e:
            logger.error(f"Failed to initialize Drive services: {e}")
            raise
    
    def _get_drive_service(self):
        """Get a Drive service instance from the pool"""
        return self.drive_services.get()
    
    def _return_drive_service(self, service):
        """Return a Drive service instance to the pool"""
        self.drive_services.put(service)
    
    def batch_upload_files(self, upload_requests: List[Dict], callback: callable = None) -> str:
        """Upload multiple files in batch"""
        batch_id = f"batch_upload_{int(time.time() * 1000)}"
        
        try:
            # Submit batch upload task
            future = self.executor.submit(self._process_batch_upload, upload_requests, batch_id, callback)
            
            with self.stats_lock:
                self.stats['total_operations'] += len(upload_requests)
            
            logger.info(f"Batch upload queued: {batch_id} with {len(upload_requests)} files")
            return batch_id
            
        except Exception as e:
            logger.error(f"Failed to queue batch upload: {e}")
            raise
    
    def _process_batch_upload(self, upload_requests: List[Dict], batch_id: str, callback: callable = None):
        """Process batch file upload"""
        results = []
        
        try:
            with self.stats_lock:
                self.stats['active_workers'] += 1
            
            # Process uploads concurrently
            upload_futures = []
            
            for i, request in enumerate(upload_requests):
                future = self.executor.submit(self._upload_single_file, request, f"{batch_id}_{i}")
                upload_futures.append(future)
            
            # Collect results
            for future in as_completed(upload_futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    with self.stats_lock:
                        if result.get('success'):
                            self.stats['completed_operations'] += 1
                        else:
                            self.stats['failed_operations'] += 1
                            
                except Exception as e:
                    logger.error(f"Upload future failed: {e}")
                    results.append({'success': False, 'error': str(e)})
                    
                    with self.stats_lock:
                        self.stats['failed_operations'] += 1
            
            # Store batch results
            self.operation_results[batch_id] = {
                'type': 'batch_upload',
                'completed_at': datetime.now(),
                'total_files': len(upload_requests),
                'successful': len([r for r in results if r.get('success')]),
                'failed': len([r for r in results if not r.get('success')]),
                'results': results
            }
            
            # Call callback if provided
            if callback:
                callback(batch_id, True, results)
            
            logger.info(f"Batch upload completed: {batch_id}")
            
        except Exception as e:
            logger.error(f"Batch upload failed: {batch_id} - {e}")
            
            self.operation_results[batch_id] = {
                'type': 'batch_upload',
                'failed_at': datetime.now(),
                'error': str(e),
                'results': results
            }
            
            if callback:
                callback(batch_id, False, str(e))
        
        finally:
            with self.stats_lock:
                self.stats['active_workers'] -= 1
    
    def _upload_single_file(self, request: Dict, operation_id: str) -> Dict:
        """Upload a single file to Google Drive"""
        drive_service = None
        
        try:
            drive_service = self._get_drive_service()
            
            # Extract request data
            file_obj = request.get('file')
            filename = request.get('filename')
            parent_folder_id = request.get('parent_folder_id')
            client_id = request.get('client_id')
            member_name = request.get('member_name')
            
            if not all([file_obj, filename, client_id, member_name]):
                return {
                    'success': False,
                    'operation_id': operation_id,
                    'error': 'Missing required parameters'
                }
            
            # Create folder structure if needed
            folder_id = self._ensure_folder_structure(drive_service, parent_folder_id, client_id, member_name)
            
            if not folder_id:
                return {
                    'success': False,
                    'operation_id': operation_id,
                    'error': 'Failed to create folder structure'
                }
            
            # Prepare file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Read file content
            if hasattr(file_obj, 'read'):
                file_content = file_obj.read()
                file_obj.seek(0)  # Reset file pointer
            else:
                file_content = file_obj
            
            # Upload file
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=request.get('mimetype', 'application/octet-stream'),
                resumable=True
            )
            
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink, size, createdTime",
                supportsAllDrives=True
            ).execute()
            
            # Update database if policy_id provided
            if request.get('policy_id'):
                try:
                    update_data = {
                        'file_path': uploaded_file.get('name'),
                        'drive_file_id': uploaded_file.get('id'),
                        'drive_url': uploaded_file.get('webViewLink'),
                        'drive_path': f"{client_id}/{member_name}/{filename}"
                    }
                    
                    execute_query(
                        'policies',
                        'update',
                        data=update_data,
                        filters={'policy_id': request['policy_id']}
                    )
                    
                except Exception as db_error:
                    logger.warning(f"Database update failed for {operation_id}: {db_error}")
            
            return {
                'success': True,
                'operation_id': operation_id,
                'file_id': uploaded_file.get('id'),
                'file_name': uploaded_file.get('name'),
                'web_view_link': uploaded_file.get('webViewLink'),
                'size': uploaded_file.get('size'),
                'drive_path': f"{client_id}/{member_name}/{filename}"
            }
            
        except HttpError as e:
            logger.error(f"Google Drive API error for {operation_id}: {e}")
            return {
                'success': False,
                'operation_id': operation_id,
                'error': f'Drive API error: {e}'
            }
            
        except Exception as e:
            logger.error(f"Upload error for {operation_id}: {e}")
            return {
                'success': False,
                'operation_id': operation_id,
                'error': str(e)
            }
        
        finally:
            if drive_service:
                self._return_drive_service(drive_service)
    
    def _ensure_folder_structure(self, drive_service, root_folder_id: str, client_id: str, member_name: str) -> Optional[str]:
        """Ensure folder structure exists and return final folder ID"""
        try:
            # Find or create client folder
            client_folder_id = self._find_or_create_folder(drive_service, root_folder_id, client_id)
            if not client_folder_id:
                return None
            
            # Find or create member folder
            member_folder_id = self._find_or_create_folder(drive_service, client_folder_id, member_name)
            return member_folder_id
            
        except Exception as e:
            logger.error(f"Error ensuring folder structure: {e}")
            return None
    
    def _find_or_create_folder(self, drive_service, parent_id: str, folder_name: str) -> Optional[str]:
        """Find existing folder or create new one"""
        try:
            # Search for existing folder
            query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            created_folder = drive_service.files().create(
                body=folder_metadata,
                fields='id, name',
                supportsAllDrives=True
            ).execute()
            
            return created_folder['id']
            
        except Exception as e:
            logger.error(f"Error finding/creating folder {folder_name}: {e}")
            return None
    
    def batch_download_files(self, download_requests: List[Dict], callback: callable = None) -> str:
        """Download multiple files in batch"""
        batch_id = f"batch_download_{int(time.time() * 1000)}"
        
        try:
            # Submit batch download task
            future = self.executor.submit(self._process_batch_download, download_requests, batch_id, callback)
            
            with self.stats_lock:
                self.stats['total_operations'] += len(download_requests)
            
            logger.info(f"Batch download queued: {batch_id} with {len(download_requests)} files")
            return batch_id
            
        except Exception as e:
            logger.error(f"Failed to queue batch download: {e}")
            raise
    
    def _process_batch_download(self, download_requests: List[Dict], batch_id: str, callback: callable = None):
        """Process batch file download"""
        results = []
        
        try:
            with self.stats_lock:
                self.stats['active_workers'] += 1
            
            # Process downloads concurrently
            download_futures = []
            
            for i, request in enumerate(download_requests):
                future = self.executor.submit(self._download_single_file, request, f"{batch_id}_{i}")
                download_futures.append(future)
            
            # Collect results
            for future in as_completed(download_futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    with self.stats_lock:
                        if result.get('success'):
                            self.stats['completed_operations'] += 1
                        else:
                            self.stats['failed_operations'] += 1
                            
                except Exception as e:
                    logger.error(f"Download future failed: {e}")
                    results.append({'success': False, 'error': str(e)})
                    
                    with self.stats_lock:
                        self.stats['failed_operations'] += 1
            
            # Store batch results
            self.operation_results[batch_id] = {
                'type': 'batch_download',
                'completed_at': datetime.now(),
                'total_files': len(download_requests),
                'successful': len([r for r in results if r.get('success')]),
                'failed': len([r for r in results if not r.get('success')]),
                'results': results
            }
            
            # Call callback if provided
            if callback:
                callback(batch_id, True, results)
            
            logger.info(f"Batch download completed: {batch_id}")
            
        except Exception as e:
            logger.error(f"Batch download failed: {batch_id} - {e}")
            
            self.operation_results[batch_id] = {
                'type': 'batch_download',
                'failed_at': datetime.now(),
                'error': str(e),
                'results': results
            }
            
            if callback:
                callback(batch_id, False, str(e))
        
        finally:
            with self.stats_lock:
                self.stats['active_workers'] -= 1
    
    def _download_single_file(self, request: Dict, operation_id: str) -> Dict:
        """Download a single file from Google Drive"""
        drive_service = None
        temp_file_path = None
        
        try:
            drive_service = self._get_drive_service()
            
            file_id = request.get('file_id')
            filename = request.get('filename', f'download_{operation_id}')
            
            if not file_id:
                return {
                    'success': False,
                    'operation_id': operation_id,
                    'error': 'Missing file_id'
                }
            
            # Create temporary file
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, filename)
            
            # Download file
            request_obj = drive_service.files().get_media(fileId=file_id)
            
            with io.FileIO(temp_file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request_obj)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return {
                'success': True,
                'operation_id': operation_id,
                'file_id': file_id,
                'temp_file_path': temp_file_path,
                'filename': filename
            }
            
        except HttpError as e:
            logger.error(f"Google Drive API error for download {operation_id}: {e}")
            return {
                'success': False,
                'operation_id': operation_id,
                'error': f'Drive API error: {e}'
            }
            
        except Exception as e:
            logger.error(f"Download error for {operation_id}: {e}")
            return {
                'success': False,
                'operation_id': operation_id,
                'error': str(e)
            }
        
        finally:
            if drive_service:
                self._return_drive_service(drive_service)
    
    def get_batch_result(self, batch_id: str) -> Optional[Dict]:
        """Get result of a batch operation"""
        return self.operation_results.get(batch_id)
    
    def get_stats(self) -> Dict:
        """Get current operation statistics"""
        with self.stats_lock:
            return {
                **self.stats,
                'queue_sizes': {
                    priority: queue.qsize() 
                    for priority, queue in self.operation_queues.items()
                },
                'failed_queue_size': self.failed_operations.qsize()
            }
    
    def shutdown(self):
        """Gracefully shutdown the batch file manager"""
        logger.info("Shutting down batch file manager...")
        self.executor.shutdown(wait=True)
        logger.info("Batch file manager shutdown complete")

# Global batch file manager instance
# Use optimized config if available
if os.getenv('USE_OPTIMIZED_CONFIG'):
    from config_optimized import OptimizedConfig
    batch_file_manager = BatchFileManager(max_workers=OptimizedConfig.FILE_MANAGER_MAX_WORKERS)
else:
    batch_file_manager = BatchFileManager(max_workers=10)

# Convenience functions
def upload_multiple_policy_files(file_uploads: List[Dict], callback: callable = None) -> str:
    """Upload multiple policy files"""
    return batch_file_manager.batch_upload_files(file_uploads, callback)

def download_multiple_policy_files(file_downloads: List[Dict], callback: callable = None) -> str:
    """Download multiple policy files"""
    return batch_file_manager.batch_download_files(file_downloads, callback)
