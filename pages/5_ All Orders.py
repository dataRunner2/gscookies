from utils import esutils as eu
import streamlit as st
import os
import eland as ed
from json import loads
from utils.esutils import esu
from utils.esutils import uts

es = esu.conn_es()


orders = ed.DataFrame(es, es_index_pattern="orders2024")
orders = ed.eland_to_pandas(orders)
orders.reset_index(inplace=True, names='docId')
# orders.set_index(keys=['appName'],inplace=True)
ordersDF = loads(orders.to_json(orient='index'))
ds_app_names = list(ordersDF.keys())

st.dataframe(orders)

# ds_team_query = {
#     "match": {"department4": "Data Sciences - 5760"}
# }
# ds_people_results = es.search(index="m365_auto", query=ds_team_query, size=30,sort="_score")['hits']['hits']
# ds_people, ds_scores = zip(*[(n["_source"]["displayName"], n["_score"]) for n in ds_people_results])
# ds_people = list(ds_people)
# ds_scores = list(ds_scores)
# # st.write(type(ds_people),list(ds_people),ds_scores)
# ds_peop_df = pd.DataFrame({'person': ds_people,'score':ds_scores})
