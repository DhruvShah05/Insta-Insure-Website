# Policy History Implementation Guide

## Overview
This implementation adds a comprehensive policy history system that preserves all historical data whenever a policy is renewed or updated. Instead of overwriting existing data, the system now:

1. **Saves old policy data** to a dedicated `policy_history` table
2. **Archives old policy documents** to Google Drive Archive folder
3. **Updates current policy** with new information
4. **Maintains audit trail** with user information and timestamps

## Database Changes

### New Table: `policy_history`
- **File**: `policy_history_migration.sql`
- **Purpose**: Stores complete historical snapshots of policies before renewal/update
- **Key Features**:
  - Mirrors all fields from the main `policies` table
  - Adds metadata fields: `archived_at`, `archived_reason`, `archived_by`
  - Includes database function `archive_policy_data()` for easy archiving
  - Proper indexing for performance

### Migration Steps
1. Run the SQL migration file in your Supabase SQL editor:
   ```sql
   -- Execute the contents of policy_history_migration.sql
   ```

## Code Changes

### 1. Enhanced Renewal Service (`renewal_service.py`)

#### New Functions:
- `archive_policy_to_history(policy_id, archived_by)`: Archives current policy data to history table
- `get_policy_historical_data(policy_id)`: Retrieves all historical records for a policy
- `get_policy_with_history(policy_id)`: Gets current policy + complete history

#### Updated Functions:
- `renew_policy()`: Now accepts `archived_by` parameter and archives data before renewal
- `update_policy_payment()`: Now accepts `archived_by` parameter and archives data before update

### 2. Enhanced Routes (`routes/renewal_routes.py`)

#### New API Endpoints:
- `GET /api/get_policy_history/<policy_id>`: Get historical data for a policy
- `GET /api/get_policy_with_history/<policy_id>`: Get current + historical data
- `GET /policy_history/<policy_id>`: Web page to view policy history

#### Updated Endpoints:
- `POST /api/renew_policy`: Now passes current user email for audit trail
- `POST /api/update_policy_payment`: Now passes current user email for audit trail

### 3. New Template (`templates/policy_history.html`)
- **Purpose**: Web interface to view policy history
- **Features**:
  - Timeline view of all policy versions
  - Current version highlighted
  - Historical versions with archive metadata
  - Comparison of key fields across versions
  - Responsive design with Bootstrap

## How It Works

### When a Policy is Renewed:
1. **Archive Current Data**: Copy all current policy fields to `policy_history` table
2. **Archive Document**: Move current PDF to Archive folder in Google Drive
3. **Update Policy**: Replace current policy data with new information
4. **Upload New Document**: Upload new PDF to current location
5. **Audit Trail**: Record who performed the action and when

### Data Flow Example:
```
Original Policy (ID: 123)
├── Insurance Company: "ABC Insurance"
├── Premium: ₹10,000
├── Expiry: 2024-12-31
└── Document: policy_123.pdf

RENEWAL PROCESS:
├── Step 1: Copy to policy_history table
│   ├── original_policy_id: 123
│   ├── insurance_company: "ABC Insurance"
│   ├── net_premium: 10000
│   ├── archived_at: 2024-01-15 10:30:00
│   └── archived_by: "user@company.com"
├── Step 2: Archive document to Archive/2024-25/CLIENT_ID/MEMBER_NAME/
├── Step 3: Update current policy
│   ├── insurance_company: "XYZ Insurance"
│   ├── net_premium: 12000
│   └── policy_to: 2025-12-31
└── Step 4: Upload new document
```

## API Usage Examples

### Get Policy History
```javascript
fetch('/api/get_policy_history/123')
  .then(response => response.json())
  .then(data => {
    console.log(`Found ${data.total_records} historical records`);
    data.history.forEach(record => {
      console.log(`Version from ${record.archived_at}: ${record.insurance_company}`);
    });
  });
```

### Get Policy with Complete History
```javascript
fetch('/api/get_policy_with_history/123')
  .then(response => response.json())
  .then(data => {
    console.log('Current Policy:', data.data.current_policy);
    console.log('Historical Versions:', data.data.history);
    console.log('Total Versions:', data.data.total_versions);
  });
```

## Benefits

### 1. **Data Preservation**
- Never lose historical policy information
- Complete audit trail of all changes
- Ability to reference previous terms and conditions

### 2. **Compliance & Reporting**
- Track policy evolution over time
- Generate historical reports
- Meet regulatory requirements for data retention

### 3. **Customer Service**
- Answer customer queries about previous policy terms
- Compare current vs previous coverage
- Resolve disputes with historical evidence

### 4. **Business Intelligence**
- Analyze renewal patterns
- Track premium changes over time
- Identify trends in policy modifications

## Accessing Historical Data

### Via Web Interface:
1. Navigate to any policy in the system
2. Click "View History" or visit `/policy_history/<policy_id>`
3. View timeline of all policy versions
4. Compare current vs historical data

### Via API:
- Use the new API endpoints to integrate with other systems
- Build custom reports and dashboards
- Export historical data for analysis

