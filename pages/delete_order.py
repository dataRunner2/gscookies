import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, text

from utils.app_utils import setup

from utils.db_utils import get_engine

engine = get_engine()

# --------------------------------------------------
# Session checks
# --------------------------------------------------
def require_login():
    if not ss.get("authenticated"):
        st.warning("Please log in to continue.")
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
    sql = text("""
        SELECT
            o.order_id,
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
            o.submit_dt,
            o.order_type,
            o.order_qty_boxes,
            o.order_amount,
            o.status,
            o.comments
        ORDER BY o.submit_dt DESC
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {
            "scout_id": scout_id,
            "year": year
        }).fetchall()


def update_order(order_id, order_type, comments):
    sql = text("""
        UPDATE cookies_app.orders
        SET order_type = :order_type,
            comments = :comments
        WHERE order_id = :order_id
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "order_id": order_id,
            "order_type": order_type,
            "comments": comments
        })


def delete_order(order_id):
    sql_items = text("""
        DELETE FROM cookies_app.order_items
        WHERE order_id = :order_id
    """)

    sql_inventory = text("""
        DELETE FROM cookies_app.inventory_ledger
        WHERE related_order_id = :order_id
    """)

    sql_order = text("""
        DELETE FROM cookies_app.orders
        WHERE order_id = :order_id
    """)

    with engine.begin() as conn:
        conn.execute(sql_items, {"order_id": order_id})
        conn.execute(sql_inventory, {"order_id": order_id})
        conn.execute(sql_order, {"order_id": order_id})


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def is_digital(order_type):
    return "Digital" in order_type


def can_delete(order_type, order_status, paid_amount):
    if order_status == "PICKED_UP":
        return False
    if not is_digital(order_type) and paid_amount > 0:
        return False
    return True


# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    require_login()

    st.subheader("Modify or Delete Order")

    # ---- Scout ----
    scouts = get_scouts(ss.parent_id)
    if not scouts:
        st.info("No scouts found.")
        return

    scout = st.selectbox(
        "Scout",
        scouts,
        format_func=lambda s: f"{s.first_name} {s.last_name}"
    )

    # ---- Get Current Year Orders ----
    
    orders = get_orders_for_scout(scout.scout_id, ss.current_year)
    if not orders:
        st.info("No orders found.")
        return

    def order_label(o):
        paid = Decimal(o.paid_amount)
        payment_label = "PAID" if is_digital(o.order_type) or paid > 0 else "UNPAID"

        return (
            f"{o.submit_dt.strftime('%b %d %I:%M %p')} — "
            f"{o.order_type} — "
            f"{payment_label} — "
            f"{o.order_status} — "
            f"{o.order_qty_boxes} boxes — "
            f"${o.order_amount:.2f}"
        )

    order = st.selectbox("Order", orders, format_func=order_label)

    paid_amount = Decimal(order.paid_amount)
    deletable = can_delete(order.order_type, order.order_status, paid_amount)

    st.markdown("### Order Details")
    st.write(f"**Order Type:** {order.order_type}")
    st.write(f"**Order Status:** {order.order_status}")
    st.write(f"**Money Received:** ${paid_amount:.2f}")

    st.divider()

    # --------------------------------------------------
    # MODIFY
    # --------------------------------------------------
    st.markdown("### Modify Order")

    with st.form("modify_order"):
        new_order_type = st.selectbox(
            "Order Type",
            ["Paper Order", "Digital Cookie Girl Delivery"],
            index=1 if is_digital(order.order_type) else 0
        )

        comments = st.text_area("Notes", value=order.comments or "")

        if st.form_submit_button("Save Changes"):
            update_order(order.order_id, new_order_type, comments)
            st.success("Order updated successfully.")
            st.rerun()

    st.divider()

    # --------------------------------------------------
    # DELETE
    # --------------------------------------------------
    st.markdown("### Delete Order")

    if not deletable:
        if order.order_status == "PICKED_UP":
            st.info("Orders that have been picked up cannot be deleted.")
        else:
            st.info("Paper orders with received money cannot be deleted.")
        return

    with st.form("delete_order"):
        confirm = st.checkbox(
            "I understand this will permanently delete the order."
        )

        if st.form_submit_button("Delete Order"):
            if not confirm:
                st.error("Please confirm deletion.")
                return

            delete_order(order.order_id)
            st.success("Order deleted successfully.")
            st.rerun()


# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Modify or Delete Order",
        initial_sidebar_state="expanded"
    )
    main()
