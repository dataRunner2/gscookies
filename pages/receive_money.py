from json import loads
import streamlit as st
import pandas as pd
import sys
from io import StringIO
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
import datetime as dt
from itertools import chain

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es


def main():
    es = get_connected()
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        

    qry_all_nms = esu.qry_sql(es,ss.indexes['index_scouts'])
    parent_sel_gsNm = st.selectbox("Receive Money from:", qry_all_nms['parent_FullName'],placeholder='Select Parents Name')
    st.write(parent_sel_gsNm)
    all_qry_dat = esu.get_trm_qry_dat(es,indexnm=ss.indexes['index_scouts'], field='parent_FullName.keyword', value=parent_sel_gsNm)
    all_scouts = []
    if len(all_qry_dat)> 0:
        parent_qry=all_qry_dat[0]['_source']
        parent_scouts_nms = {scout['fn']:scout['nameId'] for scout in parent_qry.get('scout_details')}


    # # Select scout to receive money from
    depst_sel_gsNm = st.selectbox("Receive Money from:", parent_scouts_nms.keys())
    
    depst_sel_gsId = parent_scouts_nms.get(depst_sel_gsNm)
    depst_orders = esu.get_trm_qry_dat(es,ss.indexes['index_orders'], 'scoutId', depst_sel_gsId)
    depst_orders_id = [order['_source']['orderId'] for order in depst_orders]
    
    with st.form("money", clear_on_submit=True):
        amt = st.text_input("Amount Received")
        amt_date = st.date_input("Date Received",value="today",format="MM/DD/YYYY")
        orderRef = st.multiselect("Order Reference (optional)",options=depst_orders_id)
        orderType = st.multiselect("Order Type",options=['Paper Order','Digital Cookie'])
        
        if st.form_submit_button("Submit Money to Cookie Crew"):
            now = dt.datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")

            # Every form must have a submit button.
            moneyRec_data = {
                "scoutName": depst_sel_gsNm,
                "scoutId": depst_sel_gsId,
                "amountReceived": amt,
                "amtReceived_dt": amt_date,
                "orderRef": orderRef,
                "orderType": orderType
                }

            esu.add_es_doc(es,indexnm=ss.indexes['index_money'], id=None, doc=moneyRec_data)
            st.toast("Database updated with changes")

if __name__ == '__main__':

    setup.config_site(page_title="Receive Money")
    # Initialization
    init_ss()

    main()
