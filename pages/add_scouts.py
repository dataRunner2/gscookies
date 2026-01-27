import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from sqlalchemy import create_engine, text
from utils.app_utils import setup
from utils.order_utils import get_scouts_byparent, add_scout, update_scout


# --------------------------------------------------
# Auth guard
# --------------------------------------------------
if not ss.get("authenticated", False):
    st.warning("Please log in first")
    st.stop()

# --------------------------------------------------
# DB helpers
# --------------------------------------------------

def parse_awards(award_str: str | None) -> dict:
    """
    Converts '315+: foo || 500+: bar' into {315: foo, 500: bar}
    """
    if not award_str:
        return {}

    parsed = {}
    parts = [p.strip() for p in award_str.split("||")]

    for part in parts:
        if ":" not in part:
            continue
        level, value = part.split(":", 1)
        try:
            level_num = int(level.replace("+", "").strip())
            parsed[level_num] = value.strip()
        except ValueError:
            continue

    return parsed

def main():
    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    st.caption(f"Logged in as **{ss.parent_name}**")

    # --------------------------------------------------
    # Add new scout
    # --------------------------------------------------
    with st.expander("➕ Add a New Scout", expanded=False):
        with st.form("add_scout_form", clear_on_submit=True):

            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("Scout First Name")
            with col2:
                last_name = st.text_input("Scout Last Name")

            goals = st.number_input(
                "Cookie Goal",
                min_value=0,
                max_value=1300,
                step=25
            )

            submitted = st.form_submit_button("Add Scout")

            if submitted:
                if not first_name or not last_name:
                    st.error("First and last name are required")
                    st.stop()
                
                if goals < 315:
                    award_preferences = 'Cumulative Awards'
                else:
                    award_preferences = '!! Award Selection Required !!'
                
                scout_id = add_scout(
                    ss.parent_id,
                    first_name.strip(),
                    last_name.strip(),
                    goals=goals,
                    award_preferences=award_preferences
                )

                ss.selected_scout_id = scout_id
                rows = get_scouts_byparent(ss.parent_id)
                ss.scout_dict = {str(r["scout_id"]): r for r in rows}
                st.success("Scout added! Now select awards 👇")

    # --------------------------------------------------
    # Add Award Preferances Right after adding new scout
    # --------------------------------------------------
    if "selected_scout_id" in ss:

        scout = ss.scout_dict.get(str(ss.selected_scout_id))
        scout_name = scout["first_name"]


        st.divider()
        st.subheader(f"🎁 Award Preferences for {scout_name}")
        scout_goal = goals  # or fetch from DB by scout_id

        award_entries = []
        TSHIRT_SIZES = ["YS", "YM", "YL", "AS", "AM", "AL", "AXL", "A2XL", "A3XL"]

        if scout_goal < 500:
            award_entries.append("Awards below 500 are cumulative")

        if scout_goal >= 315:
            tshirt = st.selectbox(
                "315+ Award: T-Shirt Size",
                TSHIRT_SIZES,
                key=f"award_315_{ss.selected_scout_id}"
            )
            award_entries.append(f"315+: T-shirt size {tshirt}")

        if scout_goal >= 500:
            award_500 = st.radio(
                "500+ Award",
                [
                    "All cumulative lower awards",
                    "$50 Amazon Select Items",
                    "$50 Program Credit"
                ],
                key=f"award_500_{ss.selected_scout_id}"
            )
            award_entries.append(f"500+: {award_500}")

        if scout_goal >= 600:
            award_600 = st.radio(
                "600+ Award",
                [
                    "Build-a-Bear up to $90",
                    "$90 Program Credit"
                ],
                key=f"award_600_{ss.selected_scout_id}"
            )
            award_entries.append(f"600+: {award_600}")

        if scout_goal >= 700:
            award_700 = st.radio(
                "700+ Award",
                [
                    "Custom Vans Shoes",
                    "$140 Program Credit"
                ],
                key=f"award_700_{ss.selected_scout_id}"
            )
            award_entries.append(f"700+: {award_700}")

        if scout_goal >= 800:
            award_800 = st.radio(
                "800+ Award",
                [
                    "Lego Build Experience",
                    "$190 Program Credit"
                ],
                key=f"award_800_{ss.selected_scout_id}"
            )
            award_entries.append(f"800+: {award_800}")

        if scout_goal >= 900:
            award_900 = st.radio(
                "900+ Award",
                [
                    "Sewing Machine",
                    "Program Credits"
                ],
                key=f"award_900_{ss.selected_scout_id}"
            )
            award_entries.append(f"900+: {award_900}")

        if scout_goal >= 1000:
            sweatshirt = st.selectbox(
                "1000+ Award: Sweatshirt Size",
                TSHIRT_SIZES,
                key=f"award_1000_{ss.selected_scout_id}"
            )
            award_entries.append(f"1000+: Sweatshirt size {sweatshirt}")

        if scout_goal >= 1100:
            award_1100 = st.radio(
                "1100+ Award",
                [
                    "Chromebook",
                    "Program Credits"
                ],
                key=f"award_1100_{ss.selected_scout_id}"
            )
            award_entries.append(f"1100+: {award_1100}")

        award_preferences = " || ".join(award_entries)

    with st.form("save_awards_form"):
        st.caption("Award selections are saved separately from scout creation.")
        save_awards = st.form_submit_button("Save Award Preferences")

        if save_awards:
            update_scout(
                ss.selected_scout_id,
                award_preferences
            )
            st.success("Award preferences saved!")

    # --------------------------------------------------
    # Existing scouts
    # --------------------------------------------------
    st.divider()
    st.subheader("Your Scouts")
    # Build dict once
    rows = get_scouts_byparent(ss.parent_id)
    ss.scout_dict = {str(r["scout_id"]): r for r in rows}

    # Build dataframe
    scouts_df = pd.DataFrame(list(ss.scout_dict.values()))


    if scouts_df.empty:
        st.info("No scouts added yet.")
    else:

        for _, row in scouts_df.iterrows():
            with st.container(border=True):
                cols = st.columns([3, 2, 2,1])

                cols[0].write(f"**{row.first_name} {row.last_name}**")
                cols[1].write(f"Goal: {row.goals}")
                cols[2].write(f"Selected Awards: {row.award_preferences}")

                if cols[3].button("✏️ Edit", key=f"edit_{row.scout_id}"):
                    ss.edit_scout_id = row.scout_id

    if "edit_scout_id" in ss:
        scout = scouts_df.loc[
            scouts_df.scout_id == ss.edit_scout_id
        ].iloc[0]

        st.divider()
        st.subheader(f"Edit Scout: {scout.first_name}")

        saved_awards = parse_awards(scout.award_preferences)

        new_goal = st.number_input(
            "Cookie Goal",
            min_value=0,
            max_value=1300,
            step=25,
            value=int(scout.goals),
            key=f"goal_{scout.scout_id}"
        )

        award_entries = []
        TSHIRT_SIZES = ["YS", "YM", "YL", "AS", "AM", "AL", "AXL", "A2XL", "A3XL"]

        if new_goal < 500:
            award_entries.append("awards below 500 are cumulative")

        if new_goal >= 315:
            tshirt = st.selectbox(
                "315+ T-Shirt",
                TSHIRT_SIZES,
                index=TSHIRT_SIZES.index(
                    saved_awards.get(315, TSHIRT_SIZES[0]).replace("T-shirt size ", "")
                ) if 315 in saved_awards else 0,
                key=f"315_{scout.scout_id}"
            )
            award_entries.append(f"315+: T-shirt size {tshirt}")

        if new_goal >= 500:
            opts_500 = [
                "All cumulative lower awards",
                "$50 Amazon Select Items",
                "$50 Program Credit"
            ]
            sel_500 = saved_awards.get(500, opts_500[0])
            award_500 = st.radio(
                "500+ Award",
                opts_500,
                index=opts_500.index(sel_500),
                key=f"500_{scout.scout_id}"
            )
            award_entries.append(f"500+: {award_500}")

        if new_goal >= 600:
            opts_600 = ["Build-a-Bear up to $90", "$90 Program Credit"]
            sel_600 = saved_awards.get(600, opts_600[0])
            award_600 = st.radio(
                "600+ Award",
                opts_600,
                index=opts_600.index(sel_600),
                key=f"600_{scout.scout_id}"
            )
            award_entries.append(f"600+: {award_600}")

        if new_goal >= 700:
            opts_700 = ["Custom Vans Shoes", "$140 Program Credit"]
            sel_700 = saved_awards.get(800, opts_700[0])
            award_700 = st.radio(
                "700+ Award",
                opts_700,
                index=opts_700.index(sel_700),
                key=f"700_{scout.scout_id}"
            )
            award_entries.append(f"700+: {award_700}")

        if new_goal >= 800:
            opts_800 = ["Lego Build Experience",
                    "$190 Program Credit"]
            sel_800 = saved_awards.get(800, opts_800[0])
            award_800 = st.radio(
                "800+ Award",
                opts_800,
                index=opts_800.index(sel_800),
                key=f"800_{scout.scout_id}"
            )
            award_entries.append(f"800+: {award_800}")

        if new_goal >= 900:
            opts_900 = ["Sewing Machine",
                    "Program Credits"]
            sel_900 = saved_awards.get(900, opts_900[0])
            award_900 = st.radio(
                "900+ Award",
                opts_900,
                index=opts_900.index(sel_900),
                key=f"900_{scout.scout_id}"
            )
            award_entries.append(f"900+: {award_900}")

        if new_goal >= 1000:
            opts_1000 = TSHIRT_SIZES            
            sel_1000 = saved_awards.get(1000, opts_1000[0])
            award_1000 = st.selectbox(
                "1000+ Award: Sweatshirt Size",
                opts_1000,
                index=opts_1000.index(sel_1000),
                key=f"award_1000_{ss.selected_scout_id}"
            )
            award_entries.append(f"1000+: Sweatshirt size {award_1000}")

        if new_goal >= 1100:
            opts_1100 = [ "Chromebook",
                    "Program Credits"]
            sel_1100 = saved_awards.get(1100, opts_1100[0])
            award_1100 = st.radio(
                "1100+ Award",
                opts_1100,
                index=opts_1100.index(sel_1100),
                key=f"1100_{scout.scout_id}"
            )
            award_entries.append(f"1100+: {award_1100}")


        final_awards = " || ".join(award_entries)

        with st.form(f"save_scout_{scout.scout_id}"):
            save = st.form_submit_button("Save Changes")

            if save:
                update_scout(
                    scout_id=scout.scout_id,
                    goals=new_goal,
                    award_preferences=final_awards
                )
                st.success("Scout updated")
                del ss.edit_scout_id
                st.rerun()


if __name__ == "__main__":
    setup.config_site(
        page_title="Add / Update Scout",
        initial_sidebar_state="expanded"
    )
    main()