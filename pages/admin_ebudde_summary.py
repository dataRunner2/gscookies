import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from datetime import datetime
from decimal import Decimal
from utils.app_utils import setup 
from utils.db_utils import require_admin, fetch_all

def decimal_sum(series):
    return sum(Decimal(str(x)) for x in series.fillna(0))

def alternate_rows(df):
    return ['background-color:#f2f2f2' if i % 2 != 0 else '' for i in range(len(df))]
    
def main():
    require_admin()
    
    current_year = datetime.now().year

    # Get order data with cookie quantities aggregated by scout and order type
    order_data = fetch_all("""
        SELECT 
            o.scout_id as "scoutId",
            s.first_name || ' ' || s.last_name as "scoutName",
            o.order_type as "orderType",
            SUM(CASE WHEN oi.cookie_code = 'ADV' THEN oi.quantity ELSE 0 END) as "ADV",
            SUM(CASE WHEN oi.cookie_code = 'LEM' THEN oi.quantity ELSE 0 END) as "LEM",
            SUM(CASE WHEN oi.cookie_code = 'TRE' THEN oi.quantity ELSE 0 END) as "TRE",
            SUM(CASE WHEN oi.cookie_code = 'DSD' THEN oi.quantity ELSE 0 END) as "DSD",
            SUM(CASE WHEN oi.cookie_code = 'SAM' THEN oi.quantity ELSE 0 END) as "SAM",
            SUM(CASE WHEN oi.cookie_code = 'TAG' THEN oi.quantity ELSE 0 END) as "TAG",
            SUM(CASE WHEN oi.cookie_code = 'TM' THEN oi.quantity ELSE 0 END) as "TM",
            SUM(CASE WHEN oi.cookie_code = 'EXP' THEN oi.quantity ELSE 0 END) as "EXP",
            SUM(CASE WHEN oi.cookie_code = 'TOF' THEN oi.quantity ELSE 0 END) as "TOF",
            SUM(CASE WHEN oi.cookie_code = 'DON' THEN oi.quantity ELSE 0 END) as "DON",
            SUM(oi.quantity) as "QTY",
            SUM(o.order_amount) as "TotalAmt"
        FROM cookies_app.orders o
        LEFT JOIN cookies_app.order_items oi ON o.order_id = oi.order_id
        LEFT JOIN cookies_app.scouts s ON o.scout_id = s.scout_id
        WHERE o.program_year = :year
          AND o.order_type IN ('Paper', 'Digital')
        GROUP BY o.scout_id, s.first_name, s.last_name, o.order_type
        ORDER BY s.first_name, s.last_name, o.order_type
    """, {"year": current_year})
    
    all_orders_dat = pd.DataFrame(order_data)
    
    if all_orders_dat.empty:
        st.info("No order data found for this year.")
        st.stop()

    # Get money received data aggregated by scout (Paper orders only)
    money_data = fetch_all("""
        SELECT 
            o.scout_id as "scoutId",
            o.order_type as "orderType",
            COALESCE(SUM(ml.amount), 0) as "AmtReceived"
        FROM cookies_app.orders o
        LEFT JOIN cookies_app.money_ledger ml ON o.order_id = ml.related_order_id
        WHERE o.program_year = :year
          AND o.order_type = 'Paper'
        GROUP BY o.scout_id, o.order_type
    """, {"year": current_year})
    
    all_money_agg = pd.DataFrame(money_data)

    # Add filter
    row1 = st.columns(4)
    with row1[0]:
        orderType_filter = st.multiselect("Filter by orderType:", options=all_orders_dat["orderType"].unique())
    
    if orderType_filter:
        all_orders_dat = all_orders_dat[all_orders_dat["orderType"].isin(orderType_filter)]
    
    # Merge order and money data
    order_money_df = pd.merge(left=all_orders_dat, right=all_money_agg, how='left', on=['scoutId', 'orderType'])
    order_money_df.fillna(0, inplace=True)
    
    # For Digital orders, set AmtReceived = TotalAmt (paid in full)
    order_money_df.loc[order_money_df['orderType'] == 'Digital', 'AmtReceived'] = order_money_df.loc[order_money_df['orderType'] == 'Digital', 'TotalAmt']
    
    # Convert numeric columns
    order_money_df = order_money_df.applymap(lambda x: f"{int(x)}" if isinstance(x, (int, float)) else x)
    order_money_df = order_money_df.astype({"TotalAmt": "int", "AmtReceived": "int"})
    
    # Calculate balance
    order_money_df['balance'] = [total - rec for total, rec in zip(order_money_df['TotalAmt'], order_money_df['AmtReceived'])]
    order_money_df = order_money_df.sort_values(by='scoutName')
    order_money_df.reset_index(drop=True, inplace=True)

    # Reorder columns: name - cookie types - qty - order type - total amt - amt received - balance
    column_order = ['scoutName', 'ADV', 'LEM', 'TRE', 'DSD', 'SAM', 'TAG', 'TM', 'EXP', 'TOF', 'DON', 
                    'QTY', 'orderType', 'TotalAmt', 'AmtReceived', 'balance']
    order_money_df = order_money_df[column_order]

    # Shade every other row
    styled_df = order_money_df.style.apply(alternate_rows, axis=0)
    st.dataframe(styled_df, height=900, use_container_width=True)

if __name__ == '__main__':
    setup.config_site(page_title="Admin Ebudde Summary", initial_sidebar_state='expanded')
    main()