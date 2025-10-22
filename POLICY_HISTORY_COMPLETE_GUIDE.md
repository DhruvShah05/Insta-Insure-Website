# Complete Policy History System - Implementation Guide

## Overview
This guide documents the comprehensive policy history system that captures **ALL** policy details including additional details for factory insurance and health insurance policies.

## What Gets Saved in Policy History

### 1. **Basic Policy Information**
All standard policy fields are archived:
- Policy ID, Policy Number, Client ID, Member ID
- Insurance Company, Product Name, Agent Name
- Business Type (NEW, RENEWAL, ROLL OVER)
- Group Name, Subgroup Name
- Remarks

### 2. **Financial Details**
Complete financial information:
- Net Premium, Addon Premium, TP/TR Premium
- GST Percentage, Gross Premium
- Commission Percentage, Commission Amount
- Sum Insured
- Commission Received Status
- One Time Insurance Status

### 3. **Dates and Timeline**
All important dates:
- Payment Date
- Policy Start Date (policy_from)
- Policy End Date (policy_to)
- Created At
- Updated At (NEW)
- Renewed At
- Last Reminder Sent

### 4. **File and Document Information**
Document tracking:
- File Path
- Google Drive File ID
- Google Drive Path
- Google Drive URL

### 5. **Archive Metadata**
Historical tracking:
- Archived At (timestamp)
- Archived Reason (renewal, update, etc.)
- Archived By (user who performed the action)

### 6. **Factory Insurance Details** (NEW)
For factory insurance policies, additional details are saved:
- Building Value
- Plant & Machinery Value
- Furniture, Fittings & Fixtures Value
- Stocks Value
- Electrical Installations Value

**Products with Factory Insurance:**
- FACTORY INSURANCE
- BHARAT GRIHA RAKSHA
- BHARAT SOOKSHMA UDYAM SURAKSHA
- BHARAT LAGHU UDYAM SURAKSHA
- BHARAT GRIHA RAKSHA POLICY - LTD

### 7. **Health Insurance Details** (NEW)
For health insurance policies, additional details are saved:

**Main Health Details:**
- Plan Type (FLOATER, INDIVIDUAL, TOPUP_FLOATER, TOPUP_INDIVIDUAL)
- Floater Sum Insured
- Floater Bonus
- Floater Deductible

**Individual Member Details:**
- Member Name
- Individual Sum Insured
- Individual Bonus
- Individual Deductible

Multiple members are saved with all their details.

## Database Schema

### Main Policy History Table
```sql
CREATE TABLE public.policy_history (
    history_id SERIAL PRIMARY KEY,
    original_policy_id INTEGER NOT NULL,
    client_id TEXT NOT NULL,
    member_id INTEGER NOT NULL,
    insurance_company TEXT,
    product_name TEXT,
    policy_number TEXT,
    one_time_insurance BOOLEAN DEFAULT false,
    commission_received BOOLEAN DEFAULT false,
    file_path TEXT,
    drive_file_id TEXT,
    drive_path TEXT,
    drive_url TEXT,
    payment_date DATE,
    agent_name TEXT,
    policy_from DATE,
    policy_to DATE,
    payment_details TEXT,
    net_premium NUMERIC(10,2),
    addon_premium NUMERIC(10,2),
    tp_tr_premium NUMERIC(10,2),
    gst_percentage NUMERIC(5,2),
    gross_premium NUMERIC(10,2),
    commission_percentage NUMERIC(5,2),
    commission_amount NUMERIC(10,2),
    business_type TEXT,
    group_name TEXT,
    subgroup_name TEXT,
    remarks TEXT,
    sum_insured NUMERIC(12,2),
    last_reminder_sent TIMESTAMP WITH TIME ZONE,
    renewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,  -- NEW
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    archived_reason TEXT DEFAULT 'renewal',
    archived_by TEXT,
    CONSTRAINT fk_policy_history_original_policy 
        FOREIGN KEY (original_policy_id) 
        REFERENCES policies(policy_id) 
        ON DELETE CASCADE
);
```

