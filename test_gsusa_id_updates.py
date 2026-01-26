#!/usr/bin/env python3
"""
Test script to verify GSUSA ID updates in scouts table
"""
from utils.db_utils import fetch_all

# Test data: expected GSUSA IDs and scout names
EXPECTED_DATA = [
    {"gsusa_id": "216409382", "first_name": "Brooklyn", "last_name": "Alicia"},
    {"gsusa_id": "216321976", "first_name": "Victoria", "last_name": "Schofield"},
    {"gsusa_id": "215835733", "first_name": "Esther", "last_name": "Hoar"},
    {"gsusa_id": "215831030", "first_name": "Alicia", "last_name": "Pina"},
    {"gsusa_id": "215689229", "first_name": "Riley", "last_name": "Howes"},
    {"gsusa_id": "215423464", "first_name": "Mckenzie", "last_name": "Davis"},
    {"gsusa_id": "215369223", "first_name": "Brooklyn", "last_name": "Berry"},
    {"gsusa_id": "215310722", "first_name": "Brooklyn", "last_name": "Berry"},
    {"gsusa_id": "213770058", "first_name": "Alicia", "last_name": "Pina"},
    {"gsusa_id": "213718887", "first_name": "Hazel", "last_name": "Hoar"},
    {"gsusa_id": "213288425", "first_name": "Esther", "last_name": "Hoar"},
    {"gsusa_id": "213269965", "first_name": "Hazel", "last_name": "Hoar"},
    {"gsusa_id": "212797153", "first_name": "Alicia", "last_name": "Pina"},
    {"gsusa_id": "212154848", "first_name": "Hazel", "last_name": "Hoar"},
    {"gsusa_id": "211209767", "first_name": "Kayla", "last_name": "Callison"},
]

def test_gsusa_id_updates():
    """Verify that GSUSA IDs are correctly stored in the scouts table"""
    
    print("Testing GSUSA ID Updates in Scouts Table")
    print("=" * 60)
    
    passed = 0
    failed = 0
    not_found = 0
    
    for expected in EXPECTED_DATA:
        # Query for scout by name
        result = fetch_all("""
            SELECT scout_id, first_name, last_name, gsusa_id
            FROM cookies_app.scouts
            WHERE first_name = :first_name 
              AND last_name = :last_name
        """, {
            "first_name": expected["first_name"],
            "last_name": expected["last_name"]
        })
        
        if not result:
            print(f"❌ NOT FOUND: {expected['first_name']} {expected['last_name']}")
            not_found += 1
            continue
        
        scout = result[0]
        actual_gsusa_id = scout.gsusa_id
        expected_gsusa_id = expected["gsusa_id"]
        
        if actual_gsusa_id == expected_gsusa_id:
            print(f"✓ PASS: {expected['first_name']} {expected['last_name']} - GSUSA ID: {actual_gsusa_id}")
            passed += 1
        else:
            print(f"✗ FAIL: {expected['first_name']} {expected['last_name']}")
            print(f"   Expected: {expected_gsusa_id}")
            print(f"   Actual:   {actual_gsusa_id}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {not_found} not found")
    print(f"Total:   {passed + failed + not_found} scouts tested")
    
    if failed > 0 or not_found > 0:
        print("\n⚠️  Some tests did not pass")
        return False
    else:
        print("\n✅ All tests passed!")
        return True

if __name__ == "__main__":
    test_gsusa_id_updates()
