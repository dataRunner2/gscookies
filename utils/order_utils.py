from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional
import pandas as pd
from utils.db_utils import get_engine,fetch_all, fetch_one, execute_sql, execute_many_sql, to_pacific

from sqlalchemy import text
import uuid


# ==================================================
# Helpers
# ==================================================

def _dec(x) -> Decimal:
    if x is None:
        return Decimal("0.00")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _is_digital(order_type: str | None) -> bool:
    if not order_type:
        return False
    return "digital" in order_type.lower()


def _initial_order_window_sql() -> str:
    """
    Initial Order (IO) window rule:
      >= Jan 5 AND < Feb 1  (based on program_year)
    Uses make_date(program_year, month, day)
    """
    return """
        (o.submit_dt >= make_date(o.program_year, 1, 5)
         AND o.submit_dt <  make_date(o.program_year, 2, 1))
    """

# ==================================================
# Scout helpers
# ==================================================
def get_scouts_byparent(parent_id):
    return fetch_all("""
        SELECT scout_id, first_name, last_name, tshirt_size,
            goals, award_preferences,parent_id
        FROM cookies_app.scouts
        WHERE parent_id = :parent_id
        ORDER BY last_name, first_name
    """,{"parent_id": parent_id}
    )

    
def get_all_scouts():
    return fetch_all("""
        SELECT scout_id, first_name, last_name, gsusa_id, parent_id
        FROM cookies_app.scouts
        ORDER BY last_name, first_name
    """)

def add_scout(parent_id, first_name, last_name, goals, award_preferences):
    sql = """
        INSERT INTO cookies_app.scouts (
            parent_id,
            first_name,
            last_name,
            goals,
            award_preferences
        )
        VALUES (
            :parent_id,
            :first_name,
            :last_name,
            :goals,
            :award_preferences
        )
        RETURNING scout_id
    """
    engine = get_engine()
    
    with engine.begin() as conn:
        result = conn.execute(
            text(sql),
            {
                "parent_id": str(parent_id),
                "first_name": first_name,
                "last_name": last_name,
                "goals": goals,
                "award_preferences": award_preferences,
            }
        )
        scout_id = result.scalar()

    return scout_id
    
def update_scout(
    scout_id: str,
    goals: int | None = None,
    award_preferences: str | None = None
):
    """
    Update scout goal and/or award preferences.
    """
    fields = []
    params = {"scout_id": scout_id}

    if goals is not None:
        fields.append("goals = :goals")
        params["goals"] = goals

    if award_preferences is not None:
        fields.append("award_preferences = :award_preferences")
        params["award_preferences"] = award_preferences

    if not fields:
        return

    sql = f"""
        UPDATE cookies_app.scouts
        SET {", ".join(fields)}
        WHERE scout_id = :scout_id
    """

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def fetch_scout_aliases(conn):
    query = "SELECT alias_name, scout_id FROM scout_aliases"
    rows = conn.execute(query).fetchall()
    return {r[0].lower(): r[1] for r in rows}

def insert_scout_alias(conn, alias_name: str, scout_id: int):
    execute_sql("""
        INSERT INTO scout_aliases (alias_name, scout_id)
        VALUES (%s, %s)
        ON CONFLICT (alias_name) DO NOTHING
        """,{
            "alias": alias_name, 
            "scout":scout_id}
    )

def get_all_parents():
    return fetch_all("""
        SELECT parent_id, parent_firstname, parent_lastname
        FROM cookies_app.parents
        ORDER BY parent_lastname, parent_firstname
    """)

def update_scout_gsusa_id(scout_id, gsusa_id):
    execute_sql("""
            UPDATE scouts
            SET gsusa_id = :gsusa_id
            WHERE scout_id = :scout_id
                AND gsusa_id IS NULL
            
        """, {
                "scout_id": scout_id,
                "gsusa_id": str(gsusa_id),
            }
        )

            
# ==================================================
# Cookie helpers
# ==================================================
def get_cookie_codes_for_year(program_year: int) -> list[str]:
    """
    Returns ordered list of cookie codes for a program year.
    Used for admin grids, print pages, etc.
    """
    rows = fetch_all("""
        SELECT cookie_code
        FROM cookies_app.cookie_years
        WHERE program_year = :year
          AND active = true
        ORDER BY display_order
    """, {"year": program_year})
    
    return [r["cookie_code"] for r in rows]

def get_cookies_for_year(program_year):
    rows = fetch_all("""
        SELECT cookie_code, display_name, price_per_box
        FROM cookies_app.cookie_years
        WHERE program_year = :year
          AND active = TRUE
        ORDER BY display_order
    """,{"year": program_year})
    return rows
    

def build_cookie_rename_map(program_year: int) -> dict:
    cookies = get_cookies_for_year(program_year)

    return {
        row["display_name"]: row["cookie_code"]
        for row in cookies
    }


def aggregate_orders_by_cookie(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("cookie_name", as_index=False)
          .agg(total_boxes=("quantity", "sum"))
          .sort_values("cookie_name")
    )


