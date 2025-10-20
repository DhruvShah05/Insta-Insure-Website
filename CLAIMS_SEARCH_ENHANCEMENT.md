# Claims Search Enhancement

## Overview
Enhanced the claims management system to support searching by client and then by policy of that client, in addition to the existing policy number search functionality.

## Changes Made

### 1. Backend API Endpoints (routes/claims.py)

#### New API Endpoints Added:

**`/claims/api/search-clients`**
- **Purpose**: Search for clients by name with autocomplete functionality
- **Method**: GET
- **Parameters**: `search` (minimum 2 characters)
- **Returns**: JSON array of matching clients with `client_id` and `name`
- **Features**: Case-insensitive search, limited to 10 results

**`/claims/api/client-policies`**
- **Purpose**: Get all policies for a specific client
- **Method**: GET
- **Parameters**: `client_id` (required)
- **Returns**: JSON array of policies with policy details and associated members
- **Features**: Handles both regular and health insurance policies

### 2. Enhanced Claims Index Route

**Updated `/claims/` route**
- Added support for filtering by `client_id`, `policy_number`, and general `search`
- Enhanced query building with proper Supabase filtering
- Added text search across claim numbers, member names, client names, and policy numbers
- Returns additional context variables for template rendering

### 3. Frontend Enhancements (templates/claims.html)

#### New Search Interface:
- **General Search**: Text input for searching across all claim fields
- **Client Search**: Autocomplete input with dropdown results
- **Policy Selection**: Dynamic dropdown populated based on selected client
- **Filter Display**: Shows active filters with clear options

#### JavaScript Functionality:
- Real-time client search with debouncing (300ms delay)
- Dynamic policy loading based on client selection
- Proper handling of template variables and form state
- Click-outside-to-close functionality for dropdowns

### 4. User Experience Improvements

#### Search Capabilities:
1. **General Search**: Search by claim number, member name, client name, or policy number
2. **Client-First Search**: 
   - Type client name to get autocomplete suggestions
   - Select client to see their policies
   - Choose specific policy or view all policies for that client
3. **Combined Filtering**: Use multiple search criteria together

#### Visual Feedback:
- Loading states for dynamic content
- Clear filter indicators
- Responsive design for different screen sizes
- Hover effects and proper styling

## Usage Instructions

### For End Users:

1. **General Search**:
   - Use the "General Search" field to search across all claims
   - Enter claim number, member name, client name, or policy number

2. **Client-Based Search**:
   - Start typing in the "Search by Client" field
   - Select a client from the dropdown suggestions
   - Choose a specific policy from the "Select Policy" dropdown
   - Click "Search" to filter results

3. **Clearing Filters**:
   - Click the "Clear" button to reset all filters
   - Or click "Clear Filter" when viewing filtered results

### For Developers:

#### API Usage:
```javascript
// Search clients
fetch('/claims/api/search-clients?search=client_name')
  .then(response => response.json())
  .then(data => console.log(data.clients));

// Get client policies
fetch('/claims/api/client-policies?client_id=CLIENT001')
  .then(response => response.json())
  .then(data => console.log(data.policies));
```

#### URL Parameters:
- `?search=term` - General text search
- `?client_id=CLIENT001` - Filter by specific client
- `?policy_number=POL001` - Filter by specific policy
- Combine parameters: `?client_id=CLIENT001&policy_number=POL001`

## Database Requirements

The enhancement works with the existing database structure:
- `clients` table with `client_id` and `name` fields
- `policies` table with relationships to clients and members
- `claims` table with relationships to policies
- `health_insurance_details` and `health_insured_members` for health policies

## Testing

A test script `test_claims_search.py` has been created to verify the functionality:
- Tests client search API
- Tests client policies API  
- Tests claims filtering with various parameters

## Benefits

1. **Improved User Experience**: Easier to find claims for specific clients
2. **Flexible Search Options**: Multiple ways to search and filter claims
3. **Scalability**: Efficient database queries with proper filtering
4. **Maintainability**: Clean separation of API endpoints and frontend logic
5. **Performance**: Debounced search requests and limited result sets

## Future Enhancements

Potential improvements for future versions:
- Add search by date ranges
- Include claim status filtering in the search interface
- Add export functionality for filtered results
- Implement pagination for large result sets
- Add search history/favorites functionality
