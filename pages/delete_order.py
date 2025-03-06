from json import loads
import streamlit as st
import pandas as pd
import io
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from datetime import datetime    

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def main():
    es=get_connected()
    if not ss.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    st.subheader('Delete Order')

    gs_nms = [scout['fn'] for scout in ss['scout_dat']['scout_details']]
    # selection box can not default to none because the form defaults will fail. 
    gsNm = st.selectbox("Select Girl Scout:", gs_nms, key='gsNm') # index=noscouti, key='gsNm', on_change=update_session(gs_nms))
    selected_sct = [item for item in ss['scout_dat']['scout_details'] if item["fn"] == ss.gsNm][0]
    nmId = selected_sct['nameId']

    girl_order_qry = f'FROM {ss.indexes["index_orders"]}| WHERE scoutId LIKE """{nmId}""" | LIMIT 500'
    response = es.esql.query(
        query=girl_order_qry,
        format="csv")
    
    girl_orders = pd.read_csv(io.StringIO(response.body))
    deletable_orders = girl_orders[girl_orders['orderPickedup'] == False]
    deletable_orders.reindex()
    st.write('Deletable Orders (note orders that have been pickedup are not deleteable)')
    
    ss.deletable_orders = au.order_view(deletable_orders)
    st.write(ss.deletable_orders)

    ss.deletable_order_ids = ss.deletable_orders["Order Id"].tolist()
    ss.deletable_order_ids.sort()
    
    st.selectbox("Selet Order to Delete:", ss.deletable_order_ids, index=None,key='del_order')
    
    st.write(f'You have selected this order to delete: {ss.del_order}')
    
    
    # Button to trigger deletion
    if st.button("Delete Selected Order"):
        st.write(f'Deleting booth: {ss.del_order}')
        index_nm = ss.indexes['index_orders']
        if index_nm and ss.del_order:
            try:
                response = es.delete(index=index_nm, id=ss.del_order)
                st.success(f"Order {ss.del_order} deleted successfully!")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning(":-( something went wrong.  Contact Jennifer")

if __name__ == '__main__':

    setup.config_site(page_title="Booth Admin",initial_sidebar_state='expanded')
    # Initialization
    # init_ss()
    main()