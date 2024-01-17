from json import loads
import streamlit as st
from streamlit_calendar import calendar
# from streamlit_searchbox import st_searchbox
from typing import List, Tuple
import pandas as pd
from elasticsearch import Elasticsearch  # need to also install with pip3
import sys
from pathlib import Path
import hmac
import os


# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)

environment = os.getenv('ENV')

print(f'The folder contents are: {os.listdir()}\n')

# print(f"Now... the current directory: {Path.cwd()}")
from utils import esutils as eu
# from utils.mplcal import MplCalendar as mc

# @st.cache_data
es = eu.esu.conn_es()


# Add parent path to system path so streamlit can find css & config toml
# sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')

#---------------------------------------
# Streamlit Configuration
#---------------------------------------
# Some Basic Configuration for StreamLit - Must be the first streamlit command

st.set_page_config(
    page_title="Troop 43202 Cookies",
    page_icon="samoas.jpg",
    layout="wide",
    # initial_sidebar_state="collapsed"
)


def local_css(file_name):
    with open(f'{file_name}') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css('style.css')



#---------------------------------------
# Password Configuration
#---------------------------------------
# conn = st.connection("gsheets", type=GSheetsConnection)
# conn = st.connection('gcs', type=FilesConnection)

# ebudde = get_dat('ebudde')

# pickupSlots = get_dat('pickupSlots')

# st.table(ebudde)
# ebudde.columns
# gs_nms = ebudde['Girl']

## square app tracking -

# Megan
# Madeline Knudsvig - Troop 44044
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the passward is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# show_pages(
#         [
#             Page("main_app.py",name="主页",icon="🏠"),
#             Section(name="表格相关处理技术",icon="🏠"),
#             Page("menuPages/table_linked.py", "主从表格",icon="💪"),
#             Page("menuPages/second.py", "样例2",icon="💪"),
#             Section(name="项目相关",icon="🏠"),
#             Page("menuPages/xm.py", "项目",icon="💪"),
#             Page("menuPages/tax.py", "税率",icon="💪"),
#             # in_section=False用明确申明，该页不属于上面的菜单section子项目
#             Page("menuPages/test.py",name="最后页面",icon="🏠",in_section=False),
#         ]

#---------------------------------------
# Calendar
#---------------------------------------

st.title("GS Troop 43202 Cookie Tracker")
st.write('')


# jan = mc(2024,1)
# feb = mc(2024,2)
# mar = mc(2024,3)
# jan.add_event(15, "Digital Cookie Emails to Volunteers")
# jan.add_event(19,"In-person Sales Begin")
# feb.add_event(4,"Initial Orders Submitted")
# feb.add_event(16,"Booth Sales")
# mar.add_event(19,"Family deadline for turning in Cookie Money")
# st.pyplot(fig=jan)

st.header('Important Dates')
st.write('1/15: Primary caregivers receive Digital Cookie Registration email')
st.write('1/19: 2024 Cookie Program Launch')
st.write('1/19-2/4: Initial Orders')
st.write('2/4 - 3/11: In person Delivery of Digital Cookie Orders')
st.write('~2/9: Pick up cookies from cookie cupboard - Volutneers Needed')
st.write('1/30: Booth site picks begin at 6:30 pm')
st.write('2/4: Girl Scout inital orders due to Troop')
st.write('2/16-3/16: Booth Sales')
st.write('3/19: Family deadline for turning in Cookie Money')
st.write('3/22: Troop wrap-up deadline')

st.subheader('Reminders')
st.write('- You have 5 days in digital cookie to approve all orders\n')
st.write('- Monitor your digital cookie orders - submit your orders to us as frequently as you would like')
