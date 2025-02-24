from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from streamlit_extras.grid import grid
# from st_aggrid import AgGrid needs 3.10

def init_ss():
    pass

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def add_totals_row(df):
    # Function to add a totals row
    total_columns = ['Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff']
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

    pull_cln=pull_cln.loc[:, ['scoutName','orderId','orderType','Date','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','status']]
    ss.order_content = pull_cln.copy()

    orderType_filter = ['Booth']
    ss.order_content = ss.order_content[ss.order_content["orderType"].isin(orderType_filter)]
    row1 = st.columns(4)
    with row1[0]:
        booths = ss.order_content["scoutName"]
    
    # ss.order_content = ss.order_content.set_index('orderId')
    ss.order_content = au.just_renamer(ss.order_content,just_cookies = True)
    ss.order_content.sort_index(inplace=True)
    
    
    st.selectbox("Booth:",booths,key='sel_booth')
    st.text_area('Scouts @ Booth')
    if ss.sel_booth:
        ss.order_content = ss.order_content[ss.order_content["scoutName"].str.contains(ss.sel_booth, case=False)]
        booth_order = ss.order_content.copy()
        booth_order.drop(columns=['scoutName','orderType','orderId','Date','status'],axis=1,inplace=True)
        booth_order_trans = booth_order.T
        booth_order_trans.reset_index(inplace=True)
        booth_order_trans.columns = ['Cookie Variety','Starting Qty']

        booth_order_trans[['Ending Cases','Ending Boxes','Total Sold']] = ''
        # st.table(booth_order_trans)
        # Apply left-alignment styling
        # df_styled = booth_order_trans.style.set_properties(**{
        #     'text-align': 'left'
        # }).hide(axis="index")  # Hide the index (optional)

        # Display styled DataFrame
        # st.dataframe(df_styled)
        st.dataframe(booth_order_trans.style.set_properties(**{'text-align': 'left'}),use_container_width=True,hide_index=True)
        # st.markdown(booth_order_trans.to_html(index=False), unsafe_allow_html=True)


    # # Inject CSS for full width and left alignment
    # st.markdown(
    #     f"""
    #     <style>
    #         .dataframe-container {{
    #             width: 100%;
    #             overflow-x: auto;
    #         }}
    #         table {{
    #             width: 100%;
    #             border-collapse: collapse;
    #         }}
    #         th, td {{
    #             text-align: left !important;
    #             padding: 8px;
    #             border: 1px solid #ddd;
    #         }}
    #     </style>
    #     <div class="dataframe-container">{html_table}</div>
    #     """,
    #     unsafe_allow_html=True
    # )
   
    booth_grid = grid([.7,.3],[.3,.2,.2,.3],[.3,.2,.5],[.3,.2,.5],[.3,.15,.15,.4], [.3,.15,.3,.2], [.5,.3,.2], [.5,.35,.2], vertical_align="center")
    booth_grid.write('Out-going signiture: _____________________________')
    booth_grid.write('Total Boxes Sold: _______________')
    booth_grid.write('Finish Cash')
    booth_grid.write('$__________')
    booth_grid.write('')
    booth_grid.write('Total boxes sold * $6 = ____________')
    
    # Row 2
    booth_grid.write('Total Credit Card Sales')
    booth_grid.write('$ __________')
    booth_grid.write('')

    # Row 3
    booth_grid.write('Cash + Credit = Ending $')
    booth_grid.write('$ __________')
    booth_grid.write('')

    # Row 4
    booth_grid.write('Starting Cash')
    booth_grid.write('$ __________')
    booth_grid.write('Typically $100')
    booth_grid.write('')

    # Row 4
    booth_grid.write('Ending \$ - Starting \$ = Revenue')
    booth_grid.write('$ __________')
    booth_grid.write('------------- > Enter same revenue # here')
    booth_grid.write('$ __________')

    # Row 5
    booth_grid.write('')
    booth_grid.write ('Revenue - \$ req. for boxes')
    booth_grid.write('$ __________  ----^')

    # Row 6
    booth_grid.write('')
    booth_grid.write ('Typically ~ 10\% for operation Cookie /6 = ')
    booth_grid.write('__________ OpC boxes')




if __name__ == '__main__':

    setup.config_site(page_title="Print Booth Orders",initial_sidebar_state='collapsed',no_header=True)
    # Initialization
    init_ss()

    main()