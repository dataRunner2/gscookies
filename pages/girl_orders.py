from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import time
from typing import List, Tuple
import pandas as pd
import random
from pathlib import Path
from streamlit_extras.let_it_rain import rain

import os
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3

def init_ss():
    pass

# @st.cache_data
def get_connected():
    es = esu.conn_es()
    return es

def refresh():
    # st.rerun()
    pass

def example():
    rain(
        emoji="🎈",
        font_size=54,
        falling_speed=5,
        animation_length="infinite",
    )

def main():
    es=get_connected()
    if not ss.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        
    gs_nms = [scout['fn'] for scout in ss['scout_dat']['scout_details']]
    # st.write(ss['scout_dat'])

    # selection box can not default to none because the form defaults will fail. 
    gsNm = st.selectbox("Select Girl Scout:", gs_nms, key='gsNm') # index=noscouti, key='gsNm', on_change=update_session(gs_nms))
    # st.write(ss['scout_dat']['scout_details'])
    selected_sct = [item for item in ss['scout_dat']['scout_details'] if item["fn"] == gsNm][0]
    # st.write(selected_sct)
    nmId = selected_sct['nameId']
    


    st.markdown(f"Ready to submit a Cookie Order for **{gsNm}**")

    with st.form('submit orders', clear_on_submit=True):
        appc1, appc2, appc3 = st.columns([3,.25,3])
        guardianNm = st.write(f"Guardian accountable for order: {ss['scout_dat']['parent_FullName']}")
        with appc1:
            # At this point the URL query string is empty / unchanged, even with data in the text field.
            ordType = st.selectbox("Order Type (Submit seperate orders for paper orders vs. Digital Cookie):",options=['Digital Cookie Girl Delivery','Paper Order'],key='ordType')
            # pickupT = st.selectbox('Pickup Slot', ['Tues Feb 27 9-12','Wed Feb 28 10-4:30','Thurs Feb 29 10am-5:30pm','Fri Mar 1 10am-8:30pm','Sat Mar 2 10am-4:30pm','Mon Mar 4 10am-4:30pm','Tues Mar 5 10am-4:30pm','Mon Mar 6 10am-4:30pm','Mon Mar 7 10am-8:30pm'])

        with appc3:
            PickupNm = st.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
            PickupPh = st.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)

        st.write('----')
        ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])

        with ck1:
            advf=st.number_input(label='Adventurefuls',step=1,min_value=-5, value=0)
            tags=st.number_input(label='Tagalongs',step=1,min_value=-5, value=0)

        with ck2:
            lmup=st.number_input(label='Lemon-Ups',step=1,min_value=-5, value=0)
            tmint=st.number_input(label='Thin Mints',step=1,min_value=-5, value=0)

        with ck3:
            tre=st.number_input(label='Trefoils',step=1,min_value=-5, value=0)
            smr=st.number_input(label="S'Mores",step=1,min_value=-5, value=0)

        with ck4:
            dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=-5, value=0)
            toff=st.number_input(label='Toffee-Tastic',step=1,min_value=-5, value=0)

        with ck5:
            sam=st.number_input(label='Samoas',step=1,min_value=-5, value=0)
            opc=st.number_input(label='Operation Cookie Drop',step=1,min_value=-5, value=0)

        comments = st.text_area("Use this field to identify which order(s) in your records these cookies fulfill", key='comments')


        # submitted = st.form_submit_button()
        if st.form_submit_button("Submit Order to Cookie Crew"):
            total_boxes, order_amount=au.calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
            now = datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")
            # st.write(idTime)
            orderId = (f'{nmId}_{idTime}')
            # Every form must have a submit button.
            order_data = {
                "scoutId":nmId,
                "scoutName": selected_sct["FullName"],
                "orderType": ordType,
                "guardianNm": ss['scout_dat']["parent_FullName"],
                "guardianPh": ss['scout_dat']["parent_phone"],
                "email": ss['scout_dat']["parent_email"],
                "pickupNm": PickupNm,
                "pickupPh": PickupPh,
                # "pickupTm": pickupT ,
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
                "orderQtyBoxes": total_boxes,
                "orderAmount": order_amount,
                "submit_dt": datetime.now(),
                "comments": comments,
                "status": "Pending",
                "orderId": orderId,
                "digC_val": False,
                "addEbudde": False,
                "orderPickedup": False,
                "orderReady": False
                }
            
            esu.add_es_doc(es,indexnm=ss.indexes['index_orders'], id=orderId, doc=order_data)

            st.warning(f" {total_boxes} boxes were submitted\n Total amount owed for order = ${order_amount} \n \n your order id is {orderId}")        # get latest push of orders:                

            k=order_data.keys()
            v=order_data.values()
            # st.write(k)
            # new_order = [f"{k}:[{i}]" for k,i in zip(order_data.keys(),order_data.values())]
            order_details = pd.DataFrame(v, index =k, columns =['Order'])
            new_order = au.order_view(order_details.T)
            st.table(new_order.T)
            st.success('Your order has been submitted!', icon="✅")
            st.balloons()

if __name__ == '__main__':

    setup.config_site(page_title="Order Cookies",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()