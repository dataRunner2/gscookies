from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
import datetime

def init_ss():
    pass


def main():
    noscouti=gs_nms.index('zz scout not selected')
    if 'gsNm' not in ss:
        st.session_state['gsNm'] = gs_nms[noscouti]
        update_session(gs_nms)
        rr()
    noscout = gs_nms[noscouti]

    st.header("Receive Money")
    st.write('----')
    gsNm = st.selectbox("Receive Money from (scount):", gs_nms, index=noscouti, key='gsNm', on_change=update_session(gs_nms))
    st.write(gsNm)
    with st.form("money", clear_on_submit=True):
        amt = st.text_input("Amount Received")
        amt_date = st.date_input("Date Received",value="today",format="MM/DD/YYYY")
        orderRef = st.text_input("Order Reference (optional)")
        # from orders get all for this scout:
        # orderId = (f'{st.session_state["scout_dat"]["Concat"].replace(" ","").replace(".","_").lower()}{idTime}')

        if st.form_submit_button("Submit Money to Cookie Crew"):
            now = datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")

            # Every form must have a submit button.
            moneyRec_data = {
                "ScoutName": st.session_state["scout_dat"]["FullName"],
                "AmountReceived": amt,
                "amtReceived_dt": amt_date,
                "orderRef": orderRef
                }

            esu.add_es_doc(es,indexnm=ss.index_money, id=None, doc=moneyRec_data)
            st.toast("Database updated with changes")

if __name__ == '__main__':

    setup.config_site(page_title="Receive Money")
    # Initialization
    init_ss()

    main()
