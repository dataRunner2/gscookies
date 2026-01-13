import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

from utils.app_utils import setup


# --------------------------------------------------
# DB connection
# --------------------------------------------------
DB_HOST = "136.118.19.164"
DB_PORT = "5432"
DB_NAME = "cookies"
DB_USER = "cookie_admin"
DB_PASS = st.secrets["general"]["DB_PASSWORD"]

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_pre_ping=True,
)

# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year

# --------------------------------------------------
# Session checks
# --------------------------------------------------
def require_login():
    if not ss.get("authenticated"):
        st.warning("Please log in to view troop orders.")
        st.stop()


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def payment_status(order_type, order_amount, paid_amount):
    if "Digital" in order_type:
        return "PAID"
    return "PAID" if paid_amount >= order_amount else "UNPAID"


# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def get_all_orders(year):
    sql = text("""
        SELECT
            o.order_id,
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status AS order_status,
            o.parent_id,
            o.scout_id,
            o.booth_id,
            p.parent_firstname || ' ' || p.parent_lastname AS parent_name,
            s.first_name || ' ' || s.last_name AS scout_name,
            COALESCE(SUM(m.amount), 0) AS paid_amount
        FROM cookies_app.orders o
        LEFT JOIN cookies_app.parents p
          ON o.parent_id = p.parent_id
        LEFT JOIN cookies_app.scouts s
          ON o.scout_id = s.scout_id
        LEFT JOIN cookies_app.money_ledger m
          ON o.order_id = m.related_order_id
        WHERE o.program_year = :year
        GROUP BY
            o.order_id,
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status,
            o.parent_id,
            o.scout_id,
            o.booth_id,
            parent_name,
            scout_name
        ORDER BY o.submit_dt DESC
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"year": year}).fetchall()


def get_cookie_totals(year):
    sql = text("""
        SELECT
            cy.display_name,
            SUM(oi.quantity) AS total_boxes,
            cy.display_order
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON oi.cookie_code = cy.cookie_code
         AND oi.program_year = cy.program_year
        JOIN cookies_app.orders o
          ON oi.order_id = o.order_id
        WHERE o.program_year = :year
        GROUP BY cy.display_name, cy.display_order
        ORDER BY cy.display_order
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"year": year}).fetchall()

# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    require_login()

    st.subheader("Troop Orders Overview")
    st.caption("Summary of all orders for the selected season.")

    # ---- Year ----
    current_year = datetime.now().year
    year = st.selectbox(
        "Program Year",
        [current_year - 1, current_year, current_year + 1],
        index=1
    )

    orders = get_all_orders(year)
    if not orders:
        st.info("No orders found for this year.")
        return

    # --------------------------------------------------
    # Build aggregates
    # --------------------------------------------------
    rows = []

    girl_orders = 0
    booth_orders = 0

    girl_boxes = 0
    booth_boxes = 0

    total_sales = Decimal("0.00")
    total_paid = Decimal("0.00")

    for o in orders:
        is_booth = o.booth_id is not None
        is_girl = o.scout_id is not None

        paid = (
            Decimal(o.order_amount)
            if "Digital" in o.order_type
            else Decimal(o.paid_amount)
        )

        if is_booth:
            booth_orders += 1
            booth_boxes += o.order_qty_boxes
        elif is_girl:
            girl_orders += 1
            girl_boxes += o.order_qty_boxes

        total_sales += Decimal(o.order_amount)
        total_paid += paid

        rows.append({
            "Order Date": o.submit_dt.strftime("%Y-%m-%d %H:%M"),
            "Order Source": "Booth" if is_booth else "Girl",
            "Parent": o.parent_name if is_girl else "",
            "Scout / Booth": (
                o.scout_name if is_girl else "Booth Sale"
            ),
            "Order Type": o.order_type,
            "Boxes": o.order_qty_boxes,
            "Amount ($)": float(o.order_amount),
            "Paid ($)": float(paid),
            "Balance ($)": float(Decimal(o.order_amount) - paid),
            "Payment Status": payment_status(
                o.order_type,
                Decimal(o.order_amount),
                paid
            ),
            "Order Status": o.order_status
        })

    df = pd.DataFrame(rows)

    # --------------------------------------------------
    # BOOTH VS GIRL SUMMARY (TOP)
    # --------------------------------------------------
    st.markdown("### 🧍‍♀️ Girl Orders vs 🏪 Booth Orders")

    a, b, c, d = st.columns(4)
    a.metric("Girl Orders", girl_orders)
    b.metric("Girl Boxes", girl_boxes)
    c.metric("Booth Orders", booth_orders)
    d.metric("Booth Boxes", booth_boxes)

    st.divider()

    # --------------------------------------------------
    # COOKIE INFOGRAPHIC
    # --------------------------------------------------
    st.markdown("### 🍪 Cookies Sold by Type")

    cookie_totals = get_cookie_totals(year)
    if cookie_totals:
        cols = st.columns(len(cookie_totals))
        for col, c in zip(cols, cookie_totals):
            with col:
                st.metric(c.display_name, int(c.total_boxes))
    else:
        st.info("No cookie breakdown available.")

    st.divider()

    # --------------------------------------------------
    # SEASON SUMMARY
    # --------------------------------------------------
    balance = total_sales - total_paid

    st.markdown("### 💵 Season Totals")

    e, f, g = st.columns(3)
    e.metric("Total Sales", f"${total_sales:,.2f}")
    f.metric("Total Paid", f"${total_paid:,.2f}")
    g.metric("Outstanding Balance", f"${balance:,.2f}")

    st.divider()


# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Troop Orders Overview",
        initial_sidebar_state="expanded"
    )
    main()
