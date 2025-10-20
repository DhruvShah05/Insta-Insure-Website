#!/usr/bin/env python3
"""
Test script for the new claims search functionality
"""

import requests
import json
from config import Config

# Test configuration
BASE_URL = "http://localhost:5000"  # Adjust if your app runs on a different port

def test_client_search():
    """Test the client search API endpoint"""
    print("Testing client search API...")
    
    # Test with a sample search term
    search_term = "test"  # You can modify this based on your test data
    
    try:
        response = requests.get(f"{BASE_URL}/claims/api/search-clients", 
                              params={"search": search_term})
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Client search successful: Found {len(data.get('clients', []))} clients")
            if data.get('clients'):
                print(f"  Sample client: {data['clients'][0]}")
        else:
            print(f"✗ Client search failed: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed. Make sure the Flask app is running on port 5000")
    except Exception as e:
        print(f"✗ Error testing client search: {e}")

def test_client_policies():
    """Test the client policies API endpoint"""
    print("\nTesting client policies API...")
    
    # You'll need to replace this with an actual client_id from your database
    test_client_id = "CLIENT001"  # Modify this based on your test data
    
    try:
        response = requests.get(f"{BASE_URL}/claims/api/client-policies", 
                              params={"client_id": test_client_id})
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Client policies successful: Found {len(data.get('policies', []))} policies")
            if data.get('policies'):
                print(f"  Sample policy: {data['policies'][0]}")
        else:
            print(f"✗ Client policies failed: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed. Make sure the Flask app is running on port 5000")
    except Exception as e:
        print(f"✗ Error testing client policies: {e}")

def test_claims_filtering():
    """Test the claims page with filtering parameters"""
    print("\nTesting claims filtering...")
    
    test_cases = [
        {"search": "test"},
        {"client_id": "CLIENT001"},
        {"policy_number": "POL001"},
    ]
    
    for params in test_cases:
        try:
            response = requests.get(f"{BASE_URL}/claims/", params=params)
            
            if response.status_code == 200:
                print(f"✓ Claims filtering with {params} successful")
            else:
                print(f"✗ Claims filtering with {params} failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("✗ Connection failed. Make sure the Flask app is running on port 5000")
            break
        except Exception as e:
            print(f"✗ Error testing claims filtering with {params}: {e}")

if __name__ == "__main__":
    print("Claims Search Functionality Test")
    print("=" * 40)
    
    print("\nNOTE: Make sure to:")
    print("1. Start your Flask application (python app.py)")
    print("2. Update the test_client_id in this script with a real client ID from your database")
    print("3. Ensure you have test data in your database")
    
    print("\nRunning tests...")
    
    test_client_search()
    test_client_policies()
    test_claims_filtering()
    
    print("\nTest completed!")
    print("\nTo manually test the UI:")
    print("1. Go to http://localhost:5000/claims/")
    print("2. Try the new search functionality:")
    print("   - Use the 'General Search' field to search across all claims")
    print("   - Use the 'Search by Client' field to find and select a specific client")
    print("   - After selecting a client, choose a specific policy from the dropdown")
    print("   - Click 'Search' to filter results")
