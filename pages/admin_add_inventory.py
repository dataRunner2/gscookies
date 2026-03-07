import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from streamlit_extras.row import row as strow
from datetime import datetime
from utils.app_utils import setup 
from utils.db_utils import require_admin, fetch_all, execute_many_sql
import uuid
from functools import lru_cache

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


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


@lru_cache(maxsize=8)
def get_inventory_pickups_data(program_year: int):
    rows = fetch_all("""
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
    """, {"year": int(program_year)})
    return _rows_to_dicts(rows)


@lru_cache(maxsize=8)
def get_total_inventory_summary_data(program_year: int):
    rows = fetch_all("""
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
    """, {"year": int(program_year)})
    return _rows_to_dicts(rows)


@lru_cache(maxsize=8)
def get_cookie_inventory_summary_data(program_year: int):
    rows = fetch_all("""
        WITH pickup_orders AS (
            SELECT
                notes AS order_ref,
                cookie_code,
                SUM(quantity) AS qty,
                MIN(event_dt) AS first_dt
            FROM cookies_app.inventory_ledger
            WHERE program_year = :year
              AND event_type = 'PICKUP'
              AND notes LIKE 'Order Ref:%'
            GROUP BY notes, cookie_code
        ),
        pickup_refs AS (
            SELECT
                order_ref,
                MIN(first_dt) AS first_dt
            FROM pickup_orders
            GROUP BY order_ref
        ),
        ranked_refs AS (
            SELECT
                order_ref,
                ROW_NUMBER() OVER (ORDER BY first_dt, order_ref) AS pickup_rank
            FROM pickup_refs
        ),
        initial_pickup AS (
            SELECT
                po.cookie_code,
                SUM(po.qty) AS initial_order
            FROM pickup_orders po
            JOIN ranked_refs rr ON rr.order_ref = po.order_ref
            WHERE rr.pickup_rank = 1
            GROUP BY po.cookie_code
        ),
        add_pickup AS (
            SELECT
                po.cookie_code,
                SUM(po.qty) AS add_inventory_order
            FROM pickup_orders po
            JOIN ranked_refs rr ON rr.order_ref = po.order_ref
            WHERE rr.pickup_rank > 1
            GROUP BY po.cookie_code
        ),
        individual_orders AS (
            SELECT
                oi.cookie_code,
                SUM(oi.quantity) AS orders_qty
            FROM cookies_app.order_items oi
            JOIN cookies_app.orders o ON o.order_id = oi.order_id
            WHERE oi.program_year = :year
              AND COALESCE(o.order_type, '') <> 'Booth'
              AND COALESCE(o.status, '') <> 'CANCELLED'
            GROUP BY oi.cookie_code
        ),
        completed_booths AS (
            SELECT
                cookie_code,
                SUM(-quantity) AS completed_booths_qty
            FROM cookies_app.inventory_ledger
            WHERE program_year = :year
              AND event_type = 'BOOTH_SALE'
            GROUP BY cookie_code
        ),
        planned_booths AS (
            SELECT
                bip.cookie_code,
                SUM(bip.planned_quantity) AS planned_qty
            FROM cookies_app.booth_inventory_plan bip
            JOIN (
                SELECT DISTINCT booth_id, program_year
                FROM cookies_app.orders
                WHERE order_type = 'Booth'
                  AND program_year = :year
                  AND COALESCE(verification_status, 'DRAFT') <> 'VERIFIED'
            ) open_booths
              ON open_booths.booth_id = bip.booth_id
             AND open_booths.program_year = bip.program_year
            WHERE bip.program_year = :year
            GROUP BY bip.cookie_code
        )
        SELECT
            cy.cookie_code,
            cy.display_name,
            COALESCE(ip.initial_order, 0) AS initial_order,
            COALESCE(ap.add_inventory_order, 0) AS add_inventory_order,
            COALESCE(io.orders_qty, 0) AS orders_qty,
            COALESCE(cb.completed_booths_qty, 0) AS completed_booths_qty,
            COALESCE(pb.planned_qty, 0) AS planned_qty
        FROM cookies_app.cookie_years cy
        LEFT JOIN initial_pickup ip ON cy.cookie_code = ip.cookie_code
        LEFT JOIN add_pickup ap ON cy.cookie_code = ap.cookie_code
        LEFT JOIN individual_orders io ON cy.cookie_code = io.cookie_code
        LEFT JOIN completed_booths cb ON cy.cookie_code = cb.cookie_code
        LEFT JOIN planned_booths pb ON cy.cookie_code = pb.cookie_code
        WHERE cy.program_year = :year
        ORDER BY cy.display_order
    """, {"year": int(program_year)})
    return _rows_to_dicts(rows)