# ==================================================
# Order header + items
# ==================================================
def get_orders_for_scout_summary(scout_id: str) -> pd.DataFrame:
    # Used in admin girl order summary - joins the header and the cookie details
    rows = fetch_all("""
        SELECT
            cy.display_name AS cookie_name,
            oi.quantity,
            o.order_type,
            o.submit_dt,
            o.order_id
        FROM cookies_app.orders o
        JOIN cookies_app.order_items oi
          ON oi.order_id = o.order_id
        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = oi.cookie_code
         AND cy.program_year = o.program_year
        WHERE o.scout_id = :sid
        ORDER BY o.submit_dt DESC
    """, {"sid": scout_id})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df

def get_orders_for_scout(scout_id, year):
    """
    Returns orders + total paid so far (paper only).
    Digital orders are treated as fully paid.
    """
    rows = fetch_all("""
        SELECT
            o.order_id,
            o.order_ref,
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status AS order_status,
            o.comments,
            COALESCE(SUM(m.amount), 0) AS paid_amount
        FROM cookies_app.orders o
        LEFT JOIN cookies_app.money_ledger m
          ON o.order_id = m.related_order_id
        WHERE o.scout_id = :scout_id
          AND o.program_year = :year
        GROUP BY
            o.order_id,
            o.order_ref,
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status
        ORDER BY o.submit_dt DESC
    """, { "scout_id": scout_id,
            "year": year
        })
    if not rows:
        return pd.DataFrame()

    cln_rows = {str(r["order_id"]): r for r in rows}

    # # Build dataframe
    df = pd.DataFrame(list(cln_rows.values()))
    df['submit_dt'] = [to_pacific(subdat) for subdat in df['submit_dt']]

    return df

def get_order_items(order_id):
    rows = fetch_all("""
        SELECT
            cy.display_name,
            oi.quantity
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON oi.cookie_code = cy.cookie_code
         AND oi.program_year = cy.program_year
        WHERE oi.order_id = :order_id
        ORDER BY cy.display_order
    """, {"order_id": order_id})
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)


def get_all_orders_wide(program_year: Optional[int] = None) -> pd.DataFrame:
    """
    Get all orders in WIDE format - one row per order with admin fields.
    Ready for admin_order_management page.
    
    Columns: orderId, orderType, orderStatus, addEbudde, initialOrder, verifiedDigitalCookie,
    comments, submit_dt, scoutName, boothId, paymentStatus, plus one column per cookie type.
    """
    params = {}
    year_filter = ""
    
    if program_year:
        year_filter = "WHERE o.program_year = :year"
        params["year"] = program_year
    
    rows = fetch_all(f"""
        WITH paid AS (
            SELECT
                related_order_id AS order_id,
                COALESCE(SUM(amount), 0) AS paid_amount
            FROM cookies_app.money_ledger
            GROUP BY related_order_id
        )
        SELECT
            o.order_id AS "orderId",
            o.program_year,
            o.submit_dt,
            o.order_type AS "orderType",
            o.status AS "orderStatus",
            o.order_amount AS "orderAmount",
            o.order_qty_boxes AS "orderQtyBoxes",
            o.comments,
            o.booth_id AS "boothId",
            o.scout_id AS "scoutId",
            
            COALESCE(o.add_ebudde, false) AS "addEbudde",
            COALESCE(o.verified_digital, false) AS "verifiedDigitalCookie",
            COALESCE(o.order_pickedup, false) AS "orderPickedup",
            COALESCE(
                o.initial_order,
                (o.submit_dt >= make_date(o.program_year, 1, 5)
                 AND o.submit_dt <  make_date(o.program_year, 2, 1))
            ) AS "initialOrder",
            
            COALESCE(
                (s.first_name || ' ' || s.last_name),
                (p.parent_firstname || ' ' || p.parent_lastname),
                ''
            ) AS "scoutName",
            
            COALESCE(paid.paid_amount, 0) AS "paidAmount",
            
            oi.cookie_code AS "cookieCode",
            oi.quantity
            
        FROM cookies_app.orders o
        LEFT JOIN cookies_app.order_items oi
          ON oi.order_id = o.order_id
         AND oi.program_year = o.program_year
        LEFT JOIN cookies_app.scouts s
          ON s.scout_id = o.scout_id
        LEFT JOIN cookies_app.parents p
          ON p.parent_id = o.parent_id
        LEFT JOIN paid
          ON paid.order_id = o.order_id
        {year_filter}
        ORDER BY o.submit_dt DESC, o.order_id
    """, params)
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # Get all unique orders first (before pivoting)
    meta_cols = ['orderId', 'program_year', 'submit_dt', 'orderType', 'orderStatus', 
                 'orderAmount', 'orderQtyBoxes', 'comments', 'boothId', 'scoutId', 'addEbudde', 
                 'verifiedDigitalCookie', 'orderPickedup', 'initialOrder', 'scoutName', 'paidAmount']
    
    # Only use columns that exist in the dataframe
    available_meta_cols = [col for col in meta_cols if col in df.columns]
    
    if not available_meta_cols:
        return pd.DataFrame()
    
    # Make sure orderId is included
    if 'orderId' not in available_meta_cols:
        return pd.DataFrame()
    
    meta = df[available_meta_cols].drop_duplicates('orderId').set_index('orderId')
    
    # Calculate payment status for each order
    def calc_payment_status(row):
        return get_payment_status(
            row.get('orderType'),
            Decimal(str(row.get('orderAmount', 0))),
            Decimal(str(row.get('paidAmount', 0)))
        )
    
    meta['paymentStatus'] = meta.apply(calc_payment_status, axis=1)
    
    # Pivot cookies by cookie_code, summing quantities
    if 'cookieCode' in df.columns and 'quantity' in df.columns:
        cookies = df[df['cookieCode'].notna()].pivot_table(
            index='orderId',
            columns='cookieCode',
            values='quantity',
            aggfunc='sum',
            fill_value=0
        ).astype(int)
    else:
        cookies = pd.DataFrame()
    
    # Merge metadata with cookies, keeping all metadata rows
    if not cookies.empty:
        result = meta.join(cookies, how='left').reset_index()
    else:
        # If no cookies at all, still include all orders
        result = meta.reset_index()
    
    # Fill missing cookie columns with 0
    all_cookie_codes = get_cookie_codes_for_year(program_year) if program_year else []
    for code in all_cookie_codes:
        if code not in result.columns:
            result[code] = 0
        else:
            # Fill NaN values with 0
            result[code] = result[code].fillna(0).astype(int)
    
    # Convert submit_dt to date safely
    if 'submit_dt' in result.columns:
        result['submit_dt'] = pd.to_datetime(result['submit_dt'], errors='coerce').dt.date
    
    # Non-digital orders should never appear "verified"
    if 'orderType' in result.columns and 'verifiedDigitalCookie' in result.columns:
        result.loc[~result['orderType'].str.contains('Digital', case=False, na=False), 'verifiedDigitalCookie'] = False
    
    return result


