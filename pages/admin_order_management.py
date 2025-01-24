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
    es = get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    st.header('All Orders to Date')
    all_orders, all_orders_cln = au.get_all_orders(es)

    start_dat = all_orders_cln.copy()

    # response = es.esql.query(
    #     query="""
    #     FROM employees
    #     | STATS count = COUNT(emp_no) BY languages
    #     | WHERE languages >= (?)
    #     | SORT languages
    #     | LIMIT 500
    #     """,
    #     format="csv",
    #     params=[3],
    # )
    # df = pd.read_csv(
    #     StringIO(response.body),
    #     dtype={"count": "Int64", "languages": "Int64"},
    # )
    # print(df)
    # start_dat = start_dat[start_dat['Scout'].str.contains('zz scout not selected')==False]
    # start_dat.sort_values(by=['orderType','Date','Scout'],ascending=[False, False, False],inplace=True)

    # if 'start_dat' not in ss:
    #     ss.start_dat = pd.DataFrame(start_dat)
    #     ss.start_dat['Adv'] = pd.to_numeric(ss.start_dat['Adv'], errors='coerce').astype('Int')
    #     ss.start_dat['LmUp'] = pd.to_numeric(ss.start_dat['LmUp'], errors='coerce').astype('Int')

    with st.expander('Filter'):
        edited_content = au.filter_dataframe(all_orders_cln)

    with st.form("data_editor_form"):

        edited_dat = st.data_editor(
            edited_content, key='edited_dat', 
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