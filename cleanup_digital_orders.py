#!/usr/bin/env python3
"""
Cleanup script to delete all Digital orders and related data
"""
import sys
import json
from sqlalchemy import create_engine, text

# Load secrets from .streamlit/secrets.toml
import tomllib

with open('.streamlit/secrets.toml', 'rb') as f:
    secrets = tomllib.load(f)

db = secrets["general"]

engine = create_engine(
    f"postgresql+psycopg2://{db['DB_USER']}:{db['DB_PASSWORD']}@"
    f"{db['DB_HOST']}:{db['DB_PORT']}/{db['DB_NAME']}?sslmode={db['sslmode']}"
)

def cleanup():
    with engine.begin() as conn:
        # Get all Digital order IDs first
        result = conn.execute(text(
            "SELECT order_id FROM cookies_app.orders WHERE order_type = 'Digital'"
        ))
        digital_order_ids = [row[0] for row in result]
        
        print(f"Found {len(digital_order_ids)} Digital orders to delete")
        
        if not digital_order_ids:
            print("No Digital orders to delete")
            return
        
        # Convert to placeholder string for SQL IN clause
        ids_str = ','.join([f"'{oid}'" for oid in digital_order_ids])
        
        # Delete from inventory_ledger
        result = conn.execute(text(
            f"DELETE FROM cookies_app.inventory_ledger WHERE related_order_id IN ({ids_str})"
        ))
        print(f"Deleted {result.rowcount} inventory_ledger records")
        
        # Delete from money_ledger
        result = conn.execute(text(
            f"DELETE FROM cookies_app.money_ledger WHERE related_order_id IN ({ids_str})"
        ))
        print(f"Deleted {result.rowcount} money_ledger records")
        
        # Delete from order_items
        result = conn.execute(text(
            f"DELETE FROM cookies_app.order_items WHERE order_id IN ({ids_str})"
        ))
        print(f"Deleted {result.rowcount} order_items records")
        
        # Delete from orders
        result = conn.execute(text(
            "DELETE FROM cookies_app.orders WHERE order_type = 'Digital'"
        ))
        print(f"Deleted {result.rowcount} orders records")
        
        print("✓ Cleanup complete!")

if __name__ == "__main__":
    cleanup()
