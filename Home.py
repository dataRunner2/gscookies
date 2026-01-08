import streamlit as st
from streamlit import session_state as ss
import os
import pandas as pd
import bcrypt
from sqlalchemy import create_engine, text
from utils.app_utils import apputils as au, setup

def init_ss():
    if 'scouts_df' not in ss:
        ss.scouts_df = pd.DataFrame()
# --------------------------------------------------
# Page config
# --------------------------------------------------
# st.set_page_config(
#     page_title="Cookie Program",
#     layout="wide",
#     initial_sidebar_state="collapsed"
# )

# --------------------------------------------------
# Database connection
# --------------------------------------------------
DB_HOST = "136.118.19.164"
DB_PORT = "5432"
DB_NAME = "cookies"
DB_USER = "cookie_admin"
DB_PASS = st.secrets["general"]["DB_PASSWORD"]


engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_pre_ping=True
)

# --------------------------------------------------
# Auth helpers
# --------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8")
    )


def get_parent(username: str):
    sql = text("""
        SELECT
            parent_id,
            username,
            parent_password,
            parent_firstname,
            parent_lastname,
            verify_trp,
            is_admin
        FROM cookies_app.parents
        WHERE username = :username
        LIMIT 1
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"username": username}).fetchone()


def create_parent(username, email, password, first, last, phone):
    sql = text("""
        INSERT INTO cookies_app.parents (
            username,
            parent_email,
            parent_password,
            parent_firstname,
            parent_lastname,
            parent_phone,
            is_admin
        )
        VALUES (
            :username,
            :email,
            :password,
            :first,
            :last,
            :phone,
            FALSE
        )
        RETURNING parent_id
    """)
    with engine.begin() as conn:
        return conn.execute(sql, {
            "username": username.strip(),
            "email": email,
            "password": hash_password(password),
            "first": first.strip(),
            "last": last.strip(),
            "phone": phone.strip(),
        }).scalar()


def get_scouts(parent_id):
    sql = text("""
        SELECT
            scout_id,
            first_name,
            last_name,
            tshirt_size,
            goals
        FROM cookies_app.scouts
        WHERE parent_id = :parent_id
        ORDER BY last_name, first_name
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"parent_id": parent_id})

def main():
    # --------------------------------------------------
    # Session defaults
    # --------------------------------------------------
    if "authenticated" not in ss:
        ss.authenticated = False

    # --------------------------------------------------
    # Header
    # --------------------------------------------------
    # st.title("Cookie Tracker")
    st.caption("Troop43202 Parent portal for managing cookie orders")
    # st.write("DB_PASSWORD loaded:", bool(st.secrets['general']['DB_PASSWORD']))


    # --------------------------------------------------
    # LOGIN / CREATE ACCOUNT
    # --------------------------------------------------
    if not ss.authenticated:
        tab_login, tab_create = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                ss.username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign In")

            if submit:
                parent = get_parent(ss.username)

                if not parent or not check_password(password, parent.parent_password):
                    st.error("Invalid username or password")
                    st.stop()

                ss.authenticated = True
                ss.parent_id = parent.parent_id
                ss.parent_name = f"{parent.parent_firstname} {parent.parent_lastname}"
                ss.is_admin = bool(parent.is_admin)
                if ss.is_admin: setup.check_admin()

                st.rerun()

        with tab_create:
            with st.form("create_account_form"):
                col1, col2 = st.columns(2)
                with col1:
                    first = st.text_input("First name")
                    email = st.text_input("Email")
                with col2:
                    last = st.text_input("Last name")
                    phone = st.text_input("Phone Number")
                    troop = st.text_input("Troop Number")
                    

                with col1:
                    username = st.text_input("Username")
                    pw1 = st.text_input("Password", type="password")
                with col2:    
                    pw2 = st.text_input("Confirm password", type="password")

                submit = st.form_submit_button("Create Account")

            if submit:
                if pw1 != pw2:
                    st.error("Passwords do not match")
                    st.stop()

                if get_parent(username):
                    st.error("Username already exists")
                    st.stop()

                if troop != '43202':
                    st.error('That is not an approved troop number')
                    st.stop()
                parent_id = create_parent(username, email, pw1, first, last, phone)

                ss.authenticated = True
                ss.parent_id = parent_id
                ss.parent_name = f"{first} {last}"
                ss.is_admin = False

                st.rerun()

    # --------------------------------------------------
    # AFTER LOGIN
    # --------------------------------------------------
    else:
        # with st.sidebar:
        #     st.subheader(ss.parent_name)
        #     st.page_link("Home.py", label="Home")
        #     st.page_link("pages/add_scouts.py", label="Manage Scouts")

        #     if ss.is_admin:   
        #         # if ss.is_admin: ss.is_admin_pers = ss.is_admin #alighn the admin persistent 
        #         st.sidebar.write('----- ADMIN ------')
        #         st.sidebar.page_link('pages/admin_ebudde_summary.py',label='Ebudde Summary')
        #         st.sidebar.page_link('pages/admin_girl_order_summary.py',label='Girl Summary')
        #         st.sidebar.page_link('pages/admin_order_management.py',label='Order Management')
        #         st.sidebar.page_link('pages/admin_print_new_orders.py',label='Print Orders')
        #         st.sidebar.page_link('pages/admin_receive_money.py',label='Receive Money')
        #         st.sidebar.page_link('pages/admin_add_inventory.py',label='Add Inventory')
        #     # if ss.super_admin:
        #     #     st.sidebar.page_link('pages/admin_show_session.py',label='Manage Backups & SS')
        #     #     st.sidebar.page_link('pages/admin_booths.py',label='Booth Admin')
        #     #     st.sidebar.page_link('pages/admin_print_booths.py',label='Print Booths')

        #     st.divider()
        #     if st.button("Log out"):
        #         ss.clear()
        #         st.rerun()

        try:
            ss.scouts_df = get_scouts(ss.parent_id)
        except:
            st.switch_page("pages/add_scouts.py")

        if ss.scouts_df.empty:
            st.switch_page("pages/add_scouts.py")

        st.subheader("Your Scouts")

        st.dataframe(
            ss.scouts_df.drop(columns=["scout_id"]),
            use_container_width=True,
            hide_index=True
        )

        total_goal = ss.scouts_df["goals"].fillna(0).sum()
        st.caption(f"Combined cookie goal: {int(total_goal)}")

if __name__ == '__main__':

    setup.config_site(page_title="Home")
    # Initialization
    init_ss()

    main()