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

    st.write("This page shows the orders for delivered (not DC shipped orders) for our entire troop!  Wow that's a lot of cookies!")
    all_order_qry = f'FROM {ss.indexes["index_orders"]} | LIMIT 1000'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=all_order_qry,
        format="csv")
    
    all_orders = pd.read_csv(io.StringIO(response.body))
    
    all_orders_fmt = au.order_view(all_orders)
    all_orders_fmt.reset_index(inplace=True, drop=True)
    all_orders_fmt.fillna(0)
    all_orders_fmt = all_orders_fmt.astype({"Amt": 'int', "Qty": 'int', 'Adventurefuls':'int','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Dos':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
    all_ord_md=all_orders_fmt[['Order Type','Status','Qty','Amt','Adventurefuls','Lemon-Ups','Trefoils','Do-Si-Dos','Samoas',"S'Mores",'Tagalongs','Thin Mint','Toffee Tastic','OpC']].copy()
    cookie_totals = all_ord_md[['Qty','Amt']].sum(numeric_only=True)


    # Paper Order Calcs
    paper_orders = all_ord_md[all_ord_md['Order Type']=='Paper Order'].copy()
    paper_orders.loc['Total']= paper_orders.sum(numeric_only=True, axis=0)
    paper_orders = paper_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Dos':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
    styled_papOrds = style_dataframe(paper_orders)
    paperOrder_totals = paper_orders[['Qty','Amt']].iloc[-1]
    

    # Digital Order Calcs
    digital_orders = all_ord_md[all_ord_md['Order Type']=='Digital Cookie Girl Delivery'].copy()
    digital_orders.loc['Total']= digital_orders.sum(numeric_only=True, axis=0)
    digital_orders = digital_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Dos':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','OpC':'int64'})
    styled_digOrds = style_dataframe(digital_orders) # Apply styles to the DataFrame
    digitalOrder_totals = digital_orders[['Qty','Amt']].iloc[-1]
    
    # Totals Qty Calcs
    tot_boxes_pending = all_ord_md[all_ord_md['Status']=='Pending'].copy()
    tot_boxes_pending = tot_boxes_pending[['Status','Qty']]
    tot_boxes_pending.loc['Total']= tot_boxes_pending.sum(numeric_only=True, axis=0)
    total_pending_qty = tot_boxes_pending.loc['Total','Qty'].astype('int')

    tot_boxes_ready = all_ord_md[all_ord_md['Status']=='Order Ready for Pickup'].copy()
    tot_boxes_ready = tot_boxes_ready[['Status','Qty']]
    tot_boxes_ready.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
    total_ready_qty = tot_boxes_ready.loc['Total','Qty'].astype('int')

    tot_boxes = all_ord_md[all_ord_md['Status']=='Picked Up'].copy()
    tot_boxes = tot_boxes[['Status','Qty']]
    tot_boxes.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
    total_completed_qty = tot_boxes_ready.loc['Total','Qty'].astype('int')

    
    # Funds Received
    # All money received is for paper orders
    girl_money_qry = f'FROM {ss.indexes["index_money"]}| LIMIT 1000'
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
    
    # Inventory
    inventory_qry = f"FROM {ss.indexes['index_inventory']} | LIMIT 1000"
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=inventory_qry,
        format="csv")
    # st.write(response)
    all_inventory_dat = pd.read_csv(io.StringIO(response.body))
    # st.write(all_inventory_dat)
    sum_inventory_boxes_sum = all_inventory_dat.sum(numeric_only=True, axis=0).sum()
    # st.write(sum_inventory_boxes_sum)
    all_inventory = au.just_renamer(all_inventory_dat)
    all_inventory.loc['Total']= all_inventory.sum(axis=0) # umeric_only=True,
    # sum_inventory_boxes = all_inventory.loc['Total'].iloc[:9] # .sum(numeric_only=True, axis=0)


    # Display Tables and Graphics
    st.divider()

    if ss.is_admin:
        st.subheader("Paper Orders")
        # metric cards for paper Orders - ADMIN
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

        st.subheader("Payments received for Digital Cookie are not shown")
        metric_digital = grid([2,.15,2,.25,2,.25,2], vertical_align="center")
        metric_digital.metric(label="Total Digital Cookie Girl Delivery Boxes", value=digitalOrder_totals['Qty'])
        style_metric_cards()
    else:
        metric_paper_dig = grid(4, vertical_align="top")
        metric_paper_dig.metric(label="Total Paper Order Boxes", value=paperOrder_totals['Qty'])
        metric_paper_dig.metric(label="Total Digital Cookie Girl Delivery Boxes", value=digitalOrder_totals['Qty'])

    st.divider()

    # Status Metrics Cards
    metric_grid = grid(4, vertical_align="center")
    # Row 1
    metric_grid.metric(label='Total Ordered Boxes', value=cookie_totals.loc['Qty']) 
    metric_grid.metric(label='Pending Boxes', value=total_pending_qty)
    metric_grid.metric(label='Boxes Ready for Pickup', value=total_ready_qty)
    metric_grid.metric(label='Boxes Picked Up', value=total_completed_qty)
    
    st.divider()
    st.header('Total Orders by Cookie Type')
    type_totals = all_ord_md.copy()
    type_totals.loc['Total']= type_totals.sum(numeric_only=True, axis=0)
    # st.write(type_totals)
    metric_paper = grid(3,9, vertical_align="center") # 4 Rows of 3 columns each
    metric_paper.metric(label="Total Boxes", value=type_totals.loc['Total','Qty'].astype('int'))
    metric_paper.metric(label="Total $", value=type_totals.loc['Total','Amt'].astype('int'))
    metric_paper.metric(label="Oper. Cookie", value=type_totals.loc['Total','OpC'].astype('int'))
    metric_paper.metric(label="Adventurefuls", value=type_totals.loc['Total','Adventurefuls'].astype('int'))
    metric_paper.metric(label="Lemon-Ups", value=type_totals.loc['Total','Lemon-Ups'].astype('int'))
    metric_paper.metric(label="Trefoils", value=type_totals.loc['Total','Trefoils'].astype('int'))
    metric_paper.metric(label="Do-Si-Dos", value=type_totals.loc['Total','Do-Si-Dos'].astype('int'))
    metric_paper.metric(label="Samoas", value=type_totals.loc['Total','Samoas'].astype('int'))
    metric_paper.metric(label="S'Mores", value=type_totals.loc['Total',"S'Mores"].astype('int'))
    metric_paper.metric(label="Tagalongs", value=type_totals.loc['Total','Tagalongs'].astype('int'))
    metric_paper.metric(label="Thin Mint", value=type_totals.loc['Total','Thin Mint'].astype('int'))
    metric_paper.metric(label="Toffee Tastic", value=type_totals.loc['Total','Toffee Tastic'].astype('int'))
    
    style_metric_cards()

    if ss.is_admin:
        st.divider()
        st.header('~ ~ Additional Metrics for Admins ~ ~')
        # Inventory #'s
        st.subheader('Received Inventory')
        metric_inventory = grid(2,9, vertical_align="center") # 4 Rows of 3 columns each
        metric_inventory.metric(label="Total Boxes", value= sum_inventory_boxes_sum.astype('int'))
        metric_inventory.metric(label="Total $ Due", value= sum_inventory_boxes_sum*6)
    
        metric_inventory.metric(label="Adventurefuls", value=all_inventory.loc['Total','Adventurefuls'].astype('int'))
        metric_inventory.metric(label="Lemon-Ups", value=all_inventory.loc['Total','Lemon-Ups'].astype('int'))
        metric_inventory.metric(label="Trefoils", value=all_inventory.loc['Total','Trefoils'].astype('int'))
        metric_inventory.metric(label="Do-Si-Dos", value=all_inventory.loc['Total','Do-Si-Dos'].astype('int'))
        metric_inventory.metric(label="Samoas", value=all_inventory.loc['Total','Samoas'].astype('int'))
        metric_inventory.metric(label="S'Mores", value=all_inventory.loc['Total',"S'Mores"].astype('int'))
        metric_inventory.metric(label="Tagalongs", value=all_inventory.loc['Total','Tagalongs'].astype('int'))
        metric_inventory.metric(label="Thin Mint", value=all_inventory.loc['Total','Thin Mint'].astype('int'))
        metric_inventory.metric(label="Toffee Tastic", value=all_inventory.loc['Total','Toffee Tastic'].astype('int'))
        
        # Inventory #'s
        st.subheader('Inventory - Orders = Outstanding Inventory')
        metric_inventory = grid(2,9, vertical_align="center") # 4 Rows of 3 columns each
        metric_inventory.metric(label="Delta Total Boxes", value= sum_inventory_boxes_sum.astype('int')-type_totals.loc['Total','Qty'])
        metric_inventory.metric(label="Delta Total $ Due", value= sum_inventory_boxes_sum*6 - type_totals.loc['Total','Amt'].astype('int'))
    
        metric_inventory.metric(label="Adventurefuls", value=all_inventory.loc['Total','Adventurefuls'].astype('int') - type_totals.loc['Total','Adventurefuls'].astype('int'))
        metric_inventory.metric(label="Lemon-Ups", value=all_inventory.loc['Total','Lemon-Ups'].astype('int')-type_totals.loc['Total','Lemon-Ups'].astype('int'))
        metric_inventory.metric(label="Trefoils", value=all_inventory.loc['Total','Trefoils'].astype('int')-type_totals.loc['Total','Trefoils'].astype('int'))
        metric_inventory.metric(label="Do-Si-Dos", value=all_inventory.loc['Total','Do-Si-Dos'].astype('int')-type_totals.loc['Total','Do-Si-Dos'].astype('int'))
        metric_inventory.metric(label="Samoas", value=all_inventory.loc['Total','Samoas'].astype('int')-type_totals.loc['Total','Samoas'].astype('int'))
        metric_inventory.metric(label="S'Mores", value=all_inventory.loc['Total',"S'Mores"].astype('int')-type_totals.loc['Total',"S'Mores"].astype('int'))
        metric_inventory.metric(label="Tagalongs", value=all_inventory.loc['Total','Tagalongs'].astype('int')-type_totals.loc['Total','Tagalongs'].astype('int'))
        metric_inventory.metric(label="Thin Mint", value=all_inventory.loc['Total','Thin Mint'].astype('int')-type_totals.loc['Total','Thin Mint'].astype('int'))
        metric_inventory.metric(label="Toffee Tastic", value=all_inventory.loc['Total','Toffee Tastic'].astype('int')-type_totals.loc['Total','Toffee Tastic'].astype('int'))
        
        # % of Inventory
        metric_inventory = grid(9, vertical_align="center")
        st.write('At the end of cookies we want these to be Zero')
        metric_inventory.metric(label="% Adv", value=f"{(all_inventory.loc['Total','Adventurefuls'].astype('int') - type_totals.loc['Total','Adventurefuls'].astype('int'))/all_inventory.loc['Total','Adventurefuls'].astype('int'):.2f}")
        metric_inventory.metric(label="% Lemon-Ups", value=f"{(all_inventory.loc['Total','Lemon-Ups'].astype('int')-type_totals.loc['Total','Lemon-Ups'].astype('int'))/all_inventory.loc['Total','Lemon-Ups'].astype('int'):.2f}")
        metric_inventory.metric(label="% Trefoils", value=f"{(all_inventory.loc['Total','Trefoils'].astype('int')-type_totals.loc['Total','Trefoils'].astype('int'))/all_inventory.loc['Total','Trefoils'].astype('int'):.2f}")
        metric_inventory.metric(label="% Do-Si-Dos", value=f"{(all_inventory.loc['Total','Do-Si-Dos'].astype('int')-type_totals.loc['Total','Do-Si-Dos'].astype('int'))/all_inventory.loc['Total','Do-Si-Dos'].astype('int'):.2f}")
        metric_inventory.metric(label="% Samoas", value=f"{(all_inventory.loc['Total','Samoas'].astype('int')-type_totals.loc['Total','Samoas'].astype('int'))/all_inventory.loc['Total','Samoas'].astype('int'):.2f}")
        metric_inventory.metric(label="% S'Mores", value=f"""{(all_inventory.loc['Total',"S'Mores"].astype('int')-type_totals.loc['Total',"S'Mores"].astype('int'))/all_inventory.loc['Total',"S'Mores"].astype('int'):.2f}""")
        metric_inventory.metric(label="% Tagalongs", value=f"{(all_inventory.loc['Total','Tagalongs'].astype('int')-type_totals.loc['Total','Tagalongs'].astype('int'))/all_inventory.loc['Total','Tagalongs'].astype('int'):.2f}")
        metric_inventory.metric(label="% Thin Mint", value=f"{(all_inventory.loc['Total','Thin Mint'].astype('int')-type_totals.loc['Total','Thin Mint'].astype('int'))/all_inventory.loc['Total','Thin Mint'].astype('int'):.2f}")
        metric_inventory.metric(label="% Toffee Tastic", value=f"{(all_inventory.loc['Total','Toffee Tastic'].astype('int')-type_totals.loc['Total','Toffee Tastic'].astype('int'))/all_inventory.loc['Total','Toffee Tastic'].astype('int'):.2f}")
        

if __name__ == '__main__':

    setup.config_site(page_title="Troop Order Overview",initial_sidebar_state='expanded')
    # Initialization
    init_ss()
    main()