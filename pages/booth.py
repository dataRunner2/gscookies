import math
import streamlit as st
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text
from streamlit import session_state as ss

from utils.app_utils import setup
from utils.db_utils import get_engine, execute_sql, fetch_all
from utils.order_utils import get_cookies_for_year

engine = get_engine()

# --------------------------------------------------
# Guards
# --------------------------------------------------
def require_login():
    if not ss.get("authenticated"):
        st.error("Please log in.")
        st.stop()


# --------------------------------------------------
# Data helpers
# --------------------------------------------------
def get_booths():
    sql = text("""
        SELECT
            b.booth_id,
            b.location,
            b.booth_date,
            b.start_time,
            b.end_time,
            b.quantity_multiplier,
            COALESCE(o.verification_status, 'NEW') as status
        FROM cookies_app.booths b
        LEFT JOIN cookies_app.orders o ON o.booth_id = b.booth_id AND o.order_type = 'Booth'
        WHERE COALESCE(o.verification_status, 'NEW') != 'VERIFIED'
        ORDER BY 
            CASE COALESCE(o.verification_status, 'NEW')
                WHEN 'NEW' THEN 1
                WHEN 'DRAFT' THEN 2
                WHEN 'VERIFIED' THEN 3
            END,
            b.booth_date DESC, 
            b.start_time
    """)
    with engine.connect() as conn:
        return conn.execute(sql).fetchall()


# Uses get_cookies_for_year from order_utils


def save_booth_order(booth_id, year, total_boxes, total_amount, starting_cash, ending_cash, square_total, parent_id=None, scout_id=None):
    # Default parent_id and scout_id to 999 if not provided
    if parent_id is None:
        parent_id = 999
    if scout_id is None:
        scout_id = 999
    
    # Check if order already exists for this booth
    existing = fetch_all("""
        SELECT order_id 
        FROM cookies_app.orders 
        WHERE booth_id = :booth_id 
          AND order_type = 'BOOTH'
          AND program_year = :year
    """, {"booth_id": booth_id, "year": year})
    
    if existing:
        # Update existing order - set status to PENDING since parent is submitting data
        # Also update parent_id and scout_id from the scouts selected by the parent
        order_id = existing[0].order_id
        execute_sql("""
            UPDATE cookies_app.orders
            SET order_qty_boxes = :qty,
                order_amount = :amt,
                starting_cash = :starting_cash,
                ending_cash = :ending_cash,
                square_total = :square_total,
                parent_id = :parent_id,
                scout_id = :scout_id,
                submit_dt = now(),
                status = 'PENDING',
                verification_status = 'DRAFT'
            WHERE order_id = :order_id
        """, {
            "order_id": str(order_id),
            "qty": total_boxes,
            "amt": float(total_amount),
            "starting_cash": float(starting_cash),
            "ending_cash": float(ending_cash),
            "square_total": float(square_total),
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
        })
    else:
        # Create new order (fallback if admin didn't create it)
        order_id = uuid4()
        execute_sql("""
            INSERT INTO cookies_app.orders (
                order_id,
                booth_id,
                parent_id,
                scout_id,
                program_year,
                order_type,
                status,
                verification_status,
                order_qty_boxes,
                order_amount,
                starting_cash,
                ending_cash,
                square_total,
                submit_dt,
                created_at
            )
            VALUES (
                :order_id,
                :booth_id,
                :parent_id,
                :scout_id,
                :year,
                'Booth',
                'PENDING',
                'DRAFT',
                :qty,
                :amt,
                :starting_cash,
                :ending_cash,
                :square_total,
                now(),
                now()
            )
        """, {
            "order_id": str(order_id),
            "booth_id": str(booth_id),
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
            "year": year,
            "qty": total_boxes,
            "amt": float(total_amount),
            "starting_cash": float(starting_cash),
            "ending_cash": float(ending_cash),
            "square_total": float(square_total),
        })

    return order_id


