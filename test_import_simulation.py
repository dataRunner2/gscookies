#!/usr/bin/env python3
"""
Comprehensive test: simulate importing the same orders twice
"""
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

def test_import_simulation():
    """Simulate importing the same batch twice to verify no duplicates"""
    
    print("=" * 60)
    print("IMPORT DEDUPLICATION TEST")
    print("=" * 60)
    
    # Check current state
    existing = fetch_existing_external_orders("Digital Cookie Import")
    print(f"\n1. Current state: {len(existing)} Digital Cookie Import orders in DB")
    
    # Simulate a batch of 3 orders
    batch = pd.DataFrame({
        'external_order_id': ['TEST-BATCH-001', 'TEST-BATCH-002', 'TEST-BATCH-003'],
        'scout_first_name': ['Scout', 'Scout', 'Scout'],
        'scout_last_name': ['One', 'Two', 'Three'],
    })
    
    print(f"\n2. New batch to import: {len(batch)} orders")
    print(batch[['external_order_id']].to_string())
    
    # Simulate first import
    batch['external_order_id'] = batch['external_order_id'].astype(str)
    existing_before = fetch_existing_external_orders("Digital Cookie Import")
    to_import_1 = batch[~batch['external_order_id'].isin(existing_before)]
    
    print(f"\n3. FIRST IMPORT:")
    print(f"   - Existing before: {len(existing_before)} orders")
    print(f"   - Would import: {len(to_import_1)} orders")
    print(f"   - Orders: {to_import_1['external_order_id'].tolist()}")
    
    # Simulate second import with same batch
    # (In real world, user would upload the same Excel file)
    existing_after_first = fetch_existing_external_orders("Digital Cookie Import")
    to_import_2 = batch[~batch['external_order_id'].isin(existing_after_first)]
    
    print(f"\n4. SECOND IMPORT (same batch):")
    print(f"   - Existing after first: {len(existing_after_first)} orders")
    print(f"   - Would import: {len(to_import_2)} orders")
    print(f"   - Orders: {to_import_2['external_order_id'].tolist()}")
    
    print("\n" + "=" * 60)
    if len(to_import_1) > 0 and len(to_import_2) == 0:
        print("✓ DEDUPLICATION WORKS CORRECTLY!")
        print("  - First import: imported all new orders")
        print("  - Second import: imported 0 (prevented duplicates)")
    elif len(to_import_1) == 0 and len(to_import_2) == 0:
        print("✓ ORDERS ALREADY IMPORTED (previous test run)")
        print(f"  - Existing orders: {existing_after_first[:3]}")
    else:
        print("✗ UNEXPECTED STATE")
        print(f"  - First import would import {len(to_import_1)} orders")
        print(f"  - Second import would import {len(to_import_2)} orders")
    print("=" * 60)

if __name__ == "__main__":
    test_import_simulation()
