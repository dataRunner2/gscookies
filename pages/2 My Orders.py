# from json import loads
# import streamlit as st
# import streamlit_permalink as stp
# from typing import List, Tuple
# import pandas as pd
# import elasticsearch
# import sys
# from pathlib import Path
# # from PIL import Image
# import os
# from utils.esutils import esu
# from utils.esutils import uts
# import eland as ed


# es = esu.conn_es()
# gs_nms = esu.get_dat(es,"scouts", "FullName")


# st.subheader(f'{st.session_state["gsNm"]} Cookie Orders')

# scout_dat = esu.get_qry_dat(es,indexnm="scouts",field='FullName',value=st.session_state.gsNm)

# with st.sidebar:  
#     st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout',key='gsNm', on_change=uts.get_parent(scout_dat))

# st.session_state
# def get_qry_dat(es,indexnm="orders",field=None,value=None):
#         if not value:
#               value = st.session_state.gsNm
#         sq1 = es.search(index = indexnm, query={"match": {field: value}})
#         qresp=sq1['hits']['hits']
#         st.table(qresp)
#         return qresp

# girl_orders = ed.DataFrame(es, es_index_pattern="orders2024")
# girl_orders = ed.eland_to_pandas(girl_orders)
# girl_orders.reset_index(inplace=True, names='docId')
# girl_orders = girl_orders[girl_orders['ScoutName'] == st.session_state["gsNm"]]
# # orders.set_index(keys=['appName'],inplace=True)

# # girl_orders = get_qry_dat(es,"orders2024",field='ScoutName',value=gsNm)
# st.table(girl_orders)