def get_outstanding_non_booth_orders(program_year=None):
    params = {}
    year_filter = ""

    if program_year:
        year_filter = "AND o.program_year = :year"
        params["year"] = program_year

    return fetch_all(f"""
        SELECT
            o.order_id,
            o.parent_id,
            o.program_year,
            o.submit_dt,
            p.parent_firstname,
            p.parent_lastname,
            p.parent_phone
        FROM cookies_app.orders o
        JOIN cookies_app.parents p ON p.parent_id = o.parent_id
        WHERE o.order_type <> 'Booth'
          AND o.status <> 'PICKED_UP'
          {year_filter}
        ORDER BY p.parent_lastname, p.parent_firstname, o.submit_dt
    """, params)


def fetch_orders_for_scout(scout_id):
    return fetch_all("""
        SELECT
            o.order_id,
            o.scout_id,
            o.order_qty_boxes,
            o.order_type,
            o.order_source,
            o.submit_date,
            o.program_year,
            o.status
        FROM orders o
        WHERE o.scout_id = {scout_id}
    """)

def fetch_orders_for_scout_with_fallback(
    scout_id,
    scout_first_name: str,
    scout_last_name: str,
):
    """
    Fetch cookie-level order items for a scout.

    Priority:
    1) Match on scout_id
    2) Fallback to first + last name for legacy rows
    """

    sql = """
        SELECT
            oi.cookie_name,
            oi.qty_boxes,
            o.order_type,
            o.submit_dt,
            o.order_id
        FROM order_items oi
        JOIN orders o
          ON o.order_id = oi.order_id
        WHERE o.scout_id = :scout_id

        UNION ALL

        SELECT
            oi.cookie_name,
            oi.qty_boxes,
            o.order_type,
            o.submit_dt,
            o.order_id
        FROM order_items oi
        JOIN orders o
          ON o.order_id = oi.order_id
        WHERE o.scout_id IS NULL
          
    """

    return fetch_all(
        sql,
        {
            "scout_id": scout_id,
            "first_name": scout_first_name,
            "last_name": scout_last_name,
        },
    )


def get_order_header(order_id: str):
    return fetch_one("""
        SELECT
            o.order_id,
            o.parent_id,
            o.scout_id,
            o.booth_id,
            o.program_year,
            o.order_type,
            o.status,
            o.submit_dt,
            o.order_amount,
            o.order_qty_boxes,
            o.comments,
            o.initial_order,
            o.add_ebudde,
            o.verified_digital
        FROM cookies_app.orders o
        WHERE o.order_id = :oid
    """, {"oid": order_id})

def get_order_items(order_id: str, program_year: int):
    """
    Returns cookie line items with price and display name (for that year).
    """
    return fetch_all("""
        SELECT
            oi.cookie_code,
            cy.display_name,
            cy.price_per_box,
            oi.quantity,
            oi.scout_id
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = oi.cookie_code
         AND cy.program_year = oi.program_year
        WHERE oi.order_id = :oid
          AND oi.program_year = :year
        ORDER BY cy.display_order
    """, {"oid": order_id, "year": program_year})

def insert_order_header(
    parent_id, scout_id, program_year, order_ref, order_type, comments,
    total_boxes, order_amount, status, external_order_id = None
):
    order_id = uuid.uuid4()

    sql = """
        INSERT INTO cookies_app.orders (
            order_id,
            parent_id,
            scout_id,
            program_year,
            order_ref,
            order_type,
            status,
            order_qty_boxes,
            order_amount,
            comments,
            external_order_id,
            initial_order,
            submit_dt,
            created_at            
        )
        VALUES (
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :order_ref,
            :order_type,
            :status,
            :order_qty_boxes,
            :order_amount,
            :comments,
            :external_order_id,
            (now() >= make_date(:program_year, 1, 5) AND now() < make_date(:program_year, 2, 1)),
            now(),
            now()
        )
    """

    execute_sql(sql, {
            "order_id": str(order_id),
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
            "program_year": program_year,
            "order_ref": order_ref,
            "order_type": order_type,
            "status": status,
            "order_qty_boxes": total_boxes,
            "order_amount": order_amount,
            "comments": comments,
            "external_order_id": external_order_id
        })

    return order_id

