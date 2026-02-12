import io
import pandas as pd
import streamlit as st
from streamlit import session_state as ss

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import datetime

from utils.db_utils import require_admin
from utils.app_utils import setup, apputils
from utils.order_utils import get_admin_print_orders, mark_orders_printed


STATUS_OPTIONS = ["NEW","IMPORTED", "PRINTED", "PICKED_UP"]


# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year

# =========================
# PDF BUILDER
# =========================
def build_pdf(df_orders: pd.DataFrame, df_items: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))
    width, height = landscape(letter)

    LEFT = 0.5 * inch
    RIGHT = width - 0.5 * inch
    TOP = height - 0.6 * inch
    BOTTOM = 0.8 * inch  # Minimum bottom margin

    def header(y, scout, parent, phone):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(LEFT, y, scout)
        c.setFont("Helvetica", 12)
        c.drawString(LEFT + 3.5 * inch, y, f"parent: {parent} {phone}")
        return y - 0.35 * inch

    def table_header(y, cookie_cols, widths):
        headers = ["Order Date", "Comments"] + cookie_cols

        c.setFont("Helvetica-Bold", 10)
        x = LEFT
        h = 0.32 * inch
        for htxt, w in zip(headers, widths):
            c.rect(x, y - h, w, h)
            c.drawString(x + 4, y - h + 0.10 * inch, str(htxt))
            x += w

        return y - h


    def table_row(y, values, widths):
        c.setFont("Helvetica", 10)
        x = LEFT
        h = 0.30 * inch

        for v, w in zip(values, widths):
            c.rect(x, y - h, w, h)
            txt = "" if v is None else str(v)

            # keep comments readable but not overflowing
            if w >= 2.0 * inch:  # comments column (reduced from 4.0)
                txt = txt[:60]  # reduced from 90 to match smaller width
            else:
                txt = txt[:12]

            c.drawString(x + 4, y - h + 0.10 * inch, txt)
            x += w

        return y - h


    def table_totals_row(y, cookie_cols, totals, widths):
        c.setFont("Helvetica-Bold", 10)
        x = LEFT
        h = 0.30 * inch

        # TOTAL label in Order Date cell
        c.rect(x, y - h, widths[0], h)
        c.drawString(x + 4, y - h + 0.10 * inch, "TOTAL")
        x += widths[0]

        # blank comments cell
        c.rect(x, y - h, widths[1], h)
        x += widths[1]

        # cookie totals
        for code, w in zip(cookie_cols, widths[2:]):
            val = int(totals.get(code, 0) or 0)
            c.rect(x, y - h, w, h)
            c.drawString(x + 4, y - h + 0.10 * inch, str(val) if val else "")
            x += w

        return y - (h + 0.10 * inch)

    def reminder(y):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(LEFT, y, "Reminder — All initial order funds due back to us by 3/9 at Noon")
        y -= 0.22 * inch
        return y - 0.35 * inch
    
    def signature(y):
        c.setFont("Helvetica", 11)
        c.drawString(LEFT, y, "Signature: _______________________________   Date: _______________")
        return y - 0.35 * inch

    def render_receipt(y, scout, parent, phone, title, scout_orders, scout_items, cookie_cols, totals, widths, include_reminder=False, include_signature=False, force_render=False):
        """Render one receipt (parent or admin). Returns final y position or None if needs new page."""
        # Handle None input
        if y is None:
            return None
        
        # Calculate space needed
        header_space = 0.35 * inch
        title_space = 0.25 * inch
        table_header_space = 0.32 * inch
        row_height = 0.30 * inch
        show_totals = bool(totals)  # Only show totals if dict is not empty
        totals_space = 0.40 * inch if show_totals else 0
        reminder_space = 0.57 * inch if include_reminder else 0
        signature_space = 0.35 * inch if include_signature else 0
        divider_space = 0.30 * inch if not include_signature else 0
        
        num_rows = len(scout_orders)
        total_needed = (header_space + title_space + table_header_space + 
                       (num_rows * row_height) + totals_space + 
                       reminder_space + signature_space + divider_space + 0.2 * inch)
        
        # Check if we have enough space (unless forced to render)
        if not force_render and y - total_needed < BOTTOM:
            return None  # Signal that we need a new page
        
        # We have enough space, render the receipt
        y = header(y, scout, parent, phone)
        
        c.setFont("Helvetica-Bold", 13)
        c.drawString(LEFT, y, title)
        y -= title_space

        y = table_header(y, cookie_cols, widths)

        for _, o in scout_orders.sort_values("Date").iterrows():
            items = scout_items[scout_items["order_id"] == o["orderId"]]
            qty = items.set_index("cookie_code")["quantity"].to_dict()

            row = [
                o["Date"],
                o["comments"] or "",
            ] + [qty.get(c, "") for c in cookie_cols]

            y = table_row(y, row, widths)

        # Only show totals row if we have totals to display
        if totals:
            y = table_totals_row(y, cookie_cols, totals, widths)

        if include_reminder:
            y -= 0.2 * inch
            y = reminder(y)

        if include_signature:
            y -= 0.2 * inch
            y = signature(y)

        if not include_signature:
            # Divider after parent receipt
            c.setDash(3, 3)
            c.line(LEFT, y, RIGHT, y)
            c.setDash()
            y -= 0.3 * inch

        return y

    # ===== One page per scout (or more if needed) =====
    for scout, scout_orders in df_orders.groupby("scoutName"):
        y = TOP

        parent = scout_orders["guardianNm"].iloc[0] or ""
        phone = scout_orders["guardianPh"].iloc[0] or ""

        # Determine cookie columns used by this scout (across all their orders)
        order_ids = scout_orders["orderId"].tolist()
        scout_items = df_items[df_items["order_id"].isin(order_ids)]

        cookie_cols = sorted(scout_items["cookie_code"].unique())
        
        # Calculate widths once
        date_w = 1.2 * inch
        comments_w = 2.8 * inch
        available = (RIGHT - LEFT) - (date_w + comments_w)
        cookie_w = available / max(len(cookie_cols), 1)  # distribute evenly, no minimum
        widths = [date_w, comments_w] + [cookie_w] * len(cookie_cols)

        totals = (
            scout_items.groupby("cookie_code")["quantity"]
            .sum()
            .to_dict()
        )

        # Split orders into chunks of maximum 20 orders per receipt
        MAX_ORDERS_PER_PAGE = 20
        num_orders = len(scout_orders)
        num_chunks = (num_orders + MAX_ORDERS_PER_PAGE - 1) // MAX_ORDERS_PER_PAGE  # ceiling division
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * MAX_ORDERS_PER_PAGE
            end_idx = min(start_idx + MAX_ORDERS_PER_PAGE, num_orders)
            chunk_orders = scout_orders.iloc[start_idx:end_idx]
            
            # Determine if this is the last chunk (for totals display)
            is_last_chunk = (chunk_idx == num_chunks - 1)
            
            # Title suffix for multi-page receipts
            page_suffix = f" (page {chunk_idx + 1} of {num_chunks})" if num_chunks > 1 else ""
            
            # Track the starting y position to detect blank pages
            start_y = y
            
            # ----- PARENT RECEIPT -----
            y = render_receipt(
                y, scout, parent, phone, 
                f"Packing + Pickup (Parent Receipt){page_suffix}",
                chunk_orders, scout_items, cookie_cols, totals if is_last_chunk else {}, widths,
                include_reminder=is_last_chunk, include_signature=False
            )
            
            if y is None:
                # Need new page for parent receipt
                # Only call showPage if we've rendered something (y position changed from start)
                if start_y < TOP:
                    c.showPage()
                y = TOP
                # Force render on new page
                y = render_receipt(
                    y, scout, parent, phone, 
                    f"Packing + Pickup (Parent Receipt){page_suffix}",
                    chunk_orders, scout_items, cookie_cols, totals if is_last_chunk else {}, widths,
                    include_reminder=is_last_chunk, include_signature=False,
                    force_render=True
                )

            # ----- ADMIN RECEIPT -----
            admin_y = render_receipt(
                y, scout, parent, phone, 
                f"Packing + Pickup (Cookie Crew Receipt){page_suffix}",
                chunk_orders, scout_items, cookie_cols, totals if is_last_chunk else {}, widths,
                include_reminder=False, include_signature=is_last_chunk
            )
            
            if admin_y is None:
                # Need new page for admin receipt
                c.showPage()
                y = TOP
                # Force render on new page
                render_receipt(
                    y, scout, parent, phone, 
                    f"Packing + Pickup (Cookie Crew Receipt){page_suffix}",
                    chunk_orders, scout_items, cookie_cols, totals if is_last_chunk else {}, widths,
                    include_reminder=False, include_signature=is_last_chunk,
                    force_render=True
                )

            c.showPage()
            y = TOP  # Reset for next chunk

    c.save()
    return buf.getvalue()


