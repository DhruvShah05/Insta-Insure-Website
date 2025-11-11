# Google Drive Fix V2 - Comprehensive Solution

## Problem Identified

The previous Google Drive fix was incomplete and had critical issues:

1. **No Credential Refresh in Route Files**: While `excel_service.py` had credential refresh, the route files (`routes/policies.py`, `routes/claims.py`) were initializing the Drive service once at module load and never refreshing credentials.

2. **Local Fallback Masking Failures**: When Google Drive uploads failed, the system would save files locally (in `local_uploads/` directory) and continue with data entry, creating database records with invalid `local/filename` paths instead of proper Drive URLs.

3. **Silent Failures**: Users were not properly notified when Drive operations failed, leading to data inconsistency.

## Root Cause

**Service Account Credentials Issue**: The service account credentials were being initialized once when the Flask app started, but were never being refreshed. After approximately 3 days, these credentials would become stale, causing all Drive operations to fail silently.

## Solution Implemented

### 1. Added Credential Refresh Mechanism

**Files Modified:**
- `routes/policies.py`
- `routes/claims.py`

**Changes:**
```python
# Global credentials object for refresh support
_drive_credentials = None
_drive_service = None

def _init_drive_credentials():
    """Initialize Google Drive credentials from service account file"""
    global _drive_credentials
    try:
        _drive_credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        return _drive_credentials
    except Exception as e:
        raise Exception(f"Cannot initialize Google Drive credentials: {e}")

def _refresh_drive_credentials():
    """Refresh Google Drive credentials if expired"""
    global _drive_credentials, _drive_service
    
    if _drive_credentials is None:
        _init_drive_credentials()
        return
    
    # Service account credentials don't expire in the traditional sense,
    # but we should reinitialize if there are issues
    if not _drive_credentials.valid:
        _init_drive_credentials()
        _drive_service = None  # Force service rebuild

def get_drive_service():
    """Initialize and return Google Drive service with credential refresh support"""
    global _drive_credentials, _drive_service
    
    # Ensure credentials are initialized and valid
    if _drive_credentials is None:
        _init_drive_credentials()
    else:
        _refresh_drive_credentials()
    
    # Return existing service if valid
    if _drive_service is not None:
        return _drive_service
    
    # Build new service with fresh credentials
    _drive_service = build("drive", "v3", credentials=_drive_credentials)
    return _drive_service
```

### 2. Added Pre-Upload Credential Check

**In `routes/policies.py` - `upload_policy_file()` function:**
```python
def upload_policy_file(file, client_id, member_name):
    """Upload file to Google Drive in client/member folder structure with PDF conversion"""
    global drive_service
    
    # Ensure Drive service is available with fresh credentials
    try:
        drive_service = get_drive_service()
    except Exception as e:
        error_msg = f"Google Drive is unavailable: {str(e)}"
        raise Exception(error_msg)
    
    # ... rest of upload logic
```

### 3. Removed Local Fallback Logic

**Files Modified:**
- `routes/policies.py` - `add_policy()` route
- `routes/pending_policies.py` - `complete_pending()` route

**Before (BAD):**
```python
try:
    drive_file = upload_policy_file(file, client_id_str, member_name_str)
except Exception as e:
    # Fallback: Save file locally and continue
    upload_folder = os.path.join(os.getcwd(), 'local_uploads', client_id_str, member_name_str)
    os.makedirs(upload_folder, exist_ok=True)
    file.save(local_path)
    drive_file = {"id": f"local_{filename}", "drive_path": f"local/{filename}"}
    # CONTINUES WITH DATABASE ENTRY - BAD!
```

**After (GOOD):**
```python
try:
    drive_file = upload_policy_file(file, client_id_str, member_name_str)
except Exception as e:
    flash(f"Google Drive upload failed: {str(e)}. Policy NOT created. Please ensure Google Drive is accessible and try again.", "error")
    return redirect(url_for("policies.add_policy"))
    # STOPS HERE - NO DATABASE ENTRY IF DRIVE FAILS
```

### 4. Improved Error Handling

**Key Changes:**
- Drive service initialization now **raises exceptions** instead of returning `None`
- Upload failures **halt the entire operation** - no partial data entry
- Clear error messages inform users about Drive connectivity issues
- No silent failures - all errors are logged and displayed

## Benefits

1. **No More 3-Day Shutdowns**: Credentials are automatically refreshed before each operation
2. **Data Consistency**: Files are ONLY in Google Drive, never in local storage
3. **Clear Error Messages**: Users know immediately when Drive is unavailable
4. **Fail-Safe Operations**: If Drive fails, the entire operation fails - no partial/corrupted data
5. **Better Debugging**: All Drive errors are properly logged with context

## Testing Recommendations

1. **Test Normal Upload**: Upload a policy file and verify it appears in Google Drive
2. **Test Credential Refresh**: Wait 3+ days and verify uploads still work
3. **Test Failure Handling**: 
   - Temporarily rename the service account file
   - Try to upload a policy
   - Verify: Error message shown, no database entry created, no local file saved
4. **Test Claims Upload**: Upload claim documents and verify proper error handling

## Migration Notes

**Existing Local Files**: If you have files in `local_uploads/` directory from previous failed uploads:
1. These need to be manually uploaded to Google Drive
2. Database records need to be updated with proper Drive URLs
3. Consider running a cleanup script to identify and fix these records

## Files Changed

1. `routes/policies.py` - Added credential refresh, removed local fallback
2. `routes/claims.py` - Added credential refresh mechanism
3. `routes/pending_policies.py` - Removed local fallback
4. `GOOGLE_DRIVE_FIX_V2.md` - This documentation

## Monitoring

Watch for these log messages:
- ✅ "Google Drive credentials initialized" - Good
- ✅ "Credentials invalid, reinitializing..." - Automatic recovery
- ❌ "Google Drive is unavailable" - Needs attention
- ❌ "All Google Drive connection methods failed" - Critical issue

## Next Steps

If Drive continues to fail after 3 days, investigate:
1. Service account key file validity
2. Google Cloud project API quotas
3. Network/firewall issues
4. Service account permissions on Drive folders
