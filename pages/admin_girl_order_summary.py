from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import io
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
    st.rerun()

def main():
    es=get_connected()
    if not ss.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        
    # st.button('Refresh',on_click=refresh())
    gs_nms = [scout['fn'] for scout in ss['scout_dat']['scout_details']]
    

    # selection box can not default to none because the form defaults will fail. 
    gsNm = st.selectbox("Select Girl Scout:", gs_nms, key='gsNm') # index=noscouti, key='gsNm', on_change=update_session(gs_nms))
    # st.write(ss['scout_dat']['scout_details'])
    selected_sct = [item for item in ss['scout_dat']['scout_details'] if item["fn"] == ss.gsNm][0]
    # st.write(selected_sct)
    nmId = selected_sct['nameId']
    
    st.markdown(f"{ss.gsNm} Order Summary")
    girl_order_qry = f'FROM {ss.indexes["index_orders"]}| WHERE scoutId LIKE """{nmId}""" | LIMIT 500'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=girl_order_qry,
        format="csv")
    girl_orders = pd.read_csv(io.StringIO(response.body))

    
    girl_orders = au.order_view(girl_orders)
    girl_orders.reset_index(inplace=True, drop=True)
    girl_orders.fillna(0)
    girl_ord_md=girl_orders[['Order Id','Order Type','Date','Status','Comments']]

    just_cookies = girl_orders[['Adventurefuls','Lemon-Ups','Trefoils','Do-Si-Do','Samoas',"S'Mores",'Tagalongs','Thin Mint','Toffee Tastic','OpC','Qty','Amt']]
    # just_cookies['Qty']= just_cookies.sum(axis=1)
    # just_cookies['Amt']=just_cookies['Qty']*6
    col = just_cookies.pop('Qty')
    just_cookies.insert(0, col.name, col)
    col = just_cookies.pop('Amt')
    just_cookies.insert(0, col.name, col)
    cookie_orders = pd.concat([girl_ord_md, just_cookies], axis=1)

    st.write("Paper Orders")
    paper_orders = cookie_orders[cookie_orders['Order Type']=='Paper Order'].copy()
    paper_orders.loc['Total']= paper_orders.sum(numeric_only=True, axis=0)
    paper_orders = paper_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})

    st.dataframe(paper_orders.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))), use_container_width=True,
                column_config={
                    "Amount": st.column_config.NumberColumn(
                        "Amt.",
                        format="$%d",
                    ),
                    "Date": st.column_config.DateColumn(
                        "Order Date",
                        format="MM-DD-YY",
                    )})
    total_due_po = paper_orders.loc['Total','Amt']

    st.write("Digital Orders")
    digital_orders = cookie_orders[cookie_orders['Order Type']=='Digital Cookie Girl Delivery'].copy()
    digital_orders.loc['Total']= digital_orders.sum(numeric_only=True, axis=0)
    digital_orders = digital_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
    st.dataframe(digital_orders.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))), use_container_width=True,
                column_config={
                    "Amt": st.column_config.NumberColumn(
                        "Order Amt.",
                        format="$%d",
                    )})

    tot_boxes_pending = cookie_orders[cookie_orders['Status']=='Pending'].copy()
    tot_boxes_pending = tot_boxes_pending[['Status','Qty']]
    tot_boxes_pending.loc['Total']= tot_boxes_pending.sum(numeric_only=True, axis=0)
    total_pending = tot_boxes_pending.loc['Total','Qty'].astype('int')

    tot_boxes_ready = cookie_orders[cookie_orders['Status']=='Order Ready for Pickup'].copy()
    tot_boxes_ready = tot_boxes_ready[['Status','Qty']]
    tot_boxes_ready.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
    total_ready = tot_boxes_ready.loc['Total','Qty'].astype('int')

    tot_boxes = girl_orders[girl_orders['Status']=='Order Ready for Pickup'].copy()
    tot_boxes = girl_orders[['Status','Qty']]
    tot_boxes.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
    total_boxes = tot_boxes_ready.loc['Total','Qty'].astype('int')

    total_boxes_ordered = cookie_orders[['Qty','Amt']].sum(numeric_only=True)

    # Summary of Funds Received
    st.write('Funds Deposited')
    depst_received = esu.get_trm_qry_dat(es,ss.indexes['index_money'], 'scoutId', nmId)
    girl_money_qry = f'FROM {ss.indexes["index_money"]}| WHERE scoutId LIKE """{nmId}""" | LIMIT 500'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=girl_money_qry,
        format="csv")
    girl_money = pd.read_csv(io.StringIO(response.body))

    if depst_received:
        depst_received = [order['_source'] for order in depst_received]
        deposits_received_df = pd.DataFrame(depst_received)
        st.write(deposits_received_df)
    else:
        deposits_received_df = pd.DataFrame({'amountReceived': [0]})

    st.subheader('Summary')
    mc1, mc2,mc3,mc4,mc5 = st.columns([2,2,2,2,2])
    if len(deposits_received_df).is_integer:
        # st.write(dtype(girl_money['AmountReceived']))
        deposits_received_df["amountReceived"] = pd.to_numeric(deposits_received_df["amountReceived"])
        sum_money = deposits_received_df['amountReceived'].sum()
        with mc1: st.metric(label="Total Boxes",value=total_boxes_ordered.iloc[0])
        with mc2: st.metric(label="Total Amt Due",value=f"${total_boxes_ordered.iloc[1]}")
        with mc3: st.metric(label="Total Amount Received", value=f"${sum_money}")
        with mc4: st.metric(label="Total Amount Owed", value=f"${total_boxes_ordered.iloc[1] - sum_money}")

        with mc2: st.metric(label="Total Due for Paper Orders", value=f"${total_due_po}")
        with mc3: st.metric(label='Pending Boxes', value=total_pending)
        with mc4: st.metric(label='Boxes Ready for Pickup', value=total_ready)
        # st.metric(label="Total Amount Due for Paper Orders", value=f"${paper_money_due}")

    st.subheader("Payments Received - EXCLUDE DIGITAL COOKIE PAYMENTS")
    # if len(dpst_qry['_source']> 0):
    #     girl_money.sort_values(by="amtReceived_dt")
    #     girl_money.rename(inplace=True, columns={'scoutName': 'Scouts Name','amountReceived':'Amount Received','amtReceived_dt': 'Date Money Received','orderRef':'Money Reference Note'})
    #     girl_money.reset_index(inplace=True, drop=True)
    #     st.dataframe(girl_money,use_container_width=False)

if __name__ == '__main__':

    setup.config_site(page_title="Admin Girl Order Summary",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()