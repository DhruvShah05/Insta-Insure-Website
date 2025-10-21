# WhatsApp Logs Feature

## Overview
The WhatsApp Logs feature provides comprehensive tracking and monitoring of all WhatsApp messages sent through the insurance portal. You can view message delivery status, read receipts, and troubleshoot any delivery issues.

## Features

### 📊 **Dashboard Statistics**
- **Total Messages**: Count of all WhatsApp messages sent
- **Delivered Messages**: Successfully delivered messages
- **Read Messages**: Messages that have been read by recipients
- **Success Rate**: Percentage of successfully delivered messages

### 🔍 **Message Tracking**
- **Real-time Status**: Track messages from `queued` → `sending` → `sent` → `delivered` → `read`
- **Error Tracking**: View error codes and messages for failed deliveries
- **Delivery Timestamps**: See exactly when messages were delivered and read
- **Message Types**: Categorized as Policy Document, Renewal Reminder, or General

### 🎯 **Advanced Filtering**
- Filter by message status (queued, sent, delivered, failed, etc.)
- Filter by message type (policy documents, renewal reminders, general)
- Search by phone number
- Date range filtering
- Pagination for large datasets

### 🔄 **Status Refresh**
- **Bulk Refresh**: Update status for all pending messages at once
- **Individual Refresh**: Update status for specific messages
- **Automatic Logging**: All new messages are automatically logged

## Message Status Values

| Status | Description |
|--------|-------------|
| `queued` | Message is queued for sending |
| `sending` | Message is currently being sent |
| `sent` | Message has been sent to carrier |
| `delivered` | Message delivered to recipient's device |
| `read` | Message has been read by recipient (WhatsApp only) |
| `failed` | Message failed to send |
| `undelivered` | Message could not be delivered |

## Usage

### Accessing WhatsApp Logs
1. Navigate to the dashboard
2. Click **"WhatsApp Logs"** in the navigation bar
3. View all your WhatsApp message history

### Refreshing Message Status
- **All Messages**: Click "Refresh All Statuses" to update all pending messages
- **Single Message**: Click "Refresh Status" next to any message
- **Automatic**: New messages are automatically tracked

### Viewing Message Details
- Click **"View Details"** next to any message
- See complete Twilio message information including:
  - Message SID
  - Price and segments
  - Detailed timestamps
  - Error codes (if any)

### Filtering Messages
Use the filter section to narrow down results:
- **Status Filter**: Show only messages with specific status
- **Type Filter**: Filter by message type
- **Phone Search**: Find messages to specific numbers
- **Date Range**: View messages from specific time periods

## Technical Implementation

### Database Schema
```sql
CREATE TABLE whatsapp_logs (
    log_id SERIAL PRIMARY KEY,
    message_sid VARCHAR(100) UNIQUE NOT NULL,
    policy_id INTEGER REFERENCES policies(policy_id),
    client_id INTEGER REFERENCES clients(client_id),
    phone_number VARCHAR(20) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    message_content TEXT,
    media_url TEXT,
    status VARCHAR(50) DEFAULT 'queued',
    error_code VARCHAR(20),
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    last_status_check TIMESTAMP,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints
- `GET /whatsapp_logs` - View logs page
- `POST /api/whatsapp/refresh_all_statuses` - Refresh all message statuses
- `POST /api/whatsapp/refresh_status` - Refresh single message status
- `GET /api/whatsapp/message_details/<sid>` - Get detailed message info
- `GET /api/whatsapp/stats` - Get statistics for dashboard

### Integration Points
- **WhatsApp Bot**: Automatically logs all outgoing messages
- **Policy Documents**: Links messages to specific policies
- **Customer Records**: Associates messages with client records
- **Twilio API**: Fetches real-time status from Twilio

## Installation & Setup

### 1. Run Database Migration
```bash
python run_whatsapp_migration.py
```

### 2. Copy and Execute SQL
Copy the displayed SQL and run it in your Supabase SQL editor:
```
https://app.supabase.com/project/YOUR_PROJECT/sql
```

### 3. Restart Application
Restart your Flask application to load the new routes.

### 4. Access Feature
Navigate to `/whatsapp_logs` or click the "WhatsApp Logs" button in the navigation.

## Configuration

### Environment Variables
Ensure these Twilio credentials are set in your `.env` file:
```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+1234567890
```

### Permissions
- All logged-in users can view WhatsApp logs
- Only authorized users can refresh message statuses
- Message details require valid session

## Troubleshooting

### Common Issues

**1. Messages Not Being Logged**
- Check if `WhatsAppService` is properly imported
- Verify database connection
- Check for errors in application logs

**2. Status Not Updating**
- Verify Twilio credentials are correct
- Check internet connectivity
- Ensure message SID is valid

**3. Page Not Loading**
- Confirm migration was run successfully
- Check if blueprint is registered in app
- Verify template file exists

### Error Messages

**"Twilio client not configured"**
- Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in environment

**"WhatsApp service not available"**
- Restart application after installing whatsapp_service.py
- Check for import errors in logs

**"Failed to log WhatsApp message"**
- Check database connectivity
- Verify whatsapp_logs table exists
- Check for constraint violations

## Benefits

### For Administrators
- **Complete Visibility**: See all WhatsApp communications
- **Delivery Confirmation**: Know which messages were delivered
- **Error Tracking**: Quickly identify and resolve delivery issues
- **Performance Metrics**: Monitor success rates and trends

### For Customer Service
- **Message History**: View complete communication history with customers
- **Delivery Status**: Confirm if important documents were received
- **Troubleshooting**: Identify why messages might not be reaching customers

### For Compliance
- **Audit Trail**: Complete record of all communications
- **Delivery Proof**: Evidence that important notices were sent
- **Error Documentation**: Record of any delivery failures

## Future Enhancements

### Planned Features
- **Message Templates**: Save and reuse common messages
- **Scheduled Messages**: Send messages at specific times
- **Bulk Messaging**: Send messages to multiple recipients
- **Analytics Dashboard**: Advanced reporting and insights
- **Webhook Integration**: Real-time status updates from Twilio
- **Export Functionality**: Download logs as CSV/Excel

### Integration Opportunities
- **Email Logs**: Similar tracking for email communications
- **SMS Logs**: Track SMS messages alongside WhatsApp
- **Notification Center**: Unified view of all communications
- **Customer Portal**: Let customers view their message history

## Support

For technical support or feature requests:
1. Check the application logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure database migration was completed successfully
4. Test with a simple message to verify Twilio integration

## Version History

- **v1.0** - Initial implementation with basic logging and status tracking
- **v1.1** - Added filtering, pagination, and bulk refresh functionality
- **v1.2** - Enhanced UI with statistics dashboard and message details modal
