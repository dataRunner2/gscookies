import io
import pandas as pd
import streamlit as st

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from utils.db_utils import require_admin
from utils.app_utils import setup, apputils
from utils.order_utils import get_admin_print_orders, mark_orders_printed


STATUS_OPTIONS = ["NEW", "PRINTED", "PICKED_UP"]


# =========================
# PDF BUILDER
# =========================
def build_pdf(df_orders: pd.DataFrame, df_items: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))
    width, height = landscape(letter)

    LEFT = 0.5 * inch
    RIGHT = width - 0.5 * inch

    def header(y, scout, parent, phone):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(LEFT, y, scout)
        c.setFont("Helvetica", 12)
        c.drawString(LEFT + 3.5 * inch, y, f"parent: {parent} {phone}")
        return y - 0.35 * inch

    def table_header(y, cookie_cols):
        headers = ["Order Date", "Comments"] + cookie_cols

        date_w = 1.2 * inch
        comments_w = 4.2 * inch  # wider so comments don't crush
        available = (RIGHT - LEFT) - (date_w + comments_w)
        cookie_w = max(0.55 * inch, available / max(len(cookie_cols), 1))  # enforce a minimum width

        widths = [date_w, comments_w] + [cookie_w] * len(cookie_cols)

        c.setFont("Helvetica-Bold", 10)
        x = LEFT
        h = 0.32 * inch
        for htxt, w in zip(headers, widths):
            c.rect(x, y - h, w, h)
            c.drawString(x + 4, y - h + 0.10 * inch, str(htxt))
            x += w

        return y - h, widths


    def table_row(y, values, widths):
        c.setFont("Helvetica", 10)
        x = LEFT
        h = 0.30 * inch

        for v, w in zip(values, widths):
            c.rect(x, y - h, w, h)
            txt = "" if v is None else str(v)

            # keep comments readable but not overflowing
            if w >= 4.0 * inch:
                txt = txt[:90]
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

    # ===== One page per scout =====
    for scout, scout_orders in df_orders.groupby("scoutName"):
        y = height - 0.6 * inch

        parent = scout_orders["guardianNm"].iloc[0] or ""
        phone = scout_orders["guardianPh"].iloc[0] or ""

        y = header(y, scout, parent, phone)

        # Determine cookie columns used by this scout (across all their orders)
        order_ids = scout_orders["orderId"].tolist()
        scout_items = df_items[df_items["order_id"].isin(order_ids)]

        cookie_cols = sorted(scout_items["cookie_code"].unique())

        # ----- PARENT RECEIPT -----
        c.setFont("Helvetica-Bold", 13)
        c.drawString(LEFT, y, "Packing + Pickup (Parent Receipt)")
        y -= 0.25 * inch

        y, widths = table_header(y, cookie_cols)
        totals = (
            scout_items.groupby("cookie_code")["quantity"]
            .sum()
            .to_dict()
        )

        for _, o in scout_orders.sort_values("Date").iterrows():
            items = scout_items[scout_items["order_id"] == o["orderId"]]
            qty = items.set_index("cookie_code")["quantity"].to_dict()

            row = [
                o["Date"],
                o["comments"] or "",
            ] + [qty.get(c, "") for c in cookie_cols]

            y = table_row(y, row, widths)

        y = table_totals_row(y, cookie_cols, totals, widths)

        y -= 0.2 * inch
        y = reminder(y)

        # Divider
        c.setDash(3, 3)
        c.line(LEFT, y, RIGHT, y)
        c.setDash()
        y -= 0.3 * inch

        # ----- ADMIN RECEIPT -----
        c.setFont("Helvetica-Bold", 13)
        c.drawString(LEFT, y, "Packing + Pickup (Admin Receipt)")
        y -= 0.25 * inch

        y, widths = table_header(y, cookie_cols)

        for _, o in scout_orders.sort_values("Date").iterrows():
            items = scout_items[scout_items["order_id"] == o["orderId"]]
            qty = items.set_index("cookie_code")["quantity"].to_dict()

            row = [
                o["Date"],
                o["comments"] or "",
            ] + [qty.get(c, "") for c in cookie_cols]

            y = table_row(y, row, widths)

        y = table_totals_row(y, cookie_cols, totals, widths)

        y -= 0.2 * inch
        y = signature(y)

        c.showPage()

    c.save()
    return buf.getvalue()


# =========================
# PAGE
# =========================
def main():
    require_admin()
    setup.config_site(page_title="Print Orders", initial_sidebar_state="expanded")

    st.title("Admin Print Orders")

    statuses = st.multiselect("Statuses", STATUS_OPTIONS, default=["NEW"])

    rows = get_admin_print_orders(statuses=statuses)
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
    st.dataframe(df_view, use_container_width=True, hide_index=True)

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
            use_container_width=True,
        )

        if st.button("Mark PRINTED", type="primary"):
            mark_orders_printed(df_view["orderId"].tolist())
            st.success("Orders marked as PRINTED")
            st.rerun()


if __name__ == "__main__":
    main()
