from json import loads
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import time
from streamlit import session_state as ss
from utils.esutils import esu
from PIL import Image

p = Path.cwd()

class setup:
    def is_admin():
        if ss.username in ['jklemisch','jbutler']:
            ss.is_admin = True
        else:
            st.write('You are not listed as an admin, please contact Jennifer')
            ss.is_admin = False

    def config_site(page_title="",initial_sidebar_state='collapsed'):
        
        st.set_page_config(
            page_title = page_title,
            page_icon = "samoas.jpg",
            layout = "wide",
            initial_sidebar_state = initial_sidebar_state
            # menu_items = {"About": "Developed for Girl Scout Troop 43202, by Jennifer Klemisch"}
        )

        st.title('Troop 43202 Cookie Season')
        sgL = Image.open(Path(p, 'samoas.jpg'))

        st.sidebar.page_link("pages/parent_home.py", label='Cookie Portal')
        st.divider()
        if 'is_admin' not in ss:
            ss.is_admin = False

        if ss.is_admin:   
            if ss.is_admin: ss.is_admin_pers = ss.is_admin #alighn the admin persistent 
            st.sidebar.write('----- ADMIN ------')
            st.sidebar.page_link('pages/order_management',label='Order Management')
            st.sidebar.page_link('pages/print_new_orders',label='Print Orders')
            st.sidebar.page_link('pages/receive_money',label='Receive Money')
        with open('style.css') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

class apputils:
    def order_view(df):
        col_order = ['ScoutName','OrderType','submit_dt','status','comments','order_qty_boxes', 'order_amount','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC']

        view_df=df.loc[:, col_order].copy()

        view_df.rename(columns={'OrderType':'Order Type','comments':'Comments','guardianNm':'Guardian Name','guardianPh':'Guardian Phone','PickupT':'Pickup Date/Time','ScoutName':'Scouts Name','order_qty_boxes':'Qty','order_amount':'Amt','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Do','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic','OpC':'Operation Cookies'},inplace=True)
        view_df['Date'] = pd.to_datetime(view_df['submit_dt']).dt.date
        mv_dt_column = view_df.pop('Date')

        view_df.insert(3, 'Date', mv_dt_column)
        return view_df

    def allorder_view(df):
        df=df.loc[:, ['ScoutName','OrderType','submit_dt','order_qty_boxes', 'order_amount','status','inEbudde','order_ready','order_pickedup','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','PickupNm','PickupPh','Email']]
        df = df.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'}) #,'addEbudde':'bool','digC_val':'bool'})
        df.rename(inplace=True, columns={'ScoutName': 'Scout','order_qty_boxes':'Qty','order_amount':'Amt'})
        df.index.name ="id"
        df['Date'] = pd.to_datetime(df['submit_dt']).dt.date
        df.drop(columns='submit_dt',inplace=True)
        mv_dt_column = df.pop('Date')
        df.insert(3, 'Date', mv_dt_column)
        return df

    def get_all_orders():
        # orders = ed.DataFrame(es, es_index_pattern=index_orders)
        # orders = ed.eland_to_pandas(orders)
        all_orders = pd.DataFrame()

        # all_orders = pd.DataFrame(orders)
        all_orders_cln = apputils.allorder_view(all_orders)

        all_orders_cln.loc[all_orders_cln.order_ready == True, 'status'] = 'Order Ready to Pickup'
        all_orders_cln.loc[all_orders_cln.order_pickedup == True, 'status'] = 'Order Pickedup'

        if "all_orders" not in st.session_state:
            st.session_state['all_orders'] = all_orders
        return all_orders, all_orders_cln

    def update_es(es, update_index, edited_content, all_orders):
        edited_allorders = st.session_state['edited_dat']['edited_rows']
        st.write('EDITED ROWS:')
        st.markdown(f'Initial Edited Rows: {edited_allorders}')

        for key, value in edited_allorders.items():
            new_key = all_orders.index[key]

            st.write(f'Updated Values to Submit to ES: {new_key}:{value}')
            resp = es.update(index=update_index, id=new_key, doc=value,)
            time.sleep(1)
        st.toast("Database updated with changes")
        apputils.get_all_orders()  # this should updadte the session state with all orders

