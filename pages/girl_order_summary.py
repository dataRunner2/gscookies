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
# Session checks
# --------------------------------------------------
def require_login():
    if not ss.get("authenticated"):
        st.warning("Please log in to view your orders.")
        st.stop()


# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def get_scouts(parent_id):
    sql = text("""
        SELECT scout_id, first_name, last_name
        FROM cookies_app.scouts
        WHERE parent_id = :parent_id
        ORDER BY last_name, first_name
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"parent_id": parent_id}).fetchall()


def get_orders_for_scout(scout_id, year):
    """
    Returns orders + total paid so far (paper only).
    Digital orders are treated as fully paid.
    """
    sql = text("""
        SELECT
            o.order_id,
            o.order_ref,
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status AS order_status,
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
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {
            "scout_id": scout_id,
            "year": year
        }).fetchall()


def get_order_items(order_id):
    sql = text("""
        SELECT
            cy.display_name,
            oi.quantity
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON oi.cookie_code = cy.cookie_code
         AND oi.program_year = cy.program_year
        WHERE oi.order_id = :order_id
        ORDER BY cy.display_order
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"order_id": order_id}).fetchall()


# --------------------------------------------------
# Status helpers
# --------------------------------------------------
def payment_status(order_type, order_amount, paid_amount):
    if "Digital" in order_type:
        return "PAID"
    return "PAID" if paid_amount >= order_amount else "UNPAID"


# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    require_login()

    st.subheader("Order Summary")

    # ---- Scout ----
    scouts = get_scouts(ss.parent_id)
    if not scouts:
        st.info("No scouts found.")
        return

    c1, c2 = st.columns(2)
    with c1:
        scout = st.selectbox(
            "Scout",
            scouts,
            format_func=lambda s: f"{s.first_name} {s.last_name}"
        )
    with c2:
        # ---- Year ----
        current_year = datetime.now().year
        year = st.selectbox(
            "Program Year",
            [current_year - 1, current_year, current_year + 1],
            index=1
        )

    orders = get_orders_for_scout(scout.scout_id, year)
    if not orders:
        st.info("No orders found for this scout and year.")
        return

    # --------------------------------------------------
    # SUMMARY METRICS
    # --------------------------------------------------
    total_boxes = 0
    paper_boxes = 0
    digital_boxes = 0

    total_due = Decimal("0.00")
    paid_paper = Decimal("0.00")
    paid_digital = Decimal("0.00")

    for o in orders:
        total_boxes += o.order_qty_boxes
        total_due += Decimal(o.order_amount)

        if "Digital" in o.order_type:
            digital_boxes += o.order_qty_boxes
            paid_digital += Decimal(o.order_amount)
        else:
            paper_boxes += o.order_qty_boxes
            paid_paper += Decimal(o.paid_amount)

    total_paid = paid_paper + paid_digital
    balance = total_due - total_paid

    st.markdown("### Season Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Boxes", total_boxes)
    c2.metric("Paper Boxes", paper_boxes)
    c3.metric("Digital Boxes", digital_boxes)

    c4, c5, c6 = st.columns(3)
    c4.metric("Total Due", f"${total_due:.2f}")
    c5.metric("Total Paid", f"${total_paid:.2f}")
    c6.metric("Balance", f"${balance:.2f}")

    st.divider()

    # --------------------------------------------------
    # ORDERS TABLE
    # --------------------------------------------------
    table_rows = []

    for o in orders:
        paid = (
            Decimal(o.order_amount)
            if "Digital" in o.order_type
            else Decimal(o.paid_amount)
        )

        bal = (
            Decimal("0.00")
            if "Digital" in o.order_type
            else Decimal(o.order_amount) - paid
        )

        pay_status = payment_status(o.order_type, Decimal(o.order_amount), paid)

        table_rows.append({
            "Order Date": o.submit_dt.strftime("%Y-%m-%d %H:%M"),
            "Order Type": o.order_type,
            "Boxes": o.order_qty_boxes,
            "Amount": float(o.order_amount),
            "Paid": float(paid),
            "Balance": float(bal),
            "Payment Status": pay_status,
            "Order Status": o.order_status
        })

    st.markdown("### Orders")
    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --------------------------------------------------
    # EXPANDABLE ORDER DETAILS
    # --------------------------------------------------
    st.subheader('Order Details')
    for o in orders:
        paid = (
            Decimal(o.order_amount)
            if "Digital" in o.order_type
            else Decimal(o.paid_amount)
        )

        bal = (
            Decimal("0.00")
            if "Digital" in o.order_type
            else Decimal(o.order_amount) - paid
        )

        pay_status = payment_status(o.order_type, Decimal(o.order_amount), paid)

        order_dt = o.submit_dt.strftime("%b %d, %Y %I:%M %p")

        with st.expander(
            f"{order_dt} — {o.order_qty_boxes} boxes — "
            f"${o.order_amount:.2f} | {pay_status} | {o.order_status}"
        ):
            st.write(f"**Payment Status:** {pay_status}")
            st.write(f"**Order Status:** {o.order_status}")
            st.write(f"**Amount Due:** ${o.order_amount:.2f}")
            st.write(f"**Amount Paid:** ${paid:.2f}")
            st.write(f"**Balance:** ${bal:.2f}")

            st.markdown("**Cookies Ordered**")
            items = get_order_items(o.order_id)
            for item in items:
                st.write(f"- {item.display_name}: {item.quantity}")

            if bal <= 0:
                st.success("Paid in full")
            else:
                st.warning("Payment outstanding")


# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Order Summary",
        initial_sidebar_state="expanded"
    )
    main()
