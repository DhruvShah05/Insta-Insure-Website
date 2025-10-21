#!/usr/bin/env python3
"""
Daily Renewal File Cleanup Script
Run this script daily via cron to automatically clean up old renewal files
"""
import sys
import os
from datetime import datetime
import logging

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from renewal_file_cleanup import run_cleanup_job

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/renewal_cleanup.log'),
        logging.StreamHandler()
    ]
)

def main():
    """Run daily cleanup job"""
    logger = logging.getLogger(__name__)
    
    logger.info("Starting daily renewal file cleanup")
    
    try:
        # Run cleanup (not dry run)
        results = run_cleanup_job(dry_run=False)
        
        # Log results
        logger.info(f"Cleanup completed: {results['summary']}")
        logger.info(f"Total files processed: {results['total_files_processed']}")
        logger.info(f"Total size freed: {results['total_size_freed'] / (1024 * 1024):.2f} MB")
        
        # Log any failures
        status_failures = results['status_based_cleanup']['failed_deletions']
        orphaned_failures = results['orphaned_cleanup']['failed_deletions']
        
        if status_failures or orphaned_failures:
            logger.warning(f"Some deletions failed:")
            for failure in status_failures + orphaned_failures:
                logger.warning(f"  - {failure['filename']}: {failure['error']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Daily cleanup failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
