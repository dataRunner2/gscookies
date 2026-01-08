import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from sqlalchemy import create_engine, text
from utils.app_utils import setup

# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(page_title="Manage Scouts", layout="wide")

# --------------------------------------------------
# Database connection (Streamlit secrets)
# --------------------------------------------------
DB_HOST = "136.118.19.164"
DB_PORT = "5432"
DB_NAME = "cookies"
DB_USER = "cookie_admin"
DB_PASS = st.secrets["general"]["DB_PASSWORD"]

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_pre_ping=True
)

# --------------------------------------------------
# Auth guard
# --------------------------------------------------
if not ss.get("authenticated", False):
    st.warning("Please log in first")
    st.stop()

# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def get_scouts(parent_id):
    sql = text("""
        SELECT
            scout_id,
            first_name,
            last_name,
            tshirt_size,
            goals,
            award_preferences
        FROM cookies_app.scouts
        WHERE parent_id = :parent_id
        ORDER BY last_name, first_name
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"parent_id": parent_id})


def add_scout(parent_id, first, last, tshirt, goals, awards):
    sql = text("""
        INSERT INTO cookies_app.scouts (
            parent_id,
            first_name,
            last_name,
            tshirt_size,
            goals,
            award_preferences
        )
        VALUES (
            :parent_id,
            :first,
            :last,
            :tshirt,
            :goals,
            :awards
        )
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "parent_id": parent_id,
            "first": first,
            "last": last,
            "tshirt": tshirt,
            "goals": goals,
            "awards": awards
        })


def update_scout(scout_id, tshirt, goals, awards):
    sql = text("""
        UPDATE cookies_app.scouts
        SET
            tshirt_size = :tshirt,
            goals = :goals,
            award_preferences = :awards
        WHERE scout_id = :scout_id
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "scout_id": scout_id,
            "tshirt": tshirt,
            "goals": goals,
            "awards": awards
        })

def main():
    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    st.title("Manage Scouts")
    st.caption(f"Logged in as **{ss.parent_name}**")

    # --------------------------------------------------
    # Add new scout
    # --------------------------------------------------
    with st.expander("➕ Add a New Scout", expanded=True):
        with st.form("add_scout_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("Scout First Name")
            with col2:
                last_name = st.text_input("Scout Last Name")

            tshirt_options = ["", "YS", "YM", "YL", "AS", "AM", "AL", "AXL"]
            tshirt_size = st.selectbox("T-Shirt Size", tshirt_options)

            goals = st.number_input(
                "Cookie Goal",
                min_value=0,
                max_value=5000,
                step=25
            )

            award_preferences = st.text_area(
                "Award Preferences (optional)",
                placeholder="e.g. plush, patches, donation awards"
            )

            submitted = st.form_submit_button("Add Scout")

            if submitted:
                if not first_name or not last_name:
                    st.error("First and last name are required")
                    st.stop()

                add_scout(
                    ss.parent_id,
                    first_name.strip(),
                    last_name.strip(),
                    tshirt_size,
                    goals,
                    award_preferences
                )

                st.success(f"Added scout {first_name} {last_name}")
                st.rerun()

    # --------------------------------------------------
    # Existing scouts
    # --------------------------------------------------
    st.divider()
    st.subheader("Your Scouts")

    scouts_df = get_scouts(ss.parent_id)

    if scouts_df.empty:
        st.info("No scouts added yet.")
    else:
        tshirt_opts = ["", "YS", "YM", "YL", "AS", "AM", "AL", "AXL"]

        for _, row in scouts_df.iterrows():
            with st.expander(f"{row.first_name} {row.last_name}", expanded=False):

                tshirt = st.selectbox(
                    "T-Shirt Size",
                    tshirt_opts,
                    index=tshirt_opts.index(row.tshirt_size) if row.tshirt_size in tshirt_opts else 0,
                    key=f"tshirt_{row.scout_id}"
                )

                goals = st.number_input(
                    "Cookie Goal",
                    min_value=0,
                    max_value=5000,
                    step=25,
                    value=row.goals if row.goals is not None else 0,
                    key=f"goals_{row.scout_id}"
                )

                awards = st.text_area(
                    "Award Preferences",
                    value=row.award_preferences or "",
                    key=f"awards_{row.scout_id}"
                )

                if st.button("Save Changes", key=f"save_{row.scout_id}"):
                    update_scout(
                        row.scout_id,
                        tshirt,
                        goals,
                        awards
                    )
                    st.success("Changes saved")
                    st.rerun()


if __name__ == "__main__":
    setup.config_site(
        page_title="Booth Entry",
        initial_sidebar_state="expanded"
    )
    main()