"""
Test script to check pending renewals in database
"""
from supabase import create_client
from dynamic_config import Config

def test_pending_renewals():
    print("=" * 60)
    print("TESTING PENDING RENEWALS")
    print("=" * 60)
    
    # Initialize Supabase client
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    # Test 1: Count all policies
    print("\n1. Counting all policies...")
    all_policies = supabase.table("policies").select("policy_id, is_pending_renewal", count="exact").execute()
    print(f"   Total policies: {all_policies.count if hasattr(all_policies, 'count') else len(all_policies.data)}")
    
    # Test 2: Check is_pending_renewal column values
    print("\n2. Checking is_pending_renewal values...")
    sample = supabase.table("policies").select("policy_id, is_pending_renewal").limit(5).execute()
    for policy in sample.data:
        print(f"   Policy {policy['policy_id']}: is_pending_renewal = {policy.get('is_pending_renewal')}")
    
    # Test 3: Count pending renewals (True)
    print("\n3. Counting policies with is_pending_renewal = True...")
    pending_true = supabase.table("policies").select("*", count="exact").eq("is_pending_renewal", True).execute()
    print(f"   Pending renewals (True): {pending_true.count if hasattr(pending_true, 'count') else len(pending_true.data)}")
    if pending_true.data:
        print(f"   Sample data: {pending_true.data[0]}")
    
    # Test 4: Count non-pending (False or NULL)
    print("\n4. Counting policies with is_pending_renewal = False...")
    pending_false = supabase.table("policies").select("policy_id", count="exact").eq("is_pending_renewal", False).execute()
    print(f"   Non-pending (False): {pending_false.count if hasattr(pending_false, 'count') else len(pending_false.data)}")
    
    # Test 5: Check for NULL values
    print("\n5. Checking for NULL is_pending_renewal values...")
    pending_null = supabase.table("policies").select("policy_id", count="exact").is_("is_pending_renewal", "null").execute()
    print(f"   NULL values: {pending_null.count if hasattr(pending_null, 'count') else len(pending_null.data)}")
    
    # Test 6: Try the exact query from pending_renewals route
    print("\n6. Testing exact query from pending_renewals route...")
    try:
        result = (
            supabase.table("policies")
            .select("*, clients!policies_client_id_fkey(*), members!policies_member_id_fkey(*)")
            .eq("is_pending_renewal", True)
            .order("policy_to", desc=True)
            .execute()
        )
        print(f"   Query successful! Found {len(result.data)} records")
        if result.data:
            print(f"   First record: Policy ID {result.data[0]['policy_id']}")
    except Exception as e:
        print(f"   ❌ Query failed: {e}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    if pending_true.count == 0 or len(pending_true.data) == 0:
        print("⚠ No policies have is_pending_renewal = True")
        print("  → You need to mark a policy as pending renewal first!")
        print("  → Go to dashboard → Click 'Mark as Pending Renewal' on a policy")
    else:
        print("✓ Found pending renewals in database")
        print("  → If page still shows empty, check:")
        print("    1. Are you logged in?")
        print("    2. Is the correct app file running?")
        print("    3. Check browser console for errors")
    
    print("=" * 60)

if __name__ == "__main__":
    test_pending_renewals()
