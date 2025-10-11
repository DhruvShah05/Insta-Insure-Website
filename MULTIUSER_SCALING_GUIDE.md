# Multi-User Scaling Guide

This guide explains how to deploy and manage the insurance portal for multiple concurrent users.

## 🚀 Overview

The multi-user scaling implementation includes:

- **Database Connection Pooling**: Efficient handling of concurrent database operations
- **Async Task Queue**: Background processing for WhatsApp, email, and file operations
- **Batch File Operations**: Concurrent Google Drive file handling
- **Redis Caching**: Session management and rate limiting
- **Production WSGI Server**: Gunicorn with worker processes
- **Monitoring & Health Checks**: Real-time system monitoring
- **Rate Limiting**: Prevent abuse and ensure fair usage

## 📋 Prerequisites

- Python 3.8 or higher
- Redis server (optional but recommended)
- Nginx (for production deployment)
- Sufficient system resources (minimum 4GB RAM, 2 CPU cores)

## 🛠️ Quick Deployment

### 1. Automated Deployment

Run the automated deployment script:

```bash
python deploy_multiuser.py
```

This will:
- Create virtual environment
- Install dependencies
- Check configuration
- Test all services
- Create startup scripts
- Generate nginx configuration

### 2. Manual Deployment

If you prefer manual setup:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install production dependencies
pip install -r requirements_production.txt

# Create necessary directories
mkdir -p logs static/renewals static/uploads temp

# Set environment variables (see Environment Variables section)

# Test the application
python app_multiuser.py
```

## 🔧 Environment Variables

### Required Variables

```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Authentication
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_FRONTEND_API=your_clerk_frontend_api

# Google Drive
GOOGLE_CREDENTIALS_FILE=path/to/credentials.json
ROOT_FOLDER_ID=your_root_folder_id

# Twilio
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

### Optional Variables

```bash
# Redis (recommended for production)
REDIS_URL=redis://localhost:6379/0

# WhatsApp (if using WhatsApp Business API)
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_ID=your_phone_id
VERIFY_TOKEN=your_verify_token

# Application
FLASK_ENV=production
SECRET_KEY=your_secret_key
PORT=5050
APP_BASE_URL=https://your-domain.com
```

## 🏭 Production Deployment

### Using Gunicorn (Recommended)

```bash
# Start with Gunicorn
gunicorn -c gunicorn_config.py wsgi:application

# Or use the startup script
./start_multiuser.sh  # Linux/macOS
./start_multiuser.bat  # Windows
```

### Gunicorn Configuration

The `gunicorn_config.py` file includes optimized settings:

- **Workers**: CPU cores × 2 + 1
- **Worker Class**: Gevent for async operations
- **Connections**: 1000 per worker
- **Timeouts**: Optimized for file operations
- **Memory Management**: Auto-restart workers

### Nginx Configuration

Use the generated `nginx.conf` for:

- **Load Balancing**: Distribute requests across workers
- **Rate Limiting**: Prevent abuse
- **Static File Serving**: Efficient static content delivery
- **SSL Termination**: HTTPS support
- **Caching**: Improved performance

```bash
# Install nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/insurance-portal
sudo ln -s /etc/nginx/sites-available/insurance-portal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Service (Linux)

```bash
# Install systemd service
sudo cp insurance-portal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable insurance-portal
sudo systemctl start insurance-portal

# Check status
sudo systemctl status insurance-portal
```

## 📊 Monitoring & Health Checks

### Health Check Endpoints

- `/health` - Basic health check
- `/health/detailed` - Detailed service status
- `/metrics` - System metrics
- `/api/system/status` - Complete system status

### Monitoring Dashboard

Access real-time metrics:

```bash
curl http://localhost:5050/metrics
```

Response includes:
- System performance (CPU, memory, disk)
- Service health (database, cache, task queue)
- Request statistics
- User activity
- Alerts and warnings

### Log Files

Monitor application logs:

```bash
# Application logs
tail -f logs/multiuser_app.log

# Access logs (if using Gunicorn)
tail -f logs/access.log

# Error logs
tail -f logs/error.log
```

## 🔄 Scaling Components

### 1. Database Connection Pooling

**File**: `database_pool.py`

- **Pool Size**: 15 connections
- **Max Overflow**: 30 additional connections
- **Timeout**: 45 seconds
- **Retry Logic**: 3 attempts with exponential backoff

**Usage**:
```python
from database_pool import execute_query

# Execute query with connection pooling
result = execute_query('policies', 'select', columns='*', filters={'client_id_eq': 123})
```

### 2. Async Task Queue

**File**: `task_queue.py`

- **Workers**: 15 concurrent workers
- **Priority Queues**: High, medium, low priority
- **Retry Logic**: Automatic retry with backoff
- **Task Types**: WhatsApp, email, file operations

**Usage**:
```python
from task_queue import send_whatsapp_async, send_email_async

# Send WhatsApp message asynchronously
task_id = send_whatsapp_async(phone, message, priority=1)

