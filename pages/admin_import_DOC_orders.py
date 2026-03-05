import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import uuid
from datetime import datetime, date

from utils.app_utils import setup
from utils.db_utils import require_admin
from utils.order_utils import (
    fetch_existing_external_orders,
    bulk_insert_order_headers, bulk_insert_order_items,
    bulk_insert_planned_inventory, bulk_insert_money_ledger,
    build_cookie_rename_map,
    get_all_scouts,
    update_scout_gsusa_id
)

DOC_IMPORT_TYPES = ["In-Person Delivery", "In-Person Delivery with Donation"]

# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year

# ======================================================
# Helpers (page-level only)
# ======================================================

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(
        columns={
            "Order Number": "external_order_id",
            "Order Date": "submit_dt",

            "Girl First Name": "scout_first_name",
            "Girl Last Name": "scout_last_name",
            "Girl GSUSAID": "scout_gsusa_id",

            "Order Type": "order_type",
            "Order Status": "order_status",
            "Customer Name": "customer_name",
            "Customer Email": "customer_email",
            "Customer First Name": "customer_first_name",
            "Customer Last Name": "customer_last_name",
            "Order Total": "order_total",
            "Quantity": "order_qty_boxes",
            "Total": "order_amount",
            "Original Cookie Subtotal": "order_amount",
            "Total Packages (Excluding Donation)": "order_qty_boxes",
        }
    )

def build_gsusa_mapping(
    scouts: dict,
    orders_df: pd.DataFrame
    ) -> dict[tuple[str, str], str]:

    gsusa_map: dict[tuple[str, str], str] = {}

    # 1️⃣ DB values win first
    # scouts looks like: "{'scout_id': UUID('131....6dade'), 'first_name': 'Grace', 'last_name': 'Alexander', 'gsusa_id': None}"
    for scout in scouts:
        if scout['gsusa_id']:
            key = (scout["first_name"], scout["last_name"])
            gsusa_map[key] = scout["gsusa_id"]

    # 2️⃣ Fill gaps from orders DF
    for _, row in orders_df.iterrows():
        key = (row["scout_first_name"], row["scout_last_name"])
        if key not in gsusa_map and pd.notna(row["scout_gsusa_id"]):
            gsusa_map[key] = row["scout_gsusa_id"]

    return gsusa_map

def build_scout_updates(
    scouts: list[dict],
    gsusa_by_name: dict
    ) -> list[tuple]:

    updates = []

    for scout in scouts:
        if scout["gsusa_id"] is not None:
            continue

        key = (scout["first_name"], scout["last_name"])
        gsu_id = gsusa_by_name.get(key)

        if gsu_id:
            updates.append(
                (str(scout["scout_id"]), gsu_id)
            )

    return updates


def attach_scout_id(orders_df: pd.DataFrame):
    df = orders_df.copy()

    def _scout_lookup(row):
        return ss.scout_name_lookup.get(
                (row["scout_first_name"], row["scout_last_name"])
            )
    def _parent_lookup(row):
        return ss.parent_id_lookup.get(row['scout_id'])
    
    df["scout_id"] = df.apply(_scout_lookup, axis=1)

    df["parent_id"] = df.apply(_parent_lookup, axis=1)

    return df

def rename_cookie_columns(order_df: pd.DataFrame, program_year: int) -> pd.DataFrame:
    rename_map = build_cookie_rename_map(program_year)

    # Only rename columns that exist in the DF
    valid_map = {
        col: rename_map[col]
        for col in order_df.columns
        if col in rename_map
    }

    # Fallback: map any donation-ish columns to DON
    for col in order_df.columns:
        col_l = col.lower()
        if "donation" in col_l or "donate" in col_l or col_l == "don" or col_l == "donations":
            valid_map[col] = "DON"

    return order_df.rename(columns=valid_map), rename_map


def build_filter_exclusion_reason(row: pd.Series) -> str:
    reasons = []
    allowed_types = set(DOC_IMPORT_TYPES)

    if row.get("order_type") not in allowed_types:
        reasons.append("Order type not eligible")
    if row.get("order_status") != "PROCESSING":
        reasons.append("Order status not PROCESSING")

    return "; ".join(reasons) if reasons else "Filtered out"

    


# ======================================================
# Main
# ======================================================

