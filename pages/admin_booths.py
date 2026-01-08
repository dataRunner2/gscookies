import streamlit as st
from decimal import Decimal, ROUND_FLOOR
from sqlalchemy import create_engine, text
from streamlit import session_state as ss
from datetime import time, datetime, timedelta
from uuid import uuid4
from utils.app_utils import setup


# --------------------------------------------------
# DB
# --------------------------------------------------
engine = create_engine(
    f"postgresql+psycopg2://cookie_admin:{st.secrets['general']['DB_PASSWORD']}@136.118.19.164:5432/cookies",
    pool_pre_ping=True,
)


# --------------------------------------------------
# Guards
# --------------------------------------------------
def require_admin():
    if not ss.get("authenticated") or not ss.get("is_admin"):
        st.error("Admin access required.")
        st.stop()


# --------------------------------------------------
# Data helpers
# --------------------------------------------------
def fetch_all(sql, params=None):
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).fetchall()


def execute(sql, params=None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})

# --------------------------------------------------
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
        WHERE o.order_type = 'BOOTH'
          AND o.verification_status = 'DRAFT'
        ORDER BY b.booth_date DESC
    """)


def get_order_items(order_id, year):
    return fetch_all("""
        SELECT
            oi.cookie_code,
            cy.display_name,
            cy.price_per_box,
            oi.quantity AS sold
        FROM cookies_app.order_items oi
        JOIN cookies_app.cookie_years cy
          ON oi.cookie_code = cy.cookie_code
         AND cy.program_year = :year
        WHERE oi.order_id = :oid
        ORDER BY cy.display_order
    """, {"oid": order_id, "year": year})


# --------------------------------------------------
# Inventory + verification
# --------------------------------------------------
def verify_booth(order_id, year, items, admin_name, notes, opc_boxes):
    with engine.begin() as conn:

        result = conn.execute(text("""
            UPDATE cookies_app.orders
            SET verification_status = 'VERIFIED',
                verified_by = :by,
                verified_at = now(),
                verification_notes = :notes,
                opc_boxes = :opc
            WHERE order_id = :oid
              AND verification_status <> 'VERIFIED'
        """), {
            "oid": order_id,
            "by": admin_name,
            "notes": notes,
            "opc": opc_boxes,
        })

        if result.rowcount == 0:
            raise ValueError("Booth already verified or not found")

        for i in items:
            if i.sold == 0:
                continue

            conn.execute(text("""
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
            """), {
                "year": year,
                "cookie": i.cookie_code,
                "qty": -i.sold,
                "oid": order_id,
            })


# --------------------------------------------------
# Page
# --------------------------------------------------
def main():
    require_admin()

    st.subheader("Booth Administration")

    tab_add, tab_print, tab_verify = st.tabs([
        "➕ Add / Manage Booths",
        "🖨️ Print Booth Sheet",
        "✅ Verify Booth"
    ])

    # ==================================================
    # TAB 1 — ADD / MANAGE BOOTHS
    # ==================================================
    

    # -------------------------------------------------------------------
    # CONSTANTS
    # -------------------------------------------------------------------

    DEFAULT_BOOTH_QTY = {
        "TM": 36,   # Thin Mints
        "SAM": 24,  # Samoas
        "TAG": 24,  # Tagalongs
        "ADV": 12,  # Adventurefuls
        "EXP": 0,   # Explorermores
        "TRE": 6,   # Trefoils
        "LEM": 6,   # Lemon-Ups
        "DOS": 8,   # Do-si-dos
        "TOF": 0,   # Toffee-Tastic
    }

    COOKIE_LAYOUT = [
        ["TM", "SAM", "TAG"],
        ["ADV", "EXP", "TRE"],
        ["LEM", "DOS", "TOF"],
    ]

    COOKIE_AVG_PCT = {
        "TM": "27%",
        "SAM": "23%",
        "TAG": "13%",
        "ADV": "7%",
        "EXP": "7%",
        "TRE": "6%",
        "LEM": "5%",
        "DOS": "5%",
        "TOF": "3%",
    }

    # -------------------------------------------------------------------
    # TAB: CREATE BOOTH
    # -------------------------------------------------------------------

    with tab_add:
        st.subheader("➕ Create Booth")

        col1, col2 = st.columns(2)
        location = col1.text_input("Location")
        booth_date = col2.date_input("Booth Date")

        col1, col2 = st.columns(2)
        start_time = col1.time_input(
            "Start Time",
            value=time(8, 0),
            step=1800,  # 30 min
        )
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=2)).time()
        col2.markdown(f"**End Time:** {end_time.strftime('%I:%M %p')}")

        col1, col2 = st.columns(2)
        weekend_number = col1.selectbox(
            "Weekend",
            options=[1, 2, 3],
            format_func=lambda x: f"Weekend {x}",
        )
        percent_override = col2.number_input(
            "or % Override",
            min_value=0.0,
            max_value=2.0,
            step=0.05,
            value=1.0,
        )

        multiplier = Decimal(
            percent_override if percent_override != 1.0 else
            {1: 1.0, 2: 0.75, 3: 0.50}[weekend_number]
        )

        st.markdown("### 🍪 Planned Cookie Inventory")

        planned = {}

        for col_codes in COOKIE_LAYOUT:
            c1, c2, c3 = st.columns(3)
            for col, code in zip([c1, c2, c3], col_codes):
                with col:
                    default = DEFAULT_BOOTH_QTY[code]
                    adjusted = int((Decimal(default) * multiplier).to_integral_value())
                    planned[code] = st.number_input(
                        f"{code} ({COOKIE_AVG_PCT[code]})",
                        min_value=0,
                        step=1,
                        value=adjusted,
                        key=f"plan_{code}",
                    )

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
        )

        if st.button("Create Booth"):
            with engine.begin() as conn:
                booth_id = conn.execute(text("SELECT gen_random_uuid()")).scalar()

                conn.execute(text("""
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
                """), {
                    "bid": booth_id,
                    "loc": location,
                    "date": booth_date,
                    "start": start_time,
                    "end": end_time,
                    "mult": multiplier,
                    "wk": weekend_number,
                })

                for code, qty in planned.items():
                    conn.execute(text("""
                        INSERT INTO cookies_app.booth_inventory_plan (
                            booth_id, program_year,
                            cookie_code, planned_quantity
                        )
                        VALUES (:bid, :year, :code, :qty)
                    """), {
                        "bid": booth_id,
                        "year": PROGRAM_YEAR,
                        "code": code,
                        "qty": qty,
                    })

                for sid in scout_ids:
                    conn.execute(text("""
                        INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
                        VALUES (:bid, :sid)
                    """), {
                        "bid": booth_id,
                        "sid": sid,
                    })

            st.success("Booth created successfully.")
            st.rerun()


            # -----------------------------
            # Create Booth
            # -----------------------------
            if st.button("Create Booth"):
                with engine.begin() as conn:
                    booth_id = conn.execute(text("""
                        INSERT INTO cookies_app.booths (
                            booth_id,
                            location,
                            booth_date,
                            start_time,
                            end_time,
                            weekend_number,
                            quantity_multiplier,
                            created_at
                        )
                        VALUES (
                            gen_random_uuid(),
                            :loc, :date, :start, :end, :weekend, :mult, now()
                        )
                        RETURNING booth_id
                    """), {
                        "loc": location,
                        "date": booth_date,
                        "start": start_time,
                        "end": end_time,
                        "weekend": weekend,
                        "mult": multiplier,
                    }).scalar()

                    # Save planned inventory
                    for code, qty in planned_quantities.items():
                        conn.execute(text("""
                            INSERT INTO cookies_app.booth_inventory_plan (
                                booth_id,
                                program_year,
                                cookie_code,
                                planned_quantity
                            )
                            VALUES (:bid, :year, :code, :qty)
                        """), {
                            "bid": booth_id,
                            "year": booth_date.year,
                            "code": code,
                            "qty": qty,
                        })

                    # Save booth scouts
                    for scout in selected_scouts:
                        conn.execute(text("""
                            INSERT INTO cookies_app.booth_scouts (booth_id, scout_id)
                            VALUES (:bid, :sid)
                        """), {
                            "bid": booth_id,
                            "sid": scout.scout_id,
                        })

                st.success("Booth created with planned inventory and scouts assigned.")
                st.rerun()

    # ==================================================
    # TAB 2 — PRINT BOOTH
    # ==================================================
    with tab_print:
        st.markdown("### Printable Booth Sheet")

        booths = get_booths()
        booth = st.selectbox(
            "Select Booth",
            booths,
            format_func=lambda b: (
                f"{b.booth_date.strftime('%b %d')} "
                f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
                f"{b.location}"
            )
        )

        cookies = fetch_all("""
            SELECT display_name, price_per_box
            FROM cookies_app.cookie_years
            WHERE program_year = :year
              AND active = true
            ORDER BY display_order
        """, {"year": booth.booth_date.year})

        st.table([
            {
                "Cookie": c.display_name,
                "Start Qty": "",
                "End Qty": "",
                "Sold": "",
                "Price": f"${c.price_per_box:.2f}",
                "Revenue": ""
            }
            for c in cookies
        ])

        st.markdown("""
        **Cash Reconciliation**
        1. Ending Money (Cash + Credit): ______  
        2. Starting Cash: ________________  
        3. Revenue (1 − 2): ______________  
        4. Expected Revenue: ____________  
        5. Over / Under: ________________  
        6. OPC Boxes: ___________________  

        **Outgoing Signature:** ______________________
        """)

        st.info("Use your browser print dialog to print this page.")

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
            WHERE o.order_type = 'BOOTH'
            AND o.verification_status = 'DRAFT'
            ORDER BY b.booth_date DESC, b.start_time
        """)

        if not booths:
            st.success("No booths awaiting verification.")
            st.stop()

        booth = st.selectbox(
            "Select Booth",
            booths,
            format_func=lambda b: (
                f"{b.booth_date.strftime('%b %d')} "
                f"{b.start_time.strftime('%I:%M %p')}–{b.end_time.strftime('%I:%M %p')} "
                f"{b.location}"
            )
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
            st.stop()

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
                st.stop()

            if not notes.strip():
                st.error("Verification notes are required.")
                st.stop()

            with engine.begin() as conn:
                # Mark order verified
                conn.execute(text("""
                    UPDATE cookies_app.orders
                    SET verification_status = 'VERIFIED',
                        verified_by = :by,
                        verified_at = now(),
                        verification_notes = :notes,
                        opc_boxes = :opc
                    WHERE order_id = :oid
                """), {
                    "oid": booth.order_id,
                    "by": admin_name,
                    "notes": notes,
                    "opc": opc_boxes,
                })

                # Apply inventory movements
                for v in verified_items:
                    if v["sold"] > 0:
                        conn.execute(text("""
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
                        """), {
                            "year": booth.program_year,
                            "cookie": v["cookie_code"],
                            "qty": -v["sold"],
                            "oid": booth.order_id,
                        })

            st.success(f"Booth verified by {admin_name}. Inventory updated.")
            st.rerun()

# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Admin",
        initial_sidebar_state="expanded"
    )
    main()

