import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

from utils.app_utils import setup, apputils
from utils.order_utils import get_order_items, get_scouts_byparent, get_orders_for_scout, get_orders_for_scout_summary
from utils.db_utils import require_login, to_pacific, fetch_all

def decimal_sum(series):
    return sum(Decimal(str(x)) for x in series.fillna(0))


# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    require_login()
    apputils.get_last_digital_import()

    # ---- Scout ----
    rows = get_scouts_byparent(ss.parent_id)
    ss.scout_dict = {str(r["scout_id"]): r for r in rows}

    # Build dataframe
    scouts_df = pd.DataFrame(list(ss.scout_dict.values()))

    if scouts_df.empty:
        st.info("No scouts found.")
        st.switch_page("pages/add_scouts.py")

    scout = st.selectbox(
        "Scout",
        ss.scouts_dict,
        format_func=lambda s: f"{s.first_name} {s.last_name}"
    )
    # st.write(scout.scout_id)
    # ---- Year ----
    current_year = datetime.now().year

    orders = get_orders_for_scout(scout.scout_id, current_year)
    if orders.empty:
        st.info("No orders found for this scout and year.")
        st.stop()

    # --------------------------------------------------
    # SUMMARY METRICS
    # --------------------------------------------------

    total_due = decimal_sum(orders["order_amount"])
    
    paid_digital = decimal_sum(orders.loc[orders["order_type"] == "Digital", "paid_amount"])
    paid_paper = decimal_sum(orders.loc[orders["order_type"] == "Paper", "paid_amount"])

    total_boxes = int(orders["order_qty_boxes"].fillna(0).sum())
    digital_boxes = decimal_sum(orders.loc[orders["order_type"] == "Digital", "order_qty_boxes"])
    paper_boxes = decimal_sum(orders.loc[orders["order_type"] == "Paper", "order_qty_boxes"])
    
    total_paid = paid_digital + paid_paper
    balance = total_due - total_paid

    # ---- Summary display ----
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

    st.markdown("### Orders")
    st.dataframe(
        pd.DataFrame(orders),
        hide_index=True,
        column_order=['submit_dt','order_type','order_status','order_qty_boxes','order_amount','comments']
    )

    st.divider()
    
    # --------------------------------------------------
    # EXPANDABLE ORDER DETAILS
    # --------------------------------------------------
    order_dets = get_orders_for_scout_summary(scout.scout_id)

    if order_dets.empty:
        st.info("No orders found for this scout.")
    else:
        # Ensure datetime
        order_dets["submit_dt"] = pd.to_datetime(order_dets["submit_dt"])

        # Group by order
        for order_id, df_order in orders.groupby("order_id"):
            order_type = df_order["order_type"].iloc[0]
            order_status = df_order["order_status"].iloc[0]
            submit_dt = to_pacific(df_order["submit_dt"].iloc[0])  #.strftime("%b %d, %Y %I:%M %p")
            comments = df_order["comments"].iloc[0] if "comments" in df_order else None
            order_qty = df_order["order_qty_boxes"].iloc[0]

            order_dets_by_id = order_dets[order_dets['order_id'] == order_id]
    
            # Pivot cookies into columns
            cookie_table = (
                order_dets_by_id
                .pivot_table(
                    index=None,
                    columns="cookie_name",
                    values="quantity",
                    aggfunc="sum",
                    fill_value=0
                )
            )

            with st.expander(
                f"{order_type} — {submit_dt} — {order_status}",
                expanded=False
            ):
                st.markdown(f"**Cookies Ordered**   > Total Qty {order_qty}")
                st.dataframe(
                    cookie_table,
                    hide_index=True,
                    use_container_width=True
                )

                if comments and str(comments).strip():
                    st.markdown("**Comments**")
                    st.info(comments)



# --------------------------------------------------
# Entry
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Order Summary",
        initial_sidebar_state="expanded"
    )
    main()
