from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import json
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3

es = esu.conn_es()
# Load the index template from a JSON file
def load_template_from_file(file_path):
    try:
        with open(file_path, "r") as f:
            template_body = json.load(f)
        print(f"Template loaded successfully from {file_path}.")
        return template_body
    except Exception as e:
        print(f"Error loading template from {file_path}: {e}")
        return None
    
# Create an index template
def create_index_template(es, template_name, template_body):
    try:
        es.indices.put_index_template(name=template_name, body=template_body)
        print(f"Template '{template_name}' created successfully.")
    except Exception as e:
        print(f"Error creating template '{template_name}': {e}")

# Create an index # assumes either a template is used or using the defaults
def create_index(index_name):
    try:
        if es.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
        else:
            es.indices.create(index=index_name) # body=index_body)
            print(f"Index '{index_name}' created successfully.")
    except Exception as e:
        print(f"Error creating index '{index_name}': {e}")

# Create an index
def create_index_with_mapping(index_name, mappings=None, settings=None):
    """
    # Define mappings (optional)
    mappings = {
        "properties": {
            "field1": {"type": "text"},
            "field2": {"type": "keyword"},
            "field3": {"type": "date"},
            "field4": {"type": "boolean"}
        }
    }

    # Define settings (optional)
    settings = {
        "number_of_shards": 1,
        "number_of_replicas": 1
    }
    """
    try:
        body = {}
        if mappings:
            body["mappings"] = mappings
        if settings:
            body["settings"] = settings

        # Create the index
        es.indices.create(index=index_name, body=body)
        print(f"Index '{index_name}' created successfully.")
    except Exception as e:
        print(f"Error creating index '{index_name}': {e}")

# Reindex an index
def reindex_index(src_index, dest_index):
    try:
        es.reindex(
            body={
                "source": {"index": src_index},
                "dest": {"index": dest_index}
            },
            wait_for_completion=True,
        )
        st.write(f"Reindexed from '{src_index}' to '{dest_index}'.")
    except Exception as e:
        st.write(f"Error reindexing from '{src_index}' to '{dest_index}': {e}")

# Main function
def get_latest_backup_num(index_nm):
        if es.indices.exists(index=index_nm):
            st.write(f"Index '{index_nm}' already exists.")
        
            for i in range(1,50):
                if not es.indices.exists(index=f"{index_nm}_v{i}"):
                    target_index = f"{index_nm}_v{i}"
                    st.write(f"Indexing into '{target_index}'")
                    break
                else:
                   pass

            # Reindex index to version v99
            reindex_index(index_nm, target_index)
        else: 
            st.write(f"Index '{index_nm}' does not exist.")

        st.write(f"Processed index: {index_nm}")

def main():
    es = esu.conn_es()
    make_templates = False # this is normally false unless setting up the database newly
   
    if make_templates:
        # Scouts Template
        template_body = load_template_from_file('./index_mapping_scouts.json')
        create_index_template(es, 'scouts_templ', template_body)
        create_index("scouts2026")

        # Orders Template
        template_body = load_template_from_file('./index_mapping_orders.json')
        create_index_template(es, 'orders_templ', template_body)
        create_index("orders2025")

        # Money Template
        template_body = load_template_from_file('./index_mapping_money.json')
        create_index_template(es, 'money_templ', template_body)
        create_index("money2025")

        # Inventory Template
        template_body = load_template_from_file('./index_mapping_inventory.json')
        create_index_template(es, 'inventory_templ', template_body)
        create_index("inventory2025")
    

    if st.button('make_backups'):
        now = datetime.now()
        formatted_time = now.strftime("%b%d_%H%M")  # Format the date and time as "Jan24_2032"
        st.write('Re-indexing as "_{formatted_time}')

        for index_nm in ['scouts2025','orders2025','money2025','inventory2025']:
            get_latest_backup_num(index_nm)
            st.write('__________')

   
    ss

if __name__ == '__main__':

    setup.config_site(page_title="Session State",initial_sidebar_state='expanded')
    main()