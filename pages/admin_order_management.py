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
        au.get_all_orders()  # this should updadte the session state with all orders

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

    st.warning('page in-work')
    st.header('All Orders to Date')
   
    all_orders_dat = au.get_all_orders(es)

    st.data_editor(all_orders_dat.set_index('orderId'))
    
    all_orders_cln = au.allorder_view(all_orders_dat) # this keeps short names for varity changes cols to int
    # all_orders_cln = all_orders_cln

    ss.filtered_df = all_orders_cln.copy() #set_index('orderId').copy()
    st.divider()
    name_filter = st.text_input("Filter by Scout:")
    # age_filter = st.sidebar.slider("Filter by orderType:", min_value=0, max_value=100, value=(0, 100))
    orderType_filter = st.multiselect("Filter by orderType:", options=all_orders_cln["orderType"].unique())
    status_filter = st.multiselect("Filter by status:", options=all_orders_cln["status"].unique())


    if name_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["scoutName"].str.contains(name_filter, case=False)]

    if orderType_filter:
        st.write(status_filter)
        ss.filtered_df = ss.filtered_df[ss.filtered_df["orderType"].isin(orderType_filter)]

    if status_filter:
        ss.filtered_df = ss.filtered_df[ss.filtered_df["status"].isin(status_filter)]

    filter_dat = ss.filtered_df.set_index('orderId')

    def add_totals_row(df):
        # Function to add a totals row
        total_columns = ['orderAmount','orderQtyBoxes', 'Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff', 'OpC']
        totals = {col: df[col].sum() for col in total_columns} # Calculate totals for specified columns
        # Create a new DataFrame for the totals row
        totals_df = pd.DataFrame([totals], index=["Total"])  # Pass the index as a list
        # Append the totals row to the original DataFrame
        # st.write(totals_df)
        return pd.concat([df, totals_df])
        

    # Add the totals row to the DataFrame
    filter_summed = add_totals_row(filter_dat)
   
    # st.write('data editor')
    edited_dat = st.data_editor(
        filter_summed, key='edited_dat', 
        width=1500, use_container_width=False, 
        num_rows="fixed",
        column_config={
            'scoutId': None,# st.column_config.Column()
            'scoutName': st.column_config.Column(
                width='small',
            ),
            'status': st.column_config.Column(
                width='small'
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
                "Val. in DC?",
                width='small',
            )
    }
    )
    # st.write(ss.edited_dat)
    # Monitor updates and send changes to Elasticsearch
    if edited_dat is not None:
        # Drop the "Total" row before comparison
        edited_df = edited_dat[edited_dat.index != "Total"]
        # st.write('Edited Df:')
        # st.write(edited_df)
        # st.write('vs filter dat')
        # st.write(filter_dat)
        # Compare the edited DataFrame with the original
        changes = edited_df.compare(filter_dat)

        if not changes.empty:
            st.write("Changes detected:")
            # st.write(changes)
            # if st.button('save updates to elastic:'):
            #     # Convert changes to a dictionary and send updates to Elasticsearch
            #     for doc_id in changes.index:  # Iterate over changed rows
            #         # updated_data = edited_df.loc[doc_id].to_dict()
            #         updated_data = changes.to_json(orient="records", indent=4)
            #         update_doc = {"doc": updated_data}
            #         st.write(doc_id, update_doc)
            #         es.update(index=ss.indexes['index_orders'], id=doc_id, doc=update_doc)
            #         st.write(f"Updated document {doc_id} sent to Elasticsearch:", updated_data)
    #         def _handle_table_changed(self, key_name: str):
    #     new_state = st.session_state[key_name]
    #     if "edited_rows" in new_state:
    #         for index, change_dict in new_state["edited_rows"].items():
    #             source_object = self.data[index]
    #             for changed_field, new_value in change_dict.items():
    #                 # the getattr() check is required because streamlit does not remove entries from the modification
    #                 # dictionary. 
    #                 if getattr(source_object, changed_field) != new_value:
    #                     setattr(source_object, changed_field, new_value)
    #         # new_state["edited_rows"].clear() Disabled because no effect

    # def render(self, key_name: str):
    #     st.data_editor(
    #         self.dataframe,
    #         column_config=self.st_column_specs,
    #         key=key_name,
    #         column_order=self.column_names,
    #         hide_index=True,
    #         on_change=self._handle_table_changed,
    #         args=[key_name],
    #     )

    # Display message
    # st.write("Monitor updates and push changes to Elasticsearch in real-time!")
    st.write('Changes not updating yet... check back soon')


    # filtered_df = pd.DataFrame() #filtered_df[filtered_df[column].isin(user_cat_input)]
        # filtered_df = filtered_df[filtered_df[column].isin(user_cat_input)]
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