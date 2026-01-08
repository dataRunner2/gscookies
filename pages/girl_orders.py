import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
import uuid

from sqlalchemy import create_engine, text
import pandas as pd

from utils.app_utils import apputils as au, setup


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
    ss.setdefault("authenticated", False)
    ss.setdefault("parent_id", None)
    ss.setdefault("parent_name", "")


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


def get_cookies_for_year(program_year):
    sql = text("""
        SELECT cookie_code, display_name, price_per_box
        FROM cookies_app.cookie_years
        WHERE program_year = :year
          AND active = TRUE
        ORDER BY display_order
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"year": program_year}).fetchall()


def insert_order_header(
    parent_id, scout_id, program_year, order_ref, order_type,
    guardian_nm, guardian_ph, email,
    pickup_nm, pickup_ph, comments,
    total_boxes, order_amount
):
    order_id = uuid.uuid4()

    sql = text("""
        INSERT INTO cookies_app.orders (
            order_id,
            parent_id,
            scout_id,
            program_year,
            order_ref,
            order_type,
            status,
            order_qty_boxes,
            order_amount,
            guardian_name,
            guardian_phone,
            email,
            pickup_name,
            pickup_phone,
            comments,
            submit_dt,
            created_at
        )
        VALUES (
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :order_ref,
            :order_type,
            'NEW',
            :order_qty_boxes,
            :order_amount,
            :guardian_name,
            :guardian_phone,
            :email,
            :pickup_name,
            :pickup_phone,
            :comments,
            now(),
            now()
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "order_id": str(order_id),
            "parent_id": str(parent_id),
            "scout_id": str(scout_id),
            "program_year": program_year,
            "order_ref": order_ref,
            "order_type": order_type,
            "order_qty_boxes": total_boxes,
            "order_amount": order_amount,
            "guardian_name": guardian_nm,
            "guardian_phone": guardian_ph,
            "email": email,
            "pickup_name": pickup_nm,
            "pickup_phone": pickup_ph,
            "comments": comments,
        })

    return order_id


def insert_order_items(order_id, parent_id, scout_id, program_year, items):
    sql = text("""
        INSERT INTO cookies_app.order_items (
            order_item_id,
            order_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity
        )
        VALUES (
            gen_random_uuid(),
            :order_id,
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity
        )
    """)

    with engine.begin() as conn:
        for code, qty in items.items():
            if qty != 0:
                conn.execute(sql, {
                    "order_id": str(order_id),
                    "parent_id": str(parent_id),
                    "scout_id": str(scout_id),
                    "program_year": program_year,
                    "cookie_code": code,
                    "quantity": qty
                })


def insert_planned_inventory(parent_id, scout_id, program_year, order_id, items):
    sql = text("""
        INSERT INTO cookies_app.inventory_ledger (
            inventory_event_id,
            parent_id,
            scout_id,
            program_year,
            cookie_code,
            quantity,
            event_type,
            status,
            related_order_id,
            event_dt
        )
        VALUES (
            gen_random_uuid(),
            :parent_id,
            :scout_id,
            :program_year,
            :cookie_code,
            :quantity,
            'ORDER_SUBMITTED',
            'PLANNED',
            :order_id,
            now()
        )
    """)

    with engine.begin() as conn:
        for code, qty in items.items():
            if qty != 0:
                conn.execute(sql, {
                    "parent_id": str(parent_id),
                    "scout_id": str(scout_id),
                    "program_year": program_year,
                    "cookie_code": code,
                    "quantity": -abs(qty),
                    "order_id": str(order_id)
                })


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

    year = datetime.now().year
    # year = st.selectbox(
    #     "Program Year",
    #     [current_year - 1, current_year, current_year + 1],
    #     index=1
    # )
   

    st.subheader(f"Submit Cookie Order for {year}")
    
    scout_display = st.selectbox("Select Scout", [s["display"] for s in scouts])
    scout = next(s for s in scouts if s["display"] == scout_display)

    cookies = get_cookies_for_year(year)

    if not cookies:
        st.error(f"No cookies are configured for {year}. Please contact an admin.")
        st.stop()

    with st.form("order_form", clear_on_submit=True):
        order_type = st.selectbox(
            "Order Type",
            ["Paper Order", "Digital Cookie Girl Delivery"]
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
                        key=f"{year}_{c.cookie_code}"
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
                program_year=year,
                order_ref=order_ref,
                order_type=order_type,
                guardian_nm=f"{parent.parent_firstname} {parent.parent_lastname}",
                guardian_ph=parent.parent_phone,
                email=parent.parent_email,
                pickup_nm="",
                pickup_ph="",
                comments=comments,
                total_boxes=total_boxes,
                order_amount=order_amount
            )

            insert_order_items(
                order_id,
                ss.parent_id,
                scout["scout_id"],
                year,
                cookie_inputs
            )

            insert_planned_inventory(
                ss.parent_id,
                scout["scout_id"],
                year,
                order_id,
                cookie_inputs
            )

            st.success(f"Order submitted successfully! Reference: {order_ref}")
            st.balloons()


if __name__ == "__main__":
    setup.config_site(page_title="Submit Orders", initial_sidebar_state="expanded")
    init_ss()
    main()
