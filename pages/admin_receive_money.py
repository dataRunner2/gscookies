import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text

from utils.app_utils import setup
from utils.db_utils import get_engine

engine = get_engine()

# --------------------------------------------------
# Session helpers
# --------------------------------------------------
def init_flags():
    ss.setdefault("payment_success", None)


def require_admin():
    if not ss.get("authenticated") or not ss.get("is_admin"):
        st.error("Admin access required.")
        st.stop()


# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def get_parents(year):
    sql = text("""
        SELECT DISTINCT
            p.parent_id,
            p.parent_firstname || ' ' || p.parent_lastname AS parent_name
        FROM cookies_app.parents p
        JOIN cookies_app.orders o
          ON p.parent_id = o.parent_id
        WHERE o.program_year = :year
        ORDER BY parent_name
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"year": year}).fetchall()


def get_orders_for_parent(parent_id, year):
    sql = text("""
        SELECT
            o.order_id,
            o.order_ref,
            o.scout_id,
            s.first_name || ' ' || s.last_name AS scout_name,
            o.order_qty_boxes,
            o.order_amount,
            o.status,
            o.created_at
        FROM cookies_app.orders o
        JOIN cookies_app.scouts s
          ON o.scout_id = s.scout_id
        WHERE o.parent_id = :parent_id
          AND o.program_year = :year
        ORDER BY o.created_at
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {
            "parent_id": parent_id,
            "year": year
        }).fetchall()


def get_money_received(order_id):
    sql = text("""
        SELECT COALESCE(SUM(amount), 0)
        FROM cookies_app.money_ledger
        WHERE related_order_id = :order_id
    """)
    with engine.connect() as conn:
        return Decimal(conn.execute(sql, {"order_id": order_id}).scalar())


def insert_money_received(
    parent_id,
    scout_id,
    order_id,
    program_year,
    amount,
    method,
    notes
):
    sql = text("""
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
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "parent_id": parent_id,
            "scout_id": scout_id,
            "program_year": program_year,
            "amount": amount,
            "method": method,
            "notes": notes,
            "order_id": order_id
        })


def update_order_status_if_paid(order_id):
    sql = text("""
        UPDATE cookies_app.orders o
        SET status = 'PAID'
        WHERE o.order_id = :order_id
          AND (
              SELECT COALESCE(SUM(m.amount), 0)
              FROM cookies_app.money_ledger m
              WHERE m.related_order_id = o.order_id
          ) >= o.order_amount
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"order_id": order_id})


# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    require_admin()

    # ---- Persistent confirmation ----
    if ss.payment_success:
        st.success(
            f"Payment recorded successfully.\n\n"
            f"Amount: ${ss.payment_success['amount']:.2f}\n"
            f"Method: {ss.payment_success['method']}\n"
            f"Orders: {', '.join(ss.payment_success['orders'])}"
        )

        if st.button("Record another payment"):
            ss.payment_success = None
            st.rerun()

        st.divider()

    

    # ---- Year ----
    year = datetime.now().year
    st.subheader(f"Receive Money for year {year}")
    

    # ---- Parent ----
    parents = get_parents(year)
    if not parents:
        st.info("No orders found for this year.")
        return

    parent = st.selectbox(
        "Parent",
        parents,
        format_func=lambda p: p.parent_name
    )

    # ---- Orders (multiselect) ----
    orders = get_orders_for_parent(parent.parent_id, year)
    if not orders:
        st.info("No orders for this parent.")
        return

    order_choices = st.multiselect(
        "Orders",
        orders,
        format_func=lambda o: (
            f"{o.order_ref} — {o.scout_name} "
            f"(${o.order_amount:.2f}, {o.status})"
        )
    )

    if not order_choices:
        st.info("Select one or more orders to receive payment.")
        return

    # ---- Totals ----
    total_due = Decimal("0.00")
    total_received = Decimal("0.00")

    for o in order_choices:
        rec = get_money_received(o.order_id)
        total_due += Decimal(o.order_amount)
        total_received += rec

    balance = total_due - total_received

    st.markdown("### Selected Orders Summary")
    st.write(f"**Orders Selected:** {len(order_choices)}")
    st.write(f"**Total Amount Due:** ${total_due:.2f}")
    st.write(f"**Total Received:** ${total_received:.2f}")
    st.write(f"**Balance Remaining:** ${balance:.2f}")

    with st.expander("Order breakdown"):
        for o in order_choices:
            rec = get_money_received(o.order_id)
            st.write(
                f"{o.order_ref} ({o.scout_name}) — "
                f"Due: ${o.order_amount:.2f}, "
                f"Received: ${rec:.2f}"
            )

    if balance <= 0:
        st.success("All selected orders are fully paid.")
        return

    # ---- Payment form ----
    with st.form("receive_money"):
        amount = Decimal(
            str(
                st.number_input(
                    "Amount Received",
                    min_value=0.0,
                    max_value=float(balance),
                    step=1.0
                )
            )
        )

        method = st.selectbox(
            "Payment Method",
            ["Cash", "Check", "Venmo", "Zelle", "Other"]
        )

        notes = st.text_area("Notes (optional)")

        if st.form_submit_button("Record Payment"):
            remaining = Decimal(amount)

            for o in order_choices:
                if remaining <= 0:
                    break

                already_received = get_money_received(o.order_id)
                order_balance = Decimal(o.order_amount) - already_received

                if order_balance <= 0:
                    continue

                apply_amt = min(order_balance, remaining)

                insert_money_received(
                    parent_id=parent.parent_id,
                    scout_id=o.scout_id,
                    order_id=o.order_id,
                    program_year=year,
                    amount=apply_amt,
                    method=method,
                    notes=notes
                )

                update_order_status_if_paid(o.order_id)

                remaining -= apply_amt

            ss.payment_success = {
                "orders": [o.order_ref for o in order_choices],
                "amount": float(amount),
                "method": method
            }

            st.rerun()


# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Receive Money",
        initial_sidebar_state="expanded"
    )
    init_flags()
    main()
