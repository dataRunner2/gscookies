from decimal import Decimal
from sqlalchemy import text
from utils.db_utils import fetch_all, fetch_one, execute_sql


# ==================================================
# Booth retrieval
# ==================================================

def get_booths(program_year=None):
    params = {}
    year_sql = ""

    if program_year:
        year_sql = "WHERE program_year = :year"
        params["year"] = program_year

    return fetch_all(f"""
        SELECT
            booth_id,
            location,
            booth_date,
            start_time,
            end_time,
            program_year
        FROM cookies_app.booths
        {year_sql}
        ORDER BY booth_date DESC, start_time
    """, params)


def get_booth(booth_id):
    return fetch_one("""
        SELECT
            booth_id,
            location,
            booth_date,
            start_time,
            end_time,
            program_year
        FROM cookies_app.booths
        WHERE booth_id = :bid
    """, {"bid": booth_id})


# ==================================================
# Booth scouts
# ==================================================

def set_booth_scouts(booth_id, scout_ids):
    """
    Replace scouts assigned to a booth.
    """
    execute_sql("""
        DELETE FROM cookies_app.booth_scouts
        WHERE booth_id = :bid
    """, {"bid": booth_id})

    for sid in scout_ids:
        execute_sql("""
            INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
            VALUES (:bid, :sid)
        """, {"bid": booth_id, "sid": sid})


def get_booth_scouts(booth_id):
    return fetch_all("""
        SELECT
            s.scout_id,
            s.first_name,
            s.last_name
        FROM cookies_app.booth_scouts bs
        JOIN cookies_app.scouts s ON s.scout_id = bs.scout_id
        WHERE bs.booth_id = :bid
        ORDER BY s.last_name, s.first_name
    """, {"bid": booth_id})


# ==================================================
# Booth inventory – planned
# ==================================================

def set_booth_inventory_plan(booth_id, program_year, cookie_quantities: dict):
    """
    cookie_quantities = {cookie_code: planned_qty}
    """
    execute_sql("""
        DELETE FROM cookies_app.booth_inventory_plan
        WHERE booth_id = :bid AND program_year = :year
    """, {"bid": booth_id, "year": program_year})

    for code, qty in cookie_quantities.items():
        execute_sql("""
            INSERT INTO cookies_app.booth_inventory_plan (
                booth_id,
                program_year,
                cookie_code,
                planned_quantity
            )
            VALUES (:bid, :year, :code, :qty)
        """, {
            "bid": booth_id,
            "year": program_year,
            "code": code,
            "qty": int(qty)
        })


def get_booth_inventory_plan(booth_id, program_year):
    return fetch_all("""
        SELECT
            bip.cookie_code,
            cy.display_name,
            cy.price_per_box,
            bip.planned_quantity
        FROM cookies_app.booth_inventory_plan bip
        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = bip.cookie_code
         AND cy.program_year = bip.program_year
        WHERE bip.booth_id = :bid
          AND bip.program_year = :year
        ORDER BY cy.display_order
    """, {
        "bid": booth_id,
        "year": program_year
    })


# ==================================================
# Booth inventory – actual (entered by volunteer/admin)
# ==================================================

def save_booth_inventory_actual(booth_id, program_year, end_quantities: dict):
    """
    Stores ending quantities entered on booth sheet.
    """
    execute_sql("""
        DELETE FROM cookies_app.booth_inventory_actual
        WHERE booth_id = :bid AND program_year = :year
    """, {"bid": booth_id, "year": program_year})

    for code, qty in end_quantities.items():
        execute_sql("""
            INSERT INTO cookies_app.booth_inventory_actual (
                booth_id,
                program_year,
                cookie_code,
                end_quantity
            )
            VALUES (:bid, :year, :code, :qty)
        """, {
            "bid": booth_id,
            "year": program_year,
            "code": code,
            "qty": int(qty)
        })


def get_booth_inventory_actual(booth_id, program_year):
    return fetch_all("""
        SELECT
            bia.cookie_code,
            cy.display_name,
            cy.price_per_box,
            bia.end_quantity
        FROM cookies_app.booth_inventory_actual bia
        JOIN cookies_app.cookie_years cy
          ON cy.cookie_code = bia.cookie_code
         AND cy.program_year = bia.program_year
        WHERE bia.booth_id = :bid
          AND bia.program_year = :year
        ORDER BY cy.display_order
    """, {
        "bid": booth_id,
        "year": program_year
    })


# ==================================================
# Booth calculations
# ==================================================

def calculate_booth_sales(booth_id, program_year):
    """
    Returns list of:
      cookie_code, display_name, sold, price, revenue
    """
    plan = get_booth_inventory_plan(booth_id, program_year)
    actual = {
        r["cookie_code"]: int(r["end_quantity"])
        for r in get_booth_inventory_actual(booth_id, program_year)
    }

    results = []
    total_boxes = 0
    total_revenue = Decimal("0.00")

    for p in plan:
        start = int(p["planned_quantity"])
        end = actual.get(p["cookie_code"], 0)
        sold = start - end
        price = Decimal(p["price_per_box"])
        revenue = Decimal(sold) * price

        results.append({
            "cookie_code": p["cookie_code"],
            "display_name": p["display_name"],
            "start_qty": start,
            "end_qty": end,
            "sold": sold,
            "price": price,
            "revenue": revenue
        })

        total_boxes += sold
        total_revenue += revenue

    return results, total_boxes, total_revenue


def calculate_opc_boxes(expected_revenue, actual_revenue, box_price=Decimal("6")):
    diff = actual_revenue - expected_revenue
    if diff <= 0:
        return 0
    return int((diff / box_price).to_integral_value())


# ==================================================
# Booth verification (ADMIN ONLY)
# ==================================================

def verify_booth(
    order_id,
    booth_id,
    program_year,
    admin_name,
    notes,
    opc_boxes,
    cookie_sales_rows
):
    """
    Finalizes booth:
    - marks order verified
    - writes inventory ledger ACTUAL entries
    """
    # Mark booth order verified
    execute_sql("""
        UPDATE cookies_app.orders
        SET verification_status = 'VERIFIED',
            verified_by = :by,
            verified_at = now(),
            verification_notes = :notes,
            opc_boxes = :opc
        WHERE order_id = :oid
    """, {
        "oid": order_id,
        "by": admin_name,
        "notes": notes,
        "opc": opc_boxes
    })

    # Apply inventory ledger
    for row in cookie_sales_rows:
        if row["sold"] <= 0:
            continue

        execute_sql("""
            INSERT INTO cookies_app.inventory_ledger (
                inventory_event_id,
                program_year,
                cookie_code,
                quantity,
                event_type,
                status,
                related_order_id,
                event_dt,
                notes
            )
            VALUES (
                gen_random_uuid(),
                :year,
                :cookie,
                :qty,
                'BOOTH_SALE',
                'ACTUAL',
                :oid,
                now(),
                'Booth verified'
            )
        """, {
            "year": program_year,
            "cookie": row["cookie_code"],
            "qty": -row["sold"],
            "oid": order_id
        })
