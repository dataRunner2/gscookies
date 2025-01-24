from json import loads
import streamlit as st
import pandas as pd

import sys
from pathlib import Path
import time
from streamlit import session_state as ss
import extra_streamlit_components as stx
from utils.esutils import esu
from PIL import Image
import re
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)

p = Path.cwd()

class setup:
    def is_admin():
        if ss.username in ['jklemisch','foo_girl']:
            ss.is_admin = True
        else:
            # st.write('You are not listed as an admin, please contact Jennifer')
            ss.is_admin = False

    def config_site(page_title="",initial_sidebar_state='collapsed'):
        
        st.set_page_config(
            page_title = page_title,
            page_icon = "samoas.jpg",
            layout = "wide",
            initial_sidebar_state = initial_sidebar_state
            # menu_items = {"About": "Developed for Girl Scout Troop 43202, by Jennifer Klemisch"}
        )
        # Inject custom CSS to hide the sidebar
        hide_menu_style = """
            <style>
            [data-testid="stSidebarNav"] {
                display: none;
            }
            </style>
        """
        st.markdown(hide_menu_style, unsafe_allow_html=True)
        
        st.header('Troop 43202 Cookie Tracker')
        st.title(page_title)
        sgL = Image.open(Path(p, 'samoas.jpg'))

        if 'username' not in ss:
            # look for a cookie with it
            cookie_manager = stx.CookieManager()
            try:
                cookies = cookie_manager.get_all()
                ss.username = ss.get_all.get("user")
                ss.scout_dat = ss.get_all.get("cookie_sctdat")
                ss.gs_nms = ss.get_all.get("cookie_gs_nms")
                ss.authenticated = ss.get_all.get('auth')
                ss.indices = ss.get_all.get('indices_dict')
                
            except:
                st.write('Can not find user information.  Please login')
                st.page_link(page="Home.py")

        if 'is_admin' not in ss:
            ss.is_admin = False
            if 'username' in ss:
                setup.is_admin()

        st.sidebar.page_link("Home.py", label='Account')
        st.sidebar.page_link('pages/training_reference.py',label='Training Reference')
        st.sidebar.page_link("pages/portal_home.py", label='Dates and Reminders')
        st.sidebar.page_link('pages/girl_orders.py',label='Order Cookies :cookie:')
        st.sidebar.page_link('pages/girl_order_summary.py',label='Order Summary')
        
        st.sidebar.divider()

        if ss.is_admin:   
            # if ss.is_admin: ss.is_admin_pers = ss.is_admin #alighn the admin persistent 
            st.sidebar.write('----- ADMIN ------')
            st.sidebar.page_link('pages/admin_girl_orders_summary.py',label='Girl Summary')
            st.sidebar.page_link('pages/admin_order_management.py',label='Order Management')
            st.sidebar.page_link('pages/admin_print_new_orders.py',label='Print Orders')
            st.sidebar.page_link('pages/admin_receive_money.py',label='Receive Money')

        with open('style.css') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

