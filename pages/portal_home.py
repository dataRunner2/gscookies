from json import loads
import streamlit as st
from streamlit import session_state as ss,  data_editor as de, rerun as rr
# from streamlit_calendar import calendar
import streamlit.components.v1 as components


import time
from typing import List, Tuple
import pandas as pd
from pathlib import Path
from datetime import datetime
import base64

# import eland as ed
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3


# Add parent path to system path so streamlit can find css & config toml
# sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')

# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)

# print(f'The folder contents are: {os.listdir()}\n')
# print(f"Now... the current directory: {Path.cwd()}")
# from utils.mplcal import MplCalendar as mc

#---------------------------------------
# LOADS THE SCOUT NAME, ADDRESS, PARENT AND REWARD INFO to Elastic
# Uncomment and re-do if changes to sheet
#---------------------------------------
# conn = st.connection("gsinfo", type=GSheetsConnection)
# df = conn.read()
# df.dropna(axis=1,how="all",inplace=True)
# df.dropna(axis=0,how="all",inplace=True)
# df.reset_index(inplace=True,drop=True)
# df.rename(columns={"Unnamed: 6":"Address"},inplace=True)
# df['FullName'] = [f"{f} {l}" for f,l in zip(df['First'],df['Last'])]

# df = df.fillna('None')
# type(df)

# ed.pandas_to_eland(pd_df = df, es_client=es,  es_dest_index='scouts', es_if_exists="replace", es_refresh=True) # index field 'H' as text not keyword

# # SLOW
# # for i,row in df.iterrows():
# #     rowdat = json.dupmp
# #     esu.add_es_doc(es,indexnm='scouts', doc=row)

def init_ss():
    if 'authenticated' not in ss:
        ss.authenticated = False
        # if 'gsNm' not in st.session_state:
        # st.session_state['gsNm'] = gs_nms.index('zz scout not selected')
    if 'guardianNm' not in st.session_state:
        st.session_state['guardianNm'] = 'scout parent'
    if 'adminpassword_correct' not in st.session_state:
        st.session_state['adminpassword_correct'] = False
    if "scout_dat" not in st.session_state:
        st.session_state['scout_dat'] = False
    if "edited_dat" not in st.session_state:
        st.session_state['edited_dat'] = {}

# @st.cache_data
def get_connected():
    es = esu.conn_es()
    return es
#---------------------------------------
# Password Configuration
#---------------------------------------

## square app tracking -

# Megan
# Madeline Knudsvig - Troop 44044

def move_column_inplace(df, col, pos):
    col = df.pop(col)
    df.insert(pos, col.name, col)


#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    # @st.cache_data
    es=get_connected()
    
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    st.write('----')
    # Calendar
    st.header('Important Dates, Links and Reminders')
    st.subheader('Reminders')
    st.warning("!! You will continue to use this app to submit orders to the troop cookie cupboard through 3/19 !!")
    st.markdown("""
                A few reminders:
                - Cookies are $6 per box. There's no Raspberry Rally this year, but the rest of the lineup is the same!
                - Consider setting up a QR code to link to your Girl Scout's Digital Cookie site!
                - Do not give out your personally identifiable information, such as last name or school.
                - You will need to wear your uniform when you sell, you are representing your family and Girl Scouts!
                - All in-person orders collected on digital cookie will need to be approved by the parent within 3 days. After a few days, orders not approved will be automatically rejected and will not count towards sales.
                - We are participating in Operation Cookie Drop, which donates boxes to the USO to distribute to service members. These donations will count in increments of $6 as a box your Girl Scout sold, but you will not have physical boxes for these donations. The boxes will be handled at the end of the sale at the Council level.
                - Monitor your digital cookie orders - submit your orders to us via this site as frequently as you would like
                - Have fun with selling - this is what you make it!
                """)
    # jan = mc(2024,1)
    # feb = mc(2024,2)
    # mar = mc(2024,3)
    # jan.add_event(15, "Digital Cookie Emails to Volunteers")
    # jan.add_event(19,"In-person Sales Begin")
    # feb.add_event(4,"Initial Orders Submitted")
    # feb.add_event(16,"Booth Sales")
    # mar.add_event(19,"Family deadline for turning in Cookie Money")
    # st.pyplot(fig=jan)

    st.subheader('Important Dates')
    st.write('1/139: Families receeive Digital Cookie registration email')
    st.write('1/15 - 2/2: Digital cookie sales and Promise paper Orders')
    st.write('2/2 - All initial "promise" orders and digital cookie - girl delivery order must be submitted to this site')
    st.write('~2/18 - Cookies Arrive <- Volunteers needed to collect cookies')
    st.write('2/20 - 3/16: In person Delivery Cookie Orders')
    st.write('2/28 - 3/16: Booth Sales - Watch out for Signups')
    st.write('3/9: Family deadline for turning in initial order cookie money by 12 Noon')
    st.write('3/16: Last day to sell cookies')
    st.write('3/19: Family deadline for turning in **all** order cookie money by 12 Noon')

    topc1, topc2,topc3 = st.columns([2,6,2])
    with topc1:
        pass
        # selected_page = st.selectbox("----", page_names_to_funcs.keys())
    with topc2:
        bandurl = "https://band.us/band/93124235"
        st.info("Connect with us on [Band](%s) if you have any questions" % bandurl)
        st.warning("Note - All Cookie Money Due 3/19")
    # page_names_to_funcs[selected_page]()


    # selected_page = st.sidebar.selectbox("----", page_names_to_funcs.keys())
    # page_names_to_funcs[selected_page]()

    # st.sidebar.markdown(st.session_state)


if __name__ == '__main__':

    setup.config_site(page_title="Cookie Portal Home",initial_sidebar_state='expanded')
    setup.is_admin()
    # Initialization
    init_ss()
    main()