# Policy Renewal Workflow Guide

## Overview
The renewal page uses a **two-step workflow** to ensure proper policy history tracking:
1. **Upload new policy document first** → Archives old policy to history
2. **Edit renewed policy details** → Update information for the new policy

## Complete Renewal Workflow

### Step 1: Navigate to Renewal Page
- From dashboard, click "Edit Details & Renew" button on any policy
- This opens `/renewal_page/{policy_id}`

### Step 2: View Current Policy Information
The page displays:
- **Policy Information**: Policy ID, client name, member name, contact details
- **Current Policy Details**: Insurance company, product type, expiry date, policy number
- **Renewal History**: Last renewed date, last reminder sent (if applicable)

### Step 3: Upload Renewed Policy Document (REQUIRED FIRST)
**This must be done before editing any details!**

1. **Upload New Policy PDF**: Select the renewed policy document (PDF only, max 10MB)
2. **New Expiry Date**: Enter new expiry date in DD/MM/YYYY format (optional - keeps current if empty)
3. **New Policy Number**: Enter new policy number (optional - keeps current if empty)
4. Click **"Upload & Archive Old Policy"** button

**What happens when you upload:**
- ✅ Old policy data is **immediately archived** to `policy_history` table (captures original state)
- ✅ Old PDF is moved to Google Drive "Archive" folder (not deleted)
- ✅ New PDF is uploaded to appropriate client/member folder
- ✅ Policy record is updated with new file information
- ✅ Notifications sent to customer (WhatsApp/Email if available)
- ✅ Edit section becomes **enabled** for updating renewed policy details

### Step 4: Edit Renewed Policy Details (Optional)
**This section is disabled until Step 3 is complete.**

After successful upload, the edit section becomes active and you can update:

#### Basic Information
- Insurance Company (dropdown)
- Product Type
- Policy Number
- Agent Name (dropdown)
- Business Type (NEW/RENEWAL/ROLL OVER)
- One-time Insurance checkbox

#### Financial Information
- Payment Details
- Sum Insured
- Net Premium/OD
- Addon Premium
- TP/TR Premium
- GST Percentage
- Gross Premium (auto-calculated)
- Commission Percentage
- Commission Amount (auto-calculated)
- Commission Received checkbox

#### Policy Dates
- Policy Start Date (DD/MM/YYYY)
- Policy End Date (DD/MM/YYYY)
- Payment Date (DD/MM/YYYY)

#### Additional Information
- Group Name
- Subgroup Name
- Remarks

#### Health Insurance Details (if applicable)
- Plan Type (FLOATER/INDIVIDUAL)
- Floater Sum Insured (for FLOATER plans)
- Floater Bonus (for FLOATER plans)
- Health Insured Members with individual sum insured/bonus (for INDIVIDUAL plans)

#### Factory Insurance Details (if applicable)
- Building Coverage
- Plant & Machinery Coverage
- Furniture & Fittings Coverage
- Stocks Coverage
- Electrical Installations Coverage

**Actions:**
- Click **"Save Renewed Policy Details"** to update the renewed policy information
- All changes apply to the **renewed policy**, not the archived one

## Important Notes

### Policy History Behavior - CRITICAL
The new workflow ensures **proper history tracking**:

1. **Upload Document First** (Step 3):
   - Archives **original policy state** to history immediately
   - History captures the policy **before any changes**
   - This is the correct historical record ✅

2. **Edit Details After** (Step 4):
   - Updates the **renewed policy** (not the old one)
   - Changes apply to the new policy record
   - No additional history created (already archived in Step 3)

**Why this order matters:**
- ❌ **Old way**: Edit first → Archive edited data → History contains NEW details (wrong!)
- ✅ **New way**: Archive first → Edit after → History contains ORIGINAL details (correct!)

### Edit Section Disabled Until Upload
- The edit section is **visually disabled** (grayed out) until you upload the new document
- This prevents accidentally editing the old policy before archiving
- Badge shows "Upload document first" until renewal is complete
- After upload, badge changes to "Ready to edit" and section becomes active

### Data Validation
- All dates are validated and converted from DD/MM/YYYY to YYYY-MM-DD for database
- Numeric fields are validated for proper format
- File type and size are validated before upload
- Empty/invalid values are handled gracefully

### Auto-Calculations
- **Gross Premium** = Net Premium + Addon Premium + TP/TR Premium + (Subtotal × GST%)
- **Commission Amount** = (Net Premium + Addon Premium) × Commission%
- Both values are automatically rounded to whole numbers

## Viewing Policy History

To view complete policy history:
1. Go to the policy details page
2. Look for "Policy History" section
3. Or access via `/policy_history/{policy_id}` endpoint

The history shows:
- All previous versions of the policy
- What changed in each renewal
- Who made the changes
- When changes were made
- Archived file references

## Excel Sync

Policy history is automatically synced to Excel:
- Go to Excel Dashboard (`/excel`)
- Click "Refresh Excel Data"
- Download Excel file
- View "Policy History" sheet for complete audit trail

## Technical Details

### API Endpoints
- `POST /api/update_policy_details` - Updates policy details (no history)
- `POST /api/renew_policy` - Renews policy with new PDF (creates history)
- `GET /api/get_policy_history/<policy_id>` - Retrieves policy history
- `GET /renewal_page/<policy_id>` - Displays renewal page

### Database Tables
- `policies` - Current active policies
- `policy_history` - Historical policy records
- `health_insurance_details` - Health insurance information
- `health_insured_members` - Individual health insurance members
- `factory_insurance_details` - Factory insurance coverage details

### Files Modified
- `templates/renewal_page.html` - Made edit section visible by default
- `routes/renewal_routes.py` - Handles renewal and detail updates
- `renewal_service.py` - Core renewal logic with history archiving

## Workflow Summary

```
1. Open Renewal Page
   ↓
2. View Current Policy Details (read-only display)
   ↓
3. Upload New Policy PDF + Update Expiry/Policy Number
   ↓
4. Click "Upload & Archive Old Policy"
   ↓
5. System Archives OLD Policy Data to History ✅ (Original State)
   ↓
6. System Archives Old File to Drive Archive Folder
   ↓
7. System Uploads New File
   ↓
8. System Updates Policy Record
   ↓
9. System Sends Notifications (WhatsApp/Email)
   ↓
10. Edit Section Becomes ENABLED
   ↓
11. [Optional] Edit Renewed Policy Details → Click "Save Renewed Policy Details"
   ↓
12. Success! Policy Renewed with Proper History
```

## Benefits

✅ **Proper History Tracking**: Original policy state always captured before changes
✅ **Complete Visibility**: All policy details visible and editable after renewal
✅ **Flexible Editing**: Edit any field for the renewed policy
✅ **Audit Trail**: Complete history of all renewals with original data
✅ **File Management**: Old files archived, not deleted
✅ **Automatic Notifications**: Customers receive new policy automatically
✅ **Data Integrity**: All changes validated and tracked
✅ **Excel Integration**: History syncs to Excel for reporting
✅ **Foolproof Workflow**: Can't edit old policy before archiving (prevented by UI)
