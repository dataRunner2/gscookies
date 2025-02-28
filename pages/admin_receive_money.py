from json import loads
import streamlit as st
import pandas as pd
from io import StringIO
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
import datetime as dt
from streamlit_extras.row import row

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

    if 'all_scout_dat' not in ss:
        esu.get_all_scts(es)    

    admin_gs_nms = [scout['FullName'] for scout in ss.all_scout_dat]
    
    # selection box can not default to none because the form defaults will fail. 
    st.selectbox("Select Girl Scout:", options=admin_gs_nms, key='depst_sel_gsNm', index=None,  placeholder="Receive Money From... ")
    if ss.depst_sel_gsNm:
        selected_sct_dat = [item for item in ss['all_scout_dat'] if item["FullName"] == ss.depst_sel_gsNm][0]
        # st.write(selected_sct_dat)
        depst_sel_gsId = selected_sct_dat.get('nameId')
   
        # Total Deposits Made to date
        depst_money= esu.get_trm_qry_dat(es,ss.indexes['index_money'], 'scoutId', depst_sel_gsId)
        depst_money_amts = [float(order["_source"].get("amountReceived", 0)) for order in depst_money] # Extract the "amountReceived" field
        depst_money_tot = sum(depst_money_amts)
        st.write(f"Total amount already received': ${depst_money_tot}")

        # Get list of orders for paper orders
        depst_orders = esu.get_trm_qry_dat(es,ss.indexes['index_orders'], 'scoutId', depst_sel_gsId)
        # st.write(depst_orders)

        # Create a DataFrame from the _source
        depst_orders_df = pd.DataFrame([item["_source"] for item in depst_orders])
        # st.write(depst_orders_df)
        if not depst_orders_df.empty:
            # Convert 'amountReceived' to numeric (handling non-numeric values)
            depst_orders_df['orderAmount'] = pd.to_numeric(depst_orders_df['orderAmount'], errors='coerce')

            # Filter rows where 'orderType' contains 'Paper Order'
            filtered_df = depst_orders_df[depst_orders_df['orderType'].apply(lambda x: 'Paper Order' in x)]

            # Calculate the total sum of 'orderAmount' for filtered rows
            depst_orders_tot = filtered_df['orderAmount'].sum()

            st.write(f"Total due for sales: ${depst_orders_tot}")
            st.write(f"Amount outstanding for paper orders ${depst_orders_tot - depst_money_tot}")


        depst_orders_id = [order['_source']['orderId'] for order in depst_orders] or []
        
        with st.form("money", clear_on_submit=True):
            amt = st.text_input("Amount Received")
            amt_date = st.date_input("Date Received",value="today",format="MM/DD/YYYY")
            orderRef = st.multiselect("Order Reference (optional)",options=depst_orders_id)
            orderType = st.multiselect("Order Type",options=['Paper Order','Booth'])
            refComment = st.text_input("Ref. Comments")
            
            if st.form_submit_button("Submit Money to Cookie Crew"):
                now = dt.datetime.now()
                idTime = now.strftime("%m%d%Y%H%M")

                # Every form must have a submit button.
                moneyRec_data = {
                    "scoutName": ss.depst_sel_gsNm,
                    "scoutId": depst_sel_gsId,
                    "amountReceived": amt,
                    "amtReceived_dt": amt_date,
                    "orderRef": orderRef,
                    "orderType": orderType,
                    "refComment": refComment
                    }

                esu.add_es_doc(es,indexnm=ss.indexes['index_money'], id=None, doc=moneyRec_data)
                st.toast("Database updated with changes")

if __name__ == '__main__':

    setup.config_site(page_title="Receive Money", initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()
