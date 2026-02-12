import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from datetime import datetime
from decimal import Decimal
from utils.app_utils import setup 
from utils.db_utils import require_admin, fetch_all, execute_sql

def decimal_sum(series):
    return sum(Decimal(str(x)) for x in series.fillna(0))

def alternate_rows(df):
    return ['background-color:#f2f2f2' if i % 2 != 0 else '' for i in range(len(df))]
    
def main():
    require_admin()
    
    current_year = datetime.now().year

    # Add controls
    c1,c2,c3,c4 = st.columns([30, 30, 10, 30])
    with c2:
        combine_orders = st.checkbox("Combine Paper & Digital", value=False, help="Show one line per scout combining all order types")
    
    # Build GROUP BY clause based on checkbox
    if combine_orders:
        group_by_clause = "GROUP BY o.scout_id, s.first_name, s.last_name, COALESCE(o.add_ebudde, false)"
        order_by_clause = "ORDER BY s.first_name, s.last_name, COALESCE(o.add_ebudde, false)"
    else:
        group_by_clause = "GROUP BY o.scout_id, s.first_name, s.last_name, o.order_type, COALESCE(o.add_ebudde, false)"
        order_by_clause = "ORDER BY s.first_name, s.last_name, o.order_type, COALESCE(o.add_ebudde, false)"

    # Get order data with cookie quantities aggregated by scout, order type, and ebudde status
    order_query = f"""
        SELECT 
            o.scout_id as "scoutId",
            s.first_name || ' ' || s.last_name as "scoutName",
            {'\'Combined\' as "orderType"' if combine_orders else 'o.order_type as "orderType"'},
            COALESCE(o.add_ebudde, false) as "ebudde",
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
        {group_by_clause}
        {order_by_clause}
    """
    
    order_data = fetch_all(order_query, {"year": current_year})
    all_orders_dat = pd.DataFrame(order_data)
    
    if all_orders_dat.empty:
        st.info("No order data found for this year.")
        st.stop()

    # Get money received data aggregated by scout and ebudde status (Paper orders only)
    if combine_orders:
        money_query = """
            SELECT 
                o.scout_id as "scoutId",
                'Combined' as "orderType",
                COALESCE(o.add_ebudde, false) as "ebudde",
                COALESCE(SUM(ml.amount), 0) as "AmtReceived"
            FROM cookies_app.orders o
            LEFT JOIN cookies_app.money_ledger ml ON o.order_id = ml.related_order_id
            WHERE o.program_year = :year
              AND o.order_type = 'Paper'
            GROUP BY o.scout_id, COALESCE(o.add_ebudde, false)
        """
    else:
        money_query = """
            SELECT 
                o.scout_id as "scoutId",
                o.order_type as "orderType",
                COALESCE(o.add_ebudde, false) as "ebudde",
                COALESCE(SUM(ml.amount), 0) as "AmtReceived"
            FROM cookies_app.orders o
            LEFT JOIN cookies_app.money_ledger ml ON o.order_id = ml.related_order_id
            WHERE o.program_year = :year
              AND o.order_type = 'Paper'
            GROUP BY o.scout_id, o.order_type, COALESCE(o.add_ebudde, false)
        """
    
    money_data = fetch_all(money_query, {"year": current_year})
    all_money_agg = pd.DataFrame(money_data)

    # Add filter
    with c1:
        orderType_filter = st.multiselect("Filter by orderType:", options=all_orders_dat["orderType"].unique())
    
    if orderType_filter:
        all_orders_dat = all_orders_dat[all_orders_dat["orderType"].isin(orderType_filter)]
    
    # Merge order and money data
    order_money_df = pd.merge(left=all_orders_dat, right=all_money_agg, how='left', on=['scoutId', 'orderType', 'ebudde'])
    order_money_df.fillna(0, inplace=True)
    
    # For Digital orders, set AmtReceived = TotalAmt (paid in full)
    order_money_df.loc[order_money_df['orderType'] == 'Digital', 'AmtReceived'] = order_money_df.loc[order_money_df['orderType'] == 'Digital', 'TotalAmt']
    
    # Convert numeric columns (except ebudde which is boolean)
    numeric_cols = ['ADV', 'LEM', 'TRE', 'DSD', 'SAM', 'TAG', 'TM', 'EXP', 'TOF', 'DON', 'QTY', 'TotalAmt', 'AmtReceived']
    for col in numeric_cols:
        order_money_df[col] = order_money_df[col].apply(lambda x: int(x) if isinstance(x, (int, float)) else x)
    
    # Calculate balance
    order_money_df['balance'] = [total - rec for total, rec in zip(order_money_df['TotalAmt'], order_money_df['AmtReceived'])]
    order_money_df = order_money_df.sort_values(by='scoutName')
    order_money_df.reset_index(drop=True, inplace=True)

    # Reorder columns: name - ebudde - cookie types - qty - order type - total amt - amt received - balance
    column_order = ['scoutName', 'ebudde', 'ADV', 'LEM', 'TRE', 'DSD', 'SAM', 'TAG', 'TM', 'EXP', 'TOF', 'DON', 
                    'QTY', 'orderType', 'TotalAmt', 'AmtReceived', 'balance']
    display_df = order_money_df[column_order]

    # Use data editor for editable ebudde column
    edited_df = st.data_editor(
        display_df,
        column_config={
            "ebudde": st.column_config.CheckboxColumn("eBudde", help="Add to eBudde"),
            "scoutName": st.column_config.TextColumn("Scout Name", disabled=True),
            "ADV": st.column_config.NumberColumn("ADV", disabled=True),
            "LEM": st.column_config.NumberColumn("LEM", disabled=True),
            "TRE": st.column_config.NumberColumn("TRE", disabled=True),
            "DSD": st.column_config.NumberColumn("DSD", disabled=True),
            "SAM": st.column_config.NumberColumn("SAM", disabled=True),
            "TAG": st.column_config.NumberColumn("TAG", disabled=True),
            "TM": st.column_config.NumberColumn("TM", disabled=True),
            "EXP": st.column_config.NumberColumn("EXP", disabled=True),
            "TOF": st.column_config.NumberColumn("TOF", disabled=True),
            "DON": st.column_config.NumberColumn("DON", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", disabled=True),
            "orderType": st.column_config.TextColumn("Order Type", disabled=True),
            "TotalAmt": st.column_config.NumberColumn("Total Amt", disabled=True),
            "AmtReceived": st.column_config.NumberColumn("Amt Received", disabled=True),
            "balance": st.column_config.NumberColumn("Balance", disabled=True),
        },
        hide_index=True,
        height=900,
        width="stretch",
        key="ebudde_editor"
    )
    
    # Check for changes and save
    if st.button("💾 Save eBudde Changes"):
        changes_made = False
        for idx in range(len(edited_df)):
            # Convert to bool for comparison to handle numpy bool types
            old_val = bool(display_df.loc[idx, 'ebudde']) if pd.notna(display_df.loc[idx, 'ebudde']) else False
            new_val = bool(edited_df.loc[idx, 'ebudde']) if pd.notna(edited_df.loc[idx, 'ebudde']) else False
            
            if new_val != old_val:
                scout_id = order_money_df.loc[idx, 'scoutId']
                order_type = order_money_df.loc[idx, 'orderType']
                old_ebudde = old_val
                new_ebudde = new_val
                
                # Update ALL orders for this scout_id + order_type + old_ebudde combination
                # When combined, update all order types; otherwise, update specific order type
                if combine_orders:
                    execute_sql("""
                        UPDATE cookies_app.orders
                        SET add_ebudde = :new_ebudde
                        WHERE scout_id = :sid
                          AND COALESCE(add_ebudde, false) = :old_ebudde
                          AND program_year = :year
                    """, {
                        "new_ebudde": new_ebudde,
                        "sid": scout_id,
                        "old_ebudde": old_ebudde,
                        "year": current_year
                    })
                else:
                    execute_sql("""
                        UPDATE cookies_app.orders
                        SET add_ebudde = :new_ebudde
                        WHERE scout_id = :sid
                          AND order_type = :otype
                          AND COALESCE(add_ebudde, false) = :old_ebudde
                          AND program_year = :year
                    """, {
                        "new_ebudde": new_ebudde,
                        "sid": scout_id,
                        "otype": order_type,
                        "old_ebudde": old_ebudde,
                        "year": current_year
                    })
                changes_made = True
        
        if changes_made:
            st.success("✅ eBudde values updated successfully!")
            st.rerun()
        else:
            st.info("No changes detected.")

if __name__ == '__main__':
    setup.config_site(page_title="Admin Ebudde Summary", initial_sidebar_state='expanded')
    main()