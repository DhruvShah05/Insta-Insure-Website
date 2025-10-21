# Renewal File Cleanup System

## Overview
The Renewal File Cleanup System automatically manages renewal files in `static/renewals/` based on WhatsApp message delivery status. This prevents disk space issues by removing files that are no longer needed.

## 🎯 **How It Works**

### **Smart Cleanup Logic**
The system uses WhatsApp delivery status to determine when files can be safely deleted:

1. **✅ Delivered/Read Messages** - Files deleted after 1 hour (customer received the file)
2. **❌ Failed Messages** - Files deleted after 2 hours (delivery unsuccessful)
3. **⏳ Stuck Messages** - Files deleted after 6 hours (likely failed)
4. **📤 Sent but Not Delivered** - Files deleted after 24 hours (probably won't deliver)
5. **🗂️ Orphaned Files** - Files without WhatsApp logs deleted after 7 days

### **Two Types of Cleanup**

#### **Status-Based Cleanup**
- Uses WhatsApp logs to determine file fate
- Links files to message delivery status
- Safe and intelligent deletion

#### **Orphaned File Cleanup**
- Removes files not tracked in WhatsApp logs
- Cleans up files from failed uploads or system errors
- Age-based deletion (7+ days old)

## 🚀 **Usage**

### **Manual Cleanup (Web Interface)**

1. **Navigate to WhatsApp Logs**
   - Go to Dashboard → WhatsApp Logs
   
2. **Preview Cleanup**
   - Click "Preview File Cleanup" (orange button)
   - See what files would be deleted
   - Get size estimates

3. **Run Cleanup**
   - Click "Clean Up Files" (red button)
   - Confirm deletion
   - View cleanup results

### **Manual Cleanup (Command Line)**

```bash
# Preview what would be deleted (dry run)
python renewal_file_cleanup.py --dry-run

# Actually delete files
python renewal_file_cleanup.py
```

### **Automated Daily Cleanup**

Set up a cron job for automatic daily cleanup:

```bash
# Edit crontab
crontab -e

# Add this line to run cleanup daily at 2 AM
0 2 * * * /path/to/your/project/run_daily_cleanup.py
```

## 📊 **Cleanup Criteria**

### **Files Ready for Deletion**

| Message Status | Wait Time | Reason |
|---------------|-----------|---------|
| `delivered` | 1 hour | Customer received file |
| `read` | 1 hour | Customer opened file |
| `failed` | 2 hours | Delivery failed permanently |
| `undelivered` | 2 hours | Could not deliver |
| `queued`/`sending` | 6 hours | Stuck in system |
| `sent` | 24 hours | Sent but not delivered |

### **Orphaned Files**
- Files in `static/renewals/` without WhatsApp log entries
- Older than 7 days
- Usually from failed uploads or system errors

## 🔧 **API Endpoints**

### **Preview Cleanup**
```http
GET /api/whatsapp/cleanup_preview
```
Returns list of files that would be deleted without actually deleting them.

### **Run Cleanup**
```http
POST /api/whatsapp/cleanup_files
Content-Type: application/json

{
    "dry_run": false
}
```

### **Response Format**
```json
{
    "success": true,
    "results": {
        "timestamp": "2025-10-21T18:53:28",
        "total_files_processed": 15,
        "total_size_freed": 52428800,
        "summary": "Deleted 15 files, freed 50.00 MB",
        "status_based_cleanup": {
            "total_files": 10,
            "deleted_files": [...],
            "failed_deletions": []
        },
        "orphaned_cleanup": {
            "total_orphaned": 5,
            "deleted_orphaned": [...],
            "failed_deletions": []
        }
    }
}
```

## 🛡️ **Safety Features**

### **Minimum Age Requirements**
- Files must be at least 2 hours old before cleanup
- Prevents deletion of recently uploaded files
- Gives time for message delivery

### **Status Verification**
- Only deletes files with confirmed delivery status
- Checks multiple conditions before deletion
- Logs all deletion decisions

### **Dry Run Mode**
- Test cleanup without actually deleting files
- Preview what would be deleted
- Estimate space savings

### **Comprehensive Logging**
- All cleanup actions logged
- Failed deletions tracked
- Audit trail for compliance

## 📈 **Benefits**

### **Disk Space Management**
- Prevents `static/renewals/` from growing indefinitely
- Automatic cleanup of successful deliveries
- Removes failed upload files

### **Performance**
- Faster file system operations
- Reduced backup sizes
- Better server performance

### **Maintenance**
- No manual file management needed
- Automatic orphaned file cleanup
- Intelligent deletion based on business logic

## 🔍 **Monitoring**

### **Cleanup Logs**
Check `logs/renewal_cleanup.log` for:
- Daily cleanup results
- Failed deletions
- Space freed statistics

### **Web Interface Statistics**
The WhatsApp logs page shows:
- Total messages sent
- Delivery success rates
- File cleanup history

## ⚙️ **Configuration**

### **Timing Settings**
You can adjust cleanup timing in `renewal_file_cleanup.py`:

```python
# Minimum age before cleanup (default: 2 hours)
files_to_cleanup = cleanup_service.get_files_ready_for_cleanup(min_age_hours=2)

# Orphaned file age (default: 7 days)
orphaned_results = cleanup_service.cleanup_orphaned_files(max_age_days=7)
```

### **Directory Settings**
The cleanup service automatically finds the renewals directory:
```python
self.static_renewals_dir = os.path.join(os.path.dirname(__file__), 'static', 'renewals')
```

## 🚨 **Troubleshooting**

### **Files Not Being Deleted**
1. Check WhatsApp logs for message status
2. Verify file age (must be 2+ hours old)
3. Check file permissions
4. Review cleanup logs for errors

### **Orphaned Files Remaining**
1. Ensure files are 7+ days old
2. Check if files have corresponding WhatsApp logs
3. Verify directory permissions

### **Cleanup Errors**
1. Check `logs/renewal_cleanup.log`
2. Verify file system permissions
3. Ensure files aren't locked by other processes

## 📋 **Best Practices**

### **Regular Monitoring**
- Check cleanup logs weekly
- Monitor disk space usage
- Review failed deletions

### **Backup Strategy**
- Ensure important files are backed up before cleanup
- Consider archiving instead of deletion for compliance
- Test restore procedures

### **Scheduling**
- Run cleanup during low-traffic hours (2-4 AM)
- Avoid running during backup windows
- Monitor system resources during cleanup

## 🔄 **Integration with WhatsApp Logs**

The cleanup system is fully integrated with the WhatsApp logs feature:

1. **Message Tracking** - Every renewal reminder is logged
2. **Status Updates** - Delivery status determines cleanup eligibility  
3. **File Linking** - Files are linked to specific messages
4. **Audit Trail** - Complete history of file lifecycle

This ensures that files are only deleted when it's safe and appropriate based on actual delivery confirmation from Twilio.

## 📊 **Example Cleanup Results**

```
Cleanup completed: Deleted 12 files, freed 45.67 MB
├── Status-based cleanup: 8 files
│   ├── 5 delivered messages (files no longer needed)
│   ├── 2 failed messages (delivery unsuccessful)  
│   └── 1 stuck message (likely failed)
└── Orphaned cleanup: 4 files
    └── 4 old files without WhatsApp logs
```

This intelligent cleanup system ensures your renewal files directory stays clean and manageable while preserving files that customers might still need to access.
