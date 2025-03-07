from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import io
import pandas as pd
from streamlit_extras.row import row as strow
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
import json

def init_ss():
    pass

@st.cache_resource
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

    # ADD INVENTORY PICKUP
    st.markdown(f"Ready to submit a Cookie Inventory Pickup")

    with st.form('submit orders', clear_on_submit=True):
      
        row1 = strow(5, vertical_align="center")
        row1.text_input(label='Order Ref #',key='orderId')
        row1.number_input(label='Adventurefuls',step=1,min_value=-5, value=0,key='inv_adv')
        row1.number_input(label='Lemon-Ups',step=1,min_value=-5, value=0, key='inv_lmup')
        row1.number_input(label='Trefoils',step=1,min_value=-5, value=0, key='inv_tre')
        row1.number_input(label='Do-Si_Dos',step=1,min_value=-5, value=0, key='inv_dsd')

        row2 = strow(5, vertical_align="center")
        row2.number_input(label='Samoas',step=1,min_value=-5, value=0, key='inv_sam')
        row2.number_input(label='Tagalongs',step=1,min_value=-5, value=0, key='inv_tags')
        row2.number_input(label='Thin Mints',step=1,min_value=-5, value=0, key='inv_tmint')
        row2.number_input(label="S'mores",step=1,min_value=-5, value=0, key='inv_smr')
        row2.number_input(label='Toffee-Tastic',step=1,min_value=-5, value=0, key='inv_toff')
        
 
        # submitted = st.form_submit_button()
        if st.form_submit_button("Submit Inventory Pickup"):
            total_boxes, order_amount=au.calc_tots(ss.inv_adv,ss.inv_lmup,ss.inv_tre,ss.inv_dsd,ss.inv_sam,ss.inv_tags,ss.inv_tmint,ss.inv_smr,ss.inv_toff,0)
            st.write(total_boxes)
            # Every form must have a submit button.
            order_data = {
                "orderRef_id":ss.orderId,
                "Adf": ss.inv_adv,
                "LmUp": ss.inv_lmup,
                "Tre": ss.inv_tre,
                "DSD": ss.inv_dsd,
                "Sam": ss.inv_sam,
                "Tags": ss.inv_tags,
                "Tmint": ss.inv_tmint,
                "Smr": ss.inv_smr,
                "Toff": ss.inv_toff,
                "pickup_dt": datetime.now(),
                }
            
            esu.add_es_doc(es,indexnm=ss.indexes['index_inventory'], id=ss.orderId, doc=order_data)

            st.warning(f" {total_boxes} boxes were submitted\n \n your order id is {ss.orderId}")        # get latest push of orders:                

    # ALL INVENTORY
    inventory_qry = f"FROM {ss.indexes['index_inventory']} | LIMIT 1000"
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=inventory_qry,
        format="csv")
    
    all_inventory = pd.read_csv(io.StringIO(response.body))
    all_inventory = all_inventory.set_index('orderRef_id')
    sum_cols = all_inventory.columns
    drop_cols = {'pickup_dt'}
   
    sum_cols = [item for item in sum_cols if item not in drop_cols]
    all_inventory_tot = au.add_totals_row(all_inventory, sum_cols)
    column_order = ['orderRef_id','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','pickup_dt']
    st.write('Inventory Orders with Totals')
    st.dataframe(all_inventory_tot, column_order=column_order)
    
    
    st.write('Click in a cell to edit it')
    edited_data = st.data_editor(all_inventory, num_rows='fixed', key='update_inventory_dat', use_container_width=True, column_order = column_order)

    # if edited_data is not None:
    #     # Drop the "Total" row before comparison
    #     edited_df = edited_data[edited_data.index != "Total"]
    #     st.divider()

    changes = edited_data.compare(all_inventory)
               
    if not changes.empty:
        st.write("Changes detected:")
            # Keep only columns where the second level is "Self"
        changed_df = changes.loc[:, changes.columns.get_level_values(1) == "self"]
        changed_df.fillna(0,inplace=True)
        # Reset the column index if needed
        changed_df.columns = changed_df.columns.droplevel(1)  # Remove second level
        # st.write(changed_df)
        
        changed_str = changed_df.to_json(orient="index") # type str
        changed_dict = json.loads(changed_str)  # type json
        st.write(changed_dict)
        
        st.divider()
        
        if st.button('save updates to elastic'):
            # Convert changes to a dictionary and send updates to Elasticsearch
            for doc_id, v in changed_dict.items():  # Iterate over changed rows
                st.write(f'{doc_id} :> {v}')
                update_doc = {"doc": v}
                # st.write(doc_id, update_doc)
                resp = es.update(index=ss.indexes['index_inventory'], id=doc_id, body=update_doc)
                st.write(f"{doc_id} : {resp.get('result')}")
                    
    # # Monitor changes
    # if st.button("Save to Elasticsearch"):
    #     # Find new rows by comparing indices
    #     new_rows = edited_data[~edited_data["orderRef_id"].isin(all_inventory["orderRef_id"])]

    #     if not new_rows.empty:
    #         st.write("New Rows to Add to Elasticsearch:", new_rows)

    #         # Send new rows to Elasticsearch
    #         for _, row in new_rows.iterrows():
    #             # Example index and document ID
    #             index_name = f"{ss.indexes['index_inventory']}"
    #             document_id = row["orderRef_id"]

    #             # Convert row to dictionary and index it
    #             es.index(index=index_name, id=document_id, document=row.to_dict())

            st.success("New data has been added to Elasticsearch!")
        else:
            st.info("Data not updated.")

        # Display current data
        st.write("Edited Data:")
        st.write(edited_data)

if __name__ == '__main__':

    setup.config_site(page_title="Add Inventory",initial_sidebar_state='expanded')
    # Initialization
    init_ss()
    main()