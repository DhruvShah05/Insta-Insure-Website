# Simplified Pending Renewal System - Implementation Summary

## Overview
Implemented a simplified pending renewal tracking system using a boolean flag instead of a separate table. This system tracks policies where payment has been received but the insurance company hasn't issued the new policy details yet.

## Use Case
- Client pays insurance company for renewal
- Insurance company hasn't issued new policy details or PDF yet
- Need to track and follow up with the company
- Once company provides everything → complete the renewal

## Database Changes

### Migration File: `add_pending_renewal_flag.sql`
```sql
ALTER TABLE policies ADD COLUMN IF NOT EXISTS is_pending_renewal BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_policies_pending_renewal ON policies(is_pending_renewal);
```

**Run this migration in Supabase SQL Editor before using the feature!**

## Implementation Details

### 1. Marking Policy as Pending Renewal
**Endpoint:** `POST /api/mark_pending_renewal`
- Takes: `policy_id`, `new_policy_from`, `new_policy_to`
- Updates policy with new dates
- Sets `is_pending_renewal = TRUE`
- Policy disappears from dashboard

### 2. Pending Renewals Page (`/pending_renewals`)
- Shows only policies where `is_pending_renewal = TRUE`
- Displays: Policy ID, Customer, Company, Product, New Expiry Date, Days Pending
- Actions:
  - **Complete Renewal** → Redirects to renewal page
  - **Remove** → Clears pending flag

### 3. Dashboard Changes
- **Excludes** policies with `is_pending_renewal = TRUE`
- Only shows active policies
- Pending policies tracked separately

### 4. Renewal Completion
- When renewal is completed via renewal page:
  - Archives old policy data to history
  - Archives old PDF to Drive Archive folder
  - Uploads new PDF
  - Updates all policy details
  - **Sets `is_pending_renewal = FALSE`**
  - Policy reappears in dashboard

### 5. Removed Features
- Deleted old `pending_renewals` table logic
- Removed "Skip PDF" checkbox from renewal page
- Simplified to single-flag approach

## Files Modified

### Backend Routes:
1. **`routes/pending_renewals.py`** - Completely rewritten
   - `list_pending_renewals()` - Query policies with flag
   - `complete_pending_renewal()` - Redirect to renewal page
   - `remove_from_pending()` - Clear pending flag

2. **`routes/renewal_routes.py`**
   - Added `mark_pending_renewal()` API endpoint

3. **`routes/dashboard.py`**
   - Updated query to exclude `is_pending_renewal = TRUE`

4. **`renewal_service.py`**
   - Added `is_pending_renewal: False` to renewal update data

### Frontend Templates:
1. **`templates/pending_renewals.html`**
   - Updated to work with policy records
   - Removed pending_renewal_id references
   - Updated action buttons

2. **`templates/renewal_page.html`** (TO BE UPDATED)
   - Remove "Skip PDF" checkbox section

3. **`templates/dashboard.html`** (TO BE UPDATED)
   - Add "Mark as Pending Renewal" option to modal

## Workflow

```
1. Dashboard → "Renewal Paid" button
   ↓
2. Modal shows: Enter new from/to dates
   ↓
3. Click "Mark as Pending Renewal"
   ↓
4. Policy updated: new dates + is_pending_renewal=TRUE
   ↓
5. Policy disappears from Dashboard
   ↓
6. Policy appears in "Pending Renewals" page
   ↓
7. [Wait for insurance company to issue policy...]
   ↓
8. Click "Complete Renewal" → Goes to renewal page
   ↓
9. Upload PDF + Edit all details → Submit
   ↓
10. Archives old policy + PDF, uploads new PDF
   ↓
11. Sets is_pending_renewal=FALSE
   ↓
12. Policy reappears in Dashboard as active
```

## Benefits

✅ **Simple** - Single boolean flag instead of complex table
✅ **Clean** - No data duplication
✅ **Trackable** - Easy to see which policies are pending
✅ **Flexible** - Can update dates before completion
✅ **Integrated** - Works with existing renewal workflow

## Next Steps (TODO)

1. ✅ Run database migration
2. ⏳ Update dashboard modal to add "Mark as Pending" option
3. ⏳ Remove "Skip PDF" checkbox from renewal page
4. ⏳ Test complete workflow
5. ⏳ Update navigation/sidebar if needed

## Notes

- Old PDF stays attached until renewal is completed
- All archiving happens during completion (not when marking as pending)
- Pending policies don't show in dashboard to avoid confusion
- Days pending calculated from `updated_at` timestamp
