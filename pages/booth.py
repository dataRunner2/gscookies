import streamlit as st
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text
from streamlit import session_state as ss

from utils.app_utils import setup
from utils.db_utils import get_engine, execute_sql
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
            booth_id,
            location,
            booth_date,
            start_time,
            end_time,
            quantity_multiplier
        FROM cookies_app.booths
        ORDER BY booth_date DESC, start_time
    """)
    with engine.connect() as conn:
        return conn.execute(sql).fetchall()


# Uses get_cookies_for_year from order_utils


def save_booth_order(booth_id, year, total_boxes, total_amount):
    order_id = uuid4()

    sql = """
        INSERT INTO cookies_app.orders (
            order_id,
            booth_id,
            program_year,
            order_type,
            status,
            order_qty_boxes,
            order_amount,
            submit_dt,
            created_at
        )
        VALUES (
            :order_id,
            :booth_id,
            :year,
            'BOOTH',
            'NEW',
            :qty,
            :amt,
            now(),
            now()
        )
    """

    execute_sql(sql, {
        "order_id": str(order_id),
        "booth_id": str(booth_id),
        "year": year,
        "qty": total_boxes,
        "amt": float(total_amount),
    })

    return order_id


def save_order_items(order_id, year, items):
    sql = """
        INSERT INTO cookies_app.order_items (
            order_item_id,
            order_id,
            program_year,
            cookie_code,
            quantity
        )
        VALUES (
            gen_random_uuid(),
            :order_id,
            :year,
            :code,
            :qty
        )
    """

    for i in items:
        execute_sql(sql, {
            "order_id": str(order_id),
            "year": year,
            "code": i["cookie_code"],
            "qty": i["sold"],
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
            f"{b.location}"
        )
    )

    year = booth.booth_date.year
    cookies = get_cookies_for_year(year)

    st.markdown("---")
    st.markdown(
        f"""
        **Location:** {booth.location}  
        **Date:** {booth.booth_date.strftime('%A, %B %d, %Y')}  
        **Time:** {booth.start_time.strftime('%I:%M %p')} – {booth.end_time.strftime('%I:%M %p')}
        """
    )

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

        default_start = int(12 * (booth.quantity_multiplier or 1))

        with c1:
            st.markdown(f"**{c.display_name}**  \n${c.price_per_box:.2f}")

        with c2:
            start_qty = st.number_input(
                "",
                min_value=0,
                value=default_start,
                step=1,
                key=f"start_{c.cookie_code}"
            )

        with c3:
            end_qty = st.number_input(
                "",
                min_value=0,
                value=0,
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

    starting_cash = Decimal(c1.number_input("Starting Cash", value=100.0, step=1.0))
    ending_cash = Decimal(c2.number_input("Ending Cash", value=0.0, step=1.0))
    square_total = Decimal(c3.number_input("Square / Credit", value=0.0, step=1.0))

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
        st.write(f"**(5) Over / Under:** ${diff:.2f}")

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
        )

        save_order_items(order_id, year, items)

        st.success("Booth entry saved (DRAFT). Admin verification required.")
        st.rerun()


# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Entry",
        initial_sidebar_state="expanded"
    )
    main()
