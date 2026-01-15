from json import loads
import streamlit as st
import pandas as pd
import numpy as np
import io
from pathlib import Path
import time
from streamlit import session_state as ss
import extra_streamlit_components as stx
from utils.esutils import esu
from PIL import Image
import re
from pandas.api.types import is_categorical_dtype, is_numeric_dtype, is_datetime64_any_dtype
from utils.db_utils import fetch_all, fetch_one, execute_sql
import random


p = Path.cwd()

class setup:
    def check_admin():
        st.warning('YOU ARE AN ADMIN')
        if ss.username in ['jklemisch','shawna']: #st.secrets['general']['super_admin']:
            ss.super_admin = True
        else:
            # st.write('You are not listed as an admin, please contact Jennifer')
            ss.is_admin = False
            ss.super_admin = False
    

    def config_site(page_title="",initial_sidebar_state='collapsed',no_header=False):
        if no_header:
            page_title=''
        else:
            page_title = page_title
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
            ss.super_admin = False
            if 'username' in ss:
                setup.is_admin()

        st.sidebar.page_link("Home.py", label='Account')
        st.sidebar.page_link('pages/training_reference.py',label='Training & Dates')
        st.sidebar.page_link('pages/add_scouts.py',label='Add or Modify Scout Info')
        st.sidebar.page_link('pages/orders_overview.py',label='Troop Order Overview')  # all and admin content
        st.sidebar.page_link('pages/girl_order_summary.py',label='Order Summary')
        st.sidebar.page_link('pages/girl_orders.py',label='Order Cookies :cookie:')
        st.sidebar.page_link('pages/delete_order.py',label='Delete Cookie Order')
        st.sidebar.page_link('pages/booth.py',label='Booth Entry')
        
        
        st.sidebar.divider()

        if ss.is_admin:   
            # if ss.is_admin: ss.is_admin_pers = ss.is_admin #alighn the admin persistent 
            st.sidebar.write('----- ADMIN ------')
            st.sidebar.page_link('pages/admin_ebudde_summary.py',label='Ebudde Summary')
            st.sidebar.page_link('pages/admin_girl_order_summary.py',label='Girl Summary')
            st.sidebar.page_link('pages/admin_order_management.py',label='Order Management')
            st.sidebar.page_link('pages/admin_print_new_orders.py',label='Print Orders')
            st.sidebar.page_link('pages/admin_receive_money.py',label='Receive Money')
            st.sidebar.page_link('pages/admin_add_inventory.py',label='Add Inventory')
            st.sidebar.page_link('pages/admin_import_DOC_orders.py',label='Import DOC')
            st.sidebar.page_link('pages/admin_booths.py',label='Booth Admin')

        if ss.super_admin:
            # st.sidebar.page_link('pages/admin_show_session.py',label='Manage Backups & SS')
            st.sidebar.page_link('pages/move_es_data.py',label='Move Data')

        st.sidebar.divider()
        if st.sidebar.button("Log out"):
            ss.clear()
            st.rerun()

        with open('style.css') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

