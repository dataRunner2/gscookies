from elasticsearch import Elasticsearch
import streamlit as st


class esu:
    def conn_es():
        # Found in the 'Manage Deployment' page
        CLOUD_ID = "Cookies2024Trp43202:dXMtd2VzdDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyQ0ZGY4YWU4MTJiN2Y0MmQyODIwMjA0OThmNzAxNGE2ZiRlNWM0MTBjNTNlYTg0ODlkOTViYTMxNjVjNGI2ZDM0MA=="
        # if environment in (None,'local'):
        api_key = st.secrets["es_key"]
        conn = Elasticsearch(cloud_id=CLOUD_ID, api_key=api_key)

        # Successful response!
        print(conn.info())
        return conn

    def add_es_doc(es,indexnm,id=None, doc=""):
        resp = es.index(index=indexnm, id=id, document=doc)
        # print(resp["result"])
    
    def get_dat(es, indexnm, field=None):
        sq1 = es.search(index = indexnm, query={"match_all": {}},size=60)
        print(f"There are {sq1['hits']['total']['value']} documents in the index {indexnm}\n")
        if field:
            fresp = sq1['hits']['hits']
            fresp = [n["_source"][field] for n in fresp]
        else:
            fresp=sq1['hits']['hits']
        return fresp
    
    def get_qry_dat(es,indexnm="orders",field=None,value=None):
        if not value:
              value = st.session_state.gsNm
        sq1 = es.search(index = indexnm, query={"match": {field: value}})
        qresp=sq1['hits']['hits']
        # st.table(qresp)
        return qresp

class uts:
    def get_parent():
        es = esu.conn_es()
        scout_dat = esu.get_qry_dat(es,indexnm="scouts",field='FullName',value=st.session_state["gsNm"])
        if len(scout_dat) > 0:
            parent = scout_dat[0]['_source']['Parent']
            st.session_state["guardianNm"] = parent
        return