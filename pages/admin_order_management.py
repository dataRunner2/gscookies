from json import loads
import streamlit as st
import pandas as pd
import json
import time
import io
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from pandas.api.types import is_categorical_dtype, is_numeric_dtype, is_datetime64_any_dtype
from streamlit_extras.row import row

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def init_ss():
    if "filters" not in ss:
        ss.filters = {}

# Send updates to Elasticsearch
def update_elasticsearch(es, document_id, field, value):
    es.update(
        index=ss.indexes['index_orders'],
        id=document_id,
        body={"doc": {field: value}}
    )

def update_order_status(es, update_index, edited_content, all_orders):
        edited_allorders = st.session_state['edited_dat']['edited_rows']
        st.write('EDITED ROWS:')
        st.markdown(f'Initial Edited Rows: {edited_allorders}')

        for key, value in edited_allorders.items():
            new_key = all_orders.index[key]
            st.write(f'Updated Values to Submit to ES: {new_key}:{value}')
            resp = es.update(index=ss.indexes['index_orders'], id=new_key, doc=value)
            time.sleep(1)
        st.toast("Database updated with changes")
        esu.get_all_orders()  # this should updadte the session state with all orders

# @st.fragment
def update_table(column, filter):
    st.write(f'{column} - {filter}')
    filter_df = ss.filtered_df.copy()
    key_val = ss[f'filters_dyn']
    st.write(f"{column}: {key_val}")
    ss.filters[column] = key_val

# Function to apply styles to bottom row of tables
def style_dataframe(dataframe):
    def highlight_bottom_row(row):
        if row.name == "Total":
            return ["font-weight: bold; background-color: #abbaaf; color: black;"] * len(row)
        return [""] * len(row)
    
    return dataframe.style.apply(highlight_bottom_row, axis=1)

def main():
    es = get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

   
    all_orders_dat = esu.get_all_orders(es)
    all_orders_cln = au.allorder_view(all_orders_dat) # this keeps short names for varity changes cols to int
    # all_orders_cln = all_orders_cln

    ss.filtered_df = all_orders_cln.copy() #set_index('orderId').copy()
    st.divider()
    row1 = st.columns(4)
    with row1[0]:
        name_filter = st.text_input("Filter by Scout:")
    with row1[1]:
        orderType_filter = st.multiselect("Filter by orderType:", options=all_orders_cln["orderType"].unique())
    with row1[2]:
        status_filter = st.multiselect("Filter by status:", options=all_orders_cln["status"].unique())
    with row1[3]:
        ebudde_filter = st.multiselect("In Ebudde:", options=all_orders_cln["addEbudde"].unique())

  
    if name_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["scoutName"].str.contains(name_filter, case=False)]

    if orderType_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["orderType"].isin(orderType_filter)]

    if status_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["status"].isin(status_filter)]

    if ebudde_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["addEbudde"].isin(ebudde_filter)]

    filter_dat = ss.filtered_df.set_index('orderId')
    filter_dat.sort_index(inplace=True)

    def add_totals_row(df):
        # Function to add a totals row
        total_columns = ['orderAmount','orderQtyBoxes', 'Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff', 'OpC']
        totals = {col: df[col].sum() for col in total_columns} # Calculate totals for specified columns
        # Create a new DataFrame for the totals row
        totals_df = pd.DataFrame([totals], index=["Total"])  # Pass the index as a list
        # Append the totals row to the original DataFrame
        # st.write(totals_df)
        return pd.concat([df, totals_df])
        
    # Calculate the paper order totals
    papers = ss.filtered_df.copy()
    papers = papers[papers["orderType"] == "Paper Order"]
    papers_sum = add_totals_row(papers)
    paper_ord_money = papers_sum.loc['Total','orderAmount']
    scts_sel = list(filter_dat['scoutId'].unique())
    scts_sel = [x for x in scts_sel if not pd.isna(x)]
    girl_money_qry = f'FROM {ss.indexes["index_money"]} | WHERE scoutId IN ("' + '", "'.join(scts_sel) + '") | LIMIT 500'

    # Amount Received
    response = es.esql.query(
        query=girl_money_qry,
        format="csv")
    amt_received =  pd.read_csv(io.StringIO(response.body))
    amt_received = amt_received.fillna(0)
    amt_received = amt_received.astype({"amountReceived": 'int'})
    total_amt_received = amt_received['amountReceived'].sum()
    st.write(f"Total Paper Orders Money Due: ${paper_ord_money}")
    st.write(f'Total amount received: ${total_amt_received}')
    st.write(f'Amount that should show in Ebudde for **delivery** orders, assuming any money received are in ebudde: ${paper_ord_money - total_amt_received}')
    
    # sort by order number
    filter_dat.sort_index(inplace=True) 
    
    # Add the totals row to the DataFrame
    filter_summed = add_totals_row(filter_dat)
    # st.write(f'{filter_summed.columns}')

    column_config = column_config={
            'scoutId': None,# st.column_config.Column()
            'scoutName': st.column_config.Column(
                width='small',
            ),
            'status': st.column_config.Column(
                width='small',
                disabled=True
            ),
            'orderQtyBoxes': st.column_config.Column(
                "Qty", width='small'
            ),
            'orderAmount': st.column_config.Column(
                "Amt", width='small'
            ),
            "addEbudde": st.column_config.CheckboxColumn(
                "In Ebudde",
                help="Has this order been added to Ebudde",
                width='small',
                disabled=False
            ),
            "digC_val": st.column_config.CheckboxColumn(
                "ValDC",
                width='small'
            ),
            "Date": st.column_config.DateColumn(
                disabled=True
            )

    }
    column_order=['scoutName','orderType','Date','status','addEbudde','orderReady','orderPickedup','initialOrder','orderAmount','orderQtyBoxes','digC_val','OpC','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','comments','guardianNm','guardianPh','submit_dt']
       
    # st.write('data editor')
    edited_dat = st.data_editor(
        filter_summed, key='edited_dat', 
        width=1500, use_container_width=False, 
        num_rows="fixed", column_order = column_order,
        column_config = column_config
    )

    # Monitor updates and send changes to Elasticsearch
    if edited_dat is not None:
        # Drop the "Total" row before comparison
        edited_df = edited_dat[edited_dat.index != "Total"]
        st.divider()
        st.write('Updated table:')
        updated_frame = st.dataframe(
            edited_df, key='updated_tbl', 
            width=1500, use_container_width=False, 
            column_order = column_order,
            column_config = column_config
            )
        time.sleep(1)
        changes = edited_df.compare(filter_dat)
               
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
                for doc_id,v in changed_dict.items():  # Iterate over changed rows
                    # st.write(f'{doc_id} :> {v}')
                    update_doc = {"doc": v}
                    # st.write(doc_id, update_doc)
                    resp = es.update(index=ss.indexes['index_orders'], id=doc_id, body=update_doc)
                    st.write(f"{doc_id} : {resp.get('result')}")
                    # POST your_index_name/_update/your_document_id
                    #     {
                    #     "doc": {
                    #         "field1": "new_value1",
                    #         "field2": "new_value2"
                    #     }
                    #     }


if __name__ == '__main__':

    setup.config_site(page_title="Admin Cookie Management",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()