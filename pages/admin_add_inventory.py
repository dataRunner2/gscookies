import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from streamlit_extras.row import row as strow
from datetime import datetime
from utils.app_utils import setup 
from utils.db_utils import require_admin, fetch_all, execute_sql
import uuid

def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year

def get_cookie_data(program_year):
    """Fetch cookie configuration from database"""
    cookies = fetch_all("""
        SELECT cookie_code, display_name, display_order
        FROM cookies_app.cookie_years
        WHERE program_year = :year
        ORDER BY display_order
    """, {"year": program_year})
    return cookies
    
def main():
    require_admin()

    # Get cookie data from database
    current_year = ss.current_year
    cookies = get_cookie_data(current_year)
    
    if not cookies:
        st.error("No cookie configuration found for this year.")
        return

    # ADD INVENTORY PICKUP
    st.markdown(f"Ready to submit a Cookie Inventory Pickup")

    with st.form('submit orders', clear_on_submit=True):
        st.text_input(label='Order Ref #', key='orderId')
        
        # Create dynamic cookie input fields
        cookie_inputs = {}
        num_cookies = len(cookies)
        cols_per_row = 5
        
        for i in range(0, num_cookies, cols_per_row):
            row_cookies = cookies[i:i+cols_per_row]
            row = strow(len(row_cookies), vertical_align="center")
            
            for cookie in row_cookies:
                cookie_inputs[cookie.cookie_code] = row.number_input(
                    label=cookie.display_name,
                    step=1,
                    min_value=-5,
                    value=0,
                    key=f'inv_{cookie.cookie_code}'
                )
 
        if st.form_submit_button("Submit Inventory Pickup"):
            # Calculate totals
            quantities = {code: ss[f'inv_{code}'] for code in cookie_inputs.keys()}
            total_boxes = sum(quantities.values())
            
            if not ss.orderId:
                st.error("Please enter an Order Ref #")
                return
            
            st.write(f"Total boxes: {total_boxes}")
            
            # Insert into inventory_ledger for each cookie type
            # Use booth parent and scout as system defaults for general inventory
            BOOTH_PARENT_ID = 'f056ec09-9273-4e2d-8532-3b2cf0c7b704'
            BOOTH_SCOUT_ID = '7bcf1980-ccb7-4d0c-b0a0-521b542356fa'
            
            for cookie_code, qty in quantities.items():
                if qty != 0:  # Only insert non-zero quantities
                    execute_sql("""
                        INSERT INTO cookies_app.inventory_ledger 
                        (inventory_event_id, parent_id, scout_id, program_year, cookie_code, quantity, event_type, 
                         event_dt, notes, status)
                        VALUES (:event_id, :parent_id, :scout_id, :year, :cookie_code, :qty, 'PICKUP', :dt, :notes, 'COMPLETED')
                    """, {
                        "event_id": str(uuid.uuid4()),
                        "parent_id": BOOTH_PARENT_ID,
                        "scout_id": BOOTH_SCOUT_ID,
                        "year": current_year,
                        "cookie_code": cookie_code,
                        "qty": qty,
                        "dt": datetime.now(),
                        "notes": f"Order Ref: {ss.orderId}"
                    })

            st.success(f"{total_boxes} boxes were submitted\nYour order id is {ss.orderId}")

    # Create tabs
    tab1, tab2 = st.tabs(["Inventory Pickups", "Total Inventory"])
    
    with tab1:
        # ALL INVENTORY PICKUPS
        all_inventory = fetch_all("""
            SELECT 
                notes as order_ref,
                cookie_code,
                SUM(quantity) as quantity,
                MAX(event_dt) as last_pickup_dt
            FROM cookies_app.inventory_ledger
            WHERE program_year = :year
              AND event_type = 'PICKUP'
              AND notes LIKE 'Order Ref:%'
            GROUP BY notes, cookie_code
            ORDER BY last_pickup_dt DESC, notes
        """, {"year": current_year})
        
        if all_inventory:
            df = pd.DataFrame(all_inventory)
            
            # Pivot to wide format
            pivot_df = df.pivot_table(
                index='order_ref',
                columns='cookie_code',
                values='quantity',
                fill_value=0,
                aggfunc='sum'
            )
            
            # Reorder columns based on cookie display order
            cookie_order = [c.cookie_code for c in cookies]
            available_cols = [c for c in cookie_order if c in pivot_df.columns]
            pivot_df = pivot_df[available_cols]
            
            # Add totals row
            totals = pivot_df.sum()
            totals.name = 'TOTAL'
            pivot_df_with_totals = pd.concat([pivot_df, totals.to_frame().T])
            
            st.write('Inventory Orders with Totals')
            st.dataframe(pivot_df_with_totals, use_container_width=True)
            
            st.write('Click in a cell to edit it')
            edited_data = st.data_editor(pivot_df, num_rows='fixed', key='update_inventory_dat', use_container_width=True)

            changes = edited_data.compare(pivot_df)
                       
            if not changes.empty:
                st.write("Changes detected:")
                changed_df = changes.loc[:, changes.columns.get_level_values(1) == "self"]
                changed_df.columns = changed_df.columns.droplevel(1)
                st.write(changed_df)
                
                st.divider()
                
                if st.button('Save updates to database'):
                    for order_ref, row in changed_df.iterrows():
                        for cookie_code, new_qty in row.items():
                            if pd.notna(new_qty):
                                # Update the inventory ledger entry
                                execute_sql("""
                                    UPDATE cookies_app.inventory_ledger
                                    SET quantity = :qty
                                    WHERE notes = :notes
                                      AND cookie_code = :code
                                      AND program_year = :year
                                      AND event_type = 'PICKUP'
                                """, {
                                    "qty": int(new_qty),
                                    "notes": order_ref,
                                    "code": cookie_code,
                                    "year": current_year
                                })
                                st.success(f"Updated {order_ref} - {cookie_code} to {int(new_qty)}")
                    
                    st.rerun()
        else:
            st.info("No inventory pickups found for this year.")
    
    with tab2:
        # TOTAL INVENTORY SUMMARY
        st.subheader("Total Inventory Summary")
        
        # Get inventory totals by cookie type using separate subqueries to avoid row multiplication
        inventory_summary = fetch_all("""
            SELECT 
                cy.cookie_code,
                cy.display_name,
                COALESCE(pickups.total, 0) as total_pickup,
                COALESCE(distributed.total, 0) as total_distributed,
                COALESCE(pending.total, 0) as total_pending
            FROM cookies_app.cookie_years cy
            LEFT JOIN (
                SELECT cookie_code, SUM(quantity) as total
                FROM cookies_app.inventory_ledger
                WHERE program_year = :year AND event_type = 'PICKUP'
                GROUP BY cookie_code
            ) pickups ON cy.cookie_code = pickups.cookie_code
            LEFT JOIN (
                SELECT oi.cookie_code, SUM(oi.quantity) as total
                FROM cookies_app.order_items oi
                JOIN cookies_app.orders o ON oi.order_id = o.order_id
                WHERE oi.program_year = :year AND o.status = 'PICKED_UP'
                GROUP BY oi.cookie_code
            ) distributed ON cy.cookie_code = distributed.cookie_code
            LEFT JOIN (
                SELECT oi.cookie_code, SUM(oi.quantity) as total
                FROM cookies_app.order_items oi
                JOIN cookies_app.orders o ON oi.order_id = o.order_id
                WHERE oi.program_year = :year AND o.status NOT IN ('PICKED_UP', 'CANCELLED')
                GROUP BY oi.cookie_code
            ) pending ON cy.cookie_code = pending.cookie_code
            WHERE cy.program_year = :year
            ORDER BY cy.display_order
        """, {"year": current_year})
        
        if inventory_summary:
            summary_df = pd.DataFrame(inventory_summary)
            
            # Calculate net total
            summary_df['net_total'] = (
                summary_df['total_pickup'] - 
                summary_df['total_distributed'] - 
                summary_df['total_pending']
            )
            
            # Reorder columns
            summary_df = summary_df[['cookie_code', 'display_name', 'total_pickup', 'total_distributed', 'total_pending', 'net_total']]
            summary_df.columns = ['Code', 'Cookie Type', '+ Pickups', '- Distributed', '- Pending', 'Net Total']
            
            # Add totals row
            totals_row = pd.DataFrame([{
                'Code': 'TOTAL',
                'Cookie Type': '',
                '+ Pickups': summary_df['+ Pickups'].sum(),
                '- Distributed': summary_df['- Distributed'].sum(),
                '- Pending': summary_df['- Pending'].sum(),
                'Net Total': summary_df['Net Total'].sum()
            }])
            summary_with_totals = pd.concat([summary_df, totals_row], ignore_index=True)
            
            st.dataframe(summary_with_totals, use_container_width=True, hide_index=True)
        else:
            st.info("No inventory data found for this year.")
if __name__ == '__main__':
    setup.config_site(page_title="Add Inventory", initial_sidebar_state='expanded')
    init_ss()
    main()