from json import loads
import streamlit as st
from streamlit import session_state as ss,  data_editor as de, rerun as rr
# from streamlit_calendar import calendar
import streamlit.components.v1 as components
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
import time
from typing import List, Tuple
import pandas as pd
import sys
from pathlib import Path
import hmac
import os
from datetime import datetime
import yaml
from yaml.loader import SafeLoader
import base64
import streamlit_authenticator as stauth
from utils import params
# import eland as ed
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3


index_scouts = 'scouts'

print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')


# print(f'The folder contents are: {os.listdir()}\n')
# print(f"Now... the current directory: {Path.cwd()}")
# from utils.mplcal import MplCalendar as mc
from dotenv import load_dotenv, find_dotenv
find_dotenv()
load_dotenv()
# Get the base directory
basepath = Path()
basedir = str(basepath.cwd())
# Load the environment variables
envars = basepath.cwd() / '.env'
load_dotenv(envars)
# Read an environment variable.
SECRET_KEY = os.getenv('API_SECRET')


#---------------------------------------
# LOADS THE SCOUT NAME, ADDRESS, PARENT AND REWARD INFO to Elastic
# Uncomment and re-do if changes to sheet
#---------------------------------------
# conn = st.connection("gsinfo", type=GSheetsConnection)

# ed.pandas_to_eland(pd_df = df, es_client=es,  es_dest_index='scouts', es_if_exists="replace", es_refresh=True) # index field 'H' as text not keyword

# # SLOW
# # for i,row in df.iterrows():
# #     rowdat = json.dupmp
# #     esu.add_es_doc(es,indexnm='scouts', doc=row)

def init_ss():
    if 'authenticated' not in ss:
        ss.authenticated = False

    if 'adminpassword_correct' not in st.session_state:
        st.session_state['adminpassword_correct'] = False
    if "form_data" not in ss:
        ss.form_data = {"parent_firstname": "", "parent_lastname": "","parent_email": "", "parent_phone": "","username":"","parent_password": "","passcopy":"","passhint":"","gs1_fn":"","gs1_ln":"","gs2_fn":"","gs2_ln":"","scouts":[]}
    if "form_submitted" not in st.session_state:
        ss.form_submitted = False
    if "show_form" not in st.session_state:
        st.session_state.show_form = False

# @st.cache_data
def get_connected():
    es = esu.conn_es()
    st.write(es.info())
    return es

def validate_form(data):
    st.write('validating content')
    errors = []
    if not data["parent_firstname"]:
        errors.append("A first name is required.")
    if not data["parent_lastname"]:
        errors.append("A last name is required.")
    if "@" not in data['parent_email']:
                st.error("Please enter a valid email address.")
    if len(data["parent_password"]) < 6:
        st.error("Password must be at least 6 characters long.")
    st.write(len(data['scouts']))
    if len(data['scouts'])==0:
        st.error("You must have at least 1 girl scout.")
    return errors


def verify_troop():
    """Checks whether a password entered by the user is correct."""
    if hmac.compare_digest(st.session_state["verifytrp"], st.secrets["password"]):
        st.session_state["password_correct"] = True
        del st.session_state["verifytrp"]  # Don't store the password.
    else:
        st.error("😕 Troop Verification Incorrect - please type our leaders name, 5 characters, all lower case")
        st.session_state["password_correct"] = False
        st.session_state["adminpassword_correct"] = False
        del st.session_state["verifytrp"]  # Don't store the password.

# Handle form submission
def handle_form_submission():
    ss.form_submitted = True

