from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
from typing import List, Tuple
import pandas as pd
import base64
import random
from pathlib import Path
import hmac
import bcrypt
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
    if "form_data" not in ss:
        ss.form_data = {"parent_firstname": "", "parent_lastname": "","parent_email": "", "parent_phone": "","username":"","parent_password": "","parent_password_hash":""}
    if 'show_account_expander' not in ss:
        ss.show_account_expander = False
    if  'validated' not in ss:
        ss.validated = False
    if 'account_info_valid' not in ss:
        ss.account_info_valid = False
    if 'scouts_added' not in ss:
        ss.scouts_added = False
    if "sections" not in st.session_state:
        st.session_state.sections = [{}]  # Start with one empty section
    if 'cnt_scts_label' not in ss:
        ss.cnt_scts_label = '1 Scout'
    if 'username' not in ss:
        ss.username = ''
    if 'doc_id' not in ss:
        ss.doc_id = None
    if 'indexes' not in ss:
        ss.indexes = {}
        ss.indexes['index_scouts'] = 'scouts2025'
        ss.indexes['index_orders'] = 'orders2025'
        ss.indexes['index_money'] = 'money_received2025'
        ss.indexes['index_inventory'] = 'inventory2025'


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

def reset_account_formdata():
    ss.form_data = {"parent_firstname": "", "parent_lastname": "","parent_email": "", "parent_phone": "","username":"","parent_password": "","parent_password_hash":""}

def get_connected():
    es = esu.conn_es()
    ss.es = es
    return es

@st.cache_data
def is_authenticated():
    ss.authenticated = True

def validate_form(es,data):
    st.write(f"validating content for {data['username']}")
    # st.write(data)
    errors = []
    ss.form_data['create_dt'] = datetime.now()
    if not data["parent_firstname"]:
        errors.append("A first name is required.")
    if not data["parent_lastname"]:
        errors.append("A last name is required.")
    if not data["parent_phone"]:
        errors.append("A valid phone number is required.")
    if "@" not in data['parent_email']:
        errors.append("Please enter a valid email address.")
    # if len(data["parent_password"]) <= 6:
    #     st.error("Password must be at least 6 characters long.")
    # verify_troop()
    # verify the username is not already used
    qry_dat = esu.get_qry_dat(ss.es,indexnm=ss.indexes['index_scouts'], field='username', value=data['username'])
    if len(qry_dat)> 0:
        errors.append('This username is already registered')
    if errors:
        return False, errors
    else:
        return True, []

# def verify_pass():
#     if len(ssusrpass) <= 6:
#         st.error("Password must be at least 6 characters long.")

def verify_troop():
    """Checks whether a password entered by the user is correct."""
    st.write(f"Compare {ss.verifytrp} - {st.secrets['general']['trpverify']}")
    if hmac.compare_digest(ss.verifytrp, st.secrets['general']["trpverify"]):
        st.session_state["password_correct"] = True
    else:
        st.error("😕 Troop Verification Incorrect - please type our leaders name, 5 characters, all lower case")
        st.session_state["password_correct"] = False


# my_grid = grid(2, [2, 4, 1], 1, 4, vertical_align="bottom")
#     # Row 1:
#     my_grid.dataframe(random_df, use_container_width=True)
#     my_grid.line_chart(random_df, use_container_width=True)
#     # Row 2:
#     my_grid.selectbox("Select Country", ["Germany", "Italy", "Japan", "USA"])
#     my_grid.text_input("Your name")
#     my_grid.button("Send", use_container_width=True)
#     # Row 3:
def add_scouts(es):
    update_sections()
    with st.form('scout_deets', border=False):
        # Iterate through sections
        for i, section in enumerate(ss.sections):
            st.write(f"**Scout {i + 1}**")
            c3_1,c3_2,c3_3,c3_4 = st.columns(4)
            section['fn'] = (c3_1.text_input('Girl Scout First Name', key=f'sct_fn_{i}',)).title().strip()
            section['ln'] = (c3_2.text_input('Girl Scout Last Name',value=ss.form_data['parent_lastname'], key=f'sct_ln_{i}')).title().strip()
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
        
        c1,c2,c3 = st.columns(3)
        with c2: 
            submitted = st.form_submit_button("💾 Save Scout Info", type="primary") 

    if submitted:
        scout_deets = {"scout_details":ss.sections }
        resp = es.update(index=ss.indexes['index_scouts'], id=ss.doc_id, doc=scout_deets, doc_as_upsert=True)
        if resp.get('result') == 'updated':
            ss.scouts_added = True
            ss.show_account_expander = False
            reset_sections()
            reset_account_formdata()
            st.rerun()

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
        "Adulting can be hard.... cookies help.",
        "Thank you for being a good human.",
        "You bring joy to those around you.",
        "You handle tough situations like a pro.",
        "You have a natural ability to connect with others.",
    ]

    comp = random.choice(compliments)
    st.info(comp)

