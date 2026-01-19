import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import text

from utils.app_utils import setup
from utils.db_utils import get_engine, require_login, to_pacific
from utils.order_utils import get_all_orders_wide

engine = get_engine()


# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year



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
    """Get all orders for the year in wide format with cookie columns"""
    df = get_all_orders_wide(year)
    if df.empty:
        return pd.DataFrame()
    return df

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
    if orders.empty:
        st.info("No orders found for this year.")
        return

    # --------------------------------------------------
    # Build aggregates
    # --------------------------------------------------
    booth_orders = 0
    digital_orders = 0
    paper_orders = 0

    booth_boxes = 0
    digital_boxes = 0
    paper_boxes = 0

    total_sales = Decimal("0.00")
    total_paid = Decimal("0.00")

    # Calculate cookie totals from wide format
    meta_cols = {'orderId', 'program_year', 'submit_dt', 'orderType', 'orderStatus', 
                 'orderAmount', 'orderQtyBoxes', 'comments', 'boothId', 'addEbudde', 
                 'verifiedDigitalCookie', 'initialOrder', 'scoutName', 'paymentStatus', 'paidAmount'}
    
    # Get all cookie columns (includes configured cookies + any others like DON)
    cookie_cols = [col for col in orders.columns if col not in meta_cols]
    # Sort alphabetically to ensure consistent display (DON will be with other codes)
    cookie_cols = sorted(cookie_cols)
    
    # Split into distributed (booth validated or picked up) vs pending
    distributed_mask = orders['orderStatus'].isin(['PICKED_UP', 'BOOTH_VALIDATED'])
    distributed_orders = orders[distributed_mask]
    pending_orders = orders[~distributed_mask]
    
    # Further split pending into booth and scout orders
    booth_pending_mask = (orders['orderType'] == 'BOOTH') & (~distributed_mask)
    scout_pending_mask = (orders['orderType'] != 'BOOTH') & (~distributed_mask)
    booth_pending_orders = orders[booth_pending_mask]
    scout_pending_orders = orders[scout_pending_mask]
    
    cookie_totals = {}
    cookie_distributed = {}
    cookie_booth_pending = {}
    cookie_scout_pending = {}
    
    for col in cookie_cols:
        if col in orders.columns:
            total = orders[col].fillna(0).sum()
            distributed = distributed_orders[col].fillna(0).sum()
            booth_pending = booth_pending_orders[col].fillna(0).sum()
            scout_pending = scout_pending_orders[col].fillna(0).sum()
            
            if total > 0:
                cookie_totals[col] = int(total)
                cookie_distributed[col] = int(distributed)
                cookie_booth_pending[col] = int(booth_pending)
                cookie_scout_pending[col] = int(scout_pending)

    for _, o in orders.iterrows():
        order_type = str(o.get('orderType', '')).lower()
        is_booth = order_type == 'booth'
        is_digital = 'digital' in order_type
        is_paper = 'paper' in order_type
        
        qty = int(o.get('orderQtyBoxes', 0) or 0)
        amount = Decimal(str(o.get('orderAmount', 0)))

        paid = (
            amount
            if is_digital
            else Decimal(str(o.get('paidAmount', 0) or 0))
        )

        if is_booth:
            booth_orders += 1
            booth_boxes += qty
        elif is_digital:
            digital_orders += 1
            digital_boxes += qty
        elif is_paper:
            paper_orders += 1
            paper_boxes += qty

        total_sales += amount
        total_paid += paid

    # Calculate metrics
    total_orders = booth_orders + digital_orders + paper_orders
    total_boxes = booth_boxes + digital_boxes + paper_boxes
    avg_boxes_per_order = total_boxes / total_orders if total_orders > 0 else 0
    percent_paid = (total_paid / total_sales * 100) if total_sales > 0 else 0
    balance = total_sales - total_paid
    
    # Count unique scouts
    unique_scouts = orders['scoutName'].nunique() if 'scoutName' in orders.columns else 0

    st.divider()

    # --------------------------------------------------
    # 📊 ORDER VOLUME
    # --------------------------------------------------
    st.markdown("### 📊 Order Volume")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Boxes", total_boxes, f"{avg_boxes_per_order:.1f} per order")
    with col2:
        st.metric("Total Orders", total_orders)
    with col3:
        st.metric("Paper Orders", paper_orders)
    with col4:
        st.metric("Booth Orders", booth_orders)
    with col5:
        st.metric("Girls Selling", unique_scouts)

    st.divider()

    # --------------------------------------------------
    # 🍪 COOKIES SOLD BY TYPE
    # --------------------------------------------------
    st.markdown("### 🍪 Cookies Sold by Type")

    if cookie_totals:
        # Booth Pending row
        st.markdown("#### ⏳ Booth Pending")
        cols = st.columns(len(cookie_totals))
        for col, cookie_code in zip(cols, cookie_totals.keys()):
            with col:
                booth_pending_qty = cookie_booth_pending.get(cookie_code, 0)
                pct = (booth_pending_qty / total_boxes * 100) if total_boxes > 0 else 0
                st.metric(cookie_code, booth_pending_qty)
                st.caption(f"{pct:.1f}% of total")
        
        st.markdown("")  # spacing

        # Scout Orders Pending row
        st.markdown("#### ⏳ Scout Orders Pending")
        cols = st.columns(len(cookie_totals))
        for col, cookie_code in zip(cols, cookie_totals.keys()):
            with col:
                scout_pending_qty = cookie_scout_pending.get(cookie_code, 0)
                pct = (scout_pending_qty / total_boxes * 100) if total_boxes > 0 else 0
                st.metric(cookie_code, scout_pending_qty)
                st.caption(f"{pct:.1f}% of total")
        
        st.markdown("")  # spacing

        # Distributed row
        st.markdown("#### ✅ Distributed (Picked Up / Booth Validated)")
        cols = st.columns(len(cookie_totals))
        for col, cookie_code in zip(cols, cookie_totals.keys()):
            with col:
                distributed_qty = cookie_distributed.get(cookie_code, 0)
                pct = (distributed_qty / total_boxes * 100) if total_boxes > 0 else 0
                st.metric(cookie_code, distributed_qty)
                st.caption(f"{pct:.1f}% of total")
        
        
    else:
        st.info("No cookie breakdown available.")

    st.divider()

    # --------------------------------------------------
    # 💵 FINANCIAL SUMMARY
    # --------------------------------------------------
    st.markdown("### 💵 Financial Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Total Sales", f"${total_sales:,.2f}")
    with col2:
        st.metric("✅ Paid", f"${total_paid:,.2f}")
        st.caption(f"{percent_paid:.0f}% collected")
    with col3:
        st.metric("⏳ Outstanding", f"${balance:,.2f}")


# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Troop Orders Overview",
        initial_sidebar_state="expanded"
    )
    main()
