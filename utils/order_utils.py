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
    conn.execute(
        """
        INSERT INTO scout_aliases (alias_name, scout_id)
        VALUES (%s, %s)
        ON CONFLICT (alias_name) DO NOTHING
        """,
        (alias_name, scout_id),
    )
    conn.commit()

def get_all_parents():
    return fetch_all("""
        SELECT parent_id, parent_firstname, parent_lastname
        FROM cookies_app.parents
        ORDER BY parent_lastname, parent_firstname
    """)

def update_scout_gsusa_id(scout_id, gsusa_id):
    engine = get_engine()
    with engine().begin() as conn:
        conn.execute(
            text("""
                UPDATE scouts
                SET gsusa_id = :gsusa_id
                WHERE scout_id = :scout_id
                  AND gsusa_id IS NULL
            """),
            {
                "scout_id": scout_id,
                "gsusa_id": str(gsusa_id),
            },
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
        WHERE o.order_type <> 'BOOTH'
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
            now(),
            now()
        )
    """

    payload = []

    for r in df.itertuples():
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
        })

        # store for downstream inserts
        df.at[r.Index, "order_id"] = order_id

    execute_many_sql(sql, payload)

def bulk_insert_order_items(df):
    # send in orders df, this will submit to dict lik {"TM": 4,"TT":2}
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

    payload = []

    if 'cookie_code' in df.columns and 'quantity' in df.columns:
        # Long format: one row per item
        for r in df.itertuples():
            if getattr(r, 'quantity', 0) > 0:
                payload.append({
                    "order_item_id": str(uuid.uuid4()),
                    "order_id": str(r.order_id),
                    "parent_id": str(r.parent_id),
                    "scout_id": str(r.scout_id),
                    "program_year": r.program_year,
                    "cookie_code": r.cookie_code,
                    "quantity": r.quantity,
                })
    else:
        # Wide format: columns are cookie codes
        meta_cols = {'order_id', 'parent_id', 'scout_id', 'program_year', 'order_ref', 'order_type', 'status', 'order_qty_boxes', 'order_amount', 'comments', 'external_order_id', 'order_source', 'submit_dt', 'created_at'}

        for r in df.itertuples():
            for col in df.columns:
                if col in meta_cols:
                    continue
                qty = getattr(r, col)
                if qty > 0:
                    payload.append({
                        "order_item_id": str(uuid.uuid4()),
                        "order_id": str(r.order_id),
                        "parent_id": str(r.parent_id),
                        "scout_id": str(r.scout_id),
                        "program_year": r.program_year,
                        "cookie_code": col,
                        "quantity": qty,
                    })

    execute_many_sql(sql, payload)

def bulk_insert_planned_inventory(df):
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
            if getattr(r, 'quantity', 0) > 0:
                payload.append({
                    "parent_id": str(r.parent_id),
                    "scout_id": str(r.scout_id),
                    "program_year": r.program_year,
                    "cookie_code": r.cookie_code,
                    "quantity": r.quantity,
                    "order_id": str(r.order_id),
                })
    else:
        # Wide format
        meta_cols = {'order_id', 'parent_id', 'scout_id', 'program_year', 'order_ref', 'order_type', 'status', 'order_qty_boxes', 'order_amount', 'comments', 'external_order_id', 'order_source', 'submit_dt', 'created_at'}

        for r in df.itertuples():
            for col in df.columns:
                if col in meta_cols:
                    continue
                qty = getattr(r, col)
                if qty > 0:
                    payload.append({
                        "parent_id": str(r.parent_id),
                        "scout_id": str(r.scout_id),
                        "program_year": r.program_year,
                        "cookie_code": col,
                        "quantity": qty,
                        "order_id": str(r.order_id),
                    })

    execute_many_sql(sql, payload)

def bulk_insert_orders(df):
    bulk_insert_order_headers(df)
    bulk_insert_order_items(df)
    bulk_insert_planned_inventory(df)


# ==================================================
# Payments & balances
# ==================================================

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
        AND order_type <> 'BOOTH'
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


def get_admin_print_orders(statuses: Optional[list[str]] = None):
    """
    Rows for admin print: includes order-level header fields + item-level cookie counts.
    Output: one row per (order_id, cookie_code)
    """
    where = ["o.order_type <> 'BOOTH'"]
    params: dict[str, Any] = {}

    if statuses:
        where.append("o.status = ANY(:statuses)")
        params["statuses"] = statuses

    where_sql = " AND ".join(where)

    return fetch_all(f"""
        SELECT
            o.order_id,
            o.order_type,
            o.status,
            o.order_amount,
            o.order_qty_boxes,
            o.comments,
            o.submit_dt::date AS submit_date,

            s.scout_id,
            (s.first_name || ' ' || s.last_name) AS scout_name,

            COALESCE(o.guardian_name, p.parent_firstname || ' ' || p.parent_lastname) AS guardian_name,
            COALESCE(o.guardian_phone, p.parent_phone) AS guardian_phone,

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

def admin_update_orders_bulk(updates: list[dict[str, Any]]):
    """
    Apply bulk updates to orders.
    Each item in 'updates' should look like:
      {"orderId": "...", "initialOrder": True, "addEbudde": False, "verifiedDigitalCookie": True, "orderStatus": "PRINTED", ...}
    Only whitelisted fields are applied.
    """
    allowed = {
        "initialOrder": "initial_order",
        "addEbudde": "add_ebudde",
        "verifiedDigitalCookie": "verified_digital",
        "orderStatus": "status",
        "comments": "comments",
        "orderType": "order_type",
    }

    for u in updates:
        oid = u.get("orderId")
        if not oid:
            continue

        sets = []
        params: dict[str, Any] = {"oid": oid}

        for k, col in allowed.items():
            if k in u:
                sets.append(f"{col} = :{k}")
                params[k] = u[k]

        if not sets:
            continue

        sql = f"""
            UPDATE cookies_app.orders
            SET {", ".join(sets)}
            WHERE order_id = :oid
        """
        execute_sql(sql, params)

def fetch_existing_external_orders(order_source: str) -> set:
    rows = fetch_all("""
        SELECT external_order_id
        FROM cookies_app.orders
        WHERE order_source = :source
    """, {"source": order_source})
    return [r['external_order_id'] for r in rows]
    
