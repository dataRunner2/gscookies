from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import json
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3
from elasticsearch.helpers import bulk

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

# Check if orderId exists in Elasticsearch
def order_exists(es, index_nm, order_id):
    query = {"query": {"term": {"orderId": order_id}}}
    response = es.search(index=index_nm, body=query)
    return response["hits"]["total"]["value"] > 0

def main():
    es = get_connected()
    # Connect to Elasticsearch
    index_nm = 'orders_DOC' #ss.indexes['index_orders'] # "orders2025"

    # Load the cleaned DataFrame (df_final) here
    file_path = "your_excel_file.xlsx"
    df = pd.read_excel(file_path, skiprows=4)
    df = df.iloc[1:].reset_index(drop=True)

    # Create necessary fields by column
    df["scoutId"] = df["First Name"].str[:3] + df["Last Name"]
    df["scoutName"] = df["First Name"] + " " + df["Last Name"]
    df["orderType"] = df["Type"]
    df["orderId"] = df["First Name"].str[:3] + df["Last Name"] +  "_" +df["Order #"].astype(str)
    df["orderQtyBoxes"] = df["Total Pkgs"].astype(int)
    df["orderAmount"] = df["Total Sales"].astype(float)
    df["submit_dt"] = df["Date"]
    df["status"] = "Pending"
    df["digC_val"] = False
    df["addEbudde"] = False
    df["orderPickedup"] = False
    df["orderReady"] = False
    df["initialOrder"] = True
    df["orderPaid"] = True
    df["DSD"] = df["D-S-D"]
    df["OpC"] = df['Donated']

    columns_to_keep = [
        "scoutId", "scoutName", "orderType", "OpC","Advf", "LmUp", "Tre", "DSD", "Sam", "Tags", "TMint", "SMr", "Toff",
        "orderQtyBoxes", "orderAmount", "submit_dt", "status", "orderId", "digC_val", "addEbudde", "orderPickedup",
        "orderReady", "initialOrder", "orderPaid"
    ]

    df_final = df[columns_to_keep]
    
    new_orders = df_final[~df_final["orderId"].apply(order_exists)]

    # Insert only new orders
    if not new_orders.empty:
        actions = [
            {"_index": index_nm, "_id": row["orderId"], "_source": row.to_dict()}
            for _, row in new_orders.iterrows()
        ]
        bulk(es, actions)

    print(f"{len(new_orders)} new orders inserted into Elasticsearch.")


if __name__ == '__main__':

    setup.config_site(page_title="Import DOC",initial_sidebar_state='expanded')
    main()