def save_order_items(order_id, year, items, parent_id=None, scout_id=None):
    # Default parent_id and scout_id to 999 if not provided
    if parent_id is None:
        parent_id = 999
    if scout_id is None:
        scout_id = 999
    
    # Delete existing order items for this order
    execute_sql("""
        DELETE FROM cookies_app.order_items
        WHERE order_id = :order_id
    """, {"order_id": str(order_id)})
    
    # Insert new order items
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
            :year,
            :code,
            :qty
        )
    """

    for i in items:
        execute_sql(sql, {
            "order_id": str(order_id),
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
            "year": year,
            "code": i["cookie_code"],
            "qty": i["sold"],
        })


def save_booth_scouts(booth_id, scout_ids):
    """Save the scouts working at a booth to the booth_scouts table."""
    # Delete existing booth_scouts entries
    execute_sql("""
        DELETE FROM cookies_app.booth_scouts
        WHERE booth_id = :booth_id
    """, {"booth_id": booth_id})
    
    # Insert new booth_scouts entries
    for scout_id in scout_ids:
        execute_sql("""
            INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
            VALUES (:booth_id, :scout_id)
        """, {
            "booth_id": booth_id,
            "scout_id": scout_id,
        })


# --------------------------------------------------
# Page
# --------------------------------------------------
def main():
    require_login()

    st.subheader("Booth Entry Sheet")
    st.caption("Matches the paper booth worksheet. Saved as DRAFT until verified.")
    st.error("This page is to be completed by booth parents AFTER the booth is completed. Make sure you select your booth location, date and time")
    
    booths = get_booths()
    if not booths:
        st.info("No booths have been entered.")
        st.stop()
    
    booth = st.selectbox(
        "Choose Booth",
        booths,
        format_func=lambda b: (
            f"{b.booth_date.strftime('%b %d')} "
            f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
            f"{b.location} ({b.status})"
        )
    )

    year = booth.booth_date.year
    cookies = get_cookies_for_year(year)

    # Get planned inventory for this booth
    planned_inventory = fetch_all("""
        SELECT cookie_code, planned_quantity
        FROM cookies_app.booth_inventory_plan
        WHERE booth_id = :bid
          AND program_year = :year
    """, {"bid": booth.booth_id, "year": year})
    
    planned_qty_lookup = {item.cookie_code: item.planned_quantity for item in planned_inventory}
    
    # Load existing order data if it exists
    existing_order = fetch_all("""
        SELECT order_id, starting_cash, ending_cash, square_total
        FROM cookies_app.orders
        WHERE booth_id = :bid
          AND order_type = 'Booth'
          AND program_year = :year
    """, {"bid": booth.booth_id, "year": year})
    
    # Load existing order items to get end quantities
    existing_items = {}
    if existing_order:
        order_items = fetch_all("""
            SELECT cookie_code, quantity as sold
            FROM cookies_app.order_items
            WHERE order_id = :oid
        """, {"oid": existing_order[0].order_id})
        
        for item in order_items:
            start_qty = planned_qty_lookup.get(item.cookie_code, 0)
            existing_items[item.cookie_code] = start_qty - item.sold
    
    # Default money values from existing order or defaults
    default_starting_cash = float(existing_order[0].starting_cash) if existing_order and existing_order[0].starting_cash else 100.0
    default_ending_cash = float(existing_order[0].ending_cash) if existing_order and existing_order[0].ending_cash else 0.0
    default_square_total = float(existing_order[0].square_total) if existing_order and existing_order[0].square_total else 0.0
    
    # Debug: show what we got
    if planned_qty_lookup:
        st.write(f"✓ Loaded planned inventory for booth {booth.booth_id}")
    else:
        st.write(f"⚠️ No planned inventory found for booth {booth.booth_id} (year {year})")

    st.markdown("---")
    st.markdown(
        f"""
        **Location:** {booth.location}  
        **Date:** {booth.booth_date.strftime('%A, %B %d, %Y')}  
        **Time:** {booth.start_time.strftime('%I:%M %p')} – {booth.end_time.strftime('%I:%M %p')}
        """
    )

    # Scout selector
    scouts = fetch_all("""
        SELECT scout_id, parent_id, first_name || ' ' || last_name AS name
        FROM cookies_app.scouts
        ORDER BY last_name, first_name
    """)

    scout_ids = st.multiselect(
        "Select Scouts Working This Booth (up to 4)",
        options=[s.scout_id for s in scouts],
        format_func=lambda sid: next(s.name for s in scouts if s.scout_id == sid),
        max_selections=4,
    )

    # Get parent_id and scout_id from first selected scout
    parent_id = None
    scout_id = None
    if scout_ids:
        first_scout = next((s for s in scouts if s.scout_id == scout_ids[0]), None)
        if first_scout:
            parent_id = first_scout.parent_id
            scout_id = first_scout.scout_id

    st.markdown("---")
    st.markdown("### 🍪 Cookie Counts")

    # Totals
    total_start = 0
    total_end = 0
    total_sold = 0
    total_revenue = Decimal("0.00")
    items = []

    # Header
    h1, h2, h3, h4, h5 = st.columns([2.5, 1, 1, 1, 1])
    h1.markdown("**Cookie**")
    h2.markdown("**Start**")
    h3.markdown("**End**")
    h4.markdown("**Sold**")
    h5.markdown("**Revenue**")

    for c in cookies:
        c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1, 1, 1])

        # Use planned quantity from booth_inventory_plan
        # default_start = planned_qty_lookup.get(c.cookie_code, 0)
        # st.write(f"(default_start for {c.cookie_code}: {default_start})")

        with c1:
            st.markdown(f"**{c.display_name}**  \n${c.price_per_box:.2f}")

        with c2:
            start_qty = st.number_input(
                "",
                min_value=0,
                value=planned_qty_lookup.get(c.cookie_code, 0),
                step=1,
                key=f"start_{c.cookie_code}"
            )

        with c3:
            end_qty = st.number_input(
                "",
                min_value=0,
                value=existing_items.get(c.cookie_code, 0),
                step=1,
                key=f"end_{c.cookie_code}"
            )

        sold = max(start_qty - end_qty, 0)
        revenue = Decimal(sold) * Decimal(c.price_per_box)

        with c4:
            st.markdown(f"{sold}")

        with c5:
            st.markdown(f"${revenue:.2f}")

        total_start += start_qty
        total_end += end_qty
        total_sold += sold
        total_revenue += revenue

        if sold > 0:
            items.append({
                "cookie_code": c.cookie_code,
                "sold": sold,
            })

    # Totals row
    st.markdown("---")
    t1, t2, t3, t4, t5 = st.columns([2.5, 1, 1, 1, 1])
    t1.markdown("**TOTAL**")
    t2.markdown(f"**{total_start}**")
    t3.markdown(f"**{total_end}**")
    t4.markdown(f"**{total_sold}**")
    t5.markdown(f"**${total_revenue:.2f}**")

    # Money section
    st.markdown("---")
    st.markdown("### 💵 Money Counts")

    c1, c2, c3 = st.columns(3)

    starting_cash = Decimal(c1.number_input("Starting Cash", value=default_starting_cash, step=1.0))
    ending_cash = Decimal(c2.number_input("Ending Cash", value=default_ending_cash, step=1.0))
    square_total = Decimal(c3.number_input("Square / Credit", value=default_square_total, step=1.0))

    if st.button("Calculate"):
        ending_money = ending_cash + square_total
        revenue = ending_money - starting_cash
        diff = revenue - total_revenue

        st.markdown("---")
        st.markdown("### 🧮 Calculations")

        st.write(f"**(1) Ending Money:** ${ending_money:.2f}")
        st.write(f"**(2) Starting Cash:** ${starting_cash:.2f}")
        st.write(f"**(3) Revenue:** ${revenue:.2f}")
        st.write(f"**(4) Expected Revenue:** ${total_revenue:.2f}")
        st.write(f"**(5) Sweet Acts of Kindess Boxes:** {math.floor(diff/6):.0f} boxes")

    st.markdown("---")

    if st.button("Submit Booth Entry"):
        if total_sold == 0:
            st.error("No boxes sold.")
            st.stop()

        order_id = save_booth_order(
            booth_id=booth.booth_id,
            year=year,
            total_boxes=total_sold,
            total_amount=total_revenue,
            starting_cash=starting_cash,
            ending_cash=ending_cash,
            square_total=square_total,
            parent_id=parent_id,
            scout_id=scout_id,
        )

        save_order_items(order_id, year, items, parent_id, scout_id)
        
        # Save the scouts working this booth
        save_booth_scouts(booth.booth_id, scout_ids)

        st.success("Booth entry saved (DRAFT). Admin verification required.")
        #st.rerun()


# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Entry",
        initial_sidebar_state="expanded"
    )
    main()
