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


def get_all_scts(es):
    all_scout_qrydat = es.search(index = ss.indexes['index_scouts'], source='scout_details', query={"match_all":{}})['hits']['hits']
    all_scout_dat = [sct['_source'].get('scout_details') for sct in all_scout_qrydat if sct['_source'].get('scout_details') is not None]
    ss.all_scout_dat = [entry for sublist in all_scout_dat for entry in sublist].copy()


def main():
    es = get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    if 'all_scout_dat' not in ss:
        get_all_scts(es)

    st.header('All Orders to Date')
    all_orders_dat = au.get_all_orders(es)
    all_orders_viewer = au.order_view(all_orders_dat)

    start_dat = all_orders_cln.copy()

    with st.expander('Filter'):
        edited_content = au.filter_dataframe(all_orders_cln)

    with st.form("data_editor_form"):
        edited_dat = st.data_editor(
            all_orders_viewer, key='edited_dat', 
            width=1500, use_container_width=False, num_rows="fixed",
            column_config={
            'id': st.column_config.Column(
                width='small',
            ),
            'status': st.column_config.Column(
                width='small'
            ),
            "inEbudde": st.column_config.CheckboxColumn(
                "Ebudde Ver",
                help="Has this order been added to Ebudde",
                width='small',
                disabled=False
            ),
            "digC_val": st.column_config.CheckboxColumn(
                "Validated in Digital Cookie?",
                width='small',
            )
        }
        )
        # st.write(start_dat)
        submit_button = st.form_submit_button("Save Updates")

    # USE DEV index to test this - make sure it's only affecting the rows I think itis
    # if not ss.start_dat.equals(edited_dat):
    #     st.write('start data is Not equal to edited')
    #     ss.start_dat = edited_dat
    #     ss.start_dat.loc[,'Qty'] = ss.start_dat['Adv'] + ss.start_dat['LmUp'] 
    #     # st.write(ss.start_dat)
    #     rr()
        

    if submit_button:
        st.session_state["refresh"] = True
        try:
            # Write to database
            au.update_es(edited_dat, edited_content)
            # time.sleep(1)
            # Refresh data from Elastic
            all_orders, all_orders_cln = au.get_all_orders(es)
        except:
            st.warning("Error updating Elastic")
            st.write(st.session_state['edited_dat'])

if __name__ == '__main__':

    setup.config_site(page_title="Admin Cookie Management")
    # Initialization
    init_ss()

    main()