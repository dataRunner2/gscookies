import streamlit as st
from decimal import Decimal, ROUND_FLOOR
from streamlit import session_state as ss
from datetime import time, datetime, timedelta
from uuid import uuid4
import time as time_module
from utils.app_utils import setup
from utils.db_utils import require_admin, execute_sql, fetch_all
from utils.order_utils import delete_booth_cascade

# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year
    if 'weekend_number' not in ss:
        ss.weekend_number = 1
    if 'percent_override' not in ss:
        ss.percent_override = 1.0
    
    # Initialize cookie quantity session state keys from database
    default_booth_qty, _ = get_cookie_data(ss.current_year)
    for code, default in default_booth_qty.items():
        key = f"plan_{code}"
        if key not in ss:
            ss[key] = default



# --------------------------------------------------
# Data helpers
# --------------------------------------------------

def get_cookie_data(program_year):
    """Fetch cookie data from cookie_years table"""
    rows = fetch_all("""
        SELECT cookie_code, default_booth_qty, cookie_avg_pct
        FROM cookies_app.cookie_years
        WHERE program_year = :year AND active = TRUE
        ORDER BY display_order
    """, {"year": program_year})
    
    default_qty = {}
    avg_pct = {}
    
    for row in rows:
        code = row.cookie_code
        default_qty[code] = row.default_booth_qty or 0
        pct_value = float(row.cookie_avg_pct or 0)
        avg_pct[code] = f"{int(pct_value * 100)}%"
    
    return default_qty, avg_pct

def update_weekend_override():
    """Update percent_override when weekend selection changes"""
    weekend = ss.weekend_number
    ss.percent_override = {1: 1.0, 2: 0.75, 3: 0.50}[weekend]

def update_initial_quantities(default_qty, cookie_codes):
    """Update session state with calculated quantities based on current multiplier"""
    multiplier = Decimal(ss.percent_override)
    for code in cookie_codes:
        default = default_qty[code]
        adjusted = int((Decimal(default) * multiplier).to_integral_value())
        ss[f"plan_{code}"] = adjusted


# Booth queries
# --------------------------------------------------
def get_booths():
    return fetch_all("""
        SELECT *
        FROM cookies_app.booths
        ORDER BY booth_date DESC, start_time
    """)


def get_draft_booth_orders():
    return fetch_all("""
        SELECT
            o.order_id,
            o.program_year,
            o.starting_cash,
            o.ending_cash,
            o.square_total,
            b.booth_id,
            b.location,
            b.booth_date,
            b.start_time,
            b.end_time
        FROM cookies_app.orders o
        JOIN cookies_app.booths b ON o.booth_id = b.booth_id
        WHERE o.order_type = 'Booth'
          AND o.verification_status = 'DRAFT'
        ORDER BY b.booth_date DESC
    """)


# Booth queries
def verify_booth(order_id, year, items, admin_name, notes, opc_boxes):
    # Mark order verified - update both verification_status and status
    execute_sql("""
        UPDATE cookies_app.orders
        SET verification_status = 'VERIFIED',
            status = 'VERIFIED',
            verified_by = :by,
            verified_at = now(),
            verification_notes = :notes,
            opc_boxes = :opc
        WHERE order_id = :oid
          AND verification_status <> 'VERIFIED'
    """, {
        "oid": order_id,
        "by": admin_name,
        "notes": notes,
        "opc": opc_boxes,
    })

    # Record inventory movements
    for i in items:
        if i.get('sold', 0) == 0:
            continue
        
        execute_sql("""
            INSERT INTO cookies_app.inventory_ledger (
                inventory_event_id,
                program_year,
                cookie_code,
                quantity,
                event_type,
                status,
                related_order_id,
                event_dt,
                notes
            )
            VALUES (
                gen_random_uuid(),
                :year,
                :cookie,
                :qty,
                'BOOTH_SALE',
                'ACTUAL',
                :oid,
                now(),
                'Booth verified'
            )
        """, {
            "year": year,
            "cookie": i.get('cookie_code'),
            "qty": -i.get('sold', 0),
            "oid": order_id,
        })


