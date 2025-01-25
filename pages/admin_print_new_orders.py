from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def main():
    st.write('----')
    es =  get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        
    st.warning('page in-work')
    st.header('All Orders to Date')
    st.warning('split table per scout')
    
    pull_orders = au.get_all_orders(es)
    pull_cln = au.allorder_view(pull_orders)

    # all_orders_cln.fillna(0)
    # pull_cln = pull_cln.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
    pull_cln = pull_cln[pull_cln['orderPickedup'] == False]

    pull_cln=pull_cln.loc[:, ['Scout','orderType','Date','Qty', 'Amt','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','pickupNm','pickupPh','status']]
    # pull_cln.rename(inplace=True, columns={'ScoutName': 'Scout','submit_dt':"Date",'order_qty_boxes':'Qty','order_amount':'Amt'})
    # pull_cln = pull_cln.astype({"Amt": 'int', "Qty": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})

    pull_cln.loc['Total']= pull_cln.sum(numeric_only=True, axis=0)
    with st.expander('Filter'):
        order_content = au.filter_dataframe(pull_cln)
    st.dataframe(order_content, use_container_width=True, hide_index=True,
                    column_config={
                    "Amt": st.column_config.NumberColumn(
                        format="$%d",
                        width='small'
                    ),
                    "Date": st.column_config.DateColumn(
                        format="MM-DD-YY",
                    )})
    st.write('')
    st.write('Pickup Signature: __________________')
    st.write('----')
    st.dataframe(order_content, use_container_width=True, hide_index=True,
                    column_config={
                    "Amt": st.column_config.NumberColumn(
                        format="$%d",
                        width='small'
                    ),
                    "Date": st.column_config.DateColumn(
                        format="MM-DD-YY",
                    )})
    st.write('Reminder - All funds due back to us by 3/19 at Noon')


if __name__ == '__main__':

    setup.config_site(page_title="Print Orders")
    # Initialization
    init_ss()

    main()