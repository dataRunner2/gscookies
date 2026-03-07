import streamlit as st
import pandas as pd
from decimal import Decimal, ROUND_FLOOR
from streamlit import session_state as ss
from datetime import time, datetime, timedelta
from uuid import uuid4
import time as time_module
import math
from utils.app_utils import setup
from utils.db_utils import require_admin, execute_sql, execute_many_sql, fetch_all
from utils.order_utils import delete_booth_cascade, set_add_ebudde

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


def get_booth_scout_names(booth_id):
    rows = fetch_all("""
        SELECT s.first_name, s.last_name
        FROM cookies_app.booth_scouts bs
        JOIN cookies_app.scouts s ON s.scout_id = bs.scout_id
        WHERE bs.booth_id = :bid
        ORDER BY s.last_name, s.first_name
    """, {"bid": booth_id})
    if not rows:
        return "____________________________"
    return ", ".join(f"{r.first_name} {r.last_name}" for r in rows)


# Booth queries
def verify_booth(order_id, year, items, admin_name, notes, opc_boxes):
    order_row = fetch_all("""
        SELECT parent_id, scout_id, verification_status
        FROM cookies_app.orders
        WHERE order_id = :oid
        LIMIT 1
    """, {"oid": order_id})

    if not order_row:
        return

    order_parent_id = order_row[0].parent_id
    order_scout_id = order_row[0].scout_id
    current_status = order_row[0].verification_status

    # Safe fallbacks for required not-null ledger columns
    if not order_parent_id:
        order_parent_id = 'f056ec09-9273-4e2d-8532-3b2cf0c7b704'
    if not order_scout_id:
        order_scout_id = '7bcf1980-ccb7-4d0c-b0a0-521b542356fa'

    if current_status == 'VERIFIED':
        execute_sql("""
            UPDATE cookies_app.orders
            SET verified_by = :by,
                verified_at = now(),
                verification_notes = :notes,
                opc_boxes = :opc
            WHERE order_id = :oid
        """, {
            "oid": order_id,
            "by": admin_name,
            "notes": notes,
            "opc": opc_boxes,
        })
    else:
        execute_sql("""
            UPDATE cookies_app.orders
            SET verification_status = 'VERIFIED',
                status = 'VERIFIED',
                verified_by = :by,
                verified_at = now(),
                verification_notes = :notes,
                opc_boxes = :opc
            WHERE order_id = :oid
        """, {
            "oid": order_id,
            "by": admin_name,
            "notes": notes,
            "opc": opc_boxes,
        })

    # Rebuild booth sale ledger rows so edits to verified booths persist correctly
    execute_sql("""
        DELETE FROM cookies_app.inventory_ledger
        WHERE related_order_id = :oid
          AND event_type = 'BOOTH_SALE'
    """, {"oid": order_id})

    # Record inventory movements
    for i in items:
        if i.get('sold', 0) == 0:
            continue
        
        execute_sql("""
            INSERT INTO cookies_app.inventory_ledger (
                inventory_event_id,
                parent_id,
                scout_id,
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
                :pid,
                :sid,
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
            "pid": order_parent_id,
            "sid": order_scout_id,
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

    section_options = [
        "➕ Add / Manage Booths",
        "📋 View All Booths",
        "✏️ Edit Booths",
        "🖨️ Print Booth Sheet",
        "✅ Verify Booth",
        "📒 eBudde",
        "🗑️ Delete Booth",
    ]
    active_section = st.radio(
        "Booth Sections",
        section_options,
        horizontal=True,
        label_visibility="collapsed",
        key="booth_admin_section",
    )

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

    if active_section == "➕ Add / Manage Booths":
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
    if active_section == "🖨️ Print Booth Sheet":
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
                                                    AND bip.cookie_code != 'DON'
                        ORDER BY cy.display_order
                        """, {"bid": booth_item.booth_id, "year": ss.current_year})
                        
                        total_boxes = sum(c.planned_quantity for c in cookies)
                        scout_names = get_booth_scout_names(booth_item.booth_id)
                        
                        combined_html += f"""
                        <div class="booth-sheet">
                            <h1 style="text-align: center; border-bottom: 3px solid #333; padding-bottom: 10px;">
                                Girl Scout Cookie Booth Sheet
                            </h1>
                            
                            <div style="margin: 20px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                                <div style="padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                                    <h2 style="margin-top: 0;">Booth Information</h2>
                                    <p><strong>Location:</strong> {booth_item.location}</p>
                                    <p><strong>Date:</strong> {booth_item.booth_date.strftime('%A, %B %d, %Y')}</p>
                                    <p><strong>Time:</strong> {booth_item.start_time.strftime('%I:%M %p')} - {booth_item.end_time.strftime('%I:%M %p')}</p>
                                    <p><strong>Total Starting Boxes:</strong> {total_boxes}</p>
                                </div>
                                <div style="padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                                    <h2 style="margin-top: 0;">Scouts</h2>
                                    <p>{scout_names}</p>
                                </div>
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
                            AND bip.cookie_code != 'DON'
            ORDER BY cy.display_order
            """, {"bid": booth.booth_id, "year": ss.current_year})

            # Generate printable HTML
            total_boxes = sum(c.planned_quantity for c in cookies)
            scout_names = get_booth_scout_names(booth.booth_id)
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px;">
                <h1 style="text-align: center; border-bottom: 3px solid #333; padding-bottom: 10px;">
                    Girl Scout Cookie Booth Sheet
                </h1>
                
                <div style="margin: 20px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div style="padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                        <h2 style="margin-top: 0;">Booth Information</h2>
                        <p><strong>Location:</strong> {booth.location}</p>
                        <p><strong>Date:</strong> {booth.booth_date.strftime('%A, %B %d, %Y')}</p>
                        <p><strong>Time:</strong> {booth.start_time.strftime('%I:%M %p')} - {booth.end_time.strftime('%I:%M %p')}</p>
                        <p><strong>Total Starting Boxes:</strong> {total_boxes}</p>
                    </div>
                    <div style="padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
                        <h2 style="margin-top: 0;">Scouts</h2>
                        <p>{scout_names}</p>
                    </div>
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
    # TAB — EDIT BOOTHS (TABLE)
    # ==================================================
    if active_section == "✏️ Edit Booths":
        st.markdown("## ✏️ Edit Booths")

        status_filter = st.selectbox(
            "Filter",
            options=["Planned (Not Verified)", "Verified"],
            key="edit_booths_status_filter",
        )
        show_verified = status_filter == "Verified"
        if show_verified:
            st.caption("Showing ending quantities for verified booths.")
        else:
            st.caption("Showing starting quantities for planned booths.")

        cookie_rows = fetch_all("""
            SELECT cookie_code
            FROM cookies_app.cookie_years
            WHERE program_year = :year
              AND active = TRUE
              AND cookie_code <> 'DON'
            ORDER BY display_order
        """, {"year": int(ss.current_year)})
        cookie_codes = [r.cookie_code for r in cookie_rows]

        if not cookie_codes:
            st.info("No active cookie types configured for this year.")
        else:
            booth_orders = fetch_all("""
                SELECT
                    o.order_id,
                    o.booth_id,
                    o.program_year,
                    COALESCE(o.verification_status, 'DRAFT') AS verification_status,
                    b.booth_date,
                    b.start_time,
                    b.location
                FROM cookies_app.orders o
                JOIN cookies_app.booths b ON b.booth_id = o.booth_id
                WHERE o.order_type = 'Booth'
                  AND o.program_year = :year
                ORDER BY b.booth_date DESC, b.start_time, b.location
            """, {"year": int(ss.current_year)})

            planned_rows = fetch_all("""
                SELECT
                    booth_id,
                    program_year,
                    cookie_code,
                    planned_quantity
                FROM cookies_app.booth_inventory_plan
                WHERE program_year = :year
            """, {"year": int(ss.current_year)})

            planned_lookup = {
                (str(r.booth_id), r.cookie_code): int(r.planned_quantity or 0)
                for r in planned_rows
            }

            sold_rows = fetch_all("""
                SELECT
                    il.related_order_id AS order_id,
                    il.cookie_code,
                    SUM(-il.quantity) AS sold_qty
                FROM cookies_app.inventory_ledger il
                JOIN cookies_app.orders o ON o.order_id = il.related_order_id
                WHERE il.event_type = 'BOOTH_SALE'
                  AND o.order_type = 'Booth'
                  AND o.program_year = :year
                GROUP BY il.related_order_id, il.cookie_code
            """, {"year": int(ss.current_year)})

            sold_lookup = {
                (str(r.order_id), r.cookie_code): int(r.sold_qty or 0)
                for r in sold_rows
            }

            table_rows = []
            booth_meta_by_id = {}
            for booth in booth_orders:
                is_verified = booth.verification_status == 'VERIFIED'
                if show_verified != is_verified:
                    continue

                booth_id = str(booth.booth_id)
                booth_meta_by_id[booth_id] = {
                    "order_id": str(booth.order_id),
                    "program_year": int(booth.program_year),
                    "is_verified": is_verified,
                }

                row = {
                    "booth_id": booth_id,
                    "Date": booth.booth_date,
                    "Time": booth.start_time.strftime('%I:%M %p'),
                    "Location": booth.location,
                    "Status": "Verified" if is_verified else "Planned",
                }

                total_boxes = 0
                for code in cookie_codes:
                    start_qty = int(planned_lookup.get((booth_id, code), 0))
                    if is_verified:
                        sold_qty = int(sold_lookup.get((str(booth.order_id), code), 0))
                        display_qty = max(start_qty - sold_qty, 0)
                    else:
                        display_qty = start_qty
                    row[code] = display_qty
                    total_boxes += display_qty
                row["Total Boxes"] = total_boxes

                table_rows.append(row)

            if not table_rows:
                st.info("No booths match this filter.")
            else:
                table_df = pd.DataFrame(table_rows).set_index("booth_id")
                ordered_cols = ["Date", "Time", "Location", "Status"] + cookie_codes + ["Total Boxes"]
                table_df = table_df[ordered_cols]

                editor_key = "booth_qty_editor_verified" if show_verified else "booth_qty_editor_planned"
                save_key = "save_booth_qty_verified" if show_verified else "save_booth_qty_planned"

                edited_df = st.data_editor(
                    table_df,
                    width='stretch',
                    hide_index=True,
                    num_rows="fixed",
                    disabled=["Date", "Time", "Location", "Status", "Total Boxes"],
                    key=editor_key,
                )

                if st.button("💾 Save Quantity Updates", key=save_key):
                    changed_cells = 0
                    changed_booths = set()
                    changed_records = []

                    existing_plan_keys = {
                        (str(r.booth_id), int(r.program_year), r.cookie_code)
                        for r in planned_rows
                    }

                    booth_order_items = fetch_all("""
                        SELECT
                            oi.order_id,
                            oi.cookie_code
                        FROM cookies_app.order_items oi
                        JOIN cookies_app.orders o ON o.order_id = oi.order_id
                        WHERE o.order_type = 'Booth'
                          AND o.program_year = :year
                    """, {"year": int(ss.current_year)})
                    existing_item_keys = {
                        (str(r.order_id), r.cookie_code)
                        for r in booth_order_items
                    }

                    for booth_id in edited_df.index:
                        booth_key = str(booth_id)
                        meta = booth_meta_by_id[booth_key]
                        order_id = meta["order_id"]
                        is_verified = bool(meta["is_verified"])

                        for code in cookie_codes:
                            new_qty = pd.to_numeric(edited_df.at[booth_id, code], errors='coerce')
                            old_qty = pd.to_numeric(table_df.at[booth_id, code], errors='coerce')
                            new_qty = int(new_qty) if pd.notna(new_qty) else 0
                            old_qty = int(old_qty) if pd.notna(old_qty) else 0
                            new_qty = max(new_qty, 0)

                            if new_qty == old_qty:
                                continue

                            program_year = meta["program_year"]
                            sold_qty = int(sold_lookup.get((order_id, code), 0)) if is_verified else 0
                            start_qty = new_qty + sold_qty

                            changed_records.append({
                                "booth_id": booth_key,
                                "program_year": program_year,
                                "order_id": order_id,
                                "cookie_code": code,
                                "start_qty": start_qty,
                            })

                            changed_cells += 1
                            changed_booths.add(booth_key)

                    if changed_records:
                        plan_updates = []
                        plan_inserts = []
                        item_updates = []
                        item_inserts = []

                        for rec in changed_records:
                            plan_key = (rec["booth_id"], rec["program_year"], rec["cookie_code"])
                            if plan_key in existing_plan_keys:
                                plan_updates.append({
                                    "qty": rec["start_qty"],
                                    "bid": rec["booth_id"],
                                    "year": rec["program_year"],
                                    "code": rec["cookie_code"],
                                })
                            else:
                                plan_inserts.append({
                                    "bid": rec["booth_id"],
                                    "year": rec["program_year"],
                                    "code": rec["cookie_code"],
                                    "qty": rec["start_qty"],
                                })
                                existing_plan_keys.add(plan_key)

                            item_key = (rec["order_id"], rec["cookie_code"])
                            if item_key in existing_item_keys:
                                item_updates.append({
                                    "qty": rec["start_qty"],
                                    "oid": rec["order_id"],
                                    "code": rec["cookie_code"],
                                })
                            else:
                                item_inserts.append({
                                    "oid": rec["order_id"],
                                    "code": rec["cookie_code"],
                                    "qty": rec["start_qty"],
                                })
                                existing_item_keys.add(item_key)

                        if plan_updates:
                            execute_many_sql("""
                                UPDATE cookies_app.booth_inventory_plan
                                SET planned_quantity = :qty
                                WHERE booth_id = :bid
                                  AND program_year = :year
                                  AND cookie_code = :code
                            """, plan_updates)

                        if plan_inserts:
                            execute_many_sql("""
                                INSERT INTO cookies_app.booth_inventory_plan
                                (booth_id, program_year, cookie_code, planned_quantity)
                                VALUES (:bid, :year, :code, :qty)
                            """, plan_inserts)

                        if item_updates:
                            execute_many_sql("""
                                UPDATE cookies_app.order_items
                                SET quantity = :qty
                                WHERE order_id = :oid
                                  AND cookie_code = :code
                            """, item_updates)

                        if item_inserts:
                            execute_many_sql("""
                                INSERT INTO cookies_app.order_items
                                (order_item_id, order_id, parent_id, scout_id, program_year, cookie_code, quantity)
                                SELECT gen_random_uuid(), :oid, parent_id, scout_id, program_year, :code, :qty
                                FROM cookies_app.orders
                                WHERE order_id = :oid
                            """, item_inserts)

                    if changed_booths:
                        order_updates = []
                        for booth_key in changed_booths:
                            meta = booth_meta_by_id[booth_key]
                            order_id = meta["order_id"]
                            is_verified = bool(meta["is_verified"])

                            total_boxes = 0
                            for code in cookie_codes:
                                qty_val = pd.to_numeric(edited_df.at[booth_key, code], errors='coerce')
                                display_qty = int(qty_val) if pd.notna(qty_val) else 0
                                display_qty = max(display_qty, 0)
                                if is_verified:
                                    sold_qty = int(sold_lookup.get((order_id, code), 0))
                                    total_boxes += display_qty + sold_qty
                                else:
                                    total_boxes += display_qty

                            order_updates.append({
                                "boxes": total_boxes,
                                "amount": total_boxes * 6,
                                "oid": order_id,
                            })

                        execute_many_sql("""
                            UPDATE cookies_app.orders
                            SET order_qty_boxes = :boxes,
                                order_amount = :amount
                            WHERE order_id = :oid
                        """, order_updates)

                    if changed_cells:
                        st.success(f"✅ Saved {changed_cells} quantity update(s) across {len(changed_booths)} booth(s).")
                        st.rerun()
                    else:
                        st.info("No quantity changes to save.")

    # ==================================================
    # TAB 3 — VERIFY BOOTH
    # ==================================================
    if active_section == "✅ Verify Booth":
        st.markdown("## 🧾 Booth Verification")

        # Reset verify-form widget state safely on next rerun
        if ss.get("verify_reset_pending"):
            reset_booth_id = ss.get("verify_reset_booth_id")
            keys_to_clear = ["booth_verify_select"]

            if reset_booth_id:
                keys_to_clear.extend([
                    f"verify_notes_{reset_booth_id}",
                    f"verify_assigned_scouts_{reset_booth_id}",
                    f"edit_verified_booth_{reset_booth_id}",
                    f"verify_starting_{reset_booth_id}",
                    f"verify_ending_{reset_booth_id}",
                    f"verify_square_{reset_booth_id}",
                    f"verify_cookie_check_{reset_booth_id}",
                    f"verify_money_check_{reset_booth_id}",
                    f"verify_scout_check_{reset_booth_id}",
                    f"verify_money_lock_{reset_booth_id}",
                ])

                for code in DEFAULT_BOOTH_QTY.keys():
                    keys_to_clear.extend([
                        f"verify_end_{reset_booth_id}_{code}",
                        f"verify_startqty_{reset_booth_id}_{code}",
                    ])

            for key in keys_to_clear:
                if key in ss:
                    del ss[key]

            ss["verify_reset_pending"] = False
            if "verify_reset_booth_id" in ss:
                del ss["verify_reset_booth_id"]

        # ----------------------------------
        # Load booths awaiting verification
        # ----------------------------------
        booths = fetch_all("""
            SELECT
                o.order_id,
                o.program_year,
                o.booth_id,
                o.verification_status,
                o.verification_notes,
                COALESCE((
                    SELECT SUM(-il.quantity)
                    FROM cookies_app.inventory_ledger il
                    WHERE il.related_order_id = o.order_id
                      AND il.event_type = 'BOOTH_SALE'
                ), 0) AS total_boxes_sold,
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
            ORDER BY b.booth_date ASC, b.start_time ASC
        """)

        if not booths:
            st.success("No booths awaiting verification.")
        else:
            show_verified = st.checkbox("Show Verified", value=False, key="verify_show_verified")
            filtered_verify_booths = [b for b in booths if b.verification_status == 'VERIFIED'] if show_verified else [b for b in booths if b.verification_status != 'VERIFIED']

            if not filtered_verify_booths:
                st.info("No booths match current filter.")
                return

            booth = st.selectbox(
                "Select Booth",
                filtered_verify_booths,
                format_func=lambda b: (
                    f"{b.booth_date.strftime('%b %d, %Y')} - "
                    f"{b.start_time.strftime('%I:%M %p')} - "
                    f"{b.location}"
                    + (f" - Sold: {int(b.total_boxes_sold)}" if b.verification_status == 'VERIFIED' else "")
                ),
                index=None,
                placeholder="Select booth",
                key='booth_verify_select'
            )
            if booth is None:
                st.info("Select booth to verify.")
            else:
                all_scouts = fetch_all("""
                    SELECT scout_id, first_name, last_name
                    FROM cookies_app.scouts
                    ORDER BY last_name, first_name
                """)

                assigned_scout_rows = fetch_all("""
                    SELECT s.scout_id, s.first_name, s.last_name
                    FROM cookies_app.booth_scouts bs
                    JOIN cookies_app.scouts s ON s.scout_id = bs.scout_id
                    WHERE bs.booth_id = :bid
                    ORDER BY s.last_name, s.first_name
                """, {"bid": booth.booth_id})

                scout_name_by_id = {
                    s.scout_id: f"{s.first_name} {s.last_name}" for s in all_scouts
                }
                assigned_scout_ids = [s.scout_id for s in assigned_scout_rows]
                is_verified = booth.verification_status == 'VERIFIED'
                allow_edit_verified = st.checkbox(
                    "Edit Booth",
                    value=False,
                    key=f"edit_verified_booth_{booth.booth_id}",
                ) if is_verified else True
                fields_disabled = is_verified and not allow_edit_verified

                scout_key = f"verify_assigned_scouts_{booth.booth_id}"
                notes_key = f"verify_notes_{booth.booth_id}"

                st.markdown("### 👧 Scout Assignment")
                edited_scout_ids = st.multiselect(
                    "Select/Verify Assigned Scouts",
                    options=list(scout_name_by_id.keys()),
                    default=assigned_scout_ids,
                    format_func=lambda sid: scout_name_by_id[sid],
                    max_selections=4,
                    key=scout_key,
                    disabled=fields_disabled,
                )

                sold_rows = fetch_all("""
                    SELECT cookie_code, SUM(-quantity) AS sold_qty
                    FROM cookies_app.inventory_ledger
                    WHERE related_order_id = :oid
                      AND event_type = 'BOOTH_SALE'
                    GROUP BY cookie_code
                """, {"oid": booth.order_id})
                sold_by_code = {r.cookie_code: int(r.sold_qty or 0) for r in sold_rows}

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
                    AND bip.cookie_code != 'DON'
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
                    header[1].markdown("**Starting**")
                    header[2].markdown("**Ending**")
                    header[3].markdown("**Total Sold**")
                    header[4].markdown("**Total $**")

                    total_start_boxes = 0
                    total_sold = 0
                    expected_revenue = Decimal("0.00")

                    verified_items = []
                    row_entries = []

                    for i in items:
                        row = st.columns([3, 2, 2, 2, 2])

                        row[0].markdown(f"**{i.display_name}**  \n${Decimal(i.price_per_box):.2f}")

                        row_entries.append({
                            "item": i,
                            "start_ph": row[1].empty(),
                            "end_ph": row[2].empty(),
                            "sold_ph": row[3].empty(),
                            "revenue_ph": row[4].empty(),
                        })

                    # Render END inputs first so Tab moves straight down this column
                    for entry in row_entries:
                        item = entry["item"]
                        default_end_qty = 0
                        if is_verified:
                            default_end_qty = max(int(item.start_qty) - int(sold_by_code.get(item.cookie_code, 0)), 0)
                        entry["end_qty"] = entry["end_ph"].number_input(
                            label="",
                            min_value=0,
                            value=default_end_qty,
                            step=1,
                            key=f"verify_end_{booth.booth_id}_{item.cookie_code}",
                            disabled=fields_disabled,
                        )

                    # Render START inputs second (still editable)
                    for entry in row_entries:
                        item = entry["item"]
                        entry["start_qty"] = entry["start_ph"].number_input(
                            label="",
                            min_value=0,
                            value=int(item.start_qty),
                            step=1,
                            key=f"verify_startqty_{booth.booth_id}_{item.cookie_code}",
                            disabled=fields_disabled,
                        )

                    for entry in row_entries:
                        i = entry["item"]
                        start_qty = entry["start_qty"]
                        end_qty = entry["end_qty"]

                        sold = start_qty - end_qty
                        sold = max(sold, 0)

                        revenue = Decimal(sold) * Decimal(i.price_per_box)

                        entry["sold_ph"].markdown(f"{sold}")
                        entry["revenue_ph"].markdown(f"${revenue:.2f}")

                        total_start_boxes += start_qty
                        total_sold += sold
                        expected_revenue += revenue

                        verified_items.append({
                            "cookie_code": i.cookie_code,
                            "start_qty": start_qty,
                            "sold": sold
                        })

                    # ----------------------------------
                    # Totals
                    # ----------------------------------
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    col1.metric("Total Start Boxes", total_start_boxes)
                    col2.metric("Expected Revenue", f"${expected_revenue:.2f}")
                    st.caption(f"Total Boxes Sold: {total_sold}")

                    # ----------------------------------
                    # Money Reconciliation
                    # ----------------------------------
                    st.markdown("---")
                    st.markdown("### 💵 Money Reconciliation")

                    money_lock_key = f"verify_money_lock_{booth.booth_id}"
                    lock_money_fields = st.checkbox(
                        "Lock money fields while entering quantities",
                        value=True,
                        key=money_lock_key,
                        disabled=fields_disabled,
                    )
                    if lock_money_fields and not fields_disabled:
                        st.caption("Uncheck to enter Starting Cash, Ending Cash, and Square / Credit.")

                    c1, c2, c3 = st.columns(3)
                    money_fields_disabled = fields_disabled or lock_money_fields

                    starting_cash = Decimal(c1.number_input(
                        "Starting Cash", 
                        value=float(booth.starting_cash or 0), 
                        step=1.0,
                        key=f"verify_starting_{booth.booth_id}",
                        disabled=money_fields_disabled,
                    ))
                    ending_cash = Decimal(c2.number_input(
                        "Ending Cash", 
                        value=float(booth.ending_cash or 0), 
                        step=1.0,
                        key=f"verify_ending_{booth.booth_id}",
                        disabled=money_fields_disabled,
                    ))
                    square_total = Decimal(c3.number_input(
                        "Square / Credit", 
                        value=float(booth.square_total or 0), 
                        step=1.0,
                        key=f"verify_square_{booth.booth_id}",
                        disabled=money_fields_disabled,
                    ))

                    # Always calculate and display the money reconciliation
                    ending_money = ending_cash + square_total
                    actual_revenue = ending_money - starting_cash
                    diff = actual_revenue - expected_revenue

                    st.markdown("---")
                    st.markdown("### 🧮 Calculations")

                    st.write(
                        f"**Ending Cash + Credit = Ending Money:** "
                        f"${ending_cash:.2f} + ${square_total:.2f} = ${ending_money:.2f}"
                    )
                    st.write(
                        f"**Ending Money - Starting Cash = Revenue:** "
                        f"${ending_money:.2f} - ${starting_cash:.2f} = ${actual_revenue:.2f}"
                    )
                    st.write(f"**Expected Revenue:** ${expected_revenue:.2f}")
                    st.write(f"**Sweet Acts of Kindness Boxes:** {math.floor(diff/6):.0f} boxes")

                    # Calculate OPC boxes for verification
                    opc_boxes = int(
                        (diff / Decimal("6")).to_integral_value(rounding=ROUND_FLOOR)
                        if diff > 0 else 0
                    )

                    # ----------------------------------
                    # Verification Controls
                    # ----------------------------------
                    st.markdown("---")
                    st.markdown("### ✅ Verification")

                    verify_cookies = st.checkbox(
                        "I verify cookie counts",
                        value=is_verified,
                        key=f"verify_cookie_check_{booth.booth_id}",
                        disabled=fields_disabled,
                    )
                    verify_money = st.checkbox(
                        "I verify money totals",
                        value=is_verified,
                        key=f"verify_money_check_{booth.booth_id}",
                        disabled=fields_disabled,
                    )
                    verify_scouts = st.checkbox(
                        "I verify assigned scouts",
                        value=is_verified,
                        key=f"verify_scout_check_{booth.booth_id}",
                        disabled=fields_disabled,
                    )

                    notes = st.text_area(
                        "Admin Notes (required)",
                        height=80,
                        value=booth.verification_notes or "",
                        key=notes_key,
                        disabled=fields_disabled,
                    )

                    admin_name = ss.get("user_name", "Admin")

                    if fields_disabled:
                        st.info("This booth is verified. Check 'Edit Booth' to make changes.")

                    button_label = "Save Booth Edits" if is_verified else "Booth Verified"
                    if st.button(button_label, disabled=fields_disabled):
                        if not verify_cookies or not verify_money or not verify_scouts:
                            st.error("All verification checkboxes must be checked.")
                        elif not notes.strip():
                            st.error("Verification notes are required.")
                        elif len(edited_scout_ids) == 0:
                            st.error("Please assign at least one scout before verifying.")
                        else:
                            for item in verified_items:
                                execute_sql("""
                                    UPDATE cookies_app.booth_inventory_plan
                                    SET planned_quantity = :qty
                                    WHERE booth_id = :bid
                                      AND cookie_code = :code
                                      AND program_year = :year
                                """, {
                                    "qty": item["start_qty"],
                                    "bid": booth.booth_id,
                                    "code": item["cookie_code"],
                                    "year": booth.program_year,
                                })

                                existing_item = fetch_all("""
                                    SELECT 1 FROM cookies_app.order_items
                                    WHERE order_id = :oid AND cookie_code = :code
                                """, {
                                    "oid": booth.order_id,
                                    "code": item["cookie_code"],
                                })

                                if existing_item:
                                    execute_sql("""
                                        UPDATE cookies_app.order_items
                                        SET quantity = :qty
                                        WHERE order_id = :oid AND cookie_code = :code
                                    """, {
                                        "qty": item["start_qty"],
                                        "oid": booth.order_id,
                                        "code": item["cookie_code"],
                                    })
                                else:
                                    execute_sql("""
                                        INSERT INTO cookies_app.order_items
                                        (order_item_id, order_id, parent_id, scout_id, program_year, cookie_code, quantity)
                                        SELECT gen_random_uuid(), :oid, parent_id, scout_id, program_year, :code, :qty
                                        FROM cookies_app.orders
                                        WHERE order_id = :oid
                                    """, {
                                        "oid": booth.order_id,
                                        "code": item["cookie_code"],
                                        "qty": item["start_qty"],
                                    })

                            execute_sql("""
                                UPDATE cookies_app.orders
                                SET order_qty_boxes = :boxes,
                                    order_amount = :amount,
                                    starting_cash = :starting_cash,
                                    ending_cash = :ending_cash,
                                    square_total = :square_total
                                WHERE order_id = :oid
                            """, {
                                "boxes": total_start_boxes,
                                "amount": total_start_boxes * 6,
                                "starting_cash": float(starting_cash),
                                "ending_cash": float(ending_cash),
                                "square_total": float(square_total),
                                "oid": booth.order_id,
                            })

                            execute_sql("""
                                DELETE FROM cookies_app.booth_scouts
                                WHERE booth_id = :bid
                            """, {"bid": booth.booth_id})

                            for scout_id in edited_scout_ids:
                                execute_sql("""
                                    INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
                                    VALUES (:bid, :sid)
                                """, {
                                    "bid": booth.booth_id,
                                    "sid": scout_id,
                                })

                            verify_booth(booth.order_id, booth.program_year, verified_items, admin_name, notes, opc_boxes)

                            ss["verify_reset_pending"] = True
                            ss["verify_reset_booth_id"] = f"{booth.booth_id}"

                            st.success(f"Booth verified by {admin_name}. Inventory updated.")
                            st.rerun()

    # ==================================================
    # TAB 4 — DELETE BOOTH
    # ==================================================
    if active_section == "🗑️ Delete Booth":
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
                LEFT JOIN cookies_app.orders o
                    ON o.booth_id = b.booth_id
                   AND o.order_type = 'Booth'
                WHERE COALESCE(o.verification_status, 'DRAFT') <> 'VERIFIED'
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
    if active_section == "📋 View All Booths":
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
            unique_dates = sorted({b.booth_date for b in booths}, reverse=True)
            unique_locations = sorted({b.location for b in booths})

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                selected_date = st.selectbox(
                    "Filter by Date",
                    options=["All"] + unique_dates,
                    format_func=lambda d: "All Dates" if d == "All" else d.strftime('%b %d, %Y'),
                    key="view_booth_date_filter",
                )
            with filter_col2:
                selected_location = st.selectbox(
                    "Filter by Location",
                    options=["All"] + unique_locations,
                    format_func=lambda loc: "All Locations" if loc == "All" else loc,
                    key="view_booth_location_filter",
                )

            filtered_booths = booths
            if selected_date != "All":
                filtered_booths = [b for b in filtered_booths if b.booth_date == selected_date]
            if selected_location != "All":
                filtered_booths = [b for b in filtered_booths if b.location == selected_location]

            st.write(f"**Showing:** {len(filtered_booths)} of {len(booths)} booths")

            all_scouts = fetch_all("""
                SELECT scout_id, first_name, last_name
                FROM cookies_app.scouts
                ORDER BY last_name, first_name
            """)
            scout_name_by_id = {
                s.scout_id: f"{s.first_name} {s.last_name}" for s in all_scouts
            }

            for booth in filtered_booths:
                with st.expander(f"{booth.location} - {booth.booth_date.strftime('%b %d, %Y')} ({booth.booth_date.strftime('%A')}) {booth.start_time.strftime('%I:%M %p')}–{booth.end_time.strftime('%I:%M %p')}"):
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
                            bip.planned_quantity,
                            bip.program_year
                        FROM cookies_app.booth_inventory_plan bip
                        JOIN cookies_app.cookie_years cy
                        ON cy.cookie_code = bip.cookie_code
                        AND cy.program_year = bip.program_year
                        WHERE bip.booth_id = :bid
                        AND bip.cookie_code != 'DON'
                        ORDER BY cy.display_order
                    """, {"bid": booth.booth_id})
                    
                    if inventory:
                        st.markdown("**Edit Planned Inventory:**")
                        
                        # Create editable inventory form
                        updated_inventory = {}
                        inventory_year_by_code = {}
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
                            inventory_year_by_code[item.cookie_code] = int(item.program_year)
                        
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
                                    "year": inventory_year_by_code[cookie_code]
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
                        SELECT s.scout_id, s.first_name, s.last_name
                        FROM cookies_app.booth_scouts bs
                        JOIN cookies_app.scouts s ON bs.scout_id = s.scout_id
                        WHERE bs.booth_id = :bid
                        ORDER BY s.last_name, s.first_name
                    """, {"bid": booth.booth_id})
                    
                    if scouts:
                        st.markdown("**Assigned Scouts:**")
                        scout_names = ", ".join([f"{s.first_name} {s.last_name}" for s in scouts])
                        st.write(scout_names)
                    else:
                        st.markdown("**Assigned Scouts:**")
                        st.write("None assigned")

                    assigned_ids = [s.scout_id for s in scouts]
                    edited_scout_ids = st.multiselect(
                        "Edit Assigned Scouts",
                        options=list(scout_name_by_id.keys()),
                        default=assigned_ids,
                        format_func=lambda sid: scout_name_by_id[sid],
                        max_selections=4,
                        key=f"edit_scouts_{booth.booth_id}",
                    )

                    if st.button("💾 Save Scout Assignments", key=f"save_scouts_{booth.booth_id}"):
                        execute_sql("""
                            DELETE FROM cookies_app.booth_scouts
                            WHERE booth_id = :bid
                        """, {"bid": booth.booth_id})

                        for scout_id in edited_scout_ids:
                            execute_sql("""
                                INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
                                VALUES (:bid, :sid)
                            """, {
                                "bid": booth.booth_id,
                                "sid": scout_id,
                            })

                        st.success("✅ Scout assignments updated")
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Danger Zone**")
                    confirm_delete = st.checkbox(
                        "Confirm delete this booth",
                        key=f"confirm_delete_view_{booth.booth_id}"
                    )
                    if st.button("🗑️ Delete Booth", key=f"delete_view_{booth.booth_id}"):
                        if not confirm_delete:
                            st.warning("Please check 'Confirm delete this booth' first.")
                        else:
                            success = delete_booth_cascade(str(booth.booth_id))
                            if success:
                                st.success(f"✓ Deleted: {booth.location} on {booth.booth_date.strftime('%b %d')}", icon="🗑️")
                                time_module.sleep(2)
                                st.rerun()
                            else:
                                st.error("Failed to delete booth. Check logs for details.")

    # ==================================================
    # TAB 6 — EBUDDE
    # ==================================================
    if active_section == "📒 eBudde":
        st.markdown("## 📒 eBudde")

        booth_rows = fetch_all("""
            SELECT
                o.order_id,
                b.booth_date,
                b.start_time,
                b.location,
                COALESCE(o.add_ebudde, false) AS add_ebudde,
                COALESCE(o.opc_boxes, 0) AS donation_boxes,
                COALESCE(
                    STRING_AGG(
                        DISTINCT TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')),
                        ', '
                    ),
                    ''
                ) AS scouts
            FROM cookies_app.orders o
            JOIN cookies_app.booths b ON b.booth_id = o.booth_id
            LEFT JOIN cookies_app.booth_scouts bs ON bs.booth_id = b.booth_id
            LEFT JOIN cookies_app.scouts s ON s.scout_id = bs.scout_id
            WHERE o.order_type = 'Booth'
            GROUP BY o.order_id, b.booth_date, b.start_time, b.location, o.add_ebudde, o.opc_boxes
            ORDER BY b.booth_date, b.start_time
        """)

        if not booth_rows:
            st.info("No booth orders found.")
        else:
            cookie_codes = [r.cookie_code for r in fetch_all("""
                SELECT cookie_code
                FROM cookies_app.cookie_years
                WHERE program_year = :year
                  AND active = TRUE
                  AND cookie_code <> 'DON'
                ORDER BY display_order
            """, {"year": int(ss.current_year)})]

            sold_rows = fetch_all("""
                SELECT
                    o.order_id,
                    il.cookie_code,
                    SUM(-il.quantity) AS sold_qty
                FROM cookies_app.orders o
                LEFT JOIN cookies_app.inventory_ledger il
                    ON il.related_order_id = o.order_id
                   AND il.event_type = 'BOOTH_SALE'
                WHERE o.order_type = 'Booth'
                  AND il.cookie_code IS NOT NULL
                GROUP BY o.order_id, il.cookie_code
            """)

            sold_lookup = {}
            for r in sold_rows:
                sold_lookup[(str(r.order_id), r.cookie_code)] = int(r.sold_qty or 0)

            table_rows = []
            for r in booth_rows:
                sold_total = 0
                row = {
                    "order_id": str(r.order_id),
                    "Date": r.booth_date,
                    "Time": r.start_time.strftime('%I:%M %p'),
                    "Location": r.location,
                    "Donation Boxes": int(r.donation_boxes or 0),
                    "Scouts": r.scouts,
                    "eBudde Verified": bool(r.add_ebudde),
                }
                for code in cookie_codes:
                    qty = sold_lookup.get((str(r.order_id), code), 0)
                    row[code] = qty
                    sold_total += qty
                row["Total Cookies"] = sold_total
                row["Total Boxes"] = sold_total + row["Donation Boxes"]
                table_rows.append(row)

            df = pd.DataFrame(table_rows)
            ordered_cols = ["Date", "Time", "Location"] + cookie_codes + ["Total Cookies", "Donation Boxes", "Total Boxes", "Scouts", "eBudde Verified", "order_id"]
            df = df[ordered_cols]

            grand_total_cookies = int(df["Total Cookies"].sum())
            grand_total_donations = int(df["Donation Boxes"].sum())
            grand_total_boxes = int(df["Total Boxes"].sum())

            st.markdown("### Totals (All Booths)")
            t1, t2, t3 = st.columns(3)
            t1.metric("All Cookies", grand_total_cookies)
            t2.metric("All Donations", grand_total_donations)
            t3.metric("All Cookies + Donations", grand_total_boxes)

            edited = st.data_editor(
                df,
                width='stretch',
                hide_index=True,
                num_rows="fixed",
                disabled=[c for c in df.columns if c not in {"eBudde Verified"}],
                column_config={
                    "eBudde Verified": st.column_config.CheckboxColumn("eBudde Verified"),
                    "order_id": st.column_config.TextColumn("order_id", disabled=True),
                },
                key="booth_ebudde_editor",
            )

            if st.button("💾 Save eBudde Updates", key="save_booth_ebudde"):
                changes = 0
                for _, row in edited.iterrows():
                    order_id = str(row["order_id"])
                    new_val = bool(row["eBudde Verified"])
                    old_val = bool(df.loc[df["order_id"] == order_id, "eBudde Verified"].iloc[0])
                    if new_val != old_val:
                        set_add_ebudde(order_id, new_val)
                        changes += 1

                if changes:
                    st.success(f"✅ Updated {changes} booth eBudde flag(s).")
                    st.rerun()
                else:
                    st.info("No eBudde changes to save.")

# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Admin",
        initial_sidebar_state="expanded"
    )
    main()

