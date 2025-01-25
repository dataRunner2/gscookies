from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from pandas.api.types import is_categorical_dtype, is_numeric_dtype, is_datetime64_any_dtype


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
        au.get_all_orders()  # this should updadte the session state with all orders

@st.fragment
def update_table(column):
    filter_df = ss.filtered_df.copy()
    key_val = ss['{column}']
    st.write(f"{column}: {key_val}")
    ss.filters[column] = key_val
    # Save selections to session state
    if ss.filters[column] is not None:
        filter_df[filter_df[column].isin([ss.filters[column]])]
    ss.filtered_df = filter_df.copy()

def main():
    es = get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    st.header('All Orders to Date')
    all_orders_dat = au.get_all_orders(es)
    all_orders_cln = au.allorder_view(all_orders_dat)
    st.write(all_orders_cln)

    modification_container = st.container()
    ss.filtered_df = all_orders_cln.copy()

    # # with st.expander('Filter'):
    # if st.button("Reset Filters"):
    #     ss.filters = {}
    #     st.rerun()

    ss.filters
    with modification_container:
        to_filter_columns = st.multiselect("Filter dataframe on", ['Scout','orderType','status','guardianNm','addEbudde','orderReady','orderPickedup'],default='Scout')
        
        if len(to_filter_columns) > 0:
            cols = st.columns(len(to_filter_columns))
            for i, col in enumerate(cols):
                with col:
                    column = to_filter_columns[i]
                    st.write(column)
                    st.multiselect(f"Values for {column}", options=list(all_orders_cln[column].unique()), key=column, on_change=update_table, kwargs={"column": column})  # Pass column to the callback
        else:
            ss.filters = {}

        ss.filters
        filtered_df = pd.DataFrame() #filtered_df[filtered_df[column].isin(user_cat_input)]

            # 

            # left, right = st.columns((1, 20))
            # left.write("↳")
            
            # # Treat columns with <10 unique values as categorical
            # if is_categorical_dtype(all_orders_cln[column]) or all_orders_cln[column].nunique() < 10:
            #     # Restrict options to the already filtered DataFrame
            #     options = all_orders_cln[column].unique()
            #     # Get selected values from session state or if None then get all of them default to all
            #     selected_values = ss.filters[column] or list(options)
            #     user_cat_input = right.multiselect(
            #         f"Values for {column}",
            #         options=options,
            #         default=selected_values,
            #     )
            #     get_cat_values(user_cat_input, column)
            #     ss.filters
                
            #     # Apply the filter
            #     filtered_df = filtered_df[filtered_df[column].isin(user_cat_input)]
        
            # # Text columns
            # else:
            #     user_text_input = st.session_state.filters[column] or ""
            #     user_text_input = right.text_input(f"Substring or regex in {column}", value=user_text_input)
                
            #     # Save input to session state
            #     st.session_state.filters[column] = user_text_input
                
            #     # Apply filter
            #     if user_text_input:
            #         try:
            #             filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(user_text_input, na=False)]
            #         except Exception as e:
            #             st.warning(f"Invalid regex: {e}")

    # st.write(f'Filtered DF')
    # st.data_editor(filtered_df)

    # st.divider()
    # edited_dat = st.data_editor(
    #     filtered_df, key='edited_dat', 
    #     width=1500, use_container_width=False, 
    #     num_rows="fixed",
    #     column_config={
    #     'id': st.column_config.Column(
    #         width='small',
    #     ),
    #     'status': st.column_config.Column(
    #         width='small'
    #     ),
    #     "addEbudde": st.column_config.CheckboxColumn(
    #         "Ebudde Ver",
    #         help="Has this order been added to Ebudde",
    #         width='small',
    #         disabled=False
    #     ),
    #     "digC_val": st.column_config.CheckboxColumn(
    #         "Validated in Digital Cookie?",
    #         width='small',
    #     )
    # }
    # )
        
    #      # Monitor changes
        
    # # Check for changes and update Elasticsearch
    # if st.button("Save Changes"):
    #     update_order_status()
    #         # for index, row in edited_data.iterrows():
    #         #     original_row = df.loc[index]
    #         #     if row["is_a"] != original_row["is_a"]:
    #         #         update_elasticsearch(row["id"], "is_a", row["is_a"])
    #         #     if row["is_b"] != original_row["is_b"]:
    #         #         update_elasticsearch(row["id"], "is_b", row["is_b"])
    #         # st.success("Changes saved to Elasticsearch!")

    #     # Display current data
    #     st.write("Edited Data:")
    #     st.write(edited_dat)

    # USE DEV index to test this - make sure it's only affecting the rows I think itis
    # if not ss.start_dat.equals(edited_dat):
    #     st.write('start data is Not equal to edited')
    #     ss.start_dat = edited_dat
    #     ss.start_dat.loc[,'Qty'] = ss.start_dat['Adv'] + ss.start_dat['LmUp'] 
    #     # st.write(ss.start_dat)
    #     rr()
            

        # if submit_button:
        #     st.session_state["refresh"] = True
        #     try:
        #         # Write to database
        #         au.update_es(edited_dat, edited_content)
        #         # time.sleep(1)
        #         # Refresh data from Elastic
        #         all_orders = au.get_all_orders(es)
        #     except:
        #         st.warning("Error updating Elastic")
        #         st.write(st.session_state['edited_dat'])

if __name__ == '__main__':

    setup.config_site(page_title="Admin Cookie Management")
    # Initialization
    init_ss()

    main()