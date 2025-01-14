from elasticsearch import Elasticsearch
import streamlit as st
import json
import os
environment = os.getenv('ENV')

# elastic_url = 'https://gs-cookies-2025-c01bb8.es.us-east-1.aws.elastic.cloud:443'
# api_key = ("urMz1PyBTveamanICpHGzg", "YUlpbFRaUUJtOE9UV2U2SlpKYnE6dXJNejFQeUJUdmVhbWFuSUNwSEd6Zw==")

# es = Elasticsearch(
#     hosts=[elastic_url],  # Replace with your Elasticsearch server URL
#     api_key=api_key,  # Add if authentication is required
#     request_timeout=30  # Optional: Adjust timeout (in seconds) if needed
# )

class esu:
    def conn_es():
        # Found in the 'Manage Deployment' page
        elastic_url = 'https://gs-cookies-2025-c01bb8.es.us-east-1.aws.elastic.cloud:443'
        # Less common way to connect
        # CLOUD_ID = "GS_Cookies_2025:dXMtZWFzdC0xLmF3cy5lbGFzdGljLmNsb3VkJGMwMWJiODZkOTI4YzQ3NGVhYjdjZmNjNWY2YzNmMzZjLmVzJGMwMWJiODZkOTI4YzQ3NGVhYjdjZmNjNWY2YzNmMzZjLmti"

        api_key= (os.getenv('api_key_nm'),os.getenv('api_key'))
        conn = Elasticsearch(
            hosts=[elastic_url],
            api_key=os.getenv('api_key'),
            request_timeout=30
        )

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

# class uts:
#     pass
#     return