def insert_order_items(order_id, parent_id, scout_id, program_year, items):
    sql = """
        INSERT INTO cookies_app.order_items (
            order_item_id,
            order_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity
        )
        VALUES (
            gen_random_uuid(),
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity
        )
    """

    for code, qty in items.items():
        if qty != 0:
            execute_sql(sql, {
                "order_id": str(order_id),
                "parent_id": str(parent_id),
                "scout_id": str(scout_id),
                "program_year": program_year,
                "cookie_code": code,
                "quantity": qty
            })

def insert_planned_inventory(parent_id, scout_id, program_year, order_id, items):
    sql = """
        INSERT INTO cookies_app.inventory_ledger (
            inventory_event_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity,
            event_type,
            status,
            related_order_id,
            event_dt
        )
        VALUES (
            gen_random_uuid(),
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity,
            'ORDER_SUBMITTED',
            'PLANNED',
            :order_id,
            now()
        )
    """

    
    for code, qty in items.items():
        if qty != 0:
            execute_sql(sql, {
                "parent_id": str(parent_id),
                "scout_id": str(scout_id),
                "program_year": program_year,
                "cookie_code": code,
                "quantity": -abs(qty),
                "order_id": str(order_id)
            })

def bulk_insert_order_headers(df):
    sql = """
        INSERT INTO cookies_app.orders (
            order_id,
            parent_id,
            scout_id,
            program_year,
            order_ref,
            order_type,
            status,
            order_qty_boxes,
            order_amount,
            comments,
            external_order_id,
            order_source,
            initial_order,
            submit_dt,
            created_at
        )
        VALUES (
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :order_ref,
            :order_type,
            :status,
            :order_qty_boxes,
            :order_amount,
            :comments,
            :external_order_id,
            :order_source,
            :initial_order,
            :submit_dt,
            now()
        )
    """

    payload = []

    for r in df.itertuples():
        # Skip orders without both scout_id and parent_id
        if pd.isna(r.parent_id) or pd.isna(r.scout_id):
            continue
        
        order_id = uuid.uuid4()

        payload.append({
            "order_id": str(order_id),
            "parent_id": str(r.parent_id),
            "scout_id": str(r.scout_id),
            "program_year": r.program_year,
            "order_ref": r.order_ref,
            "order_type": r.order_type,
            "status": r.status,
            "order_qty_boxes": r.order_qty_boxes,
            "order_amount": r.order_amount,
            "comments": r.comments,
            "external_order_id": r.external_order_id,
            "order_source": r.order_source,
            "initial_order": bool(r.initial_order) if hasattr(r, "initial_order") else None,
            "submit_dt": r.submit_dt,
        })

        # store for downstream inserts
        df.at[r.Index, "order_id"] = order_id

    execute_many_sql(sql, payload)
    return df

def bulk_insert_order_items(df):
    """
    Insert order items from a wide-format DataFrame.
    
    Expects columns: order_id, scout_id, parent_id, program_year, plus cookie code columns
    (ADV, LEM, TRE, DSD, SAM, TAG, TM, EXP, TOF, DON)
    """
    sql = """
        INSERT INTO cookies_app.order_items (
            order_item_id,
            order_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity
        )
        VALUES (
            :order_item_id,
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity
        )
    """
    
    # Define all possible cookie codes
    cookie_codes = ['ADV', 'LEM', 'TRE', 'DSD', 'SAM', 'TAG', 'TM', 'EXP', 'TOF', 'DON']
    payload = []
    
    for _, row in df.iterrows():
        order_id = row.get('order_id')
        parent_id = row.get('parent_id')
        scout_id = row.get('scout_id')
        program_year = row.get('program_year')
        
        # Default parent_id and scout_id to 999 if missing
        if pd.isna(parent_id):
            parent_id = 999
        if pd.isna(scout_id):
            scout_id = 999
        
        # Skip if missing required fields
        if pd.isna(order_id):
            continue
        
        # Iterate through each cookie code
        for cookie_code in cookie_codes:
            # Skip if column doesn't exist
            if cookie_code not in df.columns:
                continue
            
            qty = row.get(cookie_code)
            
            # Convert to numeric and skip if 0 or NaN
            try:
                qty = pd.to_numeric(qty, errors='coerce')
            except (TypeError, ValueError):
                qty = 0
            
            if pd.isna(qty) or qty == 0:
                continue
            
            payload.append({
                "order_item_id": str(uuid.uuid4()),
                "order_id": str(order_id),
                "parent_id": str(parent_id),
                "scout_id": str(scout_id),
                "program_year": int(program_year),
                "cookie_code": cookie_code,
                "quantity": int(qty),
            })
    
    # Only execute if we have items to insert
    if payload:
        execute_many_sql(sql, payload)

