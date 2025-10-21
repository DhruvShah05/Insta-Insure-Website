"""
Renewal File Cleanup Service
Automatically cleans up renewal files from static/renewals based on WhatsApp delivery status
"""
import os
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict
from supabase import create_client
from config import Config
import re

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)


class RenewalFileCleanup:
    """Service for cleaning up renewal files based on WhatsApp delivery status"""
    
    def __init__(self):
        self.static_renewals_dir = os.path.join(os.path.dirname(__file__), 'static', 'renewals')
        
    def get_files_ready_for_cleanup(self, min_age_minutes: int = 1) -> List[Dict]:
        """
        Get renewal files that are ready for cleanup based on message status
        
        Args:
            min_age_minutes: Minimum age of files before considering cleanup (default 1 minute)
        
        Returns:
            List of files ready for cleanup with their status info
        """
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now() - timedelta(minutes=min_age_minutes)
            cutoff_iso = cutoff_time.isoformat()
            
            # Get WhatsApp logs for renewal reminders that are old enough
            result = supabase.table('whatsapp_logs').select(
                'message_sid, media_url, status, error_code, sent_at, last_status_check'
            ).eq('message_type', 'renewal_reminder').lt('sent_at', cutoff_iso).execute()
            
            if not result.data:
                return []
            
            files_to_cleanup = []
            
            for log in result.data:
                media_url = log.get('media_url', '')
                status = log.get('status', '')
                
                # Extract filename from media_url (e.g., "static/renewals/filename.pdf")
                if media_url and 'static/renewals/' in media_url:
                    filename = media_url.split('static/renewals/')[-1]
                    file_path = os.path.join(self.static_renewals_dir, filename)
                    
                    # Check if file exists
                    if os.path.exists(file_path):
                        # Determine if file is ready for cleanup based on status
                        should_cleanup = self._should_cleanup_file(log)
                        
                        if should_cleanup:
                            files_to_cleanup.append({
                                'filename': filename,
                                'file_path': file_path,
                                'message_sid': log['message_sid'],
                                'status': status,
                                'reason': self._get_cleanup_reason(log),
                                'sent_at': log['sent_at'],
                                'last_status_check': log['last_status_check']
                            })
            
            return files_to_cleanup
            
        except Exception as e:
            logger.error(f"Error getting files ready for cleanup: {e}")
            return []
    
    def _should_cleanup_file(self, log: Dict) -> bool:
        """
        Determine if a file should be cleaned up based on message status
        
        Args:
            log: WhatsApp log entry
            
        Returns:
            True if file should be cleaned up
        """
        status = log.get('status', '')
        sent_at = log.get('sent_at', '')
        
        # Parse sent_at timestamp
        try:
            sent_time = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
            minutes_since_sent = (datetime.now() - sent_time.replace(tzinfo=None)).total_seconds() / 60
        except:
            minutes_since_sent = 0
        
        # Aggressive cleanup conditions:
        
        # 1. Message was delivered or read - cleanup immediately after 1 minute
        if status in ['delivered', 'read'] and minutes_since_sent >= 1:
            return True
        
        # 2. Message failed permanently - cleanup immediately after 1 minute
        if status in ['failed', 'undelivered'] and minutes_since_sent >= 1:
            return True
        
        # 3. Message stuck in sending/queued for more than 5 minutes - likely failed
        if status in ['queued', 'sending'] and minutes_since_sent >= 5:
            return True
        
        # 4. Message sent but not delivered after 30 minutes - cleanup
        if status == 'sent' and minutes_since_sent >= 30:
            return True
        
        return False
    
    def _get_cleanup_reason(self, log: Dict) -> str:
        """Get human-readable reason for cleanup"""
        status = log.get('status', '')
        
        if status in ['delivered', 'read']:
            return f"Message {status} - file no longer needed"
        elif status in ['failed', 'undelivered']:
            return f"Message {status} - delivery unsuccessful"
        elif status in ['queued', 'sending']:
            return "Message stuck in queue for 5+ minutes - likely failed"
        elif status == 'sent':
            return "Message sent but not delivered after 30 minutes"
        else:
            return "Unknown status - cleanup based on age"
    
    def cleanup_files(self, files_to_cleanup: List[Dict], dry_run: bool = False) -> Dict:
        """
        Clean up the specified files
        
        Args:
            files_to_cleanup: List of files to cleanup
            dry_run: If True, don't actually delete files, just report what would be deleted
            
        Returns:
            Dictionary with cleanup results
        """
        results = {
            'total_files': len(files_to_cleanup),
            'deleted_files': [],
            'failed_deletions': [],
            'total_size_freed': 0,
            'dry_run': dry_run
        }
        
        for file_info in files_to_cleanup:
            try:
                file_path = file_info['file_path']
                filename = file_info['filename']
                
                # Get file size before deletion
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    
                    if not dry_run:
                        # Actually delete the file
                        os.remove(file_path)
                        logger.info(f"Deleted renewal file: {filename} (Reason: {file_info['reason']})")
                    else:
                        logger.info(f"[DRY RUN] Would delete: {filename} (Reason: {file_info['reason']})")
                    
                    results['deleted_files'].append({
                        'filename': filename,
                        'size': file_size,
                        'reason': file_info['reason'],
                        'message_sid': file_info['message_sid'],
                        'status': file_info['status']
                    })
                    results['total_size_freed'] += file_size
                
            except Exception as e:
                logger.error(f"Failed to delete {file_info['filename']}: {e}")
                results['failed_deletions'].append({
                    'filename': file_info['filename'],
                    'error': str(e)
                })
        
        return results
    
    def cleanup_orphaned_files(self, max_age_days: int = 7, dry_run: bool = False) -> Dict:
        """
        Clean up orphaned files that don't have corresponding WhatsApp logs
        
        Args:
            max_age_days: Maximum age of orphaned files before cleanup
            dry_run: If True, don't actually delete files
            
        Returns:
            Dictionary with cleanup results
        """
        results = {
            'total_orphaned': 0,
            'deleted_orphaned': [],
            'failed_deletions': [],
            'total_size_freed': 0,
            'dry_run': dry_run
        }
        
        try:
            if not os.path.exists(self.static_renewals_dir):
                return results
            
            # Get all files in renewals directory
            all_files = os.listdir(self.static_renewals_dir)
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            # Get all media URLs from WhatsApp logs
            logs_result = supabase.table('whatsapp_logs').select('media_url').execute()
            logged_files = set()
            
            for log in logs_result.data or []:
                media_url = log.get('media_url', '')
                if media_url and 'static/renewals/' in media_url:
                    filename = media_url.split('static/renewals/')[-1]
                    logged_files.add(filename)
            
            # Check each file
            for filename in all_files:
                file_path = os.path.join(self.static_renewals_dir, filename)
                
                # Skip directories
                if os.path.isdir(file_path):
                    continue
                
                # Check if file is orphaned (not in WhatsApp logs)
                if filename not in logged_files:
                    # Check file age
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_time:
                        results['total_orphaned'] += 1
                        
                        try:
                            file_size = os.path.getsize(file_path)
                            
                            if not dry_run:
                                os.remove(file_path)
                                logger.info(f"Deleted orphaned file: {filename}")
                            else:
                                logger.info(f"[DRY RUN] Would delete orphaned file: {filename}")
                            
                            results['deleted_orphaned'].append({
                                'filename': filename,
                                'size': file_size,
                                'age_days': (datetime.now() - file_mtime).days
                            })
                            results['total_size_freed'] += file_size
                            
                        except Exception as e:
                            logger.error(f"Failed to delete orphaned file {filename}: {e}")
                            results['failed_deletions'].append({
                                'filename': filename,
                                'error': str(e)
                            })
            
        except Exception as e:
            logger.error(f"Error during orphaned file cleanup: {e}")
        
        return results
    
    def run_full_cleanup(self, dry_run: bool = False) -> Dict:
        """
        Run complete cleanup process
        
        Args:
            dry_run: If True, don't actually delete files
            
        Returns:
            Complete cleanup results
        """
        logger.info(f"Starting renewal file cleanup {'(DRY RUN)' if dry_run else ''}")
        
        # 1. Cleanup files based on WhatsApp status
        files_to_cleanup = self.get_files_ready_for_cleanup()
        status_cleanup_results = self.cleanup_files(files_to_cleanup, dry_run)
        
        # 2. Cleanup orphaned files
        orphaned_cleanup_results = self.cleanup_orphaned_files(dry_run=dry_run)
        
        # Combine results
        total_results = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'status_based_cleanup': status_cleanup_results,
            'orphaned_cleanup': orphaned_cleanup_results,
            'total_files_processed': status_cleanup_results['total_files'] + orphaned_cleanup_results['total_orphaned'],
            'total_size_freed': status_cleanup_results['total_size_freed'] + orphaned_cleanup_results['total_size_freed'],
            'summary': self._generate_summary(status_cleanup_results, orphaned_cleanup_results)
        }
        
        logger.info(f"Cleanup completed: {total_results['summary']}")
        return total_results
    
    def _generate_summary(self, status_results: Dict, orphaned_results: Dict) -> str:
        """Generate human-readable summary"""
        total_deleted = len(status_results['deleted_files']) + len(orphaned_results['deleted_orphaned'])
        total_size_mb = (status_results['total_size_freed'] + orphaned_results['total_size_freed']) / (1024 * 1024)
        
        if total_deleted == 0:
            return "No files needed cleanup"
        
        return f"Deleted {total_deleted} files, freed {total_size_mb:.2f} MB"


def run_cleanup_job(dry_run: bool = False):
    """Standalone function to run cleanup job"""
    cleanup_service = RenewalFileCleanup()
    return cleanup_service.run_full_cleanup(dry_run=dry_run)


if __name__ == "__main__":
    # Run as standalone script
    import sys
    
    dry_run = '--dry-run' in sys.argv
    
    print("Renewal File Cleanup Service")
    print("=" * 40)
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no files will be deleted")
    
    results = run_cleanup_job(dry_run=dry_run)
    
    print(f"\n📊 Cleanup Results:")
    print(f"   • {results['summary']}")
    print(f"   • Status-based cleanup: {len(results['status_based_cleanup']['deleted_files'])} files")
    print(f"   • Orphaned file cleanup: {len(results['orphaned_cleanup']['deleted_orphaned'])} files")
    
    if results['status_based_cleanup']['failed_deletions'] or results['orphaned_cleanup']['failed_deletions']:
        print(f"   ⚠️  Some deletions failed - check logs for details")
    
    print(f"\n✅ Cleanup completed at {results['timestamp']}")
