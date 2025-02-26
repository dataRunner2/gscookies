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

def highlight_total(row):
    if row["Cookie Variety"] == "Total":
        return ["background-color: lightgray; color: black; font-weight: bold"] * len(row)
    return [""] * len(row)

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
        .stApp {
            padding-top: 10px !important; /* Adjust padding */
            }
            .st-emotion-cache-1v0mbdj {  /* Adjusts main container */
                padding-top: 0px !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
    
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
        # Add a new row with "Total" and sum of "starting qty"
        booth_order_trans.loc[len(booth_order_trans)] = ["Total", booth_order_trans["Starting Qty"].sum()]

        booth_order_trans[['Ending Qty','Total Sold (starting qty - ending qty)','Optional notes or tally']] = ''
        # st.table(booth_order_trans)
        # Apply left-alignment styling
        df_styled = booth_order_trans.style.apply(highlight_total, axis=1).set_properties(**{
            'text-align': 'left',
            'font-size': '20px',
            'padding-right': '100px',
            'color': 'blue'  # Corrected font color property
        }).hide(axis="index")  # Hide index
        st.markdown(df_styled.to_html(index=False), unsafe_allow_html=True)

        # Display styled DataFrame
        # # st.dataframe(df_styled)
        # st.dataframe(booth_order_trans.style.set_properties(**{
        #     'text-align': 'left',
        #     'font-size': '20px'}),use_container_width=True, hide_index=True)
        

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
   
    sign_row = st.columns([.35,.6])
    sign_row[0].write('')
    sign_row[0].write('Outgoing signiture: ________________________________')
    sign_row[1].write('')
    sign_row[1].write('Starting petty cash: $_______________')
    st.divider()
    calcs = st.columns([.4,.4,.2])
    with calcs[0]:
        booth_grid = grid([.4,.6],[.4,.6],[1],[.5,.5],[1],[1], vertical_align="center")
    
    # Row 1
    booth_grid.write('Finish Cash')
    booth_grid.write('  $ ____________')

    # Row 2
    booth_grid.write('Total Credit Card Sales')
    booth_grid.write('\+ $ ___________')
    
    booth_grid.write('==========================')
    # Row 3
    booth_grid.write('**Ending Money = Cash + Credit**')
    booth_grid.write('$ __________')

    # Row 4 Notes
    booth_grid.write('---')
    booth_grid.markdown('\nNotes:  \nGet the report from square click reports, filter for today and select your booth.  It will give you the total.  \n  \n A sealed case _always_ has 12 boxes of cookies.  ')


    with calcs[1]:
        right_grid = grid([.6,.4],[.6,.4],[.6,.4],[.6,.4],[.6,.4], vertical_align="center")
    
    # Row R1
    right_grid.write('(1) **Ending Money**')
    right_grid.write('$ __________')

    right_grid.write('(2) Starting Cash (typ. $100)')
    right_grid.write(' $ __________')

    # Row R2
    right_grid.write('(3) **Revenue** = Line (1) - Line (2)')
    right_grid.write('$ __________')

    # Row R3 
    right_grid.write('(4) Total # Sold Boxes sold * $6')
    right_grid.write('$ __________')

    # Row R4
    right_grid.write ('(5) Op C $$ = Line (3) - Line (4)')
    right_grid.write('$ __________')

    # Row R5
    right_grid.write ('(6) \# OpC (Donation) boxes = Line (5) / \$6 ')
    right_grid.write('________ boxes')




if __name__ == '__main__':

    setup.config_site(page_title="Print Booth Orders",initial_sidebar_state='collapsed',no_header=True)
    # Initialization
    init_ss()

    main()