class apputils:
    def calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc):
        total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
        total_money = total_boxes*6
        return total_boxes, total_money
    
    def add_totals_row(df, cols_to_total):
        # Function to add a totals row
        total_columns = cols_to_total #['orderAmount','orderQtyBoxes', 'Adf', 'LmUp', 'Tre', 'DSD', 'Sam', 'Tags', 'Tmint', 'Smr', 'Toff', 'OpC']
        totals = {col: df[col].sum() for col in total_columns} # Calculate totals for specified columns
        # Create a new DataFrame for the totals row
        totals_df = pd.DataFrame([totals], index=["Total"]).astype(np.int64)  # Pass the index as a list
        
        df_tots = pd.concat([df, totals_df])
        # Append the totals row to the original DataFrame
        # st.write(totals_df)
        return df_tots
    
    def just_renamer(df,just_cookies=False):
        if just_cookies:
            df.rename(columns={'Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Dos','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic'},inplace=True)
        else:
            df.rename(columns={'orderType':'Order Type','orderId':'Order Id','status':'Status','comments':'Comments','guardianNm':'Guardian Name','guardianPh':'Guardian Phone','pickupT':'Pickup Date/Time','scoutName':'Scouts Name','orderQtyBoxes':'Qty','orderAmount':'Amt','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Dos','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic'},inplace=True)
        return df
    
    def order_view(df):
        df.loc[df.orderReady == True, 'status'] = 'Order Ready to Pickup'
        df.loc[df.orderPickedup == True, 'status'] = 'Order Pickedup'

        col_order = ['orderType','orderId','submit_dt','status',
                     'comments','orderQtyBoxes', 'orderAmount',
                     'Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC']

        view_df=df.loc[:, col_order].copy()
        view_df.rename(columns={'orderType':'Order Type','orderId':'Order Id','status':'Status','comments':'Comments','guardianNm':'Guardian Name','guardianPh':'Guardian Phone','pickupT':'Pickup Date/Time','scoutName':'Scouts Name','orderQtyBoxes':'Qty','orderAmount':'Amt','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Dos','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic'},inplace=True)
        view_df['Date'] = pd.to_datetime(view_df['submit_dt']).dt.date
        mv_dt_column = view_df.pop('Date')

        view_df.insert(3, 'Date', mv_dt_column)
        return view_df

    def allorder_view(df):
        # This is used for admin views so the names are not changed to friendly names
        # Don't renanme columns - else when they write back to Elastic they don't match
        df=df.loc[:, ['scoutId','scoutName','orderType','orderId','submit_dt','orderQtyBoxes', 'orderAmount','status','addEbudde','orderReady','orderPickedup','initialOrder','comments','digC_val','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','pickupNm','pickupPh','email']]
        df = df.astype({"orderQtyBoxes":"int","orderAmount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'}) #,'addEbudde':'bool','digC_val':'bool'})
        df.index.name ="id"
        df['Date'] = pd.to_datetime(df['submit_dt']).dt.date
        df.drop(columns='submit_dt',inplace=True)
        mv_dt_column = df.pop('Date')
        df.insert(3, 'Date', mv_dt_column)
        return df

    
    def parse_list_string(s):
        # Match strings that look like lists and extract them
        match = re.fullmatch(r"\[(.*)\]", s)
        if match:
            # Split the items in the list by commas, remove whitespace, and return a list
            return [item.strip().strip("'").strip('"') for item in match.group(1).split(',')]
        return [s]  # If not a list string, return it as is

    def flatten_dict(d):
        flat_dict = {}
        for k, v in d.items():
            if isinstance(v, dict):
                # Flatten the nested dictionary and merge the result
                for sub_k, sub_v in v.items():
                    flat_dict[f"{k}_{sub_k}"] = sub_v
            else:
                flat_dict[k] = v
        return flat_dict
    
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

        filtered_df = df.copy()
        modification_container = st.container()
       
        with modification_container:
            to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
            for column in to_filter_columns:
                left, right = st.columns((1, 20))
                left.write("↳")
                
                # Treat columns with <10 unique values as categorical
                if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                    user_cat_input = right.multiselect(
                        f"Values for {column}",
                        df[column].unique(),
                        default=list(df[column].unique()),
                    )
                    filtered_df = filtered_df[filtered_df[column].isin(user_cat_input)]
                
                # Numeric columns
                elif is_numeric_dtype(df[column]):
                    _min, _max = df[column].min(), df[column].max()
                    step = max((_max - _min) / 100, 0.01)
                    user_num_input = right.slider(
                        f"Values for {column}",
                        min_value=_min,
                        max_value=_max,
                        value=(_min, _max),
                        step=step,
                    )
                    filtered_df = filtered_df[filtered_df[column].between(*user_num_input)]
                
                # Datetime columns
                elif is_datetime64_any_dtype(df[column]):
                    user_date_input = right.date_input(
                        f"Values for {column}",
                        value=(df[column].min(), df[column].max()),
                    )
                    if len(user_date_input) == 2:
                        start_date, end_date = tuple(map(pd.to_datetime, user_date_input))
                        filtered_df = filtered_df.loc[filtered_df[column].between(start_date, end_date)]
                
                # Text columns
                else:
                    user_text_input = right.text_input(
                        f"Substring or regex in {column}",
                    )
                    if user_text_input:
                        try:
                            filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(user_text_input, na=False)]
                        except Exception as e:
                            st.warning(f"Invalid regex: {e}")
            return filtered_df
    

    def send_reset_email(email: str, code: str):
        # plug into SendGrid / SES later
        st.write(f"[EMAIL to {email}] Reset code: {code}")


    def send_reset_sms(phone: str, code: str):
        # plug into Twilio later
        st.write(f"[SMS to {phone}] Reset code: {code}")



def cookie_celebration(
    message="🍪 Cookies coming your way! 🍪",
    num_items=20
):
    emojis = ["🍪", "🍪", "🍪", "🎉", "✨"]

    items = "".join(
        f"<span class='float'>{random.choice(emojis)}</span>"
        for _ in range(num_items)
    )

    html = f"""
    <style>
    .container {{
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        pointer-events: none;
        z-index: 9999;
        text-align: center;
    }}

    .float {{
        position: relative;
        display: inline-block;
        font-size: 2.2rem;
        animation: rise 4s ease-in forwards;
        margin: 0 6px;
    }}

    @keyframes rise {{
        0% {{ transform: translateY(0); opacity: 1; }}
        100% {{ transform: translateY(-400px); opacity: 0; }}
    }}
    </style>

    <div class="container">
        <div style="font-size:1.4rem;font-weight:600;margin-bottom:12px;">
            {message}
        </div>
        {items}
    </div>
    """

    st.components.v1.html(html, height=0)
