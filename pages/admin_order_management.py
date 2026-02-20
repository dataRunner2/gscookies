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
STATUS_OPTIONS = ["NEW", "PRINTED", "IMPORTED","PICKED_UP", "CANCELLED"]

DEFAULT_COLUMNS = [
    "orderId",
    "submitDate",
    "scoutName",
    "orderType",
    "orderStatus",
    "paymentStatus",          # computed / read-only
    "addEbudde",
    "initialOrder",
    "orderPickedup",
]

# MUST match admin_update_orders_bulk()
EDITABLE_COLUMNS = {
    "orderStatus",
    "comments",
    "addEbudde",
    "initialOrder",
    "verifiedDigitalCookie",
    "orderType",
    "orderPickedup",
}

BOOLEAN_COLUMNS = {
    "addEbudde",
    "initialOrder",
    "verifiedDigitalCookie",
    "orderPickedup",
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
    """Normalize values for comparison, handling pandas/numpy types"""
    # Handle NaN/None first
    if v is None:
        return None
    if pd.isna(v):
        return None
    
    # Handle numpy types by calling .item() if available
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:
            pass
    
    # Convert numpy bool to Python bool (check type string to catch numpy.bool_)
    type_str = str(type(v))
    if isinstance(v, bool) or "numpy.bool" in type_str:
        return bool(v)
    
    # Convert to int if it's a whole number
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return int(v)
        return float(v)
    
    # Return string types as-is
    if isinstance(v, str):
        return v
    
    return v


def _to_bool(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(v)


def diff_updates(original: pd.DataFrame, edited: pd.DataFrame, cookie_cols: list[str]):
    """
    Compare original and edited dataframes to find changes.
    Returns list of updates and a dataframe of diffs.
    """
    updates: list[dict] = []
    diffs: list[dict] = []

    # Reset index to ensure we're comparing the same rows
    orig = original.reset_index(drop=True).copy()
    edit = edited.reset_index(drop=True).copy()

    orig["orderId"] = orig["orderId"].astype(str)
    edit["orderId"] = edit["orderId"].astype(str)

    orig = orig.set_index("orderId")
    edit = edit.set_index("orderId")
    
    # Include both regular editable columns and cookie columns
    all_editable = EDITABLE_COLUMNS | set(cookie_cols)

    for oid in orig.index:
        if oid not in edit.index:
            continue

        delta = {"orderId": oid}

        for col in all_editable:
            # Skip if column doesn't exist in both dataframes
            if col not in orig.columns or col not in edit.columns:
                continue

            # Get and normalize values
            old_raw = orig.at[oid, col]
            new_raw = edit.at[oid, col]
            
            old = _norm(old_raw)
            new = _norm(new_raw)
            
            # Compare based on column type
            if col in cookie_cols:
                # For cookie columns, compare as integers (treat None as 0)
                old_val = int(old) if old is not None else 0
                new_val = int(new) if new is not None else 0
                
                if old_val != new_val:
                    delta[col] = new_val
                    diffs.append({
                        "orderId": oid,
                        "column": col,
                        "old": old_val,
                        "new": new_val,
                    })
            else:
                # For non-cookie columns (status, comments, booleans, etc.)
                # Treat None and False as equivalent for boolean fields only
                if col in BOOLEAN_COLUMNS:
                    old_bool = _to_bool(old)
                    new_bool = _to_bool(new)
                    if old_bool != new_bool:
                        delta[col] = new_bool
                        diffs.append({
                            "orderId": oid,
                            "column": col,
                            "old": old_bool,
                            "new": new_bool,
                        })
                else:
                    # For strings and other types, direct comparison
                    if old != new:
                        delta[col] = new
                        diffs.append({
                            "orderId": oid,
                            "column": col,
                            "old": old,
                            "new": new,
                        })

        # Only add to updates if there are actual changes (more than just orderId)
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
    
    # Add formatted date column
    if "submit_dt" in df_all.columns:
        df_all["submitDate"] = pd.to_datetime(df_all["submit_dt"]).dt.date
    
    # Filter out booth orders (orderType == 'Booth' or scout_id == booth scout)
    BOOTH_SCOUT_ID = '7bcf1980-ccb7-4d0c-b0a0-521b542356fa'
    df_all = df_all[
        (df_all["orderType"] != "Booth") & 
        (df_all.get("scoutId", "") != BOOTH_SCOUT_ID)
    ]
    
    if df_all.empty:
        st.info("No non-booth orders found.")
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
            default=["NEW","IMPORTED","PRINTED"] if "NEW" in status_vals else status_vals,
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
                 'submit_dt', 'submitDate', 'boothId', 'verifiedDigitalCookie', 'orderPickedup', 'scoutId', 'totalQty'}
    actual_cookie_cols = [c for c in df.columns if c not in meta_cols]
    cookie_codes = get_cookie_codes_for_year(int(ss.current_year)) or []
    # Include configured cookies (even if not in current data) + actual data columns
    cookie_cols = list(dict.fromkeys(cookie_codes + actual_cookie_cols))

    # Ensure all configured cookie columns exist in the dataframe (fill missing with 0)
    for code in cookie_codes:
        if code not in df.columns:
            df[code] = 0
    
    # Calculate total quantity across all cookie columns
    df['totalQty'] = df[cookie_cols].fillna(0).sum(axis=1).astype(int)
    
    # Build default columns - include totalQty before cookies, then all configured cookies in the order they're configured
    default_cols = [c for c in DEFAULT_COLUMNS if c in df.columns] + ['totalQty'] + cookie_codes

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

    # Cookie columns are also editable
    editable_cols = EDITABLE_COLUMNS | set(cookie_cols)
    disabled_cols = [c for c in df_view.columns if c not in editable_cols]

    edited = st.data_editor(
        df_view,
        width='stretch',
        hide_index=True,
        num_rows="fixed",
        disabled=disabled_cols,
        column_config={
            "orderId": st.column_config.TextColumn(
                "Order ID",
                width="small",
            ),
            "orderStatus": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_OPTIONS,
                width="small",
            ),
            "paymentStatus": st.column_config.TextColumn(
                "Payment",
                disabled=True,
            ),
            "totalQty": st.column_config.NumberColumn(
                "Total",
                disabled=True,
                width="small",
            ),
            "verifiedDigitalCookie": st.column_config.CheckboxColumn(
                "Verified DC",
                 width="small",
                 ),
            "initialOrder": st.column_config.CheckboxColumn(
                "Initial Order",
                width="small",
                ),
            "addEbudde": st.column_config.CheckboxColumn(
                "eBudde",
                width="small",
                ),
            
            "orderPickedup": st.column_config.CheckboxColumn(
                "Picked Up",
                width="small",
                ),
            "comments": st.column_config.TextColumn("Comments"),
            "orderType": st.column_config.SelectboxColumn(
                "Order Type",
                options=["", "Paper", "Digital", "Booth"],
                width="small",
            ),
        },
    )

    # ---------------- Save ----------------
    st.divider()
    # st.write(edited)

    if st.button("Save Changes", type="primary"):
        updates, diffs = diff_updates(df_view, edited, cookie_cols)
        st.write(diffs)
        if updates:
            try:
                admin_update_orders_bulk(updates, cookie_cols)
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
