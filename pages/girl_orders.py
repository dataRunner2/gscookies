import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
import uuid

from sqlalchemy import create_engine, text
import pandas as pd

from utils.app_utils import apputils as au, setup, cookie_celebration
from utils.order_utils import get_cookies_for_year, insert_order_header, insert_order_items, insert_planned_inventory
from utils.db_utils import get_engine

engine = get_engine()



# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    ss.setdefault("authenticated", False)
    ss.setdefault("parent_id", None)
    ss.setdefault("parent_name", "")
    if 'current_year' not in ss:
        ss.current_year = int('2026') # str(datetime.now().year)


# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def get_parent(parent_id):
    sql = text("""
        SELECT parent_firstname, parent_lastname, parent_email, parent_phone
        FROM cookies_app.parents
        WHERE parent_id = :parent_id
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"parent_id": parent_id}).fetchone()


def get_scouts(parent_id):
    sql = text("""
        SELECT scout_id, first_name, last_name
        FROM cookies_app.scouts
        WHERE parent_id = :parent_id
        ORDER BY last_name, first_name
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"parent_id": parent_id}).fetchall()

    scouts = []
    for r in rows:
        scouts.append({
            "scout_id": r.scout_id,
            "display": f"{r.first_name} {r.last_name}",
            "nameId": str(r.scout_id)
        })
    return scouts


# --------------------------------------------------
# UI
# --------------------------------------------------
def main():
    if not ss.authenticated:
        st.warning("Please log in to submit orders.")
        st.page_link("Home.py", label="Login")
        st.stop()

    parent = get_parent(ss.parent_id)
    scouts = get_scouts(ss.parent_id)

    if not scouts:
        st.info("Please add a scout before submitting orders.")
        st.page_link("pages/Add_Scouts.py", label="Manage Scouts")
        st.stop()
   

    st.subheader(f"Submit Cookie Order for {ss.current_year}")
    
    scout_display = st.selectbox("Select Scout", [s["display"] for s in scouts])
    scout = next(s for s in scouts if s["display"] == scout_display)

    cookies = get_cookies_for_year(ss.current_year)

    if not cookies:
        st.error(f"No cookies are configured for {ss.current_year}. Please contact an admin.")
        st.stop()

    with st.form("order_form", clear_on_submit=True):
        order_type = st.selectbox(
            "Order Type",
            ["Paper Order", "Dig. Cookie Delivery"]
        )

        st.markdown("### Cookie Quantities")

        cookie_inputs = {}

        # build rows of 2 cookies at a time
        for i in range(0, len(cookies), 3):
            row = cookies[i:i+3]
            cols = st.columns(len(row))

            for col, c in zip(cols, row):
                with col:
                    cookie_inputs[c.cookie_code] = st.number_input(
                        f"{c.display_name} (${c.price_per_box:.2f})",
                        min_value=-10,
                        step=1,
                        value=0,
                        key=f"{ss.current_year}_{c.cookie_code}"
                    )


        comments = st.text_area("Comments (optional)")

        if st.form_submit_button("Submit Order"):
            total_boxes = sum(cookie_inputs.values())
            order_amount = sum(
                qty * next(c.price_per_box for c in cookies if c.cookie_code == code)
                for code, qty in cookie_inputs.items()
            )

            order_ref = f"{scout['nameId']}_{datetime.now().strftime('%Y%m%d%H%M')}"

            order_id = insert_order_header(
                parent_id=ss.parent_id,
                scout_id=scout["scout_id"],
                program_year=ss.current_year,
                order_ref=order_ref,
                order_type=order_type,
                comments=comments,
                total_boxes=total_boxes,
                order_amount=order_amount,
                status='NEW'
            )

            insert_order_items(
                order_id,
                ss.parent_id,
                scout["scout_id"],
                ss.current_year,
                cookie_inputs
            )

            insert_planned_inventory(
                ss.parent_id,
                scout["scout_id"],
                ss.current_year,
                order_id,
                cookie_inputs
            )

            st.success(f"Order submitted successfully! Reference: {order_ref}")
            st.balloons()
            # cookie_celebration()



if __name__ == "__main__":
    setup.config_site(page_title="Submit Orders", initial_sidebar_state="expanded")
    init_ss()
    main()
