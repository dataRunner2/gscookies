import streamlit as st
from decimal import Decimal
from sqlalchemy import create_engine, text
from streamlit import session_state as ss

from utils.app_utils import setup
from utils.db_utils import get_engine

engine = get_engine()
# -------------------------------
# Guards
# -------------------------------
def require_admin():
    if not ss.get("authenticated") or not ss.get("is_admin"):
        st.error("Admin access required.")
        st.stop()


# -------------------------------
# Queries
# -------------------------------
def get_draft_booths():
    sql = text("""
        SELECT
            o.order_id,
            o.booth_id,
            b.location,
            b.booth_date,
            b.start_time,
            b.end_time,
            o.order_qty_boxes,
            o.order_amount,
            o.submit_dt
        FROM cookies_app.orders o
        JOIN cookies_app.booths b ON o.booth_id = b.booth_id
        WHERE o.order_type = 'BOOTH'
          AND o.verification_status = 'DRAFT'
        ORDER BY b.booth_date DESC
    """)
    with engine.connect() as conn:
        return conn.execute(sql).fetchall()


def get_order_items(order_id):
    sql = text("""
        SELECT
            oi.cookie_code,
            cy.display_name,
            oi.quantity,
            cy.price_per_box
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON oi.cookie_code = cy.cookie_code
         AND oi.program_year = cy.program_year
        WHERE oi.order_id = :order_id
        ORDER BY cy.display_order
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"order_id": order_id}).fetchall()


def verify_booth(order_id, program_year, items):
    with engine.begin() as conn:
        # Mark order verified
        conn.execute(text("""
            UPDATE cookies_app.orders
            SET verification_status = 'VERIFIED'
            WHERE order_id = :oid
        """), {"oid": order_id})

        # Inventory actuals
        for i in items:
            conn.execute(text("""
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
                    'Verified booth sale'
                )
            """), {
                "year": program_year,
                "cookie": i.cookie_code,
                "qty": -i.quantity,
                "oid": order_id,
            })


# -------------------------------
# Page
# -------------------------------
def main():
    require_admin()

    st.subheader("Admin Booth Verification")
    st.caption("Verify booth sheets and apply inventory actuals")

    booths = get_draft_booths()
    if not booths:
        st.success("No booths awaiting verification.")
        return

    booth = st.selectbox(
        "Select Booth to Verify",
        booths,
        format_func=lambda b: (
            f"{b.booth_date.strftime('%b %d')} "
            f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
            f"{b.location}"
        )
    )

    st.markdown("---")
    st.markdown(
        f"""
        **Location:** {booth.location}  
        **Date:** {booth.booth_date.strftime('%A, %B %d, %Y')}  
        **Time:** {booth.start_time.strftime('%I:%M %p')} – {booth.end_time.strftime('%I:%M %p')}  
        **Boxes Sold:** {booth.order_qty_boxes}  
        **Expected Revenue:** ${booth.order_amount:.2f}
        """
    )

    items = get_order_items(booth.order_id)

    st.markdown("---")
    st.markdown("### 🍪 Cookie Breakdown")

    total_boxes = 0
    total_revenue = Decimal("0.00")

    for i in items:
        line_total = Decimal(i.quantity) * Decimal(i.price_per_box)
        total_boxes += i.quantity
        total_revenue += line_total

        st.write(
            f"{i.display_name}: "
            f"{i.quantity} boxes × ${i.price_per_box:.2f} = ${line_total:.2f}"
        )

    st.markdown("---")
    st.metric("Total Boxes", total_boxes)
    st.metric("Total Revenue", f"${total_revenue:.2f}")

    st.markdown("---")
    if st.button("✅ Verify Booth & Apply Inventory"):
        verify_booth(
            booth.order_id,
            booth.booth_date.year,
            items
        )
        st.success("Booth verified and inventory updated.")
        st.rerun()


# -------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Verify Booth Orders",
        initial_sidebar_state="expanded"
    )
    main()
