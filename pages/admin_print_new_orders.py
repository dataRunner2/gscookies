from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
# from st_aggrid import AgGrid needs 3.10

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def add_totals_row(df):
    # Function to add a totals row
    total_columns = ['orderAmount','orderQtyBoxes', 'Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff', 'OpC']
    totals = {col: df[col].sum() for col in total_columns} # Calculate totals for specified columns
    # Create a new DataFrame for the totals row
    totals_df = pd.DataFrame([totals], index=["Total"])  # Pass the index as a list
    # Append the totals row to the original DataFrame
    # st.write(totals_df)
    return pd.concat([df, totals_df])
    
def main():
    st.write('----')
    es =  get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        
    st.warning('page in-work')
    st.header('All Orders to Date')
    st.warning('split table per scout')
    
    pull_orders = au.get_all_orders(es)
    pull_cln = au.allorder_view(pull_orders)

    # all_orders_cln.fillna(0)
    # pull_cln = pull_cln.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
    pull_cln = pull_cln[pull_cln['orderPickedup'] == False]

    pull_cln=pull_cln.loc[:, ['scoutName','orderId','orderType','Date','orderQtyBoxes', 'orderAmount','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','pickupNm','pickupPh','status']]

    column_config = column_config={
                        "scoutName":None,
                        "orderAmount": st.column_config.NumberColumn(
                            "Amt",
                            format="$%d",
                            width='20'
                        ),
                        "orderType":st.column_config.Column(
                            width='small'
                        ),
                        "orderQtyBoxes":st.column_config.NumberColumn(
                            "Qty",
                            width='10'
                        ),
                        "Date": st.column_config.DateColumn(
                            format="MM-DD-YY",
                        ),
                        "comments":st.column_config.Column(
                            width='medium'
                        ),

                        "Adf": st.column_config.Column(
                            "Adf",
                            width='10'
                        ),
                        }
    
    with st.expander('Filter'):
        order_content = au.filter_dataframe(pull_cln)
    
    orders_summed = add_totals_row(order_content)
    st.subheader(f'Pickup for {", ".join(order_content['scoutName'].unique())}')
    st.dataframe(orders_summed, use_container_width=True, hide_index=True,
                     column_config = column_config,
                     height=35*len(orders_summed)+38)
    
    st.write('')
    
    st.divider()
    st.dataframe(orders_summed, use_container_width=True, hide_index=True,
                     column_config = column_config,
                     height=35*len(orders_summed)+38)

    # AgGrid(dataframe, height=500, fit_columns_on_grid_load=True)
    st.write('Reminder - All funds due back to us by 3/19 at Noon')
    st.write('Pickup Signature: __________________')


if __name__ == '__main__':

    setup.config_site(page_title="Print Orders",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()