def bulk_insert_planned_inventory(df):
    # Only accept known cookie codes to avoid pulling in extra columns like order_total
    cookie_codes = ['ADV', 'LEM', 'TRE', 'DSD', 'SAM', 'TAG', 'TM', 'EXP', 'TOF', 'DON']

    sql = """
        INSERT INTO cookies_app.inventory_ledger (
            inventory_event_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity,
            event_type,
            status,
            related_order_id,
            event_dt
        )
        VALUES (
            gen_random_uuid(),
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity,
            'ORDER_SUBMITTED',
            'PENDING',
            :order_id,
            now()
        )
    """

    payload = []

    if 'cookie_code' in df.columns and 'quantity' in df.columns:
        # Long format
        for r in df.itertuples():
            qty = getattr(r, 'quantity', 0)
            qty = pd.to_numeric(qty, errors='coerce')
            if pd.isna(qty) or qty <= 0:
                continue

            # Require matched parent/scout
            if pd.isna(r.parent_id) or pd.isna(r.scout_id):
                continue

            # Skip unknown cookie codes
            if r.cookie_code not in cookie_codes:
                continue

            payload.append({
                "parent_id": str(r.parent_id),
                "scout_id": str(r.scout_id),
                "program_year": r.program_year,
                "cookie_code": r.cookie_code,
                "quantity": int(qty),
                "order_id": str(r.order_id),
            })
    else:
        # Wide format
        meta_cols = {'order_id', 'parent_id', 'scout_id', 'program_year', 'order_ref', 'order_type', 'status', 'order_qty_boxes', 'order_amount', 'comments', 'external_order_id', 'order_source', 'submit_dt', 'created_at', 'Customer Email Address', 'Payment Status', 'Council Name', 'Troop Number', 'Refund', 'Baker'}

        for r in df.itertuples():
            for col in df.columns:
                if col in meta_cols:
                    continue

                # Skip columns that are not cookie codes
                if col not in cookie_codes:
                    continue

                qty = getattr(r, col)
                # Coerce strings/None to numeric; skip non-positive or NaN
                qty = pd.to_numeric(qty, errors='coerce')
                if pd.isna(qty) or qty <= 0:
                    continue

                # Require matched parent/scout
                if pd.isna(r.parent_id) or pd.isna(r.scout_id):
                    continue

                payload.append({
                    "parent_id": str(r.parent_id),
                    "scout_id": str(r.scout_id),
                    "program_year": r.program_year,
                    "cookie_code": col,
                    "quantity": int(qty),
                    "order_id": str(r.order_id),
                })

    execute_many_sql(sql, payload)


# ==================================================
# Payments & balances
# ==================================================

def bulk_insert_money_ledger(df):
    """
    Insert payment records for Digital Cookie orders (they come pre-paid).
    Creates one money_ledger entry per order with full order_amount as payment.
    """
    sql = """
        INSERT INTO cookies_app.money_ledger (
            money_event_id,
            parent_id,
            scout_id,
            program_year,
            amount,
            payment_method,
            notes,
            related_order_id,
            received_dt,
            created_at
        )
        VALUES (
            gen_random_uuid(),
            :parent_id,
            :scout_id,
            :program_year,
            :amount,
            :method,
            :notes,
            :order_id,
            now(),
            now()
        )
    """

    payload = []

    for _, row in df.iterrows():
        order_id = row.get('order_id')
        parent_id = row.get('parent_id')
        scout_id = row.get('scout_id')
        program_year = row.get('program_year')
        order_amount = row.get('order_amount')
        order_type = row.get('order_type')
    
        # Only create payment entry for Digital Cookie orders
        if not _is_digital(order_type):
            continue
    
        # Skip if missing required fields
        if pd.isna(order_id) or pd.isna(parent_id) or pd.isna(scout_id) or pd.isna(order_amount):
            continue
    
        payload.append({
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
            "program_year": int(program_year),
            "amount": float(order_amount),
            "method": "DIGITAL_COOKIE",
            "notes": "Digital Cookie import - pre-paid",
            "order_id": str(order_id),
        })

    if payload:
        execute_many_sql(sql, payload)

def get_paid_amount_by_order(order_id: str) -> Decimal:
    row = fetch_one("""
        SELECT COALESCE(SUM(amount), 0) AS paid_amount
        FROM cookies_app.money_ledger
        WHERE related_order_id = :oid
    """, {"oid": order_id})
    return _dec(row["paid_amount"] if row else 0)


def get_payment_status(order_type: str | None, order_amount: Decimal, paid_amount: Decimal) -> str:
    # Digital Cookie: always PAID in your app logic
    if _is_digital(order_type):
        return "PAID"
    # allow tiny rounding tolerance
    if paid_amount + Decimal("0.005") >= order_amount:
        return "PAID"
    return "UNPAID"


# ==================================================
# Parent-editable fields (used by delete/modify page)
# ==================================================

def update_order_type(order_id: str, new_type: str):
    execute_sql("""
        UPDATE cookies_app.orders
        SET order_type = :otype
        WHERE order_id = :oid
    """, {"oid": order_id, "otype": new_type})


def update_order_notes(order_id: str, notes: str):
    execute_sql("""
        UPDATE cookies_app.orders
        SET comments = :notes
        WHERE order_id = :oid
    """, {"oid": order_id, "notes": notes})


