from elasticsearch import Elasticsearch
from io import StringIO
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import json
import io
import os
environment = os.getenv('ENV')

class esu:
    def conn_es():
        # Found in the 'Manage Deployment' page
        elastic_url = 'https://gs-cookies-2025-c01bb8.es.us-east-1.aws.elastic.cloud:443'
        # Less common way to connect
        # CLOUD_ID = "GS_Cookies_2025:dXM...
        
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
    
    def get_all_scts(es):
        all_scout_qrydat = es.search(index = ss.indexes['index_scouts'], size=100, source='scout_details', query={"nested": {"path": "scout_details", "query": {"match_all":{} }}})['hits']['hits']
        all_scout_dat = [sct['_source'].get('scout_details') for sct in all_scout_qrydat if sct['_source'].get('scout_details') is not None]
        ss.all_scout_dat = [entry for sublist in all_scout_dat for entry in sublist].copy()

    def get_scouts(es):
        """
        This function gets the scouts name and scountId
        """
        scout_list_qry = f'FROM {ss.indexes["index_scout"]}'
        # Amount Received
        response = es.esql.query(
            query=scout_list_qry,
            format="csv")
        scout_list =  pd.read_csv(io.StringIO(response.body))
        return scout_list

    def get_all_orders(es):
        all_orders_qry = f"FROM {ss.indexes['index_orders']} | LIMIT 1000"
        # st.write(girl_order_qry)
        response = es.esql.query(
            query=all_orders_qry,
            format="csv")
        
        all_orders = pd.read_csv(StringIO(response.body))

        ss.all_orders = all_orders
        return all_orders
    
    def get_booth_orders(es):
        all_orders_qry = f"""FROM {ss.indexes['index_orders']} | WHERE orderType == "Booth" | LIMIT 1000"""
        # st.write(girl_order_qry)
        response = es.esql.query(
            query=all_orders_qry,
            format="csv")
        
        booth_orders = pd.read_csv(StringIO(response.body))

        ss.booth_orders = booth_orders
        return booth_orders


    def get_sum_agg_orders(es):
        agg_query = {
            "size": 0,
            "aggs": {
                "scouts": {
                    "terms": {"field": "scoutId.keyword", "size": 100},
                    "aggs": {
                        "order_types": {
                            "terms": {"field": "orderType.keyword", "size": 10},
                            "aggs": {
                                "adv": {"sum": {"field": "adv"}},
                                "lmup": {"sum": {"field": "LmUp"}},
                                "tre": {"sum": {"field": "tre"}},
                                "dsd": {"sum": {"field": "DSD"}},
                                "sam": {"sum": {"field": "sam"}},
                                "tags": {"sum": {"field": "Tags"}},
                                "tmint": {"sum": {"field": "Tmint"}},
                                "smr": {"sum": {"field": "Smr"}},
                                "toff": {"sum": {"field": "Toff"}},
                                "opc": {"sum": {"field": "OpC"}},
                                "qty": {"sum": {"field": "orderQtyBoxes"}},
                            }
                        }
                    }
                }
            }
        }
       
        response = es.search(index = ss.indexes['index_orders'], body=agg_query)
        if response:
            agg_dat = response["aggregations"]["scouts"]["buckets"]

        data = []
        for scout in agg_dat:
            scout_name = scout["key"]
            
            for order in scout["order_types"]["buckets"]:
                order_type = order["key"]
                data.append({
                    "scoutId": scout_name,
                    "orderType": order_type,
                    "ADV": order["adv"]["value"],
                    "LmUp": order["lmup"]["value"],
                    "TRE": order["tre"]["value"],
                    "DSD": order["dsd"]["value"],
                    "SAM": order["sam"]["value"],
                    "TAGS": order["tags"]["value"],
                    "TMINT": order["tmint"]["value"],
                    "SMR": order["smr"]["value"],
                    "TOFF": order["toff"]["value"],
                    "OPC": order["opc"]["value"],
                    "QTY": order["qty"]["value"]
                })

        # Convert to DataFrame
        agg_data = pd.DataFrame(data)

        return agg_data

    def get_sum_agg_money(es):
        # Get the Sum of the amount received per scout
        girl_money_agg = {
            "size": 0,
            "aggs": {
                "scouts": {
                    "terms": {"field": "scoutId.keyword", "size": 100},
                    "aggs": {                
                        "amountReceived": {"sum": {"field": "amountReceived"}}
                    }
                }
            }
        }
       
        response = es.search(index = ss.indexes['index_money'], body=girl_money_agg)
        
        if response:
            # Normalize the JSON response into a DataFrame
            agg_dat = pd.json_normalize(response["aggregations"]["scouts"]["buckets"], sep="_")
            # Dynamically rename columns to remove '_value'
            agg_dat.columns = [col.replace(".value", "") for col in agg_dat.columns]

        return agg_dat
    
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