# =========================
# PAGE
# =========================
def main():
    require_admin()
    setup.config_site(page_title="Print Orders", initial_sidebar_state="expanded")

    st.title("Admin Print Orders")

    statuses = st.multiselect("Statuses", STATUS_OPTIONS, default=["NEW", "IMPORTED"])
    initial_only = False
    initial_only = st.checkbox("Initial Orders Only", value=False)


    rows = get_admin_print_orders(statuses=statuses, initial_only=initial_only)
    if not rows:
        st.success("No orders found.")
        return

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["submit_date"]).dt.date

    df_orders = (
        df[[
            "order_id", "scout_name", "guardian_name", "guardian_phone",
            "order_qty_boxes", "comments", "Date"
        ]]
        .drop_duplicates("order_id")
        .rename(columns={
            "order_id": "orderId",
            "scout_name": "scoutName",
            "guardian_name": "guardianNm",
            "guardian_phone": "guardianPh",
            "order_qty_boxes": "orderQtyBoxes",
        })
    )

    df_items = df[["order_id", "cookie_code", "quantity"]].dropna()

    scouts = sorted(df_orders["scoutName"].unique())
    selected = st.multiselect("Scouts", scouts, default=scouts)

    df_orders = df_orders[df_orders["scoutName"].isin(selected)]

    st.subheader("Orders")
    df_view = apputils.filter_dataframe(df_orders)
    st.dataframe(df_view, width='stretch', hide_index=True)

    st.divider()

    if not df_view.empty:
        pdf = build_pdf(
            df_view,
            df_items[df_items["order_id"].isin(df_view["orderId"])]
        )

        st.download_button(
            "Download Packing + Pickup PDF",
            pdf,
            "packing_pickup_sheets.pdf",
            "application/pdf",
            width='stretch',
        )

        if st.button("Mark PRINTED", type="primary"):
            mark_orders_printed(df_view["orderId"].tolist())
            st.success("Orders marked as PRINTED")
            st.rerun()


if __name__ == "__main__":
    main()