# ==================================================
# Status updates
# ==================================================

def mark_order_picked_up(order_id: str):
    execute_sql("""
        UPDATE cookies_app.orders
        SET status = 'PICKED_UP'
        WHERE order_id = :oid
    """, {"oid": order_id})


def mark_orders_printed(order_ids: Iterable[str]):
    """
    When you print pickup sheets, orders should move:
    NEW -> PRINTED
    (non-booth only; caller should filter, but we guard anyway)
    """
    order_ids = list(order_ids)
    if not order_ids:
        return

    execute_sql("""
        UPDATE cookies_app.orders
        SET status = 'PRINTED'
        WHERE order_id = ANY(:oids)
        AND status = 'NEW'
        AND order_type <> 'Booth'
    """, {"oids": order_ids})


def set_initial_order_flag(order_id: str, initial_order: bool):
    execute_sql("""
        UPDATE cookies_app.orders
        SET initial_order = :v
        WHERE order_id = :oid
    """, {"oid": order_id, "v": bool(initial_order)})


def set_add_ebudde(order_id: str, add_ebudde: bool):
    execute_sql("""
        UPDATE cookies_app.orders
        SET add_ebudde = :v
        WHERE order_id = :oid
    """, {"oid": order_id, "v": bool(add_ebudde)})


def set_verified_digital_cookie(order_id: str, verified: bool):
    execute_sql("""
        UPDATE cookies_app.orders
        SET verified_digital = :v
        WHERE order_id = :oid
    """, {"oid": order_id, "v": bool(verified)})


# ==================================================
# PRINT ORDERS (admin_print_new_orders page)
# ==================================================

def get_print_orders_flat(program_year: Optional[int] = None, scout_id: Optional[str] = None):
    """
    Print Orders page requirements (per your latest confirmation):
    - non-booth orders
    - status = NEW (only "new orders")
    - broken out by scout (order_items already ties to scout_id)
    Returns one row per (order_id, scout_id, cookie_code).
    """

    where = ["o.order_type <> 'BOOTH'", "o.status = 'NEW'"]
    params: dict[str, Any] = {}

    if program_year is not None:
        where.append("o.program_year = :year")
        params["year"] = program_year

    if scout_id is not None:
        where.append("oi.scout_id = :sid")
        params["sid"] = scout_id

    where_sql = " AND ".join(where)

    return fetch_all(f"""
        SELECT
            o.order_id,
            o.program_year,
            o.order_type,
            o.status,
            o.submit_dt,
            o.order_amount,
            o.order_qty_boxes,
            o.comments,
            COALESCE(o.initial_order, {_initial_order_window_sql()}) AS initial_order,

            s.scout_id,
            s.first_name || ' ' || s.last_name AS scout_name,

            p.parent_firstname || ' ' || p.parent_lastname AS guardian_name,
            p.parent_phone AS guardian_phone,

            oi.cookie_code,
            oi.quantity
        FROM cookies_app.orders o
        JOIN cookies_app.order_items oi ON oi.order_id = o.order_id
        JOIN cookies_app.scouts s ON s.scout_id = oi.scout_id
        JOIN cookies_app.parents p ON p.parent_id = o.parent_id
        WHERE {where_sql}
        ORDER BY s.last_name, s.first_name, o.submit_dt
    """, params)


def get_admin_print_orders(statuses: Optional[list[str]] = None, initial_only:bool=False):
    """
    Rows for admin print: includes order-level header fields + item-level cookie counts.
    Output: one row per (order_id, cookie_code)
    """
    where = ["o.order_type <> 'Booth'"]
    params: dict[str, Any] = {}

    if statuses:
        where.append("o.status = ANY(:statuses)")
        params["statuses"] = statuses
    if initial_only:
        where.append("COALESCE(o.initial_order, false) = true")

    where_sql = " AND ".join(where)

    return fetch_all(f"""
        SELECT
            o.order_id,
            o.order_type,
            o.status,
            o.order_amount,
            o.order_qty_boxes,
            o.comments,
            o.initial_order,
            o.submit_dt::date AS submit_date,

            s.scout_id,
            (s.first_name || ' ' || s.last_name) AS scout_name,

            p.parent_firstname || ' ' || p.parent_lastname AS guardian_name,
            p.parent_phone AS guardian_phone,

            oi.cookie_code,
            oi.quantity,

            cy.display_name,
            cy.display_order
        FROM cookies_app.orders o
        JOIN cookies_app.scouts s
          ON s.scout_id = o.scout_id
        LEFT JOIN cookies_app.parents p
          ON p.parent_id = o.parent_id
        LEFT JOIN cookies_app.order_items oi
          ON oi.order_id = o.order_id
         AND oi.program_year = o.program_year
        LEFT JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = oi.cookie_code
         AND cy.program_year = oi.program_year
        WHERE {where_sql}
        ORDER BY s.last_name, s.first_name, o.submit_dt, cy.display_order
    """, params)

