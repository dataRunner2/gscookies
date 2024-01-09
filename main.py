from json import loads
import streamlit as st
from streamlit_searchbox import st_searchbox
from typing import List, Tuple
import pandas as pd
import sys
from pathlib import Path
# from PIL import Image
import os
# from streamlit_gsheets import GSheetsConnection

from st_files_connection import FilesConnection
import streamlit_permalink as stp

import streamlit.components.v1 as components
environment = os.getenv('ENV')

# Add parent path to system path so streamlit can find css & config toml
sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')


########## Streamlit Configuration ##########
# Some Basic Configuration for StreamLit - Must be the first streamlit command

st.set_page_config(
    page_title="Troop 43202 Cookies",
    page_icon="path_of_your_favicon",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# SA frorm streamlit cloud to sa account
# app-sa@gs-cookies-410702.iam.gserviceaccount.com

#---------------------------------------
# Functions
def local_css(file_name):
    with open(f'{file_name}') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css('style.css')

# def update_order(file_uploaded):
#     if file_uploaded is not None:
#         # To read file as bytes:
#         bytes_data = file_uploaded.getvalue()
#         st.write(bytes_data)

#          # Can be used wherever a "file-like" object is accepted:
#         dataframe = pd.read_csv(file_uploaded)
#     return dataframe

def get_my_data(fileNm, gsNm=None):
    gsDat = pd.read_csv(fileNm)
    gsDat.dropna(axis=1,how='all',inplace=True)
    gsDat.dropna(axis=0,how='all',inplace=True)

    if gsNm:
        gsDat = gsDat[gsDat['gsName'] == gsNm]
    return gsDat

def get_dat(fileNm):
    gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)
    return gsDatR


def calc_tots():
    total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
    total_money = total_boxes*6
    return total_boxes, total_money
############ DATA CONNECTION ##############
# conn = st.connection("gsheets", type=GSheetsConnection)
conn = st.connection('gcs', type=FilesConnection)

ebudde = get_dat('ebudde')

# st.table(ebudde)
gs_nms = ebudde['Girl']

############ HOME PAGE APP ###############

st.title("GS Troop 43202 Cookie Tracker")
st.write('')

orders,myorders,dates,rewards = st.tabs(["Submit Order","My Orders","Important Dates","My Rewards"])

with orders:
    st.subheader('Submit a Cookie Order')
    st.warning('Submit seperate orders for paper orders vs. Digital Cookie')
    # st.subheader("Add a New Widget")
    # st.cache_data.clear()
    # st.experimental_rerun()
    with stp.form('submit orders', clear_on_submit=True):
        appc1, appc2, appc3 = st.columns([3,.25,3])

        with appc1:
            # At this point the URL query string is empty / unchanged, even with data in the text field.
            gsNm = stp.selectbox("Girl Scount Name:",gs_nms,placeholder='Select your scout',url_key='gsNm',)
            ordType = stp.selectbox("Order Type:",options=['Digital Cookie','Paper Order'],url_key='ordType')
            guardianNm = stp.text_input("Guardian accountable for order",key='guardianNm',max_chars=50,url_key='guardNm')


        with appc3:
            PickupNm = stp.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
            PickupPh = stp.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)
            pickupT = stp.selectbox('Pickup Slot',['Tuesday 5-7','Wednesday 6-9'])

        st.write('----')
        ck1,ck2,ck3 = st.columns([2,2,2])
        with ck1:
            advf=st.number_input(label='Adventurefuls',step=1,min_value=0)
            lmup=st.number_input(label='Lemon-Ups',step=1,min_value=0)
            tre=st.number_input(label='Trefoils',step=1,min_value=0)
        with ck2:
            dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=0)
            sam=st.number_input(label='Samoas',step=1,min_value=0)
            tags=st.number_input(label='Tagalongs',step=1,min_value=0)
        with ck3:
            tmint=st.number_input(label='Thin Mints',step=1,min_value=0)
            smr=st.number_input(label="S'Mores",step=1,min_value=0)
            toff=st.number_input(label='Toffee-Tastic',step=1,min_value=0)
            opc=st.number_input(label='Operation Cookie Drop',step=1,min_value=0)

        comments = st.text_area("Comments",key='comments')
        # Every form must have a submit button.
        order_data = {
            "ScoutName":[gsNm],
            "OrderType": [ordType], 
            "guardianNm":[guardianNm],
            "PickupNm":[PickupNm],
            "PickupPh":[PickupPh],
            "PickupT":[pickupT],
            "Adf":[advf],
            "LmUp":[lmup],
            "Tre":[tre],
            "DSD":[dsd],
            "Sam":[sam],
            "Tags":[tags],
            "Tmint":[tmint],
            "Smr":[smr],
            "Toff":[toff],
            "OpC":[opc]
            }
        new_order = pd.DataFrame.from_dict(order_data)

        # submitted = st.form_submit_button()
        if stp.form_submit_button("Submit Order to Cookie Crew"):
            total_boxes, total_money=calc_tots()
            st.text(f'Total boxes in order = {total_boxes}  >  Total amount owed for order = ${total_money} \n your pickup slot is: {pickupT}')
            new_order["total_boxes"]=total_boxes
            new_order["total_money"]=total_money
            # get latest push of orders:
            # orders = get_my_data('orders')
            orders = get_dat('orders')
            orders.sort_values(by='OrderNumber',ascending=False,inplace=True,na_position='last')
            max_ordNum = orders.iloc[0,0]
            new_order["OrderNumber"]=max_ordNum+1
            st.table(new_order)
            appendedOrders = orders + new_order

            df = conn.update(
                worksheet='orders',
                data=appendedOrders 
            )
            
            st.write(f"Your order has been submitted") #{form_data}")

with dates:
    st.header('Important Dates, Reminders and Links')
    st.write('REMINDER: You have 5 days in digital cookie to approve all orders\n')

    st.write('12/7: Volunteer eBudde access')
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



# with myorders:
