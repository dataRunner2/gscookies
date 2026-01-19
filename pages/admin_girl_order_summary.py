import streamlit as st
from streamlit import session_state as ss
import pandas as pd

from utils.app_utils import setup
from utils.db_utils import require_admin
from utils.order_utils import (
        aggregate_orders_by_cookie,
        get_orders_for_scout,
        get_orders_for_scout_summary,
        get_all_scouts
    )

import datetime

# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year

# ======================================================
# Main
# ======================================================

def main():
    require_admin()
    year = ss.current_year
    # ----------------------------------
    # Scout Selection
    # ----------------------------------

    scouts = get_all_scouts()

    scout_options = {
        f"{s.first_name} {s.last_name}": s.scout_id
        for s in scouts
    }

    selected_name = st.selectbox(
        "Select Girl Scout",
        options=[""] + list(scout_options.keys()),
    )

    if not selected_name:
        st.info("Select a scout to view order summary.")
        return

    if selected_name:
        scout_id = scout_options[selected_name]
        first_name=selected_name.split(' ')[0]
        last_name= selected_name.split(' ')[1]

    # ----------------------------------
    # Fetch Orders
    # ----------------------------------
    
    orders_df = get_orders_for_scout_summary(scout_id)

    if orders_df.empty:
        st.warning("No orders found for this scout.")
    
    else:
        summary_df = aggregate_orders_by_cookie(orders_df)

        total_boxes = int(summary_df["total_boxes"].sum())
        st.metric("Total Boxes Sold", total_boxes)

        st.subheader("Boxes by Cookie Type")
        st.dataframe(summary_df, use_container_width=True)

        with st.expander("View Individual Orders"):
            st.dataframe(
                orders_df.sort_values("submit_dt", ascending=False),
                use_container_width=True,
            )



# ======================================================
# Entry Point
# ======================================================

if __name__ == "__main__":
    setup.config_site(
        page_title="Girl Order Summary",
        initial_sidebar_state="expanded",
    )
    init_ss()
    main()
