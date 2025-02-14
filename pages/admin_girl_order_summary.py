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

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def refresh():
    st.rerun()

def get_all_scts(es):
    all_scout_qrydat = es.search(index = ss.indexes['index_scouts'], size=100, source='scout_details', query={"nested": {"path": "scout_details", "query": {"match_all":{} }}})['hits']['hits']
    all_scout_dat = [sct['_source'].get('scout_details') for sct in all_scout_qrydat if sct['_source'].get('scout_details') is not None]
    ss.all_scout_dat = [entry for sublist in all_scout_dat for entry in sublist].copy()

# Function to apply styles to bottom row of tables
def style_dataframe(dataframe):
    def highlight_bottom_row(row):
        if row.name == "Total":
            return ["font-weight: bold; background-color: #abbaaf; color: black;"] * len(row)
        return [""] * len(row)
    
    return dataframe.style.apply(highlight_bottom_row, axis=1)
    
def main():
    # st.write('---')
    es=get_connected()
    if not ss.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()
    
    # if 'all_scout_dat' not in ss:
    get_all_scts(es)

    admin_gs_nms = [scout['FullName'] for scout in ss.all_scout_dat]
    admin_gs_nms = list(set(admin_gs_nms))
    admin_gs_nms.sort()
    
    # selection box can not default to none because the form defaults will fail. 
    cols = st.columns(2)
    with cols[0]:
        st.selectbox("Select Girl Scout:", admin_gs_nms, key='admin_gsNm')
        selected_sct_dat = [item for item in ss['all_scout_dat'] if item["FullName"] == ss.admin_gsNm][0]
    with cols[1]:
        st.write('') # blank line
        show_sel = st.button(label='Show girl award seletions')
        if show_sel:
            st.write(selected_sct_dat)

    nmId = selected_sct_dat.get('nameId')
    
    ################################## PAGE CONTENT #########################################

    girl_order_qry = f'FROM {ss.indexes["index_orders"]}| WHERE scoutId LIKE """{nmId}""" | LIMIT 500'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=girl_order_qry,
        format="csv")
    
    girl_orders = pd.read_csv(io.StringIO(response.body))
    if not pd.DataFrame(girl_orders).empty:
    
        girl_orders = au.order_view(girl_orders)
        girl_orders.reset_index(inplace=True, drop=True)
        girl_orders.fillna(0)
        girl_ord_md=girl_orders[['Order Id','Order Type','Date','Status','Comments']]

        just_cookies = girl_orders[['Qty','Amt','Adventurefuls','Lemon-Ups','Trefoils','Do-Si-Dos','Samoas',"S'Mores",'Tagalongs','Thin Mint','Toffee Tastic','OpC']].copy()
        # col = just_cookies.pop('Qty')
        # just_cookies.insert(0, col.name, col)
        # col = just_cookies.pop('Amt')
        # just_cookies.insert(0, col.name, col)
        cookie_orders = pd.concat([girl_ord_md, just_cookies], axis=1)
        cookie_totals = cookie_orders[['Qty','Amt']].sum(numeric_only=True)


        # Paper Order Calcs
        paper_orders = cookie_orders[cookie_orders['Order Type']=='Paper Order'].copy()
        paper_orders.loc['Total']= paper_orders.sum(numeric_only=True, axis=0)
        paper_orders = paper_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Dos':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
        styled_papOrds = style_dataframe(paper_orders)
        paperOrder_totals = paper_orders[['Qty','Amt']].iloc[-1]
        

        # Digital Order Calcs
        digital_orders = cookie_orders[cookie_orders['Order Type']=='Digital Cookie Girl Delivery'].copy()
        digital_orders.loc['Total']= digital_orders.sum(numeric_only=True, axis=0)
        digital_orders = digital_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Dos':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
        styled_digOrds = style_dataframe(digital_orders) # Apply styles to the DataFrame
        digitalOrder_totals = digital_orders[['Qty','Amt']].iloc[-1]
        
        # Totals Qty Calcs
        tot_boxes_pending = cookie_orders[cookie_orders['Status']=='Pending'].copy()
        tot_boxes_pending = tot_boxes_pending[['Status','Qty']]
        tot_boxes_pending.loc['Total']= tot_boxes_pending.sum(numeric_only=True, axis=0)
        total_pending_qty = tot_boxes_pending.loc['Total','Qty'].astype('int')

        tot_boxes_ready = cookie_orders[cookie_orders['Status']=='Order Ready for Pickup'].copy()
        tot_boxes_ready = tot_boxes_ready[['Status','Qty']]
        tot_boxes_ready.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
        total_ready_qty = tot_boxes_ready.loc['Total','Qty'].astype('int')

        tot_boxes = cookie_orders[cookie_orders['Status']=='Picked Up'].copy()
        tot_boxes = tot_boxes[['Status','Qty']]
        tot_boxes.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
        total_completed_qty = tot_boxes_ready.loc['Total','Qty'].astype('int')

        
        # Funds Received
        # All money received is for paper orders
        girl_money_qry = f'FROM {ss.indexes["index_money"]}| WHERE scoutId LIKE """{nmId}""" | LIMIT 500'
        # st.write(girl_order_qry)
        response = es.esql.query(
            query=girl_money_qry,
            format="csv")
        deposits_received_dat = pd.read_csv(io.StringIO(response.body))
        if len(deposits_received_dat)>0:
            deposits_received_dat = deposits_received_dat.fillna(0)
            deposits_received_df = deposits_received_dat[['amtReceived_dt','amountReceived','orderRef']].copy()
            deposits_received_df = deposits_received_df.astype({"amountReceived": 'int'})
            deposits_received_df.loc['Total']= deposits_received_df.sum(numeric_only=True, axis=0)
            styled_received = style_dataframe(deposits_received_df)
            moneyRec_totals = deposits_received_df.loc['Total','amountReceived']
        else:
            deposits_received_df = pd.DataFrame({'amountReceived': [0]})
            styled_received = style_dataframe(deposits_received_df)
            moneyRec_totals = 0
        

        # Display Tables and Graphics
        st.divider()
        st.subheader("Paper Orders")
        st.dataframe(styled_papOrds, use_container_width=True,
                    column_config={
                        "Amt": st.column_config.NumberColumn(
                            "Amt.",
                            format="$%d",
                        ),
                        "Date": st.column_config.DateColumn(
                            "Order Date",
                            format="MM-DD-YY",
                        )})
        total_due_po = paper_orders.loc['Total','Amt']
        st.subheader('Paper Order Funds Deposited')
        
        st.dataframe(styled_received,
                column_config={
                    "amountReceived": st.column_config.NumberColumn(
                        "Amt.",
                        format="$%d",
                    ),
                    "amtReceived_dt": st.column_config.DateColumn(
                        "Date Received",
                        format="MM-DD-YY",
                    ),
                    "orderRef": st.column_config.TextColumn(
                        "Order Ref"
                    ),
                    })

        # metric cards
       
        metric_paper = grid([2,.15,2,.25,2,.25,2], vertical_align="center")
        # Row 1
        metric_paper.metric(label="Total Paper Order Boxes", value=paperOrder_totals['Qty'])
        metric_paper.write(':')
        metric_paper.metric(label="Total Amt Due for Paper Orders",value=f"${paperOrder_totals['Amt']}")
        metric_paper.write('--')
        metric_paper.metric(label="Total Amount Received", value=f"${moneyRec_totals}")
        metric_paper.write('=')
        metric_paper.metric(label="Total Amount Owed", value=f"${paperOrder_totals['Amt'] - moneyRec_totals}")
        style_metric_cards()

        st.divider()
        st.subheader("Digital Orders")
        st.dataframe(styled_digOrds, use_container_width=True,
                    column_config={
                        "Amt": st.column_config.NumberColumn(
                            "Order Amt.",
                            format="$%d",
                        ),
                        "Date": st.column_config.DateColumn(
                            "Order Date",
                            format="MM-DD-YY",
                        )})

        st.subheader("Payments received for Digital Cookie are not shown")
        metric_digital = grid([2,.15,2,.25,2,.25,2], vertical_align="center")
        # Row 1
        metric_digital.metric(label="Total Digital Cookie Girl Delivery Boxes", value=digitalOrder_totals['Qty'])
        style_metric_cards()

        st.divider()
   
        # Status Metrics Cards
        metric_grid = grid(4, vertical_align="center")
        # Row 1
        metric_grid.metric(label='Total Ordered Boxes', value=cookie_totals.loc['Qty']) 
        metric_grid.metric(label='Pending Boxes', value=total_pending_qty)
        metric_grid.metric(label='Boxes Ready for Pickup', value=total_ready_qty)
        metric_grid.metric(label='Boxes Picked Up', value=total_completed_qty)
        

    else:
        st.warning('You have not submitted any orders yet')


if __name__ == '__main__':

    setup.config_site(page_title="Admin Girl Order Summary",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()