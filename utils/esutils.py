from elasticsearch import Elasticsearch
from io import StringIO
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
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
        
        api_key= (st.secrets['general']['api_key_nm'],st.secrets['general']['api_key'])
        conn = Elasticsearch(
            hosts=[elastic_url],
            api_key=st.secrets['general']['api_key'],
            request_timeout=30
        )

        # Successful response!
        print(conn.info())
        return conn

    
    def add_es_doc(es,indexnm,id=None, doc=""):
        resp = es.index(index=indexnm, id=id, document=doc)
        # print(resp["result"])
        return resp
    
    def update_doc(es, indexnm, id, doc={}):
        resp = es.update_doc(indexnm=indexnm,id=id, doc=doc)
        return resp

    def get_dat(es, indexnm, field=None):
        sq1 = es.search(index = indexnm, query={"match_all": {}},size=60)
        print(f"There are {sq1['hits']['total']['value']} documents in the index {indexnm}\n")
        if field:
            fresp = sq1['hits']['hits']
            fresp = [n["_source"][field] for n in fresp]
        else:
            fresp=sq1['hits']['hits']

        return fresp
    

    def qry_sql(es,indexnm,fields=None,where=None):
        '''
        query = """
        SELECT scoutName, scoutId, amountReceived, amtReceived_dt
        FROM scouts_data
        WHERE amountReceived > 5000
        """

        # Execute the query
        response = es.esql.query(
            body={
                "query": query
            }
        )
        '''
        if where and fields:
            query = f"SELECT {fields} FROM {indexnm} where {where} | LIMIT 500"
            st.write(query)
            response = es.esql.query(
            query=f"SELECT {fields} FROM {indexnm} where {where} | LIMIT 500",
            format="csv",
        )
        elif fields and not where:
            response = es.esql.query(
            query=f"SELECT {fields} FROM {indexnm}| LIMIT 500",
            format="csv",
        )
        else:
            response = es.esql.query(
            query=f"FROM {indexnm} | LIMIT 500",
            format="csv",
        )
        df = pd.read_csv(StringIO(response.body))
        return df

    def get_qry_dat(es,indexnm,field=None,value=None):
        sq1 = es.search(index = indexnm, query={"match": {field: value}})
        qresp=sq1['hits']['hits']
        # st.table(qresp)
        return qresp
    
    def get_trm_qry_dat(es,indexnm, field, value):
        sq1 = es.search(index = indexnm, query={"match_phrase": {field: value}})
        qresp=sq1['hits']['hits']
        return qresp

    def get_arry_dat(es,indexnm, field=None):
        if field:
            sq1 = es.search(index = indexnm, source=field, query={"match_all":{}})
        else:
            sq1 = es.search(index = indexnm, query={"match_all":{}})
# class uts:
#     pass
#     return