from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import time
from typing import List, Tuple
import pandas as pd
import random
from pathlib import Path
import hmac
import os
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3
import extra_streamlit_components as stx

print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')


def init_ss():
    if 'authenticated' not in ss:
        ss.authenticated = False
    if 'adminpassword_correct' not in st.session_state:
        st.session_state['adminpassword_correct'] = False
    if "form_data" not in ss:
        ss.form_data = {"parent_firstname": "", "parent_lastname": "","parent_email": "", "parent_phone": "","username":"","parent_password": "","passcopy":"","passhint":""}
    if "form_submitted" not in st.session_state:
        ss.form_submitted = False
    if "validate_account" not in ss:
        ss.validate_account = False
    if  'validated' not in ss:
         ss.validated = False
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    if "sections" not in st.session_state:
        st.session_state.sections = [{}]  # Start with one empty section
    if 'cnt_scts_label' not in ss:
        ss.cnt_scts_label = '1 Scout'
    if 'indexes' not in ss:
        ss.indexes = {}
        ss.indexes['index_scouts'] = 'scouts2025f'
        ss.indexes['index_orders'] = 'orders2025'
        ss.indexes['index_money'] = 'money_received2025'

# Function to add a new section
def add_section():
    st.session_state.sections.append({})  # Add an empty dictionary for the new section

# Function to reset sections
def reset_sections():
    st.session_state.sections = [{}]  # Reset to one section

@st.fragment
def update_sections():
    reset_sections()
    st.write(f'Registering {ss.cnt_scts} Scouts')
    for i in range(1,ss.cnt_scts):
        add_section()

def reset_login_form():
    pass

def get_connected():
    es = esu.conn_es()
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
    # validation
    if data['parent_password'] != data['passcopy']:
        st.error('Passwords do not match')

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
def handle_form_submission(es):
    ss.form_data['scout_details'] = ss.sections
    # st.write(ss.form_data)
    esu.add_es_doc(es,indexnm=ss.indexes['index_scouts'],id=None, doc=ss.form_data)


def validate_account_info():
    ss.validate_account = True

# my_grid = grid(2, [2, 4, 1], 1, 4, vertical_align="bottom")
#     # Row 1:
#     my_grid.dataframe(random_df, use_container_width=True)
#     my_grid.line_chart(random_df, use_container_width=True)
#     # Row 2:
#     my_grid.selectbox("Select Country", ["Germany", "Italy", "Japan", "USA"])
#     my_grid.text_input("Your name")
#     my_grid.button("Send", use_container_width=True)
#     # Row 3:

def register_user(es,location='main',key='newuser',clear_on_submit:bool=True):
    
    with st.form("Register user"):
        st.subheader('Register user')
        password_instructions = os.getenv('password_instructions')

        c0_1, c0_2, c0_3, c0_4 = st.columns(4)
        c0_1.text_input('Troop Leader Name', help='troop verification, 5 letters all lowercase', key='verifytrp') # on_change=verify_troop())
        cnt_scts = c0_2.number_input('Number of Scouts Registering',min_value=1,max_value=4,step=1, key='cnt_scts')
        
        c1_1, c1_2, c1_3, c1_4 = st.columns(4)
        parnt_firstnm = c1_1.text_input('First name',value=ss.form_data['parent_firstname'])
        parnt_lastnm = c1_2.text_input('Last name',value=ss.form_data['parent_lastname'])
        parnt_email = c1_3.text_input('Email',value=ss.form_data['parent_email'])
        parnt_phone = c1_4.text_input('Phone',value=ss.form_data['parent_phone'])
           
        c2_1, c2_2, c2_3, c2_4 = st.columns(4)
        new_username = c2_1.text_input('Username',value=ss.form_data['username'])
        usrpass = c2_2.text_input('Password', value=ss.form_data['parent_password'],type='password', help=password_instructions)
        passcopy = c2_3.text_input('Repeat password', value=ss.form_data['passcopy'],type='password')

        process = st.form_submit_button(f"Add Scouts Information", on_click=validate_account_info)


    if process:
         # validation
        if usrpass != passcopy:
            st.warning('Passwords do not match')

        ss.form_data = {
            "username":new_username,
            "parent_firstname":parnt_firstnm.title(),
            "parent_lastname": parnt_lastnm.title(),
            "parent_FullName": f'{parnt_firstnm.title()} {parnt_lastnm.title()}',
            "parent_NameId": f'{parnt_firstnm.lower()}_{parnt_lastnm.lower()}',
            "parent_email": parnt_email.lower(),
            "parent_phone": parnt_phone,
            "parent_password": usrpass,
            "passcopy": passcopy            
        }

        # Validate the form
        errors = validate_form(ss.form_data)
        if errors:
            for error in errors:
                st.error(error)
        else:
            # esu.add_es_doc(es,indexnm=ss.indexes['index_scouts'],id=None, doc=ss.form_data)
            # st.write(ss.form_data)
            st.success('Account Information Valid')
            ss.validated = True

    if ss.validated:
        st.divider()
        update_sections()
        with st.container(border=True):
            with st.form('scout_deets'):
                for i, section in enumerate(st.session_state.sections):
                    st.write(f"**Scout {i + 1}**")
                    c3_1,c3_2,c3_3,c3_4 = st.columns(4)
                    section['fn'] = (c3_1.text_input('Girl Scout First Name', key=f'sct_fn_{i}',)).title()
                    section['ln'] = (c3_2.text_input('Girl Scout Last Name',placeholder=parnt_lastnm, key=f'sct_ln_{i}')).title()
                    section['FullName'] = section['fn'] + " " + section['ln']
                    section['nameId'] = section['fn'][:3].title() + section['ln'].title()

                    st.subheader('Award Selection')
                    st.write('Note: Cookie Dough is now **Program Credits** - this name change better reflects what the funds can be used for.')
                    c4_1,c4_2,c4_3,c4_4 = st.columns(4)
                    with c4_1:
                        st.write('**Total boxes sold => 315:**')
                        st.write('The award for 315+ boxes of cookies is a t-shirt')
                        section['tshirt_size'] = st.select_slider(label='T-shirt size',key=f'tshirt_sct_{i}',options=['YS','YM','YL','Adult-S','Adult-M','Adult-L','Adult-X','Adult-XL','Adult-2XL','Adult-3XL'])
                    with c4_2:
                        st.write('**Total boxes sold < 450:**')
                        st.write('Award prizes up to 450 boxes are cumulative, so there is no selection.')
                    with c4_3:
                        st.write('')
                        st.write('Option at 450+ boxes to receive $40 in program credits instead of the *cummulative* 75-450 prizes. ')
                        section['a450_choice'] = st.selectbox(label='Prizes up to 450 boxes or Program Credits',key=f'a450_sct_{i}',options=['Cumulative Award Prizes','Program Credits'])
                    with c4_4:
                        st.write('**Total boxes sold > 500:**')
                        st.write('500+ awards are not cummulative, option to receive program credits or reward prize')
                        section['a500_choice'] = st.selectbox(label='Award Prize or Program Credits',key=f'a500_sct_{i}', options=['Award Prize','Program Credits'])
                    st.divider()
            # Iterate through sections
    
                st.checkbox('By creating this account and ordering cookies, I understand that I am financially responsible for any cookies that I order. I also agree that I will return all funds by the due date')

                submitted = st.form_submit_button("Submit", on_click=handle_form_submission,args=(es))