@lru_cache(maxsize=8)
def get_completed_booth_count(program_year: int) -> int:
    rows = fetch_all("""
        SELECT COUNT(DISTINCT order_id) AS booth_count
        FROM cookies_app.orders
        WHERE program_year = :year
          AND order_type = 'Booth'
          AND COALESCE(verification_status, 'DRAFT') = 'VERIFIED'
    """, {"year": int(program_year)})
    if not rows:
        return 0
    return int(rows[0]["booth_count"] or 0)


def clear_inventory_page_caches():
    get_inventory_pickups_data.cache_clear()
    get_total_inventory_summary_data.cache_clear()
    get_cookie_inventory_summary_data.cache_clear()
    get_completed_booth_count.cache_clear()


def render_inventory_pickups(current_year, cookie_order):
    all_inventory = get_inventory_pickups_data(current_year)

    if all_inventory:
        df = pd.DataFrame(all_inventory)

        pivot_df = df.pivot_table(
            index='order_ref',
            columns='cookie_code',
            values='quantity',
            fill_value=0,
            aggfunc='sum'
        )

        available_cols = [c for c in cookie_order if c in pivot_df.columns]
        pivot_df = pivot_df[available_cols]

        totals = pivot_df.sum()
        totals.name = 'TOTAL'
        pivot_df_with_totals = pd.concat([pivot_df, totals.to_frame().T])

        st.write('Inventory Orders with Totals')
        st.dataframe(pivot_df_with_totals, use_container_width=True)

        st.write('Click in a cell to edit it')
        edited_data = st.data_editor(
            pivot_df,
            num_rows='fixed',
            key='update_inventory_dat',
            use_container_width=True
        )

        changes = edited_data.compare(pivot_df)

        if not changes.empty:
            st.write("Changes detected:")
            changed_df = changes.loc[:, changes.columns.get_level_values(1) == "self"]
            changed_df.columns = changed_df.columns.droplevel(1)
            st.write(changed_df)

            st.divider()

            if st.button('Save updates to database'):
                update_rows = []
                for order_ref, row in changed_df.iterrows():
                    for cookie_code, new_qty in row.items():
                        if pd.notna(new_qty):
                            update_rows.append({
                                "qty": int(new_qty),
                                "notes": order_ref,
                                "code": cookie_code,
                                "year": current_year,
                            })

                if update_rows:
                    execute_many_sql("""
                        UPDATE cookies_app.inventory_ledger
                        SET quantity = :qty
                        WHERE notes = :notes
                          AND cookie_code = :code
                          AND program_year = :year
                          AND event_type = 'PICKUP'
                    """, update_rows)

                    clear_inventory_page_caches()
                    st.success(f"Updated {len(update_rows)} pickup value(s).")
                    st.rerun()
                else:
                    st.info("No valid changes found to save.")
    else:
        st.info("No inventory pickups found for this year.")


def render_total_inventory(current_year):
    st.subheader("Total Inventory Summary")
    inventory_summary = get_total_inventory_summary_data(current_year)

    if inventory_summary:
        summary_df = pd.DataFrame(inventory_summary)

        summary_df['net_total'] = (
            summary_df['total_pickup']
            - summary_df['total_distributed']
            - summary_df['total_pending']
        )

        summary_df = summary_df[['cookie_code', 'display_name', 'total_pickup', 'total_distributed', 'total_pending', 'net_total']]
        summary_df.columns = ['Code', 'Cookie Type', '+ Pickups', '- Distributed', '- Pending', 'Net Total']

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