def register_user(es,location='main',key='newuser',clear_on_submit:bool=True):
    
    with st.form("Register user"):
        st.subheader('Register user')
        password_instructions = os.getenv('password_instructions')
        c0_1, c0_2, c0_3, c0_4 = st.columns(4)
        c0_1.text_input('Troop Leader Name', help='troop verification, 5 letters all lowercase', key='verifytrp') # on_change=verify_troop())
        
        c1_1, c1_2, c1_3, c1_4 = st.columns(4)
        parnt_firstnm = c1_1.text_input('First name',value=ss.form_data['parent_firstname'])
        parnt_lastnm = c1_2.text_input('Last name',value=ss.form_data['parent_lastname'])
        parnt_email = c1_3.text_input('Email',value=ss.form_data['parent_email'])
        parnt_phone = c1_4.text_input('Phone',value=ss.form_data['parent_phone'])
           
        c2_1, c2_2, c2_3, c2_4 = st.columns(4)
        new_username = c2_1.text_input('Username',value=ss.form_data['username'])
        usrpass = c2_2.text_input('Password', value=ss.form_data['parent_password'],type='password', help=password_instructions)
        passcopy = c2_3.text_input('Repeat password', value=ss.form_data['passcopy'],type='password')
        passhint = c2_4.text_input('Password hint',value=ss.form_data['passhint'])

        c3_1,c3_2,c3_3,c3_4 = st.columns(4)
        gs1_fn = c3_1.text_input('Girl Scout 1 First Name',value=ss.form_data['gs1_fn'])
        gs1_ln = c3_2.text_input('Girl Scout 1 Last Name',value=ss.form_data['gs1_ln'], autocomplete =parnt_lastnm)
        gs2_fn = c3_3.text_input('Girl Scout 2 First Name',value=ss.form_data['gs2_fn'])
        gs2_ln = c3_4.text_input('Girl Scout 2 Last Name',value=ss.form_data['gs2_ln'], autocomplete=parnt_lastnm)
        
        gs1_fullname = gs1_fn + " " + gs1_ln
        gs2_fullname = gs2_fn + " " + gs2_ln

        # validation
        if usrpass != passcopy:
            st.warning('Passwords do not match')

        
        st.markdown('By creating this account and ordering cookies, I understand that I am financially responsible for any cookies that I order. I also agree that I will return all funds by the due date')
        submitted = st.form_submit_button("Submit", on_click=handle_form_submission)

    if ss.form_submitted:
        ss.form_data = {
            "username":new_username,
            "parent_firstname":parnt_firstnm.title(),
            "parent_lastname": parnt_lastnm.title(),
            "parent_email": parnt_email.lower(),
            "parent_phone": parnt_phone,
            "parent_password_hint": passhint,
            "parent_password": usrpass,
            "passhint": passhint,
            "scouts": [gs1_fullname, gs2_fullname]
        }

        # Validate the form
        errors = validate_form(ss.form_data)
        if errors:
            for error in errors:
                st.error(error)
        else:
            # Optionally clear the session state after success
            # st.session_state.form_data = {"name": "", "email": "", "age": 0}
            esu.add_es_doc(es,indexnm=index_scouts,id=None, doc=ss.form_data)
            st.write(ss.form_data)
            st.success('Account Created Successfully!')
            ss.authenticated = True
            ss.username = new_username
            st.session_state.show_form = False
            st.rerun()


def update_session(es,gs_nms):
    # st.write(f'gs_nm:{gs_nm}; gsNmkey: {st.session_state["gsNm"]}')
    time.sleep(1)
    scout_dat = esu.get_qry_dat(es,indexnm=index_scouts,field='FullName',value=st.session_state["gsNm"])

    if len(scout_dat) > 0 and type('str'):
        sc_fn = scout_dat[0].get("_source").get("FullName")
        # st.subheader(f'Submit a Cookie Order for {sc_fn}')
        parent = scout_dat[0]['_source']['Parent']
        st.session_state["guardianNm"] = parent
        st.session_state["scout_dat"] = scout_dat[0]['_source']
    else:
        st.write('Scout Parent information not updated - please contact Jennifer')
        print(scout_dat)


#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    ss
    es=get_connected()
    # Show input for password.
    if not ss.authenticated:
        st.title("Login Page")
        new_account = st.button('Create an Account')
        if new_account:
            ss.show_form = True
        if st.session_state.show_form:
            register_user(es)
        if not new_account:
            with st.form('login'):
                st.text_input('username',key='login_username')
                st.text_input('Password', key='login_usrpass',type='password')
                login = st.form_submit_button("Login")
                if login:
                    ss.username = ss.login_username
                    qry_dat = esu.get_qry_dat(es,indexnm=index_scouts, field='username', value=ss.username)
                    scout_dat = qry_dat[0]['_source']
                    st.write(scout_dat)
                    if len(scout_dat['scouts'])>=0:
                        ss.authenticated = True
                        st.success("Login successful!")
                    else:
                        st.error("Invalid username or password")
    if ss.authenticated:
        ss.authenticated
        # Navigate to another page if authenticated
        st.success("You are authenticated! Navigate to the Home page.")
        st.page_link(label="Go to Cookie Portal", page="pages/parent_home.py")


if __name__ == '__main__':

    setup.config_site(page_title="Login")
    # Initialization
    init_ss()

    main()