# --------------------------------------------------
# Page
# --------------------------------------------------
def main():
    init_ss()
    require_admin()

    st.subheader("Booth Administration")

    tab_add, tab_view, tab_print, tab_verify, tab_delete = st.tabs([
        "➕ Add / Manage Booths",
        "📋 View All Booths",
        "🖨️ Print Booth Sheet",
        "✅ Verify Booth",
        "🗑️ Delete Booth",
    ])

    # ==================================================
    # TAB 1 — ADD / MANAGE BOOTHS
    # ==================================================
    

    # -------------------------------------------------------------------
    # LOAD COOKIE DATA FROM DATABASE
    # -------------------------------------------------------------------

    # Fetch default quantities and percentages from cookie_years table
    DEFAULT_BOOTH_QTY, COOKIE_AVG_PCT = get_cookie_data(ss.current_year)

    COOKIE_LAYOUT = [
        ["TM", "SAM", "TAG"],
        ["ADV", "EXP", "TRE"],
        ["LEM", "DSD", "TOF"],

    ]

    # -------------------------------------------------------------------
    # TAB: CREATE BOOTH
    # -------------------------------------------------------------------

    with tab_add:
        st.subheader("➕ Create Booth")

        col1, col2,col3, col4 = st.columns(4)
        location = col1.text_input("Location", key="create_location")
        booth_date = col2.date_input("Booth Date", format="MM/DD/YYYY", key="create_booth_date")

        start_time = col3.time_input(
            "Start Time",
            value=time(8, 0),
            step=3600,  # 30 min
            key="create_start_time"
        )
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=2)).time()
        col4.markdown(f"\n**End Time:** {end_time.strftime('%I:%M %p')}")

        
        weekend_number = col1.selectbox(
            "Weekend",
            options=[1, 2, 3],
            format_func=lambda x: f"Weekend {x}",
            index=ss.weekend_number - 1,
            key="weekend_number",
            on_change=update_weekend_override,
        )
        percent_override = col2.number_input(
            "or % Override",
            min_value=0.0,
            max_value=2.0,
            step=0.05,
            key="percent_override",
        )

        # Button to update initial quantities based on current multiplier
        all_cookie_codes = [code for row in COOKIE_LAYOUT for code in row]
        if st.button("📦 Update Initial Quantities"):
            update_initial_quantities(DEFAULT_BOOTH_QTY, all_cookie_codes)

        multiplier = Decimal(ss.percent_override)

        st.markdown("### 🍪 Planned Cookie Inventory")
        planned = {}

        for col_codes in COOKIE_LAYOUT:
            c1, c2, c3 = st.columns(3)
            for col, code in zip([c1, c2, c3], col_codes):
                with col:
                    planned[code] = st.number_input(
                        f"{code} ({COOKIE_AVG_PCT[code]})",
                        min_value=0,
                        step=1,
                        value=ss.get(f"plan_{code}", DEFAULT_BOOTH_QTY[code]),
                        key=f"plan_{code}",
                    )
        
        
        # Add DON automatically with 0 quantity (no user input needed)
        planned["DON"] = 0

        scouts = fetch_all("""
            SELECT scout_id, first_name || ' ' || last_name AS name
            FROM cookies_app.scouts
            ORDER BY last_name, first_name
        """)

        scout_ids = st.multiselect(
            "Assign Scouts (up to 4)",
            options=[s.scout_id for s in scouts],
            format_func=lambda sid: next(s.name for s in scouts if s.scout_id == sid),
            max_selections=4,
            key="create_scout_ids"
        )

        if st.button("Create Booth"):
            # Check for duplicate booth (same location, date, and start time)
            existing = fetch_all("""
                SELECT booth_id, location
                FROM cookies_app.booths
                WHERE location = :loc
                  AND booth_date = :date
                  AND start_time = :start
            """, {
                "loc": location,
                "date": booth_date,
                "start": start_time
            })
            
            if existing:
                st.error(f"⚠️ A booth already exists for {location} on {booth_date.strftime('%b %d')} at {start_time.strftime('%I:%M %p')}. Please use a different location, date, or time.")
            else:
                booth_id = str(uuid4())
                order_id = str(uuid4())
                 # Default to Booths parent and booth scout- not the assigned scout/parent
                booth_parent_id = 'f056ec09-9273-4e2d-8532-3b2cf0c7b704'
                booth_scout_id = '7bcf1980-ccb7-4d0c-b0a0-521b542356fa'
                
                # Get assigned first scout's parent_id and scout_id
                # parent_id = None
                # scout_id = None
                # if scout_ids:
                #     first_scout = fetch_all("""
                #         SELECT parent_id, scout_id 
                #         FROM cookies_app.scouts 
                #         WHERE scout_id = :sid
                #     """, {"sid": scout_ids[0]})
                #     if first_scout:
                #         parent_id = first_scout[0].parent_id if first_scout[0].parent_id else None
                #         scout_id = first_scout[0].scout_id if first_scout[0].scout_id else None
                
                # Calculate total boxes and amount
                total_boxes = sum(planned.values())
                # Assuming $6 per box (update if needed)
                total_amount = total_boxes * 6
                
                # Create booth
                execute_sql("""
                    INSERT INTO cookies_app.booths (
                        booth_id, location, booth_date,
                        start_time, end_time,
                        quantity_multiplier, weekend_number,
                        created_at
                    )
                    VALUES (
                        :bid, :loc, :date,
                        :start, :end,
                        :mult, :wk,
                        now()
                    )
                """, {
                    "bid": booth_id,
                    "loc": location,
                    "date": booth_date,
                    "start": start_time,
                    "end": end_time,
                    "mult": multiplier,
                    "wk": weekend_number,
                })

                # Add planned inventory
                for code, qty in planned.items():
                    execute_sql("""
                        INSERT INTO cookies_app.booth_inventory_plan (
                            booth_id, program_year,
                            cookie_code, planned_quantity
                        )
                        VALUES (:bid, :year, :code, :qty)
                    """, {
                        "bid": booth_id,
                        "year": ss.current_year,
                        "code": code,
                        "qty": qty,
                    })

                # Assign scouts
                for sid in scout_ids:
                    execute_sql("""
                        INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
                        VALUES (:bid, :sid)
                    """, {
                        "bid": booth_id,
                        "sid": sid,
                    })

                # Create order with status='NEW' and planned quantities
                execute_sql("""
                    INSERT INTO cookies_app.orders (
                        order_id, booth_id, parent_id, scout_id,
                        program_year, order_type, status, verification_status,
                        order_qty_boxes, order_amount, submit_dt
                    )
                    VALUES (
                        :oid, :bid, :pid, :sid,
                        :year, 'Booth', 'NEW', 'DRAFT',
                        :qty, :amt, now()
                    )
                """, {
                    "oid": order_id,
                    "bid": booth_id,
                    "pid": booth_parent_id,
                    "sid": booth_scout_id,
                    "year": ss.current_year,
                    "qty": total_boxes,
                    "amt": total_amount,
                })
                
                # Create order items with planned quantities
                for code, qty in planned.items():
                    execute_sql("""
                        INSERT INTO cookies_app.order_items (
                            order_item_id, order_id, parent_id, scout_id,
                            program_year, cookie_code, quantity
                        )
                        VALUES (
                            gen_random_uuid(), :oid, :pid, :sid,
                            :year, :code, :qty
                        )
                    """, {
                        "oid": order_id,
                        "pid": booth_parent_id,
                        "sid": booth_scout_id,
                        "year": ss.current_year,
                        "code": code,
                        "qty": qty,
                    })

                st.toast(f"✅ Booth created: {location} on {booth_date.strftime('%b %d')} at {start_time.strftime('%I:%M %p')}", icon="🎉")
                time_module.sleep(5)
                if st.button("Clear", key="clear_after_create"):
                    # Clear form fields
                    for key in ["create_location", "create_booth_date", "create_start_time", "create_scout_ids"]:
                        if key in ss:
                            del ss[key]
                    st.rerun()

    # ==================================================
    # TAB 2 — PRINT BOOTH
    # ==================================================
    with tab_print:
        st.markdown("### Printable Booth Sheet")

        booths = get_booths()
        
        if not booths:
            st.info("No booths have been created yet.")
        else:
            # Get all NEW booths (status='NEW')
            new_booths = []
            for b in booths:
                order_status = fetch_all("""
                    SELECT status 
                    FROM cookies_app.orders 
                    WHERE booth_id = :bid AND order_type = 'Booth'
                """, {"bid": b.booth_id})
                if order_status and order_status[0].status == 'NEW':
                    new_booths.append(b)
            
            if new_booths:
                st.markdown("---")
                st.markdown(f"**{len(new_booths)} NEW booth(s) ready to print**")
                
                if st.button("📙 Create 'all new' combined booth print file"):
                    # Generate combined HTML for all NEW booths
                    combined_html = """
                    <style>
                        @media print {
                            body { margin: 0; }
                            .booth-sheet { page-break-after: always; }
                            .booth-sheet:last-child { page-break-after: auto; }
                        }
                        .booth-sheet {
                            font-family: Arial, sans-serif;
                            max-width: 800px;
                            margin: 20px auto;
                            padding: 20px;
                        }
                    </style>
                    """
                    
                    for booth_item in new_booths:
                        cookies = fetch_all("""
                        SELECT 
                            cy.display_name, 
                            cy.price_per_box,
                            cy.cookie_code,
                            bip.planned_quantity
                        FROM cookies_app.booth_inventory_plan bip
                        JOIN cookies_app.cookie_years cy 
                            ON cy.cookie_code = bip.cookie_code 
                            AND cy.program_year = bip.program_year
                        WHERE bip.booth_id = :bid
                          AND bip.program_year = :year
                        ORDER BY cy.display_order
                        """, {"bid": booth_item.booth_id, "year": ss.current_year})
                        
                        total_boxes = sum(c.planned_quantity for c in cookies)
                        
                        combined_html += f"""
                        <div class="booth-sheet">
                            <h1 style="text-align: center; border-bottom: 3px solid #333; padding-bottom: 10px;">
                                Girl Scout Cookie Booth Sheet
                            </h1>
                            
                            <div style="margin: 20px 0; padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                                <h2 style="margin-top: 0;">Booth Information</h2>
                                <p><strong>Location:</strong> {booth_item.location}</p>
                                <p><strong>Date:</strong> {booth_item.booth_date.strftime('%A, %B %d, %Y')}</p>
                                <p><strong>Time:</strong> {booth_item.start_time.strftime('%I:%M %p')} - {booth_item.end_time.strftime('%I:%M %p')}</p>
                                <p><strong>Total Starting Boxes:</strong> {total_boxes}</p>
                            </div>

                            <h2>Cookie Inventory</h2>
                            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                                <thead>
                                    <tr style="background-color: #333; color: white;">
                                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Cookie</th>
                                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Start Qty</th>
                                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">End Qty</th>
                                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Sold</th>
                                        <th style="padding: 10px; text-align: right; border: 1px solid #ddd;">Price</th>
                                        <th style="padding: 10px; text-align: right; border: 1px solid #ddd;">Revenue</th>
                                    </tr>
                                </thead>
                                <tbody>
                        """
                        
                        for i, c in enumerate(cookies):
                            bg_color = "#f9f9f9" if i % 2 == 0 else "white"
                            combined_html += f"""
                                    <tr style="background-color: {bg_color};">
                                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>{c.display_name}</strong></td>
                                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">{c.planned_quantity}</td>
                                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">_____</td>
                                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">_____</td>
                                        <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">${c.price_per_box:.2f}</td>
                                        <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">_________</td>
                                    </tr>
                            """
                        
                        combined_html += """
                                    <tr style="background-color: #e0e0e0; font-weight: bold;">
                                        <td style="padding: 10px; border: 1px solid #ddd;" colspan="3">TOTALS</td>
                                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">_____</td>
                                        <td style="padding: 10px; border: 1px solid #ddd;"></td>
                                        <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">$_________</td>
                                    </tr>
                                </tbody>
                            </table>

                            <div style="margin: 30px 0; padding: 20px; border: 2px solid #333; border-radius: 5px;">
                                <h2 style="margin-top: 0;">Cash Reconciliation</h2>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                                    <div>
                                        <p><strong>1. Ending Money:</strong></p>
                                        <p><strong>   1a. (Cash):</strong> $__________</p>
                                        <p><strong>   1b. (Square):</strong> $__________</p>
                                        <p><strong>1. Total Ending Money</strong> $__________</p>
                                        <p><strong>2. Starting Cash:</strong> $__________</p>
                                        <p><strong>3. Actual Revenue (1 - 2):</strong> $__________</p>
                                    </div>
                                    <div>
                                        <p><strong>4. Expected Revenue:</strong> $__________</p>
                                        <p><strong>5. Over / Under (3 - 4):</strong> $__________</p>
                                        <p><strong>6. OPC Boxes:</strong> __________</p>
                                    </div>
                                </div>
                            </div>

                            <div style="margin: 30px 0; padding: 20px; background-color: #f9f9f9; border-radius: 5px;">
                                <h3>Notes / Issues:</h3>
                                <div style="min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: white;">
                                    &nbsp;
                                </div>
                            </div>

                            <div style="margin: 40px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                                <div style="border-top: 2px solid #333; padding-top: 10px;">
                                    <p style="margin: 5px 0;"><strong>Outgoing Signature:</strong></p>
                                    <p style="margin: 5px 0; font-size: 12px;">Name: ____________________</p>
                                    <p style="margin: 5px 0; font-size: 12px;">Date/Time: ____________________</p>
                                </div>
                                <div style="border-top: 2px solid #333; padding-top: 10px;">
                                    <p style="margin: 5px 0;"><strong>Return Signature:</strong></p>
                                    <p style="margin: 5px 0; font-size: 12px;">Name: ____________________</p>
                                    <p style="margin: 5px 0; font-size: 12px;">Date/Time: ____________________</p>
                                </div>
                            </div>
                        </div>
                        """
                    
                    st.download_button(
                        label="🖨 Download All NEW Booth Sheets (Combined HTML)",
                        data=combined_html,
                        file_name=f"all_new_booth_sheets_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html",
                        help="Download all NEW booths in one HTML file - each booth will print on a separate page",
                        key="download_all_new"
                    )
                    st.success(f"✅ Generated {len(new_booths)} booth sheets ready to download!")
                
                st.markdown("---")
            
            st.markdown("### Individual Booth Sheet")
            booth = st.selectbox(
                "Select Booth",
                booths,
                format_func=lambda b: (
                    f"{b.booth_date.strftime('%b %d')} "
                    f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
                    f"{b.location}"
                ),
                key="booth_print_select"
            )

            cookies = fetch_all("""
            SELECT 
                cy.display_name, 
                cy.price_per_box,
                cy.cookie_code,
                bip.planned_quantity
            FROM cookies_app.booth_inventory_plan bip
            JOIN cookies_app.cookie_years cy 
                ON cy.cookie_code = bip.cookie_code 
                AND cy.program_year = bip.program_year
            WHERE bip.booth_id = :bid
              AND bip.program_year = :year
            ORDER BY cy.display_order
            """, {"bid": booth.booth_id, "year": ss.current_year})

            # Generate printable HTML
            total_boxes = sum(c.planned_quantity for c in cookies)
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px;">
                <h1 style="text-align: center; border-bottom: 3px solid #333; padding-bottom: 10px;">
                    Girl Scout Cookie Booth Sheet
                </h1>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                    <h2 style="margin-top: 0;">Booth Information</h2>
                    <p><strong>Location:</strong> {booth.location}</p>
                    <p><strong>Date:</strong> {booth.booth_date.strftime('%A, %B %d, %Y')}</p>
                    <p><strong>Time:</strong> {booth.start_time.strftime('%I:%M %p')} - {booth.end_time.strftime('%I:%M %p')}</p>
                    <p><strong>Total Starting Boxes:</strong> {total_boxes}</p>
                </div>

                <h2>Cookie Inventory</h2>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background-color: #333; color: white;">
                            <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Cookie</th>
                            <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Start Qty</th>
                            <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">End Qty</th>
                            <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Sold</th>
                            <th style="padding: 10px; text-align: right; border: 1px solid #ddd;">Price</th>
                            <th style="padding: 10px; text-align: right; border: 1px solid #ddd;">Revenue</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for i, c in enumerate(cookies):
                bg_color = "#f9f9f9" if i % 2 == 0 else "white"
                html_content += f"""
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>{c.display_name}</strong></td>
                            <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">{c.planned_quantity}</td>
                            <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">_____</td>
                            <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">_____</td>
                            <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">${c.price_per_box:.2f}</td>
                            <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">_________</td>
                        </tr>
                """
            
            html_content += """
                        <tr style="background-color: #e0e0e0; font-weight: bold;">
                            <td style="padding: 10px; border: 1px solid #ddd;" colspan="3">TOTALS</td>
                            <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">_____</td>
                            <td style="padding: 10px; border: 1px solid #ddd;"></td>
                            <td style="padding: 10px; text-align: right; border: 1px solid #ddd;">$_________</td>
                        </tr>
                    </tbody>
                </table>

                <div style="margin: 30px 0; padding: 20px; border: 2px solid #333; border-radius: 5px;">
                    <h2 style="margin-top: 0;">Cash Reconciliation</h2>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <p><strong>1. Ending Money:</strong></p>
                            <p><strong>   1a. (Cash):</strong> $__________</p>
                            <p><strong>   1b. (Square):</strong> $__________</p>
                            <p><strong>1. Total Ending Money</strong> $__________</p>
                            <p><strong>2. Starting Cash:</strong> $__________</p>
                            <p><strong>3. Actual Revenue (1 - 2):</strong> $__________</p>
                        </div>
                        <div>
                            <p><strong>4. Expected Revenue:</strong> $__________</p>
                            <p><strong>5. Over / Under (3 - 4):</strong> $__________</p>
                            <p><strong>6. OPC Boxes (5/$6):</strong> __________</p>
                        </div>
                    </div>
                </div>

                <div style="margin: 30px 0; padding: 20px; background-color: #f9f9f9; border-radius: 5px;">
                    <h3>Notes / Issues:</h3>
                    <div style="min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: white;">
                        &nbsp;
                    </div>
                </div>

                <div style="margin: 40px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                    <div style="border-top: 2px solid #333; padding-top: 10px;">
                        <p style="margin: 5px 0;"><strong>Outgoing Signature:</strong></p>
                        <p style="margin: 5px 0; font-size: 12px;">Name: ____________________</p>
                        <p style="margin: 5px 0; font-size: 12px;">Date/Time: ____________________</p>
                    </div>
                    <div style="border-top: 2px solid #333; padding-top: 10px;">
                        <p style="margin: 5px 0;"><strong>Return Signature:</strong></p>
                        <p style="margin: 5px 0; font-size: 12px;">Name: ____________________</p>
                        <p style="margin: 5px 0; font-size: 12px;">Date/Time: ____________________</p>
                    </div>
                </div>
            </div>

            <style>
                @media print {{
                    body {{ margin: 0; }}
                    .stApp {{ padding: 0 !important; }}
                    header, footer, .stTabs, .stSelectbox {{ display: none !important; }}
                }}
            </style>
            """
            
            # Download button
            st.download_button(
                label="🖨 Download Booth Sheet (HTML)",
                data=html_content,
                file_name=f"booth_sheet_{booth.location.replace(' ', '_')}_{booth.booth_date.strftime('%Y%m%d')}.html",
                mime="text/html",
                help="Download as HTML file - open in browser and print"
            )
            
            st.info("💡 Click the download button above, then open the HTML file in your browser and print.")

    # ==================================================
    # TAB 3 — VERIFY BOOTH
    # ==================================================
    with tab_verify:
        st.markdown("## 🧾 Booth Verification")

        # ----------------------------------
        # Load booths awaiting verification
        # ----------------------------------
        booths = fetch_all("""
            SELECT
                o.order_id,
                o.program_year,
                o.booth_id,
                b.location,
                b.booth_date,
                b.start_time,
                b.end_time,
                o.starting_cash,
                o.ending_cash,
                o.square_total
            FROM cookies_app.orders o
            JOIN cookies_app.booths b ON b.booth_id = o.booth_id
            WHERE o.order_type = 'Booth'
            AND o.verification_status = 'DRAFT'
            ORDER BY b.booth_date DESC, b.start_time
        """)

        if not booths:
            st.success("No booths awaiting verification.")
        else:
            booth = st.selectbox(
                "Select Booth",
                booths,
                format_func=lambda b: (
                    f"{b.booth_date.strftime('%b %d')} "
                    f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
                    f"{b.location}"
                ),
                key='booth_verify_select'
            )

            # ----------------------------------
            # Load planned inventory (START)
            # ----------------------------------
            items = fetch_all("""
                SELECT
                    bip.cookie_code,
                    cy.display_name,
                    cy.price_per_box,
                    bip.planned_quantity AS start_qty
                FROM cookies_app.booth_inventory_plan bip
                JOIN cookies_app.cookie_years cy
                ON cy.cookie_code = bip.cookie_code
                AND cy.program_year = bip.program_year
                WHERE bip.booth_id = :bid
                AND bip.program_year = :year
                ORDER BY cy.display_order
            """, {
                "bid": booth.booth_id,
                "year": booth.program_year
            })

            if not items:
                st.warning("No planned inventory found for this booth.")
            else:
                st.markdown(f"### Booth: {booth.location} on {booth.booth_date.strftime('%b %d, %Y')}")
                # ----------------------------------
                # Cookie Count Table (Admin Editable)
                # ----------------------------------
                st.markdown("### 🍪 Cookie Counts")

                header = st.columns([3, 2, 2, 2, 2])
                header[0].markdown("**Cookie**")
                header[1].markdown("**Start**")
                header[2].markdown("**End**")
                header[3].markdown("**Sold**")
                header[4].markdown("**Revenue**")

                total_sold = 0
                expected_revenue = Decimal("0.00")

                verified_items = []

                for i in items:
                    row = st.columns([3, 2, 2, 2, 2])

                    row[0].markdown(f"**{i.display_name}**  \n${Decimal(i.price_per_box):.2f}")

                    start_qty = int(i.start_qty)

                    end_qty = row[2].number_input(
                        label="",
                        min_value=0,
                        value=0,
                        step=1,
                        key=f"end_{i.cookie_code}"
                    )

                    row[1].markdown(f"{start_qty}")

                    sold = start_qty - end_qty
                    sold = max(sold, 0)

                    revenue = Decimal(sold) * Decimal(i.price_per_box)

                    row[3].markdown(f"{sold}")
                    row[4].markdown(f"${revenue:.2f}")

                    total_sold += sold
                    expected_revenue += revenue

                    verified_items.append({
                        "cookie_code": i.cookie_code,
                        "sold": sold
                    })

                # ----------------------------------
                # Totals
                # ----------------------------------
                st.markdown("---")
                col1, col2 = st.columns(2)
                col1.metric("Total Boxes Sold", total_sold)
                col2.metric("Expected Revenue", f"${expected_revenue:.2f}")

                # ----------------------------------
                # Money Reconciliation
                # ----------------------------------
                st.markdown("---")
                st.markdown("### 💵 Money Reconciliation")

                starting_cash = Decimal(booth.starting_cash or 0)
                ending_cash = Decimal(booth.ending_cash or 0)
                square_total = Decimal(booth.square_total or 0)

                ending_money = ending_cash + square_total
                actual_revenue = ending_money - starting_cash
                diff = actual_revenue - expected_revenue

                st.write(f"Starting Cash: ${starting_cash:.2f}")
                st.write(f"Ending Cash: ${ending_cash:.2f}")
                st.write(f"Square / Credit: ${square_total:.2f}")
                st.write(f"Ending Money: ${ending_money:.2f}")
                st.write(f"Actual Revenue: ${actual_revenue:.2f}")
                st.write(f"Over / Under: ${diff:.2f}")

                opc_boxes = int(
                    (diff / Decimal("6")).to_integral_value(rounding=ROUND_FLOOR)
                    if diff > 0 else 0
                )

                st.write(f"**OPC Boxes:** {opc_boxes}")

                # ----------------------------------
                # Verification Controls
                # ----------------------------------
                st.markdown("---")
                st.markdown("### ✅ Verification")

                verify_cookies = st.checkbox("I verify cookie counts")
                verify_money = st.checkbox("I verify money totals")

                notes = st.text_area("Admin Notes (required)", height=80)

                admin_name = ss.get("user_name", "Admin")

                if st.button("Booth Verified"):
                    if not verify_cookies or not verify_money:
                        st.error("Both verification checkboxes must be checked.")
                    elif not notes.strip():
                        st.error("Verification notes are required.")
                    else:
                        verify_booth(booth.order_id, booth.program_year, verified_items, admin_name, notes, opc_boxes)
                        st.success(f"Booth verified by {admin_name}. Inventory updated.")
                        time_module.sleep(3)
                        if st.button("Clear", key="clear_after_verify"):
                            st.rerun()

    # ==================================================
    # TAB 4 — DELETE BOOTH
    # ==================================================
    with tab_delete:
        try:
            st.markdown("## 🗑️ Delete Booth")

            st.warning("⚠️ Deleting a booth will permanently delete the booth and all associated data (inventory, money records, etc.). This action cannot be undone.")

            # Get all booths
            all_booths = fetch_all("""
                SELECT
                    b.booth_id,
                    b.location,
                    b.booth_date,
                    b.start_time,
                    b.end_time
                FROM cookies_app.booths b
                ORDER BY b.booth_date DESC, b.start_time
            """)
            
            if not all_booths:
                st.info("No booths available for deletion.")
            else:
                booth = st.selectbox(
                    "Select Booth to Delete",
                    all_booths,
                    format_func=lambda b: (
                        f"{b.booth_date.strftime('%b %d')} "
                        f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
                        f"{b.location}"
                    ),
                    index=None,
                    key="delete_booth_select"
                )

                st.markdown("---")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    confirm = st.checkbox("I want to delete this booth")
                
                with col2:
                    confirm_permanent = st.checkbox("This is permanent and cannot be undone")

                with col3:
                    if st.button("🗑️ Delete Booth", type="secondary"):
                        if not confirm or not confirm_permanent:
                            st.error("Please confirm both checkboxes before deleting.")
                        else:
                            # Use CASCADE DELETE utility function
                            try:
                                success = delete_booth_cascade(str(booth.booth_id))
                                if success:
                                    st.success(f"✓ Deleted: {booth.location} on {booth.booth_date.strftime('%b %d')}", icon="🗑️")
                                    time_module.sleep(3)
                                    # if st.button("Clear", key="clear_after_delete"):
                                    # Clear booth selector
                                    if "delete_booth_select" in ss:
                                        del ss["delete_booth_select"]
                                        st.rerun()
                                else:
                                    st.error("Failed to delete booth. Check logs for details.")
                            except Exception as ex:
                                st.error(f"Failed to delete booth: {str(ex)}")
        except Exception as ex:
            st.error(f"🚨 EXCEPTION: {str(ex)}")
            import traceback
            st.code(traceback.format_exc())

    # ==================================================
    # TAB 5 — VIEW ALL BOOTHS
    # ==================================================
    with tab_view:
        st.markdown("## 📋 All Booths")
        
        booths = fetch_all("""
            SELECT
                b.booth_id,
                b.location,
                b.booth_date,
                b.start_time,
                b.end_time,
                b.weekend_number,
                b.quantity_multiplier,
                b.created_at
            FROM cookies_app.booths b
            ORDER BY b.booth_date DESC, b.start_time
        """)
        
        if not booths:
            st.info("No booths have been created yet.")
        else:
            st.write(f"**Total Booths:** {len(booths)}")
            
            for booth in booths:
                with st.expander(f"{booth.location} - {booth.booth_date.strftime('%b %d, %Y')} {booth.start_time.strftime('%I:%M %p')}–{booth.end_time.strftime('%I:%M %p')}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Booth ID:** `{booth.booth_id}`")
                        st.write(f"**Location:** {booth.location}")
                        
                        # Editable date
                        new_date = st.date_input(
                            "Date",
                            value=booth.booth_date,
                            key=f"date_{booth.booth_id}"
                        )
                        
                        # Editable start time (hourly increments only)
                        new_start_time = st.time_input(
                            "Start Time",
                            value=booth.start_time,
                            step=3600,  # 1 hour in seconds
                            key=f"start_{booth.booth_id}"
                        )
                        
                        # Calculate end time as 2 hours after start time
                        start_dt = datetime.combine(datetime.today(), new_start_time)
                        end_dt = start_dt + timedelta(hours=2)
                        new_end_time = end_dt.time()
                        
                        st.write(f"**End Time:** {new_end_time.strftime('%I:%M %p')}")
                    
                    with col2:
                        st.write(f"**Weekend #:** {booth.weekend_number}")
                        st.write(f"**Multiplier:** {float(booth.quantity_multiplier):.0%}")
                        st.write(f"**Created:** {booth.created_at.strftime('%b %d, %Y %I:%M %p')}")
                    
                    # Check if date or time changed
                    date_changed = new_date != booth.booth_date
                    time_changed = new_start_time != booth.start_time
                    
                    if date_changed or time_changed:
                        if st.button("💾 Save Date/Time Changes", key=f"save_datetime_{booth.booth_id}"):
                            execute_sql("""
                                UPDATE cookies_app.booths
                                SET booth_date = :date,
                                    start_time = :start,
                                    end_time = :end
                                WHERE booth_id = :bid
                            """, {
                                "date": new_date,
                                "start": new_start_time,
                                "end": new_end_time,
                                "bid": booth.booth_id
                            })
                            st.success(f"✅ Date/Time updated for {booth.location}")
                            st.rerun()
                    
                    # Get planned inventory
                    inventory = fetch_all("""
                        SELECT
                            bip.cookie_code,
                            cy.display_name,
                            bip.planned_quantity
                        FROM cookies_app.booth_inventory_plan bip
                        JOIN cookies_app.cookie_years cy
                        ON cy.cookie_code = bip.cookie_code
                        AND cy.program_year = bip.program_year
                        WHERE bip.booth_id = :bid
                        ORDER BY cy.display_order
                    """, {"bid": booth.booth_id})
                    
                    if inventory:
                        st.markdown("**Edit Planned Inventory:**")
                        
                        # Create editable inventory form
                        updated_inventory = {}
                        inv_cols = st.columns(3)
                        
                        for idx, item in enumerate(inventory):
                            col = inv_cols[idx % 3]
                            new_qty = col.number_input(
                                f"{item.cookie_code}",
                                min_value=0,
                                value=int(item.planned_quantity),
                                step=1,
                                key=f"booth_{booth.booth_id}_{item.cookie_code}"
                            )
                            updated_inventory[item.cookie_code] = new_qty
                        
                        total_boxes = sum(updated_inventory.values())
                        st.write(f"**Total Boxes:** {total_boxes}")
                        
                        # Save button
                        if st.button("💾 Save Inventory Changes", key=f"save_{booth.booth_id}"):
                            # Update each cookie quantity
                            for cookie_code, new_qty in updated_inventory.items():
                                execute_sql("""
                                    UPDATE cookies_app.booth_inventory_plan
                                    SET planned_quantity = :qty
                                    WHERE booth_id = :bid
                                      AND cookie_code = :code
                                      AND program_year = :year
                                """, {
                                    "qty": new_qty,
                                    "bid": booth.booth_id,
                                    "code": cookie_code,
                                    "year": ss.current_year
                                })
                            
                            # Also update order_items for this booth
                            order = fetch_all("""
                                SELECT order_id FROM cookies_app.orders
                                WHERE booth_id = :bid AND order_type = 'Booth'
                            """, {"bid": booth.booth_id})
                            
                            if order:
                                order_id = order[0].order_id
                                for cookie_code, new_qty in updated_inventory.items():
                                    # Check if order_item exists
                                    existing = fetch_all("""
                                        SELECT 1 FROM cookies_app.order_items
                                        WHERE order_id = :oid AND cookie_code = :code
                                    """, {"oid": order_id, "code": cookie_code})
                                    
                                    if existing:
                                        # Update existing
                                        execute_sql("""
                                            UPDATE cookies_app.order_items
                                            SET quantity = :qty
                                            WHERE order_id = :oid AND cookie_code = :code
                                        """, {"qty": new_qty, "oid": order_id, "code": cookie_code})
                                    else:
                                        # Insert new
                                        execute_sql("""
                                            INSERT INTO cookies_app.order_items 
                                            (order_item_id, order_id, parent_id, scout_id, program_year, cookie_code, quantity)
                                            SELECT gen_random_uuid(), :oid, parent_id, scout_id, program_year, :code, :qty
                                            FROM cookies_app.orders WHERE order_id = :oid
                                        """, {"oid": order_id, "code": cookie_code, "qty": new_qty})
                                
                                # Update total boxes and amount on order
                                total_amount = total_boxes * 6
                                execute_sql("""
                                    UPDATE cookies_app.orders
                                    SET order_qty_boxes = :boxes,
                                        order_amount = :amount
                                    WHERE order_id = :oid
                                """, {"boxes": total_boxes, "amount": total_amount, "oid": order_id})
                            
                            st.success(f"✅ Inventory updated for {booth.location}")
                            st.rerun()
                    
                    # Get assigned scouts
                    scouts = fetch_all("""
                        SELECT s.first_name, s.last_name
                        FROM cookies_app.booth_scouts bs
                        JOIN cookies_app.scouts s ON bs.scout_id = s.scout_id
                        WHERE bs.booth_id = :bid
                        ORDER BY s.last_name, s.first_name
                    """, {"bid": booth.booth_id})
                    
                    if scouts:
                        st.markdown("**Assigned Scouts:**")
                        scout_names = ", ".join([f"{s.first_name} {s.last_name}" for s in scouts])
                        st.write(scout_names)

# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Admin",
        initial_sidebar_state="expanded"
    )
    main()