### Factory Insurance History Table (NEW)
```sql
CREATE TABLE public.policy_history_factory_details (
    history_factory_id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL,
    building NUMERIC,
    plant_machinery NUMERIC,
    furniture_fittings NUMERIC,
    stocks NUMERIC,
    electrical_installations NUMERIC,
    CONSTRAINT fk_history_factory_history_id 
        FOREIGN KEY (history_id) 
        REFERENCES policy_history(history_id) 
        ON DELETE CASCADE
);
```

### Health Insurance History Table (NEW)
```sql
CREATE TABLE public.policy_history_health_details (
    history_health_id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL,
    plan_type TEXT CHECK (plan_type = ANY (ARRAY['FLOATER', 'INDIVIDUAL', 'TOPUP_FLOATER', 'TOPUP_INDIVIDUAL'])),
    floater_sum_insured NUMERIC,
    floater_bonus NUMERIC,
    floater_deductible NUMERIC,
    CONSTRAINT fk_history_health_history_id 
        FOREIGN KEY (history_id) 
        REFERENCES policy_history(history_id) 
        ON DELETE CASCADE
);
```

### Health Insurance Members History Table (NEW)
```sql
CREATE TABLE public.policy_history_health_members (
    history_member_id SERIAL PRIMARY KEY,
    history_health_id INTEGER NOT NULL,
    member_name TEXT NOT NULL,
    sum_insured NUMERIC,
    bonus NUMERIC,
    deductible NUMERIC,
    CONSTRAINT fk_history_health_member_health_id 
        FOREIGN KEY (history_health_id) 
        REFERENCES policy_history_health_details(history_health_id) 
        ON DELETE CASCADE
);
```

## How It Works

### 1. Automatic Archiving
When a policy is renewed or updated, the system automatically:
1. Copies all policy data to `policy_history` table
2. If factory insurance exists, copies to `policy_history_factory_details`
3. If health insurance exists, copies to `policy_history_health_details` and `policy_history_health_members`
4. Records who archived it and why
5. Timestamps the archive action

### 2. Database Function
The enhanced `archive_policy_data()` function handles everything:

```sql
SELECT archive_policy_data(
    p_policy_id := 123,
    p_reason := 'renewal',
    p_archived_by := 'admin@example.com'
);
```

This single function call:
- ✅ Archives main policy data
- ✅ Archives factory insurance details (if applicable)
- ✅ Archives health insurance details (if applicable)
- ✅ Archives all health insurance members (if applicable)
- ✅ Returns the history_id for reference

### 3. Excel Export
The Excel sync service automatically includes policy history with:
- All basic policy fields
- Factory insurance columns (if data exists)
- Health insurance columns (if data exists)
- Health members as a formatted string
- Proper date formatting (DD/MM/YYYY)
- Boolean values as Yes/No

## Migration Steps

### Step 1: Run the Enhancement Migration
Execute the SQL migration file in your Supabase SQL editor:

```bash
# File: policy_history_enhancement_migration.sql
```

This will:
1. Add `updated_at` column to `policy_history` table
2. Create `policy_history_factory_details` table
3. Create `policy_history_health_details` table
4. Create `policy_history_health_members` table
5. Update the `archive_policy_data()` function
6. Create necessary indexes
7. Grant permissions

### Step 2: Verify Tables Created
Run this query to verify:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_name LIKE 'policy_history%' 
AND table_schema = 'public';
```

Expected results:
- policy_history
- policy_history_factory_details
- policy_history_health_details
- policy_history_health_members

### Step 3: Test the Archive Function
Test with an existing policy:

```sql
-- Test with a regular policy
SELECT archive_policy_data(1, 'test', 'admin@test.com');

-- Test with a factory insurance policy
SELECT archive_policy_data(2, 'test', 'admin@test.com');

-- Test with a health insurance policy
SELECT archive_policy_data(3, 'test', 'admin@test.com');
```

### Step 4: Verify Data Archived
Check that data was archived correctly:

```sql
-- Check main policy history
SELECT * FROM policy_history WHERE archived_reason = 'test';

