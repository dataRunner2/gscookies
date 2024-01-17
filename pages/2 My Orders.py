from json import loads
import streamlit as st
import streamlit_permalink as stp
from typing import List, Tuple
import pandas as pd
import elasticsearch
import sys
from pathlib import Path
# from PIL import Image
import os
from utils import esutils as eu
import eland as ed

if 'gsNm' not in st.session_state:
    st.session_state['gsNm'] = 'value'

es = eu.esu.conn_es()
gs_nms = eu.esu.get_dat(es,"scouts", "FullName")

def get_qry_dat(es,indexnm="orders",field=None,value=None):
        if not value:
              value = st.session_state.gsNm
        sq1 = es.search(index = indexnm, query={"match": {field: value}})
        qresp=sq1['hits']['hits']
        st.table(qresp)
        return qresp

def prt_sel():
    print(st.session_state.gsNm)

gsNm = st.selectbox("Girl Scount Name:",gs_nms,index=None,placeholder='Select your scout',key='gsNm',on_change=prt_sel())


girl_orders = ed.DataFrame(es, es_index_pattern="orders2024")
girl_orders = ed.eland_to_pandas(girl_orders)
girl_orders.reset_index(inplace=True, names='docId')
girl_orders = girl_orders[girl_orders['ScoutName'] == gsNm]
# orders.set_index(keys=['appName'],inplace=True)

# girl_orders = get_qry_dat(es,"orders2024",field='ScoutName',value=gsNm)
st.table(girl_orders)