# ==================================================
# ADMIN COOKIE MANAGEMENT (admin_order_management page)
# ==================================================
def get_admin_orders_flat(program_year: int):
    """
    Admin Order Management data source.

    Returns one row per (order_id, cookie_code) with stable column names
    expected by the admin grid:
      orderId, orderType, orderStatus, paymentStatus, addEbudde,
      initialOrder, verifiedDigitalCookie, comments, submit_dt,
      scoutName, boothId, cookieCode, qty, pricePerBox
    """

    rows = fetch_all("""
        WITH paid AS (
            SELECT
                related_order_id AS order_id,
                COALESCE(SUM(amount), 0) AS paid_amount
            FROM cookies_app.money_ledger
            GROUP BY related_order_id
        )
        SELECT
            o.order_id                         AS "orderId",
            o.program_year                     AS "programYear",
            o.order_type                       AS "orderType",
            o.status                           AS "orderStatus",
            o.submit_dt                        AS "submit_dt",
            o.order_amount                     AS "orderAmount",
            o.order_qty_boxes                  AS "orderQtyBoxes",
            o.comments                         AS "comments",
            o.booth_id                         AS "boothId",

            COALESCE(
                o.initial_order,
                (o.submit_dt >= make_date(o.program_year, 1, 5)
                 AND o.submit_dt <  make_date(o.program_year, 2, 1))
            )                                  AS "initialOrder",

            COALESCE(o.add_ebudde, false)      AS "addEbudde",
            COALESCE(o.verified_digital, false)
                                               AS "verifiedDigitalCookie",

            (s.first_name || ' ' || s.last_name)
                                               AS "scoutName",

            oi.cookie_code                     AS "cookieCode",
            oi.quantity                        AS "qty",

            cy.price_per_box                   AS "pricePerBox",

            COALESCE(paid.paid_amount, 0)      AS "paidAmount"

        FROM cookies_app.orders o
        JOIN cookies_app.order_items oi
          ON oi.order_id = o.order_id
         AND oi.program_year = o.program_year

        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = oi.cookie_code
         AND cy.program_year = o.program_year

        LEFT JOIN cookies_app.scouts s
          ON s.scout_id = o.scout_id

        LEFT JOIN paid
          ON paid.order_id = o.order_id

        WHERE o.program_year = :year

        ORDER BY
            o.submit_dt DESC,
            o.order_id,
            cy.display_order
    """, {"year": program_year})

    out: list[dict] = []

    for r in rows:
        r = dict(r)  # RowMapping → dict (CRITICAL)

        # Compute paymentStatus in python (single source of truth)
        r["paymentStatus"] = get_payment_status(
            r.get("orderType"),
            r.get("orderAmount"),
            r.get("paidAmount"),
        )

        # Non-digital orders should never appear "verified"
        if not _is_digital(r.get("orderType")):
            r["verifiedDigitalCookie"] = False

        out.append(r)

    return out


# ==================================================
# Bulk admin updates (used by admin management grid)
# ==================================================

def admin_update_orders_bulk(updates: list[dict[str, Any]], cookie_cols: list[str] = None):
    """
    Apply bulk updates to orders and their cookie quantities.
    Each item in 'updates' should look like:
      {"orderId": "...", "initialOrder": True, "addEbudde": False, "verifiedDigitalCookie": True, "orderStatus": "PRINTED", "TM": 10, "SAM": 5, ...}
    Only whitelisted fields are applied for orders table.
    Cookie columns update the order_items table.
    """
    allowed = {
        "initialOrder": "initial_order",
        "addEbudde": "add_ebudde",
        "verifiedDigitalCookie": "verified_digital",
        "orderStatus": "status",
        "comments": "comments",
        "orderType": "order_type",
        "orderPickedup": "order_pickedup",
    }
    
    cookie_cols = cookie_cols or []

    for u in updates:
        oid = u.get("orderId")
        if not oid:
            continue

        # Update order table fields
        sets = []
        params: dict[str, Any] = {"oid": oid}

        for k, col in allowed.items():
            if k in u:
                sets.append(f"{col} = :{k}")
                params[k] = u[k]

        if sets:
            sql = f"""
                UPDATE cookies_app.orders
                SET {", ".join(sets)}
                WHERE order_id = :oid
            """
            execute_sql(sql, params)
        
        # Update cookie quantities in order_items
        for cookie_code in cookie_cols:
            if cookie_code in u:
                new_qty = u[cookie_code]
                
                # Get program_year for this order
                year_result = fetch_one("""
                    SELECT program_year FROM cookies_app.orders WHERE order_id = :oid
                """, {"oid": oid})
                
                if not year_result:
                    continue
                    
                program_year = year_result.program_year
                
                # Check if order_item exists
                existing = fetch_one("""
                    SELECT quantity FROM cookies_app.order_items
                    WHERE order_id = :oid AND cookie_code = :code AND program_year = :year
                """, {"oid": oid, "code": cookie_code, "year": program_year})
                
                if new_qty == 0 or new_qty is None:
                    # Delete if quantity is 0
                    if existing:
                        execute_sql("""
                            DELETE FROM cookies_app.order_items
                            WHERE order_id = :oid AND cookie_code = :code AND program_year = :year
                        """, {"oid": oid, "code": cookie_code, "year": program_year})
                else:
                    # Update or insert
                    if existing:
                        execute_sql("""
                            UPDATE cookies_app.order_items
                            SET quantity = :qty
                            WHERE order_id = :oid AND cookie_code = :code AND program_year = :year
                        """, {"oid": oid, "code": cookie_code, "qty": new_qty, "year": program_year})
                    else:
                        # Get parent_id and scout_id from order
                        order_info = fetch_one("""
                            SELECT parent_id, scout_id FROM cookies_app.orders WHERE order_id = :oid
                        """, {"oid": oid})
                        
                        if order_info:
                            execute_sql("""
                                INSERT INTO cookies_app.order_items 
                                (order_id, program_year, cookie_code, quantity, parent_id, scout_id)
                                VALUES (:oid, :year, :code, :qty, :pid, :sid)
                            """, {
                                "oid": oid, 
                                "year": program_year, 
                                "code": cookie_code, 
                                "qty": new_qty,
                                "pid": order_info.parent_id,
                                "sid": order_info.scout_id
                            })

