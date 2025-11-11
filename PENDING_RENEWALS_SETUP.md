# Pending Renewals Feature - Setup Guide

## ✅ Changes Made

### 1. Simplified Renewal Page
- **Removed** "New Expiry Date" and "New Policy Number" fields from Step 1
- These can now be edited directly in Step 2 (Edit Details section)
- Only PDF upload and checkbox remain in Step 1

### 2. Navigation Added
- **Pending Renewals** link added to sidebar navigation
- Located under "Management" section, right after "Pending Policies"
- Icon: Circular arrows (renewal symbol)

## 🚀 Setup Instructions

### Step 1: Run SQL Migration
Execute the SQL script in your Supabase database:

1. Open Supabase SQL Editor
2. Copy and paste the contents of `pending_renewals_migration.sql`
3. Click "Run" to create the tables:
   - `pending_renewals`
   - `pending_renewal_health_insurance_details`
   - `pending_renewal_health_insured_members`
   - `pending_renewal_factory_insurance_details`

### Step 2: Start Your Server
```bash
start_optimized.bat
```

That's it! The feature is now ready to use.

## 📍 How to Access

### From Sidebar Navigation:
1. Look for **"Pending Renewals"** in the left sidebar
2. It's under the "Management" section
3. Click to view all pending renewals

### From Renewal Page:
1. Go to any policy's renewal page
2. Check the box: "Skip PDF upload and edit details now"
3. Click "Create Pending Renewal & Edit Details"
4. Edit all details in Step 2
5. Later, go to Pending Renewals page to upload PDF

## 🔄 Workflow

### Option A: Create Pending Renewal (No PDF)
1. Policy Renewal Page → Check "Skip PDF upload"
2. Click "Create Pending Renewal & Edit Details"
3. Edit all policy details in Step 2
4. Go to **Pending Renewals** page (from sidebar)
5. Click "Complete Renewal"
6. Upload PDF → Finalize renewal
7. Notifications sent (if checkbox checked)

### Option B: Normal Renewal (With PDF)
1. Policy Renewal Page → Upload PDF
2. Click "Upload & Archive Old Policy"
3. Edit details in Step 2 (if needed)
4. Done!

## 📋 Features

✅ Same Google Drive upload logic (with credential refresh)
✅ Same Supabase operations
✅ Copies all policy data (health, factory details, etc.)
✅ Two-step process: Create pending → Upload PDF later
✅ Notifications only sent when completing renewal
✅ Clean UI with checkbox toggle
✅ Accessible from sidebar navigation
✅ Edit expiry date and policy number in Step 2

## 🗂️ Files Modified

### Backend:
- `routes/pending_renewals.py` (NEW)
- `routes/renewal_routes.py` (MODIFIED)
- `app.py` (MODIFIED)

### Frontend:
- `templates/pending_renewals.html` (NEW)
- `templates/complete_pending_renewal.html` (NEW)
- `templates/renewal_page.html` (MODIFIED)
- `templates/base.html` (MODIFIED - added navigation link)

### Database:
- `pending_renewals_migration.sql` (NEW)

## 🎯 URLs

- Pending Renewals List: `http://localhost:5050/pending_renewals`
- Complete Renewal: `http://localhost:5050/complete_pending_renewal/<id>`
- Policy Renewal: `http://localhost:5050/renewal_page/<policy_id>`

## ⚠️ Important Notes

1. **Run SQL migration first** before starting the server
2. The feature uses the same Drive upload logic as existing policies
3. All policy fields can be edited in Step 2 (including expiry date and policy number)
4. Pending renewals are listed in the sidebar under "Management"
5. Notifications (WhatsApp/Email) are only sent when completing the renewal, not when creating pending renewal
