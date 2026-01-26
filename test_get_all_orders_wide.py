#!/usr/bin/env python3
"""
Test get_all_orders_wide function
"""
import sys
sys.path.insert(0, '/Users/jennifer_home/Documents/08d_GSCookies/gscookies')

from utils.order_utils import get_all_orders_wide
import datetime

# Test with 2025
for year in [2025, datetime.datetime.now().year]:
    print(f"\nTesting get_all_orders_wide() for year {year}...")

    try:
        df = get_all_orders_wide(year)
        print(f"✓ Success! Got {len(df)} orders")
        print(f"✓ Columns: {list(df.columns)}")
        
        if len(df) > 0:
            print(f"\n✓ First order (showing first 5 columns):")
            print(df.iloc[0, :5])
        else:
            print("  (No orders in this year)")
            
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