def render_inventory_by_cookie_type(current_year):
    st.subheader("Inventory by Cookie Type")
    st.caption(
        "Rows: Initial Order, Add Inventory Order, Total Added Inventory, Orders, "
        "Completed Booths, Total Current Inventory, -Planned Inventory, and Future Inventory."
    )

    cookie_inventory_summary = get_cookie_inventory_summary_data(current_year)

    if cookie_inventory_summary:
        inv_df = pd.DataFrame(cookie_inventory_summary)

        quantity_cols = [
            'initial_order',
            'add_inventory_order',
            'orders_qty',
            'completed_booths_qty',
            'planned_qty',
        ]
        for col in quantity_cols:
            inv_df[col] = pd.to_numeric(inv_df[col], errors='coerce').fillna(0).astype(int)

        inv_df['total_added_inventory'] = inv_df['initial_order'] + inv_df['add_inventory_order']
        inv_df['total_current_inventory'] = (
            inv_df['total_added_inventory']
            - inv_df['orders_qty']
            - inv_df['completed_booths_qty']
        )
        inv_df['future_inventory'] = inv_df['total_current_inventory'] - inv_df['planned_qty']

        cookie_order = inv_df['cookie_code'].tolist()

        values_by_metric = {
            'Initial Order': dict(zip(inv_df['cookie_code'], inv_df['initial_order'])),
            'Add Inventory Order': dict(zip(inv_df['cookie_code'], inv_df['add_inventory_order'])),
            'Total Added Inventory': dict(zip(inv_df['cookie_code'], inv_df['total_added_inventory'])),
            'Orders': dict(zip(inv_df['cookie_code'], inv_df['orders_qty'])),
            'Completed Booths': dict(zip(inv_df['cookie_code'], inv_df['completed_booths_qty'])),
            'Total Current Inventory': dict(zip(inv_df['cookie_code'], inv_df['total_current_inventory'])),
            '-Planned Inventory': dict(zip(inv_df['cookie_code'], inv_df['planned_qty'])),
            'Future Inventory': dict(zip(inv_df['cookie_code'], inv_df['future_inventory'])),
        }

        table_rows = []
        for metric_name in [
            'Initial Order',
            'Add Inventory Order',
            'Total Added Inventory',
            'Orders',
            'Completed Booths',
            'Total Current Inventory',
            '-Planned Inventory',
            'Future Inventory',
        ]:
            row = {'Metric': metric_name}
            for code in cookie_order:
                row[code] = int(values_by_metric[metric_name].get(code, 0))
            table_rows.append(row)

        table_df = pd.DataFrame(table_rows)

        def style_current_inventory_row(row):
            if row['Metric'] == 'Total Current Inventory':
                return ['font-weight: 700; border-top: 3px solid; border-bottom: 3px solid;' for _ in row]
            return ['' for _ in row]

        styled_table = (
            table_df.style
            .hide(axis='index')
            .set_properties(subset=['Metric'], **{'font-weight': '600', 'text-align': 'left'})
            .set_properties(subset=[c for c in table_df.columns if c != 'Metric'], **{'text-align': 'right'})
            .apply(style_current_inventory_row, axis=1)
        )

        st.markdown(styled_table.to_html(), unsafe_allow_html=True)

        completed_booth_count = get_completed_booth_count(current_year)

        st.markdown("### Average Cookie Type Sold at Booths")
        st.caption(
            f"Average per completed booth (Completed Booth Count: {completed_booth_count})."
        )

        avg_row = {'Metric': 'Average Sold at Booths'}
        for code in cookie_order:
            sold_total = int(values_by_metric['Completed Booths'].get(code, 0))
            avg_row[code] = round(sold_total / completed_booth_count, 2) if completed_booth_count > 0 else 0.0

        avg_df = pd.DataFrame([avg_row])
        st.dataframe(avg_df, use_container_width=True, hide_index=True)
    else:
        st.info("No cookie inventory summary found for this year.")
    
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
            
            insert_rows = []
            for cookie_code, qty in quantities.items():
                if qty != 0:  # Only insert non-zero quantities
                    insert_rows.append({
                        "event_id": str(uuid.uuid4()),
                        "parent_id": BOOTH_PARENT_ID,
                        "scout_id": BOOTH_SCOUT_ID,
                        "year": current_year,
                        "cookie_code": cookie_code,
                        "qty": qty,
                        "dt": datetime.now(),
                        "notes": f"Order Ref: {ss.orderId}"
                    })

            if insert_rows:
                execute_many_sql("""
                    INSERT INTO cookies_app.inventory_ledger
                    (inventory_event_id, parent_id, scout_id, program_year, cookie_code, quantity, event_type,
                     event_dt, notes, status)
                    VALUES (:event_id, :parent_id, :scout_id, :year, :cookie_code, :qty, 'PICKUP', :dt, :notes, 'COMPLETED')
                """, insert_rows)

            clear_inventory_page_caches()

            st.success(f"{total_boxes} boxes were submitted\nYour order id is {ss.orderId}")

    st.markdown("### Inventory Views")
    if st.button("🔄 Refresh Data", key="refresh_inventory_view_data"):
        clear_inventory_page_caches()
        st.rerun()

    selected_view = st.radio(
        "Inventory Views",
        ["Inventory Pickups", "Total Inventory", "Inventory by Cookie Type"],
        horizontal=True,
        label_visibility="collapsed",
    )

    cookie_order = [c.cookie_code for c in cookies]

    if selected_view == "Inventory Pickups":
        render_inventory_pickups(current_year, cookie_order)
    elif selected_view == "Total Inventory":
        render_total_inventory(current_year)
    else:
        render_inventory_by_cookie_type(current_year)

if __name__ == '__main__':
    setup.config_site(page_title="Add Inventory", initial_sidebar_state='expanded')
    init_ss()
    main()