def get_compliment():
    compliments = [
        "You’re doing an amazing job.",
        "What you do makes a big difference.",
        "You handle challenges with so much grace.",
        "You inspire everyone around you.",
        "You always find a way to make things better.",
        "You bring out the best in people.",
        "Your hard work doesn’t go unnoticed.",
        "You’re stronger than you realize.",
        "You make others feel valued and appreciated.",
        "You lead by example, and it shows.",
        "Your kindness is contagious.",
        "You have a great sense of humor.",
        "You’re thoughtful and considerate in everything you do.",
        "Your positivity is truly inspiring.",
        "You’re a great problem-solver.",
        "You make people feel welcome and included.",
        "You’re so creative and full of ideas.",
        "You bring joy to those around you.",
        "You handle tough situations like a pro.",
        "You have a natural ability to connect with others.",
    ]

    comp = random.choice(compliments)
    st.success(comp)

def acct_login(es):
    qry_dat = esu.get_trm_qry_dat(es,indexnm=ss.indexes['index_scouts'], field='username', value=ss.username)
    # st.write(qry_dat)
    if len(qry_dat)> 0:
        scout_dat=qry_dat[0]['_source']
        if (scout_dat.get('parent_password') == ss.login_usrpass) and (scout_dat.get('username') == ss.login_username):
            ss.authenticated = True
            scout_dat.pop("parent_password", None)
            ss.scout_dat = scout_dat.copy()
        else:
            st.error("Invalid username or password")
    else:
        st.error("Invalid username")

 # Save state to query parameters

#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    es = get_connected()
    # Show input for password.
    if not ss.authenticated:
        st.write('Welcome to our Troop Cookie Tracker.  This site is used to submit orders to our troop cupboard for any cookies that are girl delivery (paper or girl delivery Digital Cookie.\n Please notify the admin, Jennifer, via band or text if you encounter any errors. Thank you. ')
        new_account = st.button('Create an Account')
        if new_account:
            ss.show_form = True
        if st.session_state.show_form:
            register_user(es)
        if not new_account:
            with st.form('login'):
                scout_dat = {}
                st.text_input('username',key='login_username')
                st.text_input('Password', key='login_usrpass',type='password')
                login = st.form_submit_button("Login")

                if login:
                    ss.username = ss.login_username
                    acct_login(es)

    if ss.authenticated:
        
        ss.gs_nms = [scout['fn'] for scout in ss.scout_dat.get('scout_details')]

        
        st.write(f"Welcome {ss.scout_dat.get('parent_firstname')}, your registered scouts are: {', '.join(ss.gs_nms)}")
        st.markdown(f"If you need to add a scout please reach out to the admin.") #[admin](mailto:{st.secrets['general']['email_admin']})?subject=Hello%20Streamlit&body=This%20is%20the%20email%20body)", unsafe_allow_html=True)
        
        cookie_manager = stx.CookieManager()
        cookie = cookie_manager.get(cookie="user")
        if cookie is None:
            cookie_manager.set("user", ss.username)
            cookie_manager.set("cookie_sctdat", ss.scout_dat)
            cookie_manager.set("cookie_gs_nms", ss.gs_nms)
            cookie_manager.set("auth", ss.authenticated) 
            cookie_manager.set('indexes_dict',ss.indexes)

        get_compliment()
       
        # Navigate to another page if authenticated
        st.success("You are authenticated!")
        with st.container(border=True):
            st.page_link(label="Click Here to Go to the Cookie Portal", use_container_width=True, page="pages/portal_home.py")

if __name__ == '__main__':

    setup.config_site(page_title="Login")
    # Initialization
    init_ss()

    main()