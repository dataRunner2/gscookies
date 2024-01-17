from json import loads
import streamlit as st
from streamlit_calendar import calendar
# import streamlit_permalink as st. 
# from streamlit_searchbox import st_searchbox
from typing import List, Tuple
import pandas as pd
from elasticsearch import Elasticsearch  # need to also install with pip3
import sys
from pathlib import Path
import hmac
import os
import eland as ed
from datetime import datetime


# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)

environment = os.getenv('ENV')

print(f'The folder contents are: {os.listdir()}\n')

# print(f"Now... the current directory: {Path.cwd()}")
from utils.esutils import esu
from utils.esutils import uts
# from utils.mplcal import MplCalendar as mc

# @st.cache_data
es = esu.conn_es()


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
    initial_sidebar_state="collapsed"
)


def local_css(file_name):
    with open(f'{file_name}') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css('style.css')


#---------------------------------------
# Password Configuration
#---------------------------------------

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

    # Return True if the password is validated.
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

# # show_pages(
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
# Functions
#---------------------------------------
def calc_tots():
    total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
    total_money = total_boxes*6
    return total_boxes, total_money

#---------------------------------------
# Select GS Name
#---------------------------------------

# Initialization
if 'gsNm' not in st.session_state:
    st.session_state['gsNm'] = 'no scout selected'
if 'guardianNm' not in st.session_state:
    st.session_state['guardianNm'] = 'scout parent'


gs_nms = esu.get_dat(es,"scouts", "FullName")
def update_parent():
    uts.get_parent()
             
gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout',key='gsNm', on_change=update_parent())

home, order, myorders = st.tabs(["Home","Order Cookies","My Orders"])
with home:
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

with order:
    st.subheader(f'Submit a Cookie Order for {st.session_state["gsNm"]}')
st.warning('Submit seperate orders for paper orders vs. Digital Cookie\n')

with st.form('submit orders', clear_on_submit=True):
    appc1, appc2, appc3 = st.columns([3,.25,3])

    with appc1:
        # At this point the URL query string is empty / unchanged, even with data in the text field.

        ordType = st.selectbox("Order Type:",options=['Digital Cookie','Paper Order'],key='ordType')
        guardianNm = st.text_input("Guardian accountable for order",key='guardianNm', max_chars=50)


    with appc3:
        PickupNm = st.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
        PickupPh = st.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)
        pickupT = st.selectbox('Pickup Slot',['Tuesday 5-7','Wednesday 6-9'])

    st.write('----')
    ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])
    with ck1:
        advf=st.number_input(label='Adventurefuls',step=1,min_value=0)
        tags=st.number_input(label='Tagalongs',step=1,min_value=0)

    with ck2:
        lmup=st.number_input(label='Lemon-Ups',step=1,min_value=0)
        tmint=st.number_input(label='Thin Mints',step=1,min_value=0)
    with ck3:
        tre=st.number_input(label='Trefoils',step=1,min_value=0)
        smr=st.number_input(label="S'Mores",step=1,min_value=0)

    with ck4:
        dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=0)
        toff=st.number_input(label='Toffee-Tastic',step=1,min_value=0)

    with ck5:
        sam=st.number_input(label='Samoas',step=1,min_value=0)
        opc=st.number_input(label='Operation Cookie Drop',step=1,min_value=0)

    comments = st.text_area("Comments", key='comments')


    # submitted = st.form_submit_button()
    if st.form_submit_button("Submit Order to Cookie Crew"):
        total_boxes, order_amount=calc_tots()

        # Every form must have a submit button.
        order_data = {
            "ScoutName": gsNm,
            "OrderType": ordType,
            "guardianNm":guardianNm,
            "PickupNm": PickupNm,
            "PickupPh": PickupPh,
            "PickupT": pickupT ,
            "Adf": advf,
            "LmUp": lmup,
            "Tre": tre,
            "DSD": dsd,
            "Sam": sam,
            "Tags": tags,
            "Tmint": tmint,
            "Smr": smr,
            "Toff": toff,
            "OpC": opc,
            "order_qty_boxes": total_boxes,
            "order_amount": order_amount,
            "submit_dt": datetime.now(),
            "status": "Pending"
            }
        st.text(f' {total_boxes} boxes were submitted in your order\n Total amount owed for order = ${order_amount} \n your pickup slot is: {pickupT}')        # get latest push of orders:
        # orders = get_my_data('orders')
        esu.add_es_doc(es,indexnm="orders2024", doc=order_data)
        # vent['seq'] = Time.now.strftime('%Y%m%d%H%M%S%L').to_i
        # orders.sort_values(by='OrderNumber',ascending=False,inplace=True,na_position='last')
        new_order = pd.DataFrame.from_dict(order_data, orient='index')
        st.table(new_order)

        # appendedOrders = pd.concat([orders,new_order])
        # st.write(appendedOrders.shape)

        # add_dat('orders',appendedOrders)
        # st.cache_data.clear()
        st.success('Your order has been submitted!', icon="✅")
        st.balloons()

with myorders:
    def get_qry_dat(es,indexnm="orders",field=None,value=None):
        if not value:
              value = st.session_state.gsNm
        sq1 = es.search(index = indexnm, query={"match": {field: value}})
        qresp=sq1['hits']['hits']
        st.table(qresp)
        return qresp

    girl_orders = ed.DataFrame(es, es_index_pattern="orders2024")
    girl_orders = ed.eland_to_pandas(girl_orders)
    girl_orders.reset_index(inplace=True, names='docId')
    girl_orders = girl_orders[girl_orders['ScoutName'] == st.session_state["gsNm"]]
    # orders.set_index(keys=['appName'],inplace=True)

    # girl_orders = get_qry_dat(es,"orders2024",field='ScoutName',value=gsNm)
    st.table(girl_orders)