def fetch_existing_external_orders(order_source: str) -> set:
    rows = fetch_all("""
        SELECT external_order_id
        FROM cookies_app.orders
        WHERE order_source = :source
    """, {"source": order_source})
    return [r['external_order_id'] for r in rows]


# =====================================================
# Safe deletion utilities (for cleanup/admin use)
# =====================================================

def delete_order_cascade(order_id: str) -> bool:
    """
    Delete an order and all related data in the correct order.
    
    Note: If CASCADE DELETE constraints are enabled in the database,
    only the final DELETE FROM orders is needed. This function provides
    a fallback for manual cascading if constraints aren't set up.
    
    Args:
        order_id: UUID of the order to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Delete in reverse dependency order
        # With CASCADE DELETE enabled, these are automatic, but safe to call anyway
        execute_sql("DELETE FROM cookies_app.inventory_ledger WHERE related_order_id = :oid", {"oid": order_id})
        execute_sql("DELETE FROM cookies_app.money_ledger WHERE related_order_id = :oid", {"oid": order_id})
        execute_sql("DELETE FROM cookies_app.order_items WHERE order_id = :oid", {"oid": order_id})
        execute_sql("DELETE FROM cookies_app.orders WHERE order_id = :oid", {"oid": order_id})
        return True
    except Exception as e:
        print(f"Error deleting order {order_id}: {e}")
        return False


def delete_booth_cascade(booth_id: str) -> bool:
    """
    Delete a booth and all related data in the correct order.
    
    Manually deletes in order:
    1. order_items related to booth orders
    2. inventory_ledger related to booth orders
    3. money_ledger related to booth orders
    4. orders with this booth_id
    5. booth_scouts entries
    6. booth_inventory_plan entries
    7. booth itself
    
    Args:
        booth_id: UUID of the booth to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get all orders for this booth
        orders = fetch_all("""
            SELECT order_id FROM cookies_app.orders WHERE booth_id = :bid
        """, {"bid": booth_id})
        
        # Delete order-related data for each order
        for order in orders:
            order_id = str(order.order_id)
            # Delete order items
            execute_sql("DELETE FROM cookies_app.order_items WHERE order_id = :oid", {"oid": order_id})
            # Delete inventory ledger entries (uses related_order_id column)
            execute_sql("DELETE FROM cookies_app.inventory_ledger WHERE related_order_id = :oid", {"oid": order_id})
            # Delete money ledger entries (uses related_order_id column)
            execute_sql("DELETE FROM cookies_app.money_ledger WHERE related_order_id = :oid", {"oid": order_id})
        
        # Delete the orders themselves
        execute_sql("DELETE FROM cookies_app.orders WHERE booth_id = :bid", {"bid": booth_id})
        
        # Delete booth-specific data
        execute_sql("DELETE FROM cookies_app.booth_scouts WHERE booth_id = :bid", {"bid": booth_id})
        execute_sql("DELETE FROM cookies_app.booth_inventory_plan WHERE booth_id = :bid", {"bid": booth_id})
        
        # Finally delete the booth itself
        execute_sql("DELETE FROM cookies_app.booths WHERE booth_id = :bid", {"bid": booth_id})
        
        return True
    except Exception as e:
        error_msg = f"Error deleting booth {booth_id}: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)


def delete_booth_cascade_manual(booth_id: str) -> bool:
    """
    Delete a booth and all related data manually (if CASCADE not enabled).
    
    This is a fallback version that manually deletes all related data
    in the correct order. Use this if CASCADE DELETE constraints
    haven't been applied to the database.
    
    Args:
        booth_id: UUID of the booth to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First, get all orders for this booth
        booth_orders = fetch_all(
            "SELECT order_id FROM cookies_app.orders WHERE booth_id = :bid",
            {"bid": booth_id}
        )
        
        # Delete each booth order with cascade
        for order in booth_orders:
            delete_order_cascade(str(order['order_id']))
        
        # Now delete booth-specific data
        execute_sql("DELETE FROM cookies_app.booth_inventory_plan WHERE booth_id = :bid", {"bid": booth_id})
        execute_sql("DELETE FROM cookies_app.booth_scouts WHERE booth_id = :bid", {"bid": booth_id})
        execute_sql("DELETE FROM cookies_app.booths WHERE booth_id = :bid", {"bid": booth_id})
        return True
    except Exception as e:
        print(f"Error deleting booth {booth_id}: {e}")
        return False

