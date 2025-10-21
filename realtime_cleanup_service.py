"""
Real-time Renewal File Cleanup Service
Runs continuously, checking every minute for status changes and cleaning up files immediately
"""
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List
from renewal_file_cleanup import RenewalFileCleanup
from whatsapp_service import WhatsAppService

# Set up logging
logger = logging.getLogger(__name__)


class RealtimeCleanupService:
    """Background service that monitors WhatsApp status and cleans up files in real-time"""
    
    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.cleanup_service = RenewalFileCleanup()
        self.whatsapp_service = WhatsAppService()
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the background cleanup service"""
        if self.running:
            logger.warning("Cleanup service is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_service, daemon=True)
        self.thread.start()
        logger.info(f"Real-time cleanup service started (checking every {self.check_interval} seconds)")
    
    def stop(self):
        """Stop the background cleanup service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Real-time cleanup service stopped")
    
    def _run_service(self):
        """Main service loop - runs continuously"""
        logger.info("Real-time cleanup service loop started")
        
        while self.running:
            try:
                # Step 1: Refresh status for pending messages
                self._refresh_pending_statuses()
                
                # Step 2: Clean up files based on updated statuses
                self._perform_cleanup()
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup service loop: {e}")
                time.sleep(self.check_interval)  # Continue running even if there's an error
    
    def _refresh_pending_statuses(self):
        """Refresh status for messages that might have changed"""
        try:
            # Get messages that are in transitional states (not final)
            from supabase import create_client
            from config import Config
            
            supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            
            # Get messages in non-final states
            pending_statuses = ['queued', 'sending', 'sent']
            result = supabase.table('whatsapp_logs').select(
                'message_sid, status, sent_at'
            ).in_('status', pending_statuses).execute()
            
            if not result.data:
                return
            
            updated_count = 0
            for log in result.data:
                message_sid = log['message_sid']
                
                # Check if message is old enough to warrant status check
                sent_at = log.get('sent_at', '')
                try:
                    sent_time = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                    minutes_since_sent = (datetime.now() - sent_time.replace(tzinfo=None)).total_seconds() / 60
                    
                    # Only check status for messages older than 30 seconds to avoid spam
                    if minutes_since_sent >= 0.5:
                        if self.whatsapp_service.refresh_message_status(message_sid):
                            updated_count += 1
                except:
                    # If we can't parse the date, still try to refresh
                    if self.whatsapp_service.refresh_message_status(message_sid):
                        updated_count += 1
            
            if updated_count > 0:
                logger.info(f"Refreshed status for {updated_count} messages")
                
        except Exception as e:
            logger.error(f"Error refreshing pending statuses: {e}")
    
    def _perform_cleanup(self):
        """Perform file cleanup based on current statuses"""
        try:
            # Get files ready for cleanup (1 minute minimum age)
            files_to_cleanup = self.cleanup_service.get_files_ready_for_cleanup(min_age_minutes=1)
            
            if not files_to_cleanup:
                return
            
            # Perform cleanup
            results = self.cleanup_service.cleanup_files(files_to_cleanup, dry_run=False)
            
            deleted_count = len(results['deleted_files'])
            if deleted_count > 0:
                size_mb = results['total_size_freed'] / (1024 * 1024)
                logger.info(f"Real-time cleanup: Deleted {deleted_count} files, freed {size_mb:.2f} MB")
                
                # Log details of deleted files
                for file_info in results['deleted_files']:
                    logger.info(f"  - {file_info['filename']}: {file_info['reason']}")
            
        except Exception as e:
            logger.error(f"Error performing cleanup: {e}")
    
    def get_status(self) -> Dict:
        """Get current service status"""
        return {
            'running': self.running,
            'check_interval_seconds': self.check_interval,
            'thread_alive': self.thread.is_alive() if self.thread else False
        }


# Global service instance
_cleanup_service_instance = None


def start_realtime_cleanup_service(check_interval_seconds: int = 60):
    """Start the global real-time cleanup service"""
    global _cleanup_service_instance
    
    if _cleanup_service_instance and _cleanup_service_instance.running:
        logger.warning("Real-time cleanup service is already running")
        return _cleanup_service_instance
    
    _cleanup_service_instance = RealtimeCleanupService(check_interval_seconds)
    _cleanup_service_instance.start()
    return _cleanup_service_instance


def stop_realtime_cleanup_service():
    """Stop the global real-time cleanup service"""
    global _cleanup_service_instance
    
    if _cleanup_service_instance:
        _cleanup_service_instance.stop()
        _cleanup_service_instance = None


def get_realtime_cleanup_service():
    """Get the current service instance"""
    return _cleanup_service_instance


if __name__ == "__main__":
    # Run as standalone service
    import sys
    
    print("Real-time Renewal File Cleanup Service")
    print("=" * 40)
    print("This service will:")
    print("• Check message status every minute")
    print("• Delete files 1 minute after delivery/failure")
    print("• Delete stuck files after 5 minutes")
    print("• Delete undelivered files after 30 minutes")
    print("• Run continuously until stopped")
    print()
    
    # Set up logging to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = start_realtime_cleanup_service(check_interval_seconds=60)
    
    try:
        print("Service started. Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping service...")
        stop_realtime_cleanup_service()
        print("Service stopped.")
        sys.exit(0)
