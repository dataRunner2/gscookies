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
    total_columns = ['orderAmount','orderQtyBoxes', 'Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff']
    totals = {col: df[col].sum() for col in total_columns} # Calculate totals for specified columns
    # Create a new DataFrame for the totals row
    totals_df = pd.DataFrame([totals], index=["Total"])  # Pass the index as a list
    # Append the totals row to the original DataFrame
    # st.write(totals_df)
    return pd.concat([df, totals_df])
    
def main():
    es =  get_connected()
    st.markdown(
        """
        <style>
        @media print {
            body {
                background: white !important;
                -webkit-print-color-adjust: exact; /* Ensures colors print correctly */
            }
            .stApp {
                background: white !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <style>
         @media print {
            .stDataFrame {
                background: white !important;
                color: black !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
        
    # st.warning('page in-work')
    # st.header('All Orders to Date')
    # st.warning('split table per scout')
    
    pull_orders = esu.get_all_orders(es)
    pull_cln = au.allorder_view(pull_orders)

    # all_orders_cln.fillna(0)
    # pull_cln = pull_cln.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
    pull_cln = pull_cln[pull_cln['orderPickedup'] == False]

    pull_cln=pull_cln.loc[:, ['scoutName','orderId','orderType','initialOrder','Date','orderQtyBoxes', 'orderAmount','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','guardianNm','guardianPh','status']]
    ss.order_content = pull_cln.copy()
    column_config = column_config={
                        "scoutId":None,
                        "initalOrder": st.column_config.Column(
                            width='small'
                        ),
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
    
    with st.expander('Filter Orders'):
        row1 = st.columns(4)
        with row1[0]:
            name_filter = st.text_input("Filter by Scout:")
        with row1[1]:
            orderType_filter = st.multiselect("Filter by orderType:", options=pull_cln["orderType"].unique())
        with row1[2]:
            status_filter = st.multiselect("Filter by status:", options=pull_cln["status"].unique())
        with row1[3]:
            io_filter = st.multiselect("Initial Order:", options=pull_cln["initialOrder"].unique())

  
    if name_filter:
        ss.order_content = ss.order_content[ss.order_content["scoutName"].str.contains(name_filter, case=False)]

    if orderType_filter:
        ss.order_content = ss.order_content[ss.order_content["orderType"].isin(orderType_filter)]

    if status_filter:
        ss.order_content = ss.order_content[ss.order_content["status"].isin(status_filter)]
    if io_filter:
        ss.order_content = ss.order_content[ss.order_content["initialOrder"].isin(io_filter)]

    order_content = ss.order_content.set_index('orderId')
    order_content.sort_index(inplace=True)
    
    with st.container():
        orders_summed = add_totals_row(order_content)
        st.subheader(f'Pickup for {", ".join(order_content["scoutName"].unique())}')
        styled_df = orders_summed.style.set_properties(**{"background-color": "white", "color": "black"})
        st.dataframe(styled_df, use_container_width=True, hide_index=True,
                        column_config = column_config,
                        height=35*len(orders_summed)+38)
        
        
        st.write('')
        
        st.divider()
        st.dataframe(styled_df, use_container_width=True, hide_index=True,
                        column_config = column_config,
                        height=35*len(orders_summed)+38)

        # AgGrid(dataframe, height=500, fit_columns_on_grid_load=True)
        st.markdown('Reminder - All inital order funds due back to us by 3/9 by Noon&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   Pickup Signature: ______________________________')


if __name__ == '__main__':

    setup.config_site(page_title="Print Orders",initial_sidebar_state='collapsed')
    # Initialization
    init_ss()

    main()