def acct_login(es,login_password):
    qry_resp = es.search(index = ss.indexes['index_scouts'], query={"match": {"username": ss.username}})
    if not qry_resp["hits"]["hits"]:
        return False, "User not Found", {}
    else:
        scout_dat=qry_resp["hits"]["hits"][0]['_source']
        ss.doc_id = qry_resp["hits"]["hits"][0]['_id']
        # st.write(ss.doc_id)
        # st.write(f'found account {scout_dat}')
        if scout_dat["parent_password_b64"]:
            # Retrieve the stored Base64-encoded hash
            stored_hash_base64 = scout_dat["parent_password_b64"]

            # Decode the Base64-encoded hash
            stored_hash = base64.b64decode(stored_hash_base64)

            # Verify the provided password against the stored hash
            if bcrypt.checkpw(login_password.encode('utf-8'), stored_hash):
                return True, "Authentication successful", scout_dat
            else:
                return False, "Invalid password", {}
        else:
            st.write('pass is not encrpted')
            is_correct = scout_dat.get('parent_password') == login_password
            return True, "Authentication successful"
        
 # Save state to query parameters

#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    es = get_connected()
    if st.button('logout'):
        ss.clear()
        st.rerun()
    # ss
    # Show input for password.
    if not ss.authenticated:
        # st.title('Welcome to our Troop Cookie Tracker.')
        st.write('This site is used to submit orders to our troop cupboard for any cookies that are girl delivery (paper or girl delivery Digital Cookie).')
        st.write('Please notify the admin, Jennifer, via band or text if you encounter any errors. Thank you. ')
        with st.form('login'):
            scout_dat = {}
            st.text_input('username',key='login_username')
            login_password = st.text_input('Password',type='password')
            login = st.form_submit_button("Login")

            if login:
                ss.username = ss.login_username
                ss.authenticated, message, scout_dat = acct_login(es,login_password)
                st.write(message)
                if ss.authenticated:
                    scout_dat.pop("parent_password", None)
                    ss.scout_dat = scout_dat.copy()
                    st.rerun()

        st.divider()
        # new_account = st.button('Create an Account')

        with st.expander("CREATE A NEW ACCOUNT", expanded=False):
            with st.form('new_user',border=False):
                password_instructions = os.getenv('password_instructions')

                c0_1, c0_2, c0_3, c0_4 = st.columns(4)

                c1_1, c1_2, c1_3, c1_4 = st.columns(4)
                parnt_firstnm = c1_1.text_input('First name',value=ss.form_data['parent_firstname'])
                parnt_lastnm = c1_2.text_input('Last name',value=ss.form_data['parent_lastname'])
                parnt_email = c1_3.text_input('Email',value=ss.form_data['parent_email'])
                parnt_phone = c1_4.text_input('Phone',value=ss.form_data['parent_phone'])

                c2_1, c2_2, c2_3, c2_4 = st.columns(4)
                new_username = c2_1.text_input('Username',value=ss.form_data['username'])
                usrpass = c2_2.text_input('Password', value='',type='password', help=password_instructions)
                cnt_scts = c2_3.number_input(f'**Number of Scouts Registering**',min_value=0,max_value=4,step=1, key='cnt_scts')
                verifytrp = c2_4.text_input('Troop Leader Name', help='troop verification, 5 letters all lowercase')
                
                # passcopy = c2_3.text_input('Repeat password', value=ss.form_data['passcopy'],type='password')
                # Hash the password
                hashed_password = bcrypt.hashpw(usrpass.encode('utf-8'),bcrypt.gensalt())
                # st.write("Hashed Password:", hashed_password)
                # Encode hash as Base64 to save to Elastic
                base64_encoded = base64.b64encode(hashed_password).decode('utf-8')
                # st.write(f'base64 string: {base64_encoded}')
                st.checkbox('By creating this account and ordering cookies, I understand that I am financially responsible for any cookies that I order. I also agree that I will return all funds by the due date')
                create_account = st.form_submit_button("Create Account")
                
                if create_account:
                    # evaluating password hash
                    # Retrieve the stored Base64-encoded hash
                    stored_hash_base64 = base64_encoded

                    # Decode the Base64-encoded hash
                    stored_hash = base64.b64decode(stored_hash_base64)

                    # Verify the provided password against the stored hash
                    if bcrypt.checkpw(usrpass.encode('utf-8'), stored_hash):
                        st.write('encryption verified')
                    reset_account_formdata()
                    ss.form_data = {
                        "username":new_username,
                        "parent_firstname":parnt_firstnm.title().strip(),
                        "parent_lastname": parnt_lastnm.title().strip(),
                        "parent_FullName": f'{parnt_firstnm.title()} {parnt_lastnm.title()}',
                        "parent_NameId": f'{parnt_firstnm.lower()}_{parnt_lastnm.lower()}',
                        "parent_email": parnt_email.lower().strip(),
                        "parent_phone": parnt_phone,
                        "parent_password_b64": base64_encoded,
                        "verify_trp": verifytrp,
                        "cnt_scts": cnt_scts
                        }
                    is_validated, errors = validate_form(es, ss.form_data)
                    if errors:
                        st.write(f'there are errors with your submission - validated: {is_validated}')
                        
                    for error in errors:
                        st.error(error)
                        
                    if is_validated == True: 
                        resp = esu.add_es_doc(es,indexnm=ss.indexes['index_scouts'],id=None, doc=ss.form_data)
                        # st.write(resp)
                        st.success('Account Created Successfully, please add scout information')
                        ss.doc_id = resp.get('_id')
                        ss.show_account_expander = False
                   
            if ss.doc_id:
                with st.container():
                    st.subheader('Add Scout Details')
                    add_scouts(es)
                    
    if ss.scouts_added and ss.doc_id:
        st.write('Scouts Added - ready to order cookies')
        ss.authenticated = True
        ss.scout_dat = es.get(index=ss.indexes['index_scouts'],id = ss.doc_id)['_source']

    if ss.authenticated:
        is_authenticated()
        try:
            ss.gs_nms = [scout['fn'] for scout in ss.scout_dat.get('scout_details')]
            st.write(f"Welcome {ss.scout_dat.get('parent_firstname')}, your registered scouts are: {', '.join(ss.gs_nms)}")
        except:
            st.warning('Opps during registration your scouts information was not saved')
            if ss.scout_dat.get('cnt_scts'): 
                ss.cnt_scts = ss.scout_dat['cnt_scts']
            else: ss.cnt_scts = 1
            add_scouts(es)
            qry_resp = es.search(index = ss.indexes['index_scouts'], query={"match": {"username": ss.username}})
            if not qry_resp["hits"]["hits"]:
                return False, "User not Found", {}
            else:
                scout_dat=qry_resp["hits"]["hits"][0]['_source']

        if ss.scout_dat.get('scout_details'):
            # st.write( ss.scout_dat.get('scout_details'))
            st.markdown(f"If you need to add a scout please reach out to the admin.") #[admin](mailto:{st.secrets['general']['email_admin']})?subject=Hello%20Streamlit&body=This%20is%20the%20email%20body)", unsafe_allow_html=True)

            cookie_manager = stx.CookieManager()
            cookie = cookie_manager.get(cookie="user")
            if cookie is None:
                cookie_manager.set("user", ss.username)
                cookie_manager.set("cookie_sctdat", ss.scout_dat)
                cookie_manager.set("cookie_gs_nms", ss.gs_nms)
                cookie_manager.set("auth", ss.authenticated)
                cookie_manager.set('indexes_dict',ss.indexes)
            # st.success("You are authenticated!")

            get_compliment()

            # Navigate to another page if authenticated
            with st.container(border=True):
                st.page_link(label="🍪 **Click Here to get Cookies** 🍪", use_container_width=True, page="pages/portal_home.py")

        if ss.is_admin:
            # GET ALL SCOUT DATA
            all_scout_qrydat = es.search(index = ss.indexes['index_scouts'], source='scout_details', query={"match_all":{}})['hits']['hits']
            all_scout_dat = [sct['_source'].get('scout_details') for sct in all_scout_qrydat if sct['_source'].get('scout_details') is not None]
            ss.all_scout_dat = [entry for sublist in all_scout_dat for entry in sublist]       


if __name__ == '__main__':

    setup.config_site(page_title="Account")
    # Initialization
    init_ss()

    main()