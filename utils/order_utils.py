from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from utils.db_utils import fetch_all, fetch_one, execute_sql


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
# Core: order header + items
# ==================================================

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
            o.verified_digital_cookie
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
        SET verified_digital_cookie = :v
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
    Returns rows for admin order management (pivot-friendly):
      One row per (order_id, scout_id, cookie_code)

    Column naming is intentionally aligned to the *old ES page expectations*
    to avoid KeyErrors:
      orderId, orderType, orderStatus, paymentStatus, addEbudde, verifiedDigitalCookie,
      initialOrder, scoutName, guardianNm, guardianPh, cookieCode, qty, pricePerBox, submit_dt, etc.
    """

    rows = fetch_all(f"""
        WITH paid AS (
            SELECT
                related_order_id AS order_id,
                COALESCE(SUM(amount), 0) AS paid_amount
            FROM cookies_app.money_ledger
            GROUP BY related_order_id
        )
        SELECT
            o.order_id                    AS "orderId",
            o.program_year                AS "programYear",
            o.order_type                  AS "orderType",
            o.status                      AS "orderStatus",
            o.submit_dt                   AS "submit_dt",
            o.order_amount                AS "orderAmount",
            o.order_qty_boxes             AS "orderQtyBoxes",
            o.comments                    AS "comments",
            o.parent_id                   AS "parentId",
            o.scout_id                    AS "scoutId",
            o.booth_id                    AS "boothId",

            COALESCE(o.initial_order, {_initial_order_window_sql()}) AS "initialOrder",
            COALESCE(o.add_ebudde, false)                           AS "addEbudde",
            COALESCE(o.verified_digital_cookie, false)              AS "verifiedDigitalCookie",

            (p.parent_firstname || ' ' || p.parent_lastname)        AS "guardianNm",
            p.parent_phone                                          AS "guardianPh",

            (s.first_name || ' ' || s.last_name)                    AS "scoutName",

            oi.cookie_code                                          AS "cookieCode",
            oi.quantity                                             AS "qty",
            cy.price_per_box                                        AS "pricePerBox",

            COALESCE(paid.paid_amount, 0)                           AS "paidAmount"
        FROM cookies_app.orders o
        LEFT JOIN paid ON paid.order_id = o.order_id
        LEFT JOIN cookies_app.parents p ON p.parent_id = o.parent_id
        LEFT JOIN cookies_app.scouts  s ON s.scout_id  = COALESCE(oi.scout_id, o.scout_id)
        JOIN cookies_app.order_items oi ON oi.order_id = o.order_id
        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = oi.cookie_code
         AND cy.program_year = oi.program_year
        WHERE o.program_year = :year
        ORDER BY o.submit_dt DESC, o.order_id, cy.display_order
    """, {"year": program_year})

    # Add computed paymentStatus in python (keeps SQL simpler + consistent)
    for r in rows:
        order_type = r["orderType"]
        due = _dec(r["orderAmount"])
        paid_amt = _dec(r["paidAmount"])
        r["paymentStatus"] = get_payment_status(order_type, due, paid_amt)

        # Non-digital orders: "verifiedDigitalCookie" should not be meaningful
        if not _is_digital(order_type):
            r["verifiedDigitalCookie"] = False

    return rows


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
        "verifiedDigitalCookie": "verified_digital_cookie",
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
