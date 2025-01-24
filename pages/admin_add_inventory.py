from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import io
from typing import List, Tuple
import pandas as pd
import random
from pathlib import Path
from streamlit_extras.let_it_rain import rain
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.grid import grid

from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3

def init_ss():
    pass

# @st.cache_data
def get_connected():
    es = esu.conn_es()
    return es

def add_index(es):
    # Define the mapping for the index
    # 'Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Dos','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic'
    mapping = {
        "mappings": {
            "properties": {
                "Adf": {"type": "short"},
                "LmUp": {"type": "short"},
                "Tre": {"type": "short"},
                "DSD": {"type": "short"},
                "Sam": {"type": "short"},
                "Smr": {"type": "short"},
                "Tags": {"type": "short"},
                "Tmint": {"type": "short"},
                "Toff": {"type": "short"},
                "pickup_dt": {"type": "date"},  # Date in ISO8601 format
                "orderRef_id": {"type": "text"}
            }
        }
    }

    # Create the index
    if not es.indices.exists(index=ss.indexes['index_inventory']):
        es.indices.create(index=ss.indexes['index_inventory'], body=mapping)
        print(f"Index '{ss.indexes['index_inventory']}' created successfully!")
    else:
        print(f"Index '{ss.indexes['index_inventory']}' already exists.")
        
    
def main():
    # st.write('---')
    es=get_connected()
    if not ss.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
    add_index(es)


    inventory_qry = f'FROM {ss.indexes['index_inventory']} | LIMIT 1000'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=inventory_qry,
        format="csv")
    
    all_inventory = pd.read_csv(io.StringIO(response.body))

    st.write('Click in a cell to edit it')

    edited_data = st.data_editor(all_inventory, num_rows='dynamic', key='update_inventory_dat', use_container_width=True,
                    column_config={
                        "Amt": st.column_config.NumberColumn(
                            "Amt.",
                            format="$%d",

                        ),
                        "Date": st.column_config.DateColumn(
                            "Order Date",
                            format="MM-DD-YY",
                        )})
    # Monitor changes
    if st.button("Save to Elasticsearch"):
        # Find new rows by comparing indices
        new_rows = edited_data[~edited_data["orderRef_id"].isin(all_inventory["orderRef_id"])]

        if not new_rows.empty:
            st.write("New Rows to Add to Elasticsearch:", new_rows)

            # Send new rows to Elasticsearch
            for _, row in new_rows.iterrows():
                # Example index and document ID
                index_name = f"{ss.indexes['index_inventory']}"
                document_id = row["orderRef_id"]

                # Convert row to dictionary and index it
                es.index(index=index_name, id=document_id, document=row.to_dict())

            st.success("New data has been added to Elasticsearch!")
        else:
            st.info("No new rows to add.")

        # Display current data
        st.write("Edited Data:")
        st.write(edited_data)

if __name__ == '__main__':

    setup.config_site(page_title="Add Inventory",initial_sidebar_state='expanded')
    # Initialization
    init_ss()
    main()