## File Organization

### Google Drive Structure:
```
Root Folder/
├── CLIENT_ID/
│   └── MEMBER_NAME/
│       └── current_policy.pdf (active document)
└── Archive/
    └── 2024-25/ (financial year)
        └── CLIENT_ID/
            └── MEMBER_NAME/
                ├── policy_ARCHIVED_20240115_103000.pdf
                └── policy_ARCHIVED_20240601_143000.pdf
```

## Security & Permissions

### Database Security:
- Historical data is read-only after creation
- Proper foreign key constraints prevent orphaned records
- Row-level security can be added if needed

### Access Control:
- All history endpoints require authentication (`@login_required`)
- Audit trail tracks which user performed each action
- Historical data cannot be modified, only viewed

## Excel Integration

### Enhanced Excel Export System
The policy history system is fully integrated with your existing Excel export functionality:

#### 1. **Policy History Sheet in Main Export**
- **Location**: Added as new "Policy History" sheet in your main `insurance_data.xlsx`
- **Content**: All historical policy records with proper formatting
- **Columns**: Optimized order with key fields first (history_id, original_policy_id, client_id, etc.)
- **Formatting**: Dates formatted as YYYY-MM-DD, currency fields rounded to 2 decimals

#### 2. **Dedicated Policy History Reports**
- **API Endpoint**: `POST /api/excel/policy-history-report`
- **Filtering Options**:
  - Specific policy ID
  - Specific client ID  
  - Date range (archived_at field)
- **Multiple Sheets**:
  - **Summary**: Overview statistics and metrics
  - **Policy History Details**: Complete historical data
  - **Policy Summary**: Grouped analysis by policy

#### 3. **Report Features**
```javascript
// Generate filtered report
fetch('/api/excel/policy-history-report', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    policy_id: 123,           // Optional: specific policy
    client_id: "CLIENT001",   // Optional: specific client
    date_from: "2024-01-01",  // Optional: start date
    date_to: "2024-12-31"     // Optional: end date
  })
})
```

#### 4. **Enhanced Analytics**
The dedicated reports include:
- **Summary Metrics**: Total records, unique policies, unique clients, date ranges
- **Policy Evolution**: Track how individual policies changed over time
- **Premium Analysis**: Compare original vs latest premiums
- **Company Changes**: See insurance company switches
- **Version Tracking**: Count of versions per policy

### Excel File Structure
```
insurance_data.xlsx
├── Clients
├── Members  
├── Policies
├── Claims
├── Pending Policies
├── Health Insurance Details
├── Factory Insurance Details
└── Policy History (NEW)
    ├── history_id
    ├── original_policy_id
    ├── client_id
    ├── member_id
    ├── insurance_company
    ├── policy_from → policy_to
    ├── net_premium → gross_premium
    ├── archived_at
    ├── archived_reason
    └── archived_by
```

### Dedicated History Reports
```
policy_history_report_YYYYMMDD_HHMMSS.xlsx
├── Summary
│   ├── Total Historical Records
│   ├── Unique Policies
│   ├── Unique Clients
│   ├── Date Range
│   └── Report Generated
├── Policy History Details
│   └── Complete filtered historical data
└── Policy Summary
    ├── Total_Versions per policy
    ├── First_Archived → Last_Archived
    ├── Original_Premium → Latest_Premium
    └── Company_Changes tracking
```

## Future Enhancements

### Possible Additions:
1. **Health Insurance History**: Extend to track health insurance member changes
2. **Factory Insurance History**: Track factory insurance component changes  
3. **Document Versioning**: Link historical documents to specific versions
4. **Comparison Tools**: Side-by-side comparison of any two versions
5. **Restore Functionality**: Ability to restore from historical version
6. **Advanced Excel Features**: Pivot tables, charts, and automated analysis
7. **Scheduled Reports**: Automatic generation of monthly/yearly history reports

## Troubleshooting

### Common Issues:
1. **Migration Fails**: Ensure Supabase permissions are correct
2. **History Not Saving**: Check database function permissions
3. **Documents Not Archiving**: Verify Google Drive API access
4. **Performance Issues**: Ensure indexes are created properly

### Monitoring:
- Check application logs for archiving errors
- Monitor database growth in `policy_history` table
- Verify Google Drive Archive folder structure

## Testing the Implementation

### Manual Testing Steps:
1. **Run Migration**: Execute `policy_history_migration.sql`
2. **Renew a Policy**: Use existing renewal functionality
3. **Check History**: Visit `/policy_history/<policy_id>`
4. **Verify Data**: Confirm historical data is preserved
5. **Test APIs**: Use browser dev tools to test API endpoints

### Verification Checklist:
- [ ] Migration runs successfully
- [ ] Historical data is saved before renewal
- [ ] Current policy is updated correctly
- [ ] Documents are archived properly
- [ ] History page displays correctly
- [ ] API endpoints return expected data
- [ ] Audit trail includes user information

This implementation ensures that your insurance system maintains complete historical records while providing easy access to both current and past policy information.