-- Check factory details (if applicable)
SELECT ph.policy_number, phf.*
FROM policy_history ph
LEFT JOIN policy_history_factory_details phf ON ph.history_id = phf.history_id
WHERE ph.archived_reason = 'test';

-- Check health details (if applicable)
SELECT ph.policy_number, phh.*, phm.member_name
FROM policy_history ph
LEFT JOIN policy_history_health_details phh ON ph.history_id = phh.history_id
LEFT JOIN policy_history_health_members phm ON phh.history_health_id = phm.history_health_id
WHERE ph.archived_reason = 'test';
```

### Step 5: Restart Application
The Excel sync service changes are already in place. Just restart:

```bash
# For production
sudo systemctl restart insurance-portal

# For development
python app_multiuser.py
```

## Excel Export Fields

The Policy History sheet in Excel now includes:

### Standard Fields
- History ID, Original Policy ID
- Client ID, Member ID
- Insurance Company, Product Name, Policy Number
- Payment Date, Agent Name
- Policy Start Date, Policy End Date
- Payment Details
- Net Premium, Addon Premium, TP/TR Premium
- GST %, Gross Premium
- Commission %, Commission Amount
- Business Type, Group Name, Subgroup Name
- Remarks, Sum Insured
- One Time Insurance, Commission Received
- File Path, Drive File ID, Drive Path, Drive URL
- Last Reminder Sent, Renewed At
- Created At, Updated At
- Archived At, Archived Reason, Archived By

### Factory Insurance Fields (if applicable)
- Factory - Building
- Factory - Plant & Machinery
- Factory - Furniture & Fittings
- Factory - Stocks
- Factory - Electrical Installations

### Health Insurance Fields (if applicable)
- Health - Plan Type
- Health - Floater Sum Insured
- Health - Floater Bonus
- Health - Floater Deductible
- Health - Insured Members (formatted list)

## Usage Examples

### Example 1: Renewing a Regular Policy
When you renew a regular motor insurance policy:
```
✅ Main policy data archived
❌ No factory details (not applicable)
❌ No health details (not applicable)
```

### Example 2: Renewing a Factory Insurance Policy
When you renew a factory insurance policy:
```
✅ Main policy data archived
✅ Factory details archived (building, machinery, etc.)
❌ No health details (not applicable)
```

### Example 3: Renewing a Health Insurance Policy
When you renew a health insurance policy:
```
✅ Main policy data archived
❌ No factory details (not applicable)
✅ Health details archived (plan type, floater details)
✅ All insured members archived (names, sum insured, bonus)
```

## Benefits

### Complete Audit Trail
- Every policy change is tracked with full details
- Know exactly what values were before renewal
- Track who made changes and when

### Compliance and Reporting
- Generate historical reports
- Compare policy values over time
- Audit commission calculations

### Data Integrity
- No data loss during renewals
- Complete historical record
- Easy to trace policy evolution

### Business Intelligence
- Analyze premium trends
- Track commission patterns
- Understand policy modifications

## Troubleshooting

### Issue: Factory/Health details not showing in Excel
**Solution:** Make sure the new tables exist:
```sql
SELECT * FROM policy_history_factory_details LIMIT 1;
SELECT * FROM policy_history_health_details LIMIT 1;
```

### Issue: Archive function fails
**Solution:** Check permissions:
```sql
GRANT EXECUTE ON FUNCTION archive_policy_data(INTEGER, TEXT, TEXT) TO authenticated;
```

### Issue: Missing updated_at column
**Solution:** Add the column manually:
```sql
ALTER TABLE policy_history ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;
```

## Summary

The enhanced policy history system now captures:
- ✅ **ALL** standard policy fields (including updated_at)
- ✅ **Factory insurance** details (5 additional fields)
- ✅ **Health insurance** details (4 floater fields + all members)
- ✅ Complete audit trail with timestamps and user tracking
- ✅ Automatic Excel export with all fields
- ✅ Proper formatting and display

**No policy data is lost during renewals or updates!**
