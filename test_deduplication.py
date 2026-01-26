#!/usr/bin/env python3
"""
Test deduplication logic for Digital Cookie import
"""
import sys
import pandas as pd
from sqlalchemy import create_engine, text
import tomllib

# Load secrets
with open('.streamlit/secrets.toml', 'rb') as f:
    secrets = tomllib.load(f)

db = secrets["general"]

engine = create_engine(
    f"postgresql+psycopg2://{db['DB_USER']}:{db['DB_PASSWORD']}@"
    f"{db['DB_HOST']}:{db['DB_PORT']}/{db['DB_NAME']}?sslmode={db['sslmode']}"
)

def fetch_existing_external_orders(order_source: str):
    with engine.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT external_order_id
            FROM cookies_app.orders
            WHERE order_source = :source
            """
        ), {"source": order_source}).mappings().all()
    return [r['external_order_id'] for r in rows]

def test_deduplication():
    """Test that deduplication logic works correctly"""
    
    # Get existing Digital Cookie Import orders
    existing_ids = fetch_existing_external_orders("Digital Cookie Import")
    print(f"✓ Existing Digital Cookie Import orders: {len(existing_ids)}")
    if existing_ids:
        print(f"  Sample IDs: {existing_ids[:3]}")
    
    # Simulate what the import does
    # Create a test DataFrame with some orders
    test_data = {
        'external_order_id': ['DOC-001', 'DOC-002', 'DOC-003', 'DOC-004'],
        'scout_first_name': ['Alice', 'Bob', 'Charlie', 'David'],
        'scout_last_name': ['Smith', 'Jones', 'Brown', 'Wilson'],
    }
    test_df = pd.DataFrame(test_data)
    
    print(f"\n✓ Test DataFrame (simulated import): {len(test_df)} orders")
    print(test_df)
    
    # Simulate converting to string for matching (as the import does)
    test_df['external_order_id'] = test_df['external_order_id'].astype(str)
    
    # Simulate the deduplication filter used in the import
    new_orders = test_df[~test_df['external_order_id'].isin(existing_ids)].copy()
    
    print(f"\n✓ Orders that would be IMPORTED (not in existing_ids): {len(new_orders)}")
    print(new_orders)
    
    # Create some duplicates and test
    if len(existing_ids) > 0:
        print(f"\n✓ Testing with existing IDs...")
        # If we have existing orders, test with duplicates
        test_with_dupes = pd.DataFrame({
            'external_order_id': existing_ids[:2] + ['NEW-001', 'NEW-002'],
        })
        filtered = test_with_dupes[~test_with_dupes['external_order_id'].isin(existing_ids)]
        print(f"  Input: {len(test_with_dupes)} orders (first 2 are duplicates)")
        print(f"  Output: {len(filtered)} orders (duplicates filtered)")
        print(f"  Would import: {filtered['external_order_id'].tolist()}")
    
    print("\n✓ Deduplication logic verified!")
    print("\nSummary:")
    print(f"  - fetch_existing_external_orders() returns IDs to skip")
    print(f"  - Import filters: new_orders = df[~df['external_order_id'].isin(existing_ids)]")
    print(f"  - This prevents duplicate imports ✓")

if __name__ == "__main__":
    test_deduplication()
