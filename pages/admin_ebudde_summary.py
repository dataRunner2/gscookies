from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import json
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3
from elasticsearch.helpers import bulk

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def alternate_rows(df):
        return ['background-color:#f2f2f2' if i %2 !=0 else '' for i in range(len(df))]
    
def main():
    es = get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    # Get Money Data
    all_money_agg = esu.get_sum_agg_money(es)
    all_money_agg.drop(columns=['doc_count'],inplace=True)
    all_money_agg.rename(columns={'key':'scoutId','amountReceived_value':'AmtReceived'},inplace=True)
    all_money_agg['orderType'] = 'Paper Order'

    ### Get Order Data
    all_orders_dat = esu.get_sum_agg_orders(es)

    row1 = st.columns(4)
    with row1[0]:
        orderType_filter = st.multiselect("Filter by orderType:", options=all_orders_dat["orderType"].unique())
    if orderType_filter:
        all_orders_dat = all_orders_dat[all_orders_dat["orderType"].isin(orderType_filter)]
    all_orders_dat['TotalAmt'] = [6*qty if ordert == "Paper Order" else 0 for qty, ordert in zip(all_orders_dat['QTY'],all_orders_dat['orderType'])]
    
    order_money_df = pd.merge(left= all_orders_dat, right=all_money_agg, how='left', on=['scoutId','orderType'])
    order_money_df.fillna(0,inplace=True)
    order_money_df = order_money_df.applymap(lambda x: f"{int(x)}" if isinstance(x, (int, float)) else x)
    order_money_df =order_money_df.astype({"TotalAmt":"int","AmtReceived":"int"})
    order_money_df['balance'] = [total - rec for total, rec in zip(order_money_df['TotalAmt'],order_money_df['AmtReceived']) ]
    order_money_df = order_money_df.sort_values(by='scoutId')
    order_money_df['Nm'] = order_money_df['scoutId']
    order_money_df.reset_index(drop=True, inplace=True)

    # shade every other row
    styled_df = order_money_df.style.apply(alternate_rows, axis=0)
    st.dataframe(styled_df, height=900,use_container_width=True)

if __name__ == '__main__':

    setup.config_site(page_title="Admin Ebudde Summary",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()