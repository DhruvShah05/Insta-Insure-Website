"""
Multi-User Concurrent Operations Test Suite
Tests all scaling components under concurrent load
"""
import asyncio
import threading
import time
import logging
import random
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

class MultiUserTester:
    """Test suite for multi-user concurrent operations"""
    
    def __init__(self, base_url='http://localhost:5050', num_users=50):
        self.base_url = base_url
        self.num_users = num_users
        self.test_results = {}
        
    def test_database_pool_concurrent_access(self):
        """Test database connection pool under concurrent load"""
        logger.info("Testing database pool concurrent access...")
        
        def db_operation(user_id):
            try:
                from database_pool import execute_query
                
                # Simulate various database operations
                operations = [
                    lambda: execute_query('clients', 'select', columns='*', limit=10),
                    lambda: execute_query('policies', 'select', columns='*', limit=5),
                    lambda: execute_query('clients', 'select', columns='client_id, name', limit=20)
                ]
                
                start_time = time.time()
                
                for _ in range(5):  # 5 operations per user
                    operation = random.choice(operations)
                    result = operation()
                    time.sleep(0.1)  # Small delay between operations
                
                end_time = time.time()
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'duration': end_time - start_time,
                    'operations': 5
                }
                
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'operations': 0
                }
        
        # Run concurrent database operations
        with ThreadPoolExecutor(max_workers=self.num_users) as executor:
            futures = [executor.submit(db_operation, i) for i in range(self.num_users)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        avg_duration = sum(r['duration'] for r in successful) / len(successful) if successful else 0
        total_operations = sum(r['operations'] for r in successful)
        
        self.test_results['database_pool'] = {
            'total_users': self.num_users,
            'successful_users': len(successful),
            'failed_users': len(failed),
            'success_rate': len(successful) / self.num_users * 100,
            'avg_duration_per_user': avg_duration,
            'total_operations': total_operations,
            'operations_per_second': total_operations / max(avg_duration, 0.001)
        }
        
        logger.info(f"Database pool test completed: {len(successful)}/{self.num_users} users successful")
        return len(failed) == 0
    
    def test_task_queue_concurrent_processing(self):
        """Test task queue under concurrent load"""
        logger.info("Testing task queue concurrent processing...")
        
        def queue_operations(user_id):
            try:
                from task_queue import send_whatsapp_async, send_email_async
                
                start_time = time.time()
                task_ids = []
                
                # Queue multiple tasks per user
                for i in range(3):
                    # WhatsApp task
                    task_id = send_whatsapp_async(
                        f"+91900000{user_id:04d}",
                        f"Test message {i} from user {user_id}",
                        priority=random.randint(1, 3)
                    )
                    task_ids.append(task_id)
                    
                    # Email task
                    task_id = send_email_async(
                        f"user{user_id}@test.com",
                        f"Test Subject {i}",
                        f"Test body {i} from user {user_id}",
                        priority=random.randint(1, 3)
                    )
                    task_ids.append(task_id)
                
                end_time = time.time()
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'duration': end_time - start_time,
                    'tasks_queued': len(task_ids),
                    'task_ids': task_ids
                }
                
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'tasks_queued': 0
                }
        
        # Run concurrent task queuing
        with ThreadPoolExecutor(max_workers=self.num_users) as executor:
            futures = [executor.submit(queue_operations, i) for i in range(self.num_users)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        total_tasks = sum(r['tasks_queued'] for r in successful)
        avg_duration = sum(r['duration'] for r in successful) / len(successful) if successful else 0
        
        self.test_results['task_queue'] = {
            'total_users': self.num_users,
            'successful_users': len(successful),
            'failed_users': len(failed),
            'success_rate': len(successful) / self.num_users * 100,
            'total_tasks_queued': total_tasks,
            'avg_duration_per_user': avg_duration,
            'tasks_per_second': total_tasks / max(avg_duration, 0.001)
        }
        
        logger.info(f"Task queue test completed: {total_tasks} tasks queued by {len(successful)} users")
        return len(failed) == 0
    
    def test_cache_manager_concurrent_access(self):
        """Test cache manager under concurrent load"""
        logger.info("Testing cache manager concurrent access...")
        
        def cache_operations(user_id):
            try:
                from cache_manager import cache_manager
                
                start_time = time.time()
                operations_count = 0
                
                # Perform various cache operations
                for i in range(10):
                    key = f"test_user_{user_id}_item_{i}"
                    value = {'user_id': user_id, 'item': i, 'timestamp': time.time()}
                    
                    # Set operation
                    cache_manager.set(key, value, ttl=60)
                    operations_count += 1
                    
                    # Get operation
                    retrieved = cache_manager.get(key, value_type='json')
                    operations_count += 1
                    
                    if retrieved != value:
                        raise Exception(f"Cache mismatch for key {key}")
                    
                    # Increment operation
                    counter_key = f"counter_user_{user_id}"
                    cache_manager.increment(counter_key, 1, ttl=60)
                    operations_count += 1
                
                end_time = time.time()
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'duration': end_time - start_time,
                    'operations': operations_count
                }
                
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'operations': 0
                }
        
        # Run concurrent cache operations
        with ThreadPoolExecutor(max_workers=self.num_users) as executor:
            futures = [executor.submit(cache_operations, i) for i in range(self.num_users)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        total_operations = sum(r['operations'] for r in successful)
        avg_duration = sum(r['duration'] for r in successful) / len(successful) if successful else 0
        
        self.test_results['cache_manager'] = {
            'total_users': self.num_users,
            'successful_users': len(successful),
            'failed_users': len(failed),
            'success_rate': len(successful) / self.num_users * 100,
            'total_operations': total_operations,
            'avg_duration_per_user': avg_duration,
            'operations_per_second': total_operations / max(avg_duration, 0.001)
        }
        
        logger.info(f"Cache manager test completed: {total_operations} operations by {len(successful)} users")
        return len(failed) == 0
    
    def test_api_endpoints_concurrent_requests(self):
        """Test API endpoints under concurrent load"""
        logger.info("Testing API endpoints concurrent requests...")
        
        def api_requests(user_id):
            try:
                session = requests.Session()
                start_time = time.time()
                successful_requests = 0
                
                # Test various endpoints
                endpoints = [
                    '/health',
                    '/health/detailed',
                    '/metrics',
                    '/api/system/status'
                ]
                
                for endpoint in endpoints:
                    for _ in range(2):  # 2 requests per endpoint per user
                        try:
                            response = session.get(f"{self.base_url}{endpoint}", timeout=10)
                            if response.status_code == 200:
                                successful_requests += 1
                        except requests.RequestException:
                            pass
                
                end_time = time.time()
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'duration': end_time - start_time,
                    'successful_requests': successful_requests,
                    'total_requests': len(endpoints) * 2
                }
                
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'successful_requests': 0,
                    'total_requests': 0
                }
        
        # Run concurrent API requests
        with ThreadPoolExecutor(max_workers=self.num_users) as executor:
            futures = [executor.submit(api_requests, i) for i in range(self.num_users)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        total_requests = sum(r['successful_requests'] for r in successful)
        total_attempted = sum(r['total_requests'] for r in successful)
        avg_duration = sum(r['duration'] for r in successful) / len(successful) if successful else 0
        
        self.test_results['api_endpoints'] = {
            'total_users': self.num_users,
            'successful_users': len(successful),
            'failed_users': len(failed),
            'success_rate': len(successful) / self.num_users * 100,
            'successful_requests': total_requests,
            'total_attempted_requests': total_attempted,
            'request_success_rate': total_requests / max(total_attempted, 1) * 100,
            'avg_duration_per_user': avg_duration,
            'requests_per_second': total_requests / max(avg_duration, 0.001)
        }
        
        logger.info(f"API endpoints test completed: {total_requests}/{total_attempted} requests successful")
        return total_requests > 0
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        logger.info("Testing rate limiting...")
        
        def rate_limit_test():
            try:
                session = requests.Session()
                successful_requests = 0
                rate_limited_requests = 0
                
                # Make rapid requests to trigger rate limiting
                for i in range(150):  # Exceed typical rate limits
                    try:
                        response = session.get(f"{self.base_url}/api/system/status", timeout=5)
                        if response.status_code == 200:
                            successful_requests += 1
                        elif response.status_code == 429:
                            rate_limited_requests += 1
                    except requests.RequestException:
                        pass
                    
                    time.sleep(0.01)  # Small delay
                
                return {
                    'successful_requests': successful_requests,
                    'rate_limited_requests': rate_limited_requests,
                    'total_requests': 150
                }
                
            except Exception as e:
                return {
                    'error': str(e),
                    'successful_requests': 0,
                    'rate_limited_requests': 0,
                    'total_requests': 0
                }
        
        result = rate_limit_test()
        
        self.test_results['rate_limiting'] = {
            'successful_requests': result.get('successful_requests', 0),
            'rate_limited_requests': result.get('rate_limited_requests', 0),
            'total_requests': result.get('total_requests', 0),
            'rate_limiting_working': result.get('rate_limited_requests', 0) > 0
        }
        
        logger.info(f"Rate limiting test completed: {result.get('rate_limited_requests', 0)} requests rate limited")
        return result.get('rate_limited_requests', 0) > 0
    
    def test_batch_file_operations(self):
        """Test batch file operations (mock test)"""
        logger.info("Testing batch file operations...")
        
        def batch_file_test(user_id):
            try:
                from batch_file_operations import batch_file_manager
                
                start_time = time.time()
                
                # Simulate file upload requests
                upload_requests = []
                for i in range(3):
                    upload_requests.append({
                        'file': f"mock_file_{user_id}_{i}.pdf",
                        'filename': f"test_file_{user_id}_{i}.pdf",
                        'mimetype': 'application/pdf',
                        'client_id': f"C{user_id:03d}",
                        'member_name': f"Member_{user_id}",
                        'parent_folder_id': 'mock_folder_id'
                    })
                
                # Get file manager stats (don't actually upload files in test)
                stats = batch_file_manager.get_stats()
                
                end_time = time.time()
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'duration': end_time - start_time,
                    'files_prepared': len(upload_requests),
                    'manager_stats': stats
                }
                
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'files_prepared': 0
                }
        
        # Run batch file operations test
        with ThreadPoolExecutor(max_workers=min(self.num_users, 10)) as executor:
            futures = [executor.submit(batch_file_test, i) for i in range(min(self.num_users, 10))]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        total_files = sum(r['files_prepared'] for r in successful)
        
        self.test_results['batch_file_operations'] = {
            'total_users': min(self.num_users, 10),
            'successful_users': len(successful),
            'failed_users': len(failed),
            'success_rate': len(successful) / min(self.num_users, 10) * 100,
            'total_files_prepared': total_files
        }
        
        logger.info(f"Batch file operations test completed: {total_files} files prepared by {len(successful)} users")
        return len(failed) == 0
    
    def run_all_tests(self):
        """Run all multi-user tests"""
        logger.info(f"Starting multi-user tests with {self.num_users} concurrent users...")
        
        test_functions = [
            ('Database Pool', self.test_database_pool_concurrent_access),
            ('Task Queue', self.test_task_queue_concurrent_processing),
            ('Cache Manager', self.test_cache_manager_concurrent_access),
            ('API Endpoints', self.test_api_endpoints_concurrent_requests),
            ('Rate Limiting', self.test_rate_limiting),
            ('Batch File Operations', self.test_batch_file_operations)
        ]
        
        test_results = {}
        
        for test_name, test_func in test_functions:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                start_time = time.time()
                success = test_func()
                end_time = time.time()
                
                test_results[test_name] = {
                    'success': success,
                    'duration': end_time - start_time,
                    'details': self.test_results.get(test_name.lower().replace(' ', '_'), {})
                }
                
                status = "✅ PASSED" if success else "❌ FAILED"
                logger.info(f"{test_name}: {status} (Duration: {end_time - start_time:.2f}s)")
                
            except Exception as e:
                test_results[test_name] = {
                    'success': False,
                    'duration': 0,
                    'error': str(e)
                }
                logger.error(f"{test_name}: ❌ ERROR - {e}")
        
        # Generate summary report
        self.generate_test_report(test_results)
        
        return test_results
    
    def generate_test_report(self, test_results):
        """Generate comprehensive test report"""
        logger.info(f"\n{'='*60}")
        logger.info("MULTI-USER SCALING TEST REPORT")
        logger.info(f"{'='*60}")
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result['success'])
        
        logger.info(f"Test Configuration:")
        logger.info(f"  Concurrent Users: {self.num_users}")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        logger.info(f"\nOverall Results:")
        logger.info(f"  Total Tests: {total_tests}")
        logger.info(f"  Passed: {passed_tests}")
        logger.info(f"  Failed: {total_tests - passed_tests}")
        logger.info(f"  Success Rate: {passed_tests / total_tests * 100:.1f}%")
        
        logger.info(f"\nDetailed Results:")
        for test_name, result in test_results.items():
            status = "✅ PASSED" if result['success'] else "❌ FAILED"
            duration = result.get('duration', 0)
            logger.info(f"  {test_name}: {status} ({duration:.2f}s)")
            
            if 'error' in result:
                logger.info(f"    Error: {result['error']}")
            
            # Show performance metrics if available
            details = result.get('details', {})
            if details:
                if 'success_rate' in details:
                    logger.info(f"    Success Rate: {details['success_rate']:.1f}%")
                if 'operations_per_second' in details:
                    logger.info(f"    Operations/sec: {details['operations_per_second']:.1f}")
                if 'requests_per_second' in details:
                    logger.info(f"    Requests/sec: {details['requests_per_second']:.1f}")
        
        # Save detailed report to file
        report_file = f"multiuser_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            'test_configuration': {
                'concurrent_users': self.num_users,
                'base_url': self.base_url,
                'test_time': datetime.now().isoformat()
            },
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'success_rate': passed_tests / total_tests * 100
            },
            'test_results': test_results,
            'detailed_metrics': self.test_results
        }
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            logger.info(f"\nDetailed report saved to: {report_file}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
        
        # Performance recommendations
        logger.info(f"\n{'='*60}")
        logger.info("PERFORMANCE RECOMMENDATIONS")
        logger.info(f"{'='*60}")
        
        if passed_tests == total_tests:
            logger.info("🎉 All tests passed! Your application is ready for multi-user deployment.")
        else:
            logger.info("⚠️ Some tests failed. Please review the issues before production deployment.")
        
        # Specific recommendations based on results
        db_details = self.test_results.get('database_pool', {})
        if db_details.get('success_rate', 0) < 95:
            logger.info("📊 Consider increasing database pool size for better performance")
        
        cache_details = self.test_results.get('cache_manager', {})
        if cache_details.get('operations_per_second', 0) < 1000:
            logger.info("🔄 Consider using Redis for better cache performance")
        
        api_details = self.test_results.get('api_endpoints', {})
        if api_details.get('request_success_rate', 0) < 95:
            logger.info("🌐 Consider adding more Gunicorn workers for better API performance")
        
        logger.info(f"\nFor production deployment, run:")
        logger.info(f"  python deploy_multiuser.py")
        logger.info(f"  gunicorn -c gunicorn_config.py wsgi:application")

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-User Scaling Test Suite')
    parser.add_argument('--users', type=int, default=50, help='Number of concurrent users to simulate')
    parser.add_argument('--url', type=str, default='http://localhost:5050', help='Base URL of the application')
    
    args = parser.parse_args()
    
    tester = MultiUserTester(base_url=args.url, num_users=args.users)
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    all_passed = all(result['success'] for result in results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
