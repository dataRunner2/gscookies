from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit import session_state as ss
import datetime

from utils.db_utils import require_admin, to_pacific
from utils.app_utils import setup, apputils
from utils.order_utils import (
    get_all_orders_wide,
    admin_update_orders_bulk,
    get_cookie_codes_for_year,
    get_all_scouts,
)

# -----------------------------
# Configuration
# -----------------------------
STATUS_OPTIONS = ["NEW", "PRINTED", "PICKED_UP", "CANCELLED"]

DEFAULT_COLUMNS = [
    "orderId",
    "scoutName",
    "orderType",
    "orderStatus",
    "paymentStatus",          # computed / read-only
    "addEbudde",
    "initialOrder",
]

# MUST match admin_update_orders_bulk()
EDITABLE_COLUMNS = {
    "orderStatus",
    "comments",
    "addEbudde",
    "initialOrder",
    "verifiedDigitalCookie",
    "orderType",
}

# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if "current_year" not in ss:
        ss.current_year = datetime.datetime.now().year


# -----------------------------
# Helpers
# -----------------------------
def _norm(v):
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def diff_updates(original: pd.DataFrame, edited: pd.DataFrame):
    updates: list[dict] = []
    diffs: list[dict] = []

    orig = original.set_index("orderId")
    edit = edited.set_index("orderId")

    for oid in orig.index:
        if oid not in edit.index:
            continue

        delta = {"orderId": oid}

        for col in EDITABLE_COLUMNS:
            if col not in orig.columns or col not in edit.columns:
                continue

            old = _norm(orig.at[oid, col])
            new = _norm(edit.at[oid, col])

            if old == new:
                continue

            delta[col] = new
            diffs.append({
                "orderId": oid,
                "column": col,
                "old": old,
                "new": new,
            })

        if len(delta) > 1:
            updates.append(delta)

    return updates, pd.DataFrame(diffs)

# -----------------------------
# Page
# -----------------------------
def main():
    require_admin()
    init_ss()
    
    # Show last digital import date
    apputils.get_last_digital_import()
   
    df_all = get_all_orders_wide(program_year=int(ss.current_year))
    if df_all.empty:
        st.info("No orders found.")
        return

    # Clean up blank orderType values (fill with empty string so selectbox works)
    if "orderType" in df_all.columns:
        df_all["orderType"] = df_all["orderType"].fillna("")

    # ---------------- Filters ----------------
    st.subheader("Filters")

    c1, c2, c3 = st.columns(3)

    with c1:
        status_vals = sorted(df_all["orderStatus"].dropna().unique())  if "orderStatus" in df_all.columns else []
        status_filter = st.multiselect(
            "Status",
            options=status_vals,
            default=["NEW"] if "NEW" in status_vals else status_vals,
        )

    with c2:
        scout_filter = st.multiselect(
            "Scout",
            options=sorted(df_all["scoutName"].dropna().unique()),
        )

    with c3:
        initial_only = st.checkbox("Initial Orders Only")

    df = df_all.copy()

    if status_filter:
        df = df[df["orderStatus"].isin(status_filter)]

    if scout_filter:
        # Make sure filter values are also cleaned for comparison
        df = df[df["scoutName"].str.strip().isin(scout_filter)]

    if initial_only and "initialOrder" in df.columns:
        df = df[df["initialOrder"] == True]

    # Get all cookie columns BEFORE filtering (to include DON and other codes)
    meta_cols = {'orderId', 'program_year', 'scoutName', 'orderType', 'orderStatus', 'paymentStatus', 
                 'addEbudde', 'initialOrder', 'comments', 'orderAmount', 'orderQtyBoxes',
                 'submit_dt', 'boothId', 'verifiedDigitalCookie','DON'}
    actual_cookie_cols = [c for c in df.columns if c not in meta_cols]
    cookie_codes = get_cookie_codes_for_year(int(ss.current_year)) or []
    # Include configured cookies (even if not in current data) + actual data columns
    cookie_cols = list(dict.fromkeys(cookie_codes + actual_cookie_cols))
    
    # Build default columns - include all configured cookies in the order they're configured
    default_cols = [c for c in DEFAULT_COLUMNS if c in df.columns] + cookie_codes

    df = apputils.filter_dataframe(df)

    column_choices = st.multiselect(
        "Columns",
        options=list(df.columns),
        default=[c for c in default_cols if c in df.columns],
    )

    if "orderId" not in column_choices:
        column_choices.insert(0, "orderId")

    df_view = df[column_choices].copy()

    # ---------------- Editor ----------------
    st.subheader("Orders")

    disabled_cols = [c for c in df_view.columns if c not in EDITABLE_COLUMNS]

    edited = st.data_editor(
        df_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=disabled_cols,
        column_config={
            "orderStatus": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_OPTIONS,
            ),
            "paymentStatus": st.column_config.TextColumn(
                "Payment",
                disabled=True,
            ),
            "verifiedDigitalCookie": st.column_config.CheckboxColumn("Verified DC"),
            "addEbudde": st.column_config.CheckboxColumn("eBudde"),
            "initialOrder": st.column_config.CheckboxColumn("Initial Order"),
            "comments": st.column_config.TextColumn("Comments"),
            "orderType": st.column_config.SelectboxColumn(
                "Order Type",
                options=["", "Paper", "Digital", "Booth"],
            ),
        },
    )

    # ---------------- Save ----------------
    st.divider()

    if st.button("Save Changes", type="primary"):
        updates, diffs = diff_updates(df_view, edited)

        if updates:
            try:
                admin_update_orders_bulk(updates)
            except Exception as e:
                st.error(f"Update failed: {e}")

            st.subheader("Changes Applied")
            st.dataframe(diffs.reset_index(drop=True), width='stretch', hide_index=True)

            st.success(f"Updated {len(updates)} order(s)")
            st.rerun()
        else:
            st.info("No changes detected.")

# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="Admin Order Management",
        initial_sidebar_state="expanded",
    )
    main()