def main():
    require_admin()
    
    uploaded_file = st.file_uploader(
        "Upload Digital Cookie Excel Export",
        type=["xlsx"],
    )

    if not uploaded_file:
        st.info("Upload the daily Digital Cookie export to begin.")
        return

    # ----------------------------------
    # Load + Filter
    # ----------------------------------
    # st.write('Raw data')
    
    raw_dat  = (pd.read_excel(uploaded_file).head())
    # st.write(raw_dat.columns.tolist())
    st.dataframe(raw_dat.head())
    uploaded_df = normalize_columns(pd.read_excel(uploaded_file))
    uploaded_df["external_order_id"] = uploaded_df["external_order_id"].astype(str)

    existing_ids = fetch_existing_external_orders(
        order_source="Digital Cookie Import",
    )

    completed_candidates = uploaded_df[
        uploaded_df["order_type"].isin(DOC_IMPORT_TYPES)
        & (uploaded_df["order_status"] == "COMPLETED")
    ].copy()
    completed_missing_in_db = completed_candidates[
        ~completed_candidates["external_order_id"].isin(existing_ids)
    ].copy()
    
    eligible_mask = (
        uploaded_df["order_type"].isin(DOC_IMPORT_TYPES)
        & (uploaded_df["order_status"] == "PROCESSING")
    )
    processing_df = uploaded_df[eligible_mask].copy()
    excluded_by_filter = uploaded_df[~eligible_mask].copy()

    if not excluded_by_filter.empty:
        excluded_by_filter["exclusion_reason"] = excluded_by_filter.apply(
            build_filter_exclusion_reason,
            axis=1,
        )

    st.markdown("### Audit: Completed Digital Orders Missing in DB")
    st.metric("Completed Missing", len(completed_missing_in_db))

    force_include_ids = []
    force_include_df = pd.DataFrame(columns=uploaded_df.columns)

    if not completed_missing_in_db.empty:
        audit_cols = [
            "external_order_id",
            "submit_dt",
            "scout_first_name",
            "scout_last_name",
            "order_type",
            "order_status",
            "order_total",
            "customer_first_name",
            "customer_last_name",
        ]
        display_audit_cols = [c for c in audit_cols if c in completed_missing_in_db.columns]
        st.dataframe(
            completed_missing_in_db[display_audit_cols],
            width='stretch',
            hide_index=True,
        )

        select_all_completed = st.checkbox(
            "Select all completed-missing orders for force import",
            key="doc_force_import_all_completed",
        )

        completed_options = completed_missing_in_db["external_order_id"].dropna().astype(str).tolist()

        existing_selected = ss.get("doc_force_import_ids", [])
        if not isinstance(existing_selected, list):
            existing_selected = []

        # Keep only IDs that still exist in this uploaded file's completed set
        sanitized_selected = [oid for oid in existing_selected if oid in completed_options]
        ss["doc_force_import_ids"] = sanitized_selected

        # Critical: checkbox should truly select all for import even after reruns
        if select_all_completed:
            ss["doc_force_import_ids"] = completed_options

        force_include_ids = st.multiselect(
            "Force import these completed orders",
            options=completed_options,
            key="doc_force_import_ids",
            help="Selected COMPLETED orders will be included in this import run.",
        )

        # Ensure checkbox alone always includes all, even if widget state was stale
        if select_all_completed:
            force_include_ids = completed_options

        if force_include_ids:
            force_include_df = completed_missing_in_db[
                completed_missing_in_db["external_order_id"].isin(force_include_ids)
            ].copy()
            st.info(f"Force-selected completed orders: {len(force_include_df)}")
    else:
        st.success("No completed in-person digital orders are missing from the database.")

    filtered_df = processing_df.copy()
    if not force_include_df.empty:
        filtered_df = pd.concat([filtered_df, force_include_df], ignore_index=True)
        filtered_df = filtered_df.drop_duplicates(subset=["external_order_id"], keep="first")

    if force_include_ids and not excluded_by_filter.empty:
        excluded_by_filter = excluded_by_filter[
            ~excluded_by_filter["external_order_id"].isin(force_include_ids)
        ].copy()

    m1, m2, m3 = st.columns(3)
    m1.metric("Eligible PROCESSING", len(processing_df))
    m2.metric("Force-Selected COMPLETED", len(force_include_df))
    m3.metric("Total Orders to Process", len(filtered_df))

    if filtered_df.empty:
        if not excluded_by_filter.empty:
            st.markdown("### Orders Excluded from Import")
            st.dataframe(
                excluded_by_filter[
                    [
                        "external_order_id",
                        "scout_first_name",
                        "scout_last_name",
                        "order_type",
                        "order_status",
                        "exclusion_reason",
                    ]
                ],
                width='stretch',
                hide_index=True,
            )
        st.success("No eligible orders found.")
        return

    # ----------------------------------
    # Scout Matching
    # ----------------------------------

    scouts = get_all_scouts()
    # st.write(scouts[:2])
    # aliases = fetch_scout_aliases()

    ss.scout_name_lookup = {
        (s["first_name"], s["last_name"]): s["scout_id"]
        for s in scouts
        }
    ss.parent_id_lookup = {
        s["scout_id"]: s["parent_id"]
        for s in scouts
        }
    
    ss.gsuid_map = build_gsusa_mapping(scouts, filtered_df)

    # Update Scouts Table with GSU_ID
    scout_updates = build_scout_updates(scouts, ss.gsuid_map)
    # st.write(f'Scouts table Updates: \n\n{scout_updates[:2]}')
    
    # Apply GSUSA ID updates to scouts table
    if scout_updates:
        for scout_id, gsusa_id in scout_updates:
            update_scout_gsusa_id(scout_id, gsusa_id)
        st.info(f"✓ Updated {len(scout_updates)} scout(s) with GSUSA IDs")

    #### 
    updated_df = attach_scout_id(filtered_df)
    # st.dataframe(updated_df) #[['scout_id','external_order_id','scout_gsusa_id','scout_first_name']])
    

    unmatched = updated_df[updated_df["scout_id"].isna()].copy()
    matched = updated_df[updated_df["scout_id"].notna()].copy()
    still_unmatched = pd.DataFrame(columns=updated_df.columns)
    # st.write('matched:\n')
    # st.dataframe(matched)
    # ----------------------------------
    # Alias Resolution UI
    # ----------------------------------
    if not unmatched.empty:
        st.warning("Some scout names need to be matched")

        scout_options = {
            f"{s['first_name']} {s['last_name']}": s["scout_id"] for s in scouts
        }

        # Create unique scout mapping with order count
        unmatched['scout_name'] = unmatched['scout_first_name'] + ' ' + unmatched['scout_last_name']
        scout_order_counts = unmatched.groupby('scout_name').size()
        
        # Get unique scouts (no duplicates)
        unique_scouts = sorted(scout_order_counts.index.tolist())

        scout_matches = {}
        for scout_name in unique_scouts:
            order_count = scout_order_counts[scout_name]
            st.markdown(f"**Digital Cookie Scout:** `{scout_name}` ({order_count} orders)")

            choice = st.selectbox(
                "Match to Scout",
                [""] + sorted(scout_options.keys()),
                key=f"scout_match_{scout_name.replace(' ', '_')}",
            )

            if choice:
                scout_matches[scout_name] = scout_options[choice]
                st.success(f"✓ Selected: {choice}")
            else:
                st.warning(f"⚠️ No match selected - orders will be skipped")

        # Separate newly matched from still unmatched
        newly_matched_list = []
        still_unmatched = unmatched.copy()

        for digital_scout_name, system_scout_id in scout_matches.items():
            mask = still_unmatched['scout_name'] == digital_scout_name
            newly_matched_subset = still_unmatched[mask].copy()
            newly_matched_subset['scout_id'] = system_scout_id
            newly_matched_subset['parent_id'] = ss.parent_id_lookup.get(system_scout_id)
            newly_matched_list.append(newly_matched_subset)
            
            # Remove from still_unmatched
            still_unmatched = still_unmatched[~mask].copy()
            
            # Store alias for future imports
            system_scout_name = scout_options[
                [k for k, v in scout_options.items() if v == system_scout_id][0]
            ]
            st.success(f"✓ Matched: {digital_scout_name} → {system_scout_name}")

        # Add newly matched orders to matched dataframe
        if newly_matched_list:
            matched = pd.concat([matched] + newly_matched_list, ignore_index=True)

        # Display and handle remaining unmatched scouts
        if not still_unmatched.empty:
            st.warning(f"⏳ {len(still_unmatched)} orders remain unmatched - these will be skipped")
            st.info("**Action needed:** Parents must create accounts and add scouts to the system before these orders can be imported.")
            unmatched_scouts = still_unmatched['scout_name'].unique()
            for scout in unmatched_scouts:
                count = len(still_unmatched[still_unmatched['scout_name'] == scout])
                st.info(f"  • {scout}: {count} orders (skipped)")

    # ----------------------------------
    # Final Prep + Deduplication
    # ----------------------------------
    # Ensure year exists (cookie season is program year)
    matched["program_year"] = int(ss.current_year)

    matched["order_source"] = "Digital Cookie Import"
    matched["submit_dt"] = pd.to_datetime(matched["submit_dt"])
    matched["created_at"] = datetime.utcnow()
    matched['order_type'] = matched['order_type'].replace({'In-Person Delivery': 'Digital', 'In-Person Delivery with Donation': 'Digital'})
    matched['comments'] = [f"Customer Info: {cust_first} {cust_last} ${total}" for cust_first,cust_last,total in zip(matched['customer_first_name'],matched['customer_last_name'],matched['order_total'])]
    matched["status"] = "IMPORTED"
    matched["order_ref"] = matched["external_order_id"].astype(str)

    # Mark initial orders: submitted before Feb 1 of program year
    matched["initial_order"] = matched.apply(
        lambda r: bool(r["submit_dt"].date() < date(int(r["program_year"]), 2, 1)),
        axis=1,
    )

    # Rename cookie display names -> cookie codes (must ASSIGN result)
    matched, cookie_nm_map = rename_cookie_columns(matched, int(ss.current_year))
    # st.write(cookie_nm_map)
    # st.write(matched.columns.tolist())

    if len(existing_ids) == 0:
        st.write('There are no existing DOC orders, importing all of them.')

    matched["external_order_id"] = matched["external_order_id"].astype(str)

    duplicate_orders = matched[
        matched["external_order_id"].isin(existing_ids)
    ].copy()

    new_orders = matched[
        ~matched["external_order_id"].isin(existing_ids)
    ].copy()
    # new_orders["order_id"] = [uuid.uuid4() for _ in range(len(new_orders))]
    # st.write(f'New Orders to be added {len(new_orders)}')
    
    # ----------------------------------
    # Review + Import
    # ----------------------------------

    st.metric("New Orders to Import", len(new_orders))

    excluded_frames = []
    if not excluded_by_filter.empty:
        excluded_frames.append(excluded_by_filter.copy())
    if not still_unmatched.empty:
        tmp_unmatched = still_unmatched.copy()
        tmp_unmatched["exclusion_reason"] = "Unmatched scout"
        excluded_frames.append(tmp_unmatched)
    if not duplicate_orders.empty:
        tmp_duplicate = duplicate_orders.copy()
        tmp_duplicate["exclusion_reason"] = "Already imported (duplicate external order id)"
        excluded_frames.append(tmp_duplicate)

    if excluded_frames:
        excluded_report = pd.concat(excluded_frames, ignore_index=True, sort=False)
        st.markdown("### Orders Excluded from Import")
        st.metric("Excluded Orders", len(excluded_report))

        excluded_cols = [
            "external_order_id",
            "scout_first_name",
            "scout_last_name",
            "order_type",
            "order_status",
            "submit_dt",
            "order_total",
            "exclusion_reason",
        ]
        display_cols = [c for c in excluded_cols if c in excluded_report.columns]
        st.dataframe(
            excluded_report[display_cols],
            width='stretch',
            hide_index=True,
        )

    # st.write(new_orders.columns.tolist())
    cols_to_import = ["parent_id","scout_id","program_year","order_ref",
        "order_type","submit_dt","initial_order","comments","order_qty_boxes","order_amount",
        "status"] + list(cookie_nm_map.values())

    preview_df = new_orders[cols_to_import].copy()
    for id_col in ("parent_id", "scout_id"):
        if id_col in preview_df.columns:
            preview_df[id_col] = preview_df[id_col].astype(str)

    st.dataframe(
        preview_df,
        width='stretch',
    )

    if new_orders.empty:
        st.success("All eligible orders already imported.")
        return

    if st.button("Import Digitals", type="primary"):
        # add st spinner or progress bar
        with st.spinner("Importing orders..."):
            updated_df = bulk_insert_order_headers(new_orders) # return adds the order_id
            bulk_insert_order_items(updated_df)
            bulk_insert_planned_inventory(updated_df)
            bulk_insert_money_ledger(updated_df)
            
        st.success(f"Orders submitted successfully!")

    


# ======================================================
# Entry Point
# ======================================================

if __name__ == "__main__":
    setup.config_site(
        page_title="Import Digital Cookie Orders",
        initial_sidebar_state="expanded",
    )
    main()
