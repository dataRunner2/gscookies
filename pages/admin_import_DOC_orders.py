import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import uuid
from datetime import datetime

from utils.app_utils import setup
from utils.db_utils import (
    get_all_scouts,
    require_admin,
    update_scout_gsusa_id
)
from utils.order_utils import (
    fetch_existing_external_orders,
    bulk_insert_orders, build_cookie_rename_map
)

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
            "Cookie Variety": "cookie_name",
            "Quantity": "order_qty_boxes",
            "Total": "order_amount",
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

    return order_df.rename(columns=valid_map)

    


# ======================================================
# Main
# ======================================================

def main():
    require_admin()
    st.title("Import Digital Cookie Orders")

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

    uploaded_df = normalize_columns(pd.read_excel(uploaded_file))
    st.dataframe(uploaded_df)

    filtered_df = uploaded_df[
        (uploaded_df["order_type"] == "In-Person Delivery")
        & (uploaded_df["order_status"] == "PROCESSING")
    ].copy()

    st.metric("Eligible Orders After Filtering", len(filtered_df))

    if filtered_df.empty:
        st.success("No eligible orders found.")
        return

    # ----------------------------------
    # Scout Matching
    # ----------------------------------

    scouts = get_all_scouts()
    st.write(scouts[:2])
    # aliases = fetch_scout_aliases()

    ss.scout_name_lookup = {
        (s.first_name, s.last_name): s.scout_id
        for s in scouts
        }
    ss.parent_id_lookup = {
        s.scout_id: s.parent_id
        for s in scouts
        }
    
    ss.gsuid_map = build_gsusa_mapping(scouts, filtered_df)

    # Update Scouts Table with GSU_ID
    scout_updates = build_scout_updates(scouts, ss.gsuid_map)
    st.write(f'Scouts table Updates: \n\n{scout_updates[:2]}')

    #### 
    updated_df = attach_scout_id(filtered_df)
    st.dataframe(updated_df) #[['scout_id','external_order_id','scout_gsusa_id','scout_first_name']])
    

    unmatched = updated_df[updated_df["scout_id"].isna()].copy()
    matched = updated_df[updated_df["scout_id"].notna()].copy()
    st.write('matched:\n')
    st.dataframe(matched)
    # ----------------------------------
    # Alias Resolution UI
    # ----------------------------------
    if not unmatched.empty:
        st.warning("Some scout names need to be matched")

        scout_options = {
            f"{s.first_name} {s.last_name}": s.scout_id for s in scouts
        }

        for idx, row in unmatched.iterrows():
            st.markdown(
                f"**Digital Cookie Scout:** "
                f"`{row['scout_first_name']} {row['scout_last_name']}` "
            )
            # if row.scout_gsusa_id.notna():
            #     st.markdown(f"(GSUSA ID: {row.scout_gsusa_id})")

            choice = st.selectbox(
                "Match to Scout",
                [""] + list(scout_options.keys()),
                key=f"scout_match_{idx}",
            )

            if choice:
                scout_id = scout_options[choice]
                unmatched.at[idx, "scout_id"] = scout_id

                if pd.notna(row.scout_gsusa_id):
                    update_scout_gsusa_id(
                        scout_id=scout_id,
                        gsusa_id=row.scout_gsusa_id,
                    )
                unmatched.at[idx, "scout_id"] = scout_id

        if unmatched["scout_id"].isna().any():
            pass
            # st.stop()

        # matched = pd.concat([matched, unmatched])

    # ----------------------------------
    # Final Prep + Deduplication
    # ----------------------------------
    # Ensure year exists (cookie season is program year)
    matched["program_year"] = int(ss.current_year)

    matched["order_source"] = "Digital Cookie Import"
    matched["submit_dt"] = pd.to_datetime(matched["submit_dt"])
    matched["created_at"] = datetime.utcnow()
    matched['order_type'] = matched['order_type'].replace('In-Person Delivery','Dig. Cookie Delivery')
    matched['comments'] = [f"{cust_first} {cust_last} ${total}" for cust_first,cust_last,total in zip(matched['Customer First Name'],matched['Customer Last Name'],matched['Order Total'])]
    matched["status"] = "IMPORTED"
    matched["order_ref"] = matched["external_order_id"].astype(str)

    # Rename cookie display names -> cookie codes (must ASSIGN result)
    matched = rename_cookie_columns(matched, int(ss.current_year))

    
    # Get existing orders as to not create duplicates
    existing_ids = fetch_existing_external_orders(
        order_source="Digital Cookie Import",
    )
    if len(existing_ids) == 0:
        st.write('There are no existing DOC orders, importing all of them.')

    new_orders = matched[
        ~matched["external_order_id"].isin(existing_ids)
    ].copy()
    new_orders["order_id"] = [uuid.uuid4() for _ in range(len(new_orders))]
    st.write(f'New Orders to be added {len(new_orders)}')
    st.dataframe(new_orders)
    # ----------------------------------
    # Review + Import
    # ----------------------------------

    st.metric("New Orders to Import", len(new_orders))
    
    st.dataframe(
        new_orders[[
            "parent_id","scout_id","program_year","order_ref",
            "order_type","comments","total_boxes","order_amount",
            "status","cookie_inputs"
        ]],
        width='stretch',
    )

    if new_orders.empty:
        st.success("All eligible orders already imported.")
        return

    if st.button("Import Digital Orders", type="primary"):
        st.success(f"Imported {len(new_orders)} digital orders 🎉")
        bulk_insert_orders(new_orders)
        
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
