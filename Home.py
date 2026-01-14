import streamlit as st
from streamlit import session_state as ss
import os
import pandas as pd
import bcrypt
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from utils.app_utils import apputils as au, setup
from utils.db_utils import (
    verify_username_and_phone,
    reset_password_with_username_phone,
    get_engine
)
from utils.order_utils import get_scouts_byparent

engine = get_engine()

def init_ss():
    if 'scouts_dict' not in ss:
        ss.scouts_dict = pd.DataFrame()
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year


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


            st.divider()
            st.subheader("Forgot your password?")
            

            with st.expander("Reset password"):
                username = st.text_input("Username")
                phone = st.text_input(
                    "Phone number",
                    help="Must match what you used when registering"
                )

                new_password = st.text_input("New password", type="password")
                confirm_password = st.text_input("Confirm new password", type="password")

                if st.button("Reset password"):
                    if new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif not verify_username_and_phone(username, phone):
                        st.error("Username and phone number do not match our records.")
                    else:
                        reset_password_with_username_phone(
                            username,
                            phone,
                            new_password,
                        )
                        st.success("Password updated! You can now log in.")


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
    elif ss.authenticated:
        # st.write(f'you have access: {ss.authenticated}|  parentid:{ss.parent_id}')
        try:
            ss.scouts_dict = get_scouts_byparent(ss.parent_id)
            # rows = get_scouts_byparent(ss.parent_id)
            # scouts_df = pd.DataFrame([dict(r) for r in rows])

        except:
            st.switch_page("pages/add_scouts.py")

        # if ss.scouts_df.empty:
        #     st.switch_page("pages/add_scouts.py")
    if len(ss.scouts_dict)>0:
        st.subheader("Your Scouts")

        
        st.dataframe(
            ss.scouts_dict,
            width='stretch',
            hide_index=True,
            column_order=["first_name", "tshirt_size","goals","award_preferences"],
            column_config={
                "first_name": st.column_config.TextColumn("First Name"),
                "last_name": st.column_config.TextColumn("Last Name"),
                "tshirt_size": st.column_config.TextColumn("Tshirt Size"),
                "goals": st.column_config.TextColumn("Goal"),
                "award_preferences": st.column_config.TextColumn("Award"),
                "parent_id": None,
                "scout_id": None 
            },
        )
        st.page_link('pages/add_scouts.py',label='Add or Modify Scout Info')


if __name__ == '__main__':

    setup.config_site(page_title="Home")
    # Initialization
    init_ss()

    main()