import json
import streamlit as st
from typing import List, Tuple
import pandas as pd
import elasticsearch
import sys
from pathlib import Path

import os
import streamlit_permalink as stp
from src.utils import esutils as eu
import eland as ed
from streamlit_gsheets import GSheetsConnection

import streamlit.components.v1 as components

if 'gsNm' not in st.session_state:
    st.session_state['gsNm'] = 'none'
if 'guardianNm' not in st.session_state:
    st.session_state['guardianNm'] = 'none'
#---------------------------------------
# Functions

def calc_tots():
    total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
    total_money = total_boxes*6
    return total_boxes, total_money

es = eu.esu.conn_es()
gs_nms = eu.esu.get_dat(es,"scouts", "FullName")

def get_parent():
    scout_dat = eu.esu.get_qry_dat(es,indexnm="scouts",field='FullName',value=st.session_state.gsNm)
    if len(scout_dat) > 0:
        parent = scout_dat[0]['_source']['Parent']
        st.session_state.guardianNm = parent

# LOADS THE SCOUT NAME, ADDRESS, PARENT AND REWARD INFO
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

# SLOW
# for i,row in df.iterrows():
#     rowdat = json.dupmp
#     eu.esu.add_es_doc(es,indexnm='scouts', doc=row)



st.subheader('Submit a Cookie Order')
st.warning('Submit seperate orders for paper orders vs. Digital Cookie')
gsNm = st.selectbox("Girl Scount Name:",gs_nms,placeholder='Select your scout',key='gsNm',index=None, on_change=get_parent())
st.write(st.session_state.gsNm)

with stp.form('submit orders', clear_on_submit=True):
    appc1, appc2, appc3 = st.columns([3,.25,3])

    with appc1:
        # At this point the URL query string is empty / unchanged, even with data in the text field.
       
        ordType = stp.selectbox("Order Type:",options=['Digital Cookie','Paper Order'],key='ordType')
        guardianNm = stp.text_input("Guardian accountable for order",key='guardianNm', placeholder=st.session_state.guardianNm, max_chars=50)


    with appc3:
        PickupNm = stp.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
        PickupPh = stp.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)
        pickupT = stp.selectbox('Pickup Slot',['Tuesday 5-7','Wednesday 6-9'])

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
    if stp.form_submit_button("Submit Order to Cookie Crew"):
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
            "status": "Pending"
            }
        st.text(f'Total boxes in order = {total_boxes}  >  Total amount owed for order = ${order_amount} \n your pickup slot is: {pickupT}')        # get latest push of orders:
        # orders = get_my_data('orders')
        eu.esu.add_es_doc(es,indexnm="orders2024", doc=order_data)
        # vent['seq'] = Time.now.strftime('%Y%m%d%H%M%S%L').to_i  
        # orders.sort_values(by='OrderNumber',ascending=False,inplace=True,na_position='last')
        new_order = pd.DataFrame.from_dict(order_data, orient='index')
        st.table(new_order)

        # appendedOrders = pd.concat([orders,new_order])
        # st.write(appendedOrders.shape)

        # add_dat('orders',appendedOrders)
        # st.cache_data.clear()
        st.write(f"Your order has been submitted") #{form_data}")