# Send email asynchronously
task_id = send_email_async(email, subject, body, priority=2)
```

### 3. Batch File Operations

**File**: `batch_file_operations.py`

- **Concurrent Uploads**: 10 parallel uploads
- **Drive Service Pool**: Multiple authenticated instances
- **Folder Management**: Automatic folder creation
- **Error Handling**: Individual file retry logic

**Usage**:
```python
from batch_file_operations import upload_multiple_policy_files

# Upload multiple files
upload_requests = [
    {'file': file1, 'client_id': 'C001', 'member_name': 'John'},
    {'file': file2, 'client_id': 'C002', 'member_name': 'Jane'}
]
batch_id = upload_multiple_policy_files(upload_requests)
```

### 4. Redis Caching

**File**: `cache_manager.py`

- **Session Storage**: User session management
- **Rate Limiting**: IP-based rate limiting
- **Data Caching**: Frequently accessed data
- **Fallback**: In-memory cache if Redis unavailable

**Usage**:
```python
from cache_manager import cache_manager, rate_limit

# Cache data
cache_manager.set('user_policies:123', policies, ttl=600)

# Rate limiting decorator
@rate_limit(limit=100, window=60)
def api_endpoint():
    return "API response"
```

## 🔧 Configuration Tuning

### Performance Optimization

1. **Database Pool Size**:
   ```python
   # Adjust based on concurrent users
   db_pool = DatabasePool(pool_size=20, max_overflow=40)
   ```

2. **Task Queue Workers**:
   ```python
   # Increase for high message volume
   task_queue = TaskQueue(max_workers=20)
   ```

3. **File Manager Workers**:
   ```python
   # Adjust based on file upload frequency
   batch_file_manager = BatchFileManager(max_workers=15)
   ```

4. **Gunicorn Workers**:
   ```python
   # In gunicorn_config.py
   workers = multiprocessing.cpu_count() * 2 + 1
   worker_connections = 1000
   ```

### Memory Management

Monitor memory usage and adjust:

```bash
# Check memory usage
ps aux | grep gunicorn
htop

# Restart workers if memory usage is high
sudo systemctl reload insurance-portal
```

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   ```bash
   # Check database pool status
   curl http://localhost:5050/api/system/status
   
   # Restart application
   sudo systemctl restart insurance-portal
   ```

2. **Task Queue Overload**:
   ```bash
   # Check queue status
   curl http://localhost:5050/metrics | grep queue
   
   # Increase workers in task_queue.py
   ```

3. **File Upload Failures**:
   ```bash
   # Check Google Drive credentials
   python -c "from batch_file_operations import batch_file_manager; print(batch_file_manager.get_stats())"
   ```

4. **Rate Limiting Issues**:
   ```bash
   # Check rate limit status
   redis-cli keys "rate_limit:*"
   
   # Clear rate limits if needed
   redis-cli flushdb
   ```

### Performance Monitoring

Use these commands to monitor performance:

```bash
# System resources
htop
iostat -x 1
free -h

# Application metrics
curl http://localhost:5050/metrics

# Database connections
curl http://localhost:5050/api/system/status | jq '.services.database'

# Task queue status
curl http://localhost:5050/api/system/status | jq '.services.task_queue'
```

## 📈 Scaling Beyond Single Server

### Horizontal Scaling

For very high loads, consider:

1. **Load Balancer**: Multiple application servers behind nginx
2. **Database Scaling**: Read replicas for Supabase
3. **Redis Cluster**: Distributed caching
4. **CDN**: Static file delivery
5. **Message Queue**: External queue service (RabbitMQ, AWS SQS)

### Microservices Architecture

Split into separate services:

- **Web Application**: User interface
- **API Service**: REST API endpoints
- **WhatsApp Service**: Message handling
- **File Service**: Google Drive operations
- **Email Service**: Email processing

## 🔒 Security Considerations

### Production Security

1. **Environment Variables**: Use secure secret management
2. **HTTPS**: Always use SSL in production
3. **Rate Limiting**: Implement aggressive rate limiting
4. **Input Validation**: Validate all user inputs
5. **Access Control**: Implement proper authentication
6. **Monitoring**: Monitor for suspicious activity

### Security Headers

The application includes security headers:
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

## 📞 Support

For issues or questions:

1. Check the logs first: `tail -f logs/multiuser_app.log`
2. Verify system status: `curl http://localhost:5050/health/detailed`
3. Check resource usage: `htop` and `free -h`
4. Review configuration files
5. Restart services if needed

## 🎯 Performance Benchmarks

Expected performance with recommended configuration:

- **Concurrent Users**: 100-500 users
- **Request Throughput**: 1000+ requests/minute
- **WhatsApp Messages**: 500+ messages/minute
- **File Uploads**: 50+ concurrent uploads
- **Database Operations**: 2000+ queries/minute

Monitor these metrics and scale resources as needed.

---

**Note**: This multi-user implementation significantly improves the application's ability to handle concurrent users. Monitor performance metrics and adjust configuration based on your specific usage patterns.