class apputils:
    def calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc):
        total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
        total_money = total_boxes*6
        return total_boxes, total_money

    def order_view(df):
        df.loc[df.orderReady == True, 'status'] = 'Order Ready to Pickup'
        df.loc[df.orderPickedup == True, 'status'] = 'Order Pickedup'

        col_order = ['orderType','orderId','submit_dt','status',
                     'comments','orderQtyBoxes', 'orderAmount',
                     'Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC']

        view_df=df.loc[:, col_order].copy()
        view_df.rename(columns={'orderType':'Order Type','orderId':'Order Id','status':'Status','comments':'Comments','guardianNm':'Guardian Name','guardianPh':'Guardian Phone','pickupT':'Pickup Date/Time','scoutName':'Scouts Name','orderQtyBoxes':'Qty','orderAmount':'Amt','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Do','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic'},inplace=True)
        view_df['Date'] = pd.to_datetime(view_df['submit_dt']).dt.date
        mv_dt_column = view_df.pop('Date')

        view_df.insert(3, 'Date', mv_dt_column)
        return view_df

    def allorder_view(df):
        df=df.loc[:, ['scoutId','orderType','orderId','submit_dt','orderQtyBoxes', 'orderAmount','status','addEbudde','orderReady','orderPickedup','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','pickupNm','pickupPh','email']]
        df = df.astype({"orderQtyBoxes":"int","orderAmount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'}) #,'addEbudde':'bool','digC_val':'bool'})
        df.rename(inplace=True, columns={'scoutId': 'Scout','orderId':'Order Id','orderQtyBoxes':'Qty','orderAmount':'Amt'})
        df.index.name ="id"
        df['Date'] = pd.to_datetime(df['submit_dt']).dt.date
        df.drop(columns='submit_dt',inplace=True)
        mv_dt_column = df.pop('Date')
        df.insert(3, 'Date', mv_dt_column)
        return df

    def get_all_orders(es):
        all_orders = esu.qry_sql(es, indexnm=ss.indexes['index_orders'])
        # st.write(all_orders)

        all_orders_cln = apputils.allorder_view(all_orders)

        all_orders_cln.loc[all_orders_cln.orderReady == True, 'status'] = 'Order Ready to Pickup'
        all_orders_cln.loc[all_orders_cln.orderPickedup == True, 'status'] = 'Order Pickedup'

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


    def parse_list_string(s):
        # Match strings that look like lists and extract them
        match = re.fullmatch(r"\[(.*)\]", s)
        if match:
            # Split the items in the list by commas, remove whitespace, and return a list
            return [item.strip().strip("'").strip('"') for item in match.group(1).split(',')]
        return [s]  # If not a list string, return it as is

    def flatten_and_parse(nested_list):
        flat_list = []
        for item in nested_list:
            if isinstance(item, str):
                # Check if the string looks like a list and parse it
                flat_list.extend(apputils.parse_list_string(item))  # Flatten the parsed list
            elif isinstance(item, list):
                flat_list.extend(apputils.flatten_and_parse(item))  # Recursive call for actual lists
            else:
                flat_list.append(item)
        return flat_list
    
    def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds a UI on top of a dataframe to let viewers filter columns
        Args:
            df (pd.DataFrame): Original dataframe
        Returns   pd.DataFrame: Filtered dataframe
        """
        # modify = st.checkbox("Add filters")

        # if not modify:
        #     return df

        df = df.copy()
        modification_container = st.container()
        with modification_container:
            to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
            for column in to_filter_columns:
                left, right = st.columns((1, 20))
                left.write("↳")
                # Treat columns with < 10 unique values as categorical
                if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                    user_cat_input = right.multiselect(
                        f"Values for {column}",
                        df[column].unique(),
                        default=list(df[column].unique()),
                    )
                    df = df[df[column].isin(user_cat_input)]
                elif is_numeric_dtype(df[column]):
                    _min = (df[column].min())
                    _max = (df[column].max())
                    step = (_max - _min) / 100
                    user_num_input = right.slider(
                    f"Values for {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                    )
                    df = df[df[column].between(*user_num_input)]
                elif is_datetime64_any_dtype(df[column]):
                    user_date_input = right.date_input(
                        f"Values for {column}",
                        value=(
                            df[column].min(),
                            df[column].max(),
                        ),
                    )
                    if len(user_date_input) == 2:
                        user_date_input = tuple(map(pd.to_datetime, user_date_input))
                        start_date, end_date = user_date_input
                        df = df.loc[df[column].between(start_date, end_date)]
                else:
                    user_text_input = right.text_input(
                        f"Substring or regex in {column}",
                    )
                    if user_text_input:
                        df = df[df[column].astype(str).str.contains(user_text_input)]
            df.loc['Total']= df.sum(numeric_only=True, axis=0)
        return df