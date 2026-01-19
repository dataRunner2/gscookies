import streamlit as st
from streamlit import session_state as ss
from datetime import datetime
from uuid import uuid4
from utils.app_utils import setup
from utils.db_utils import require_admin, execute_sql, fetch_all


# --------------------------------------------------
# Session init
# --------------------------------------------------
def init_ss():
    if 'current_year' not in ss:
        ss.current_year = datetime.now().year


# --------------------------------------------------
# Data helpers
# --------------------------------------------------
def get_all_parents():
    """Get all parents with scout count."""
    return fetch_all("""
        SELECT 
            p.parent_id,
            p.parent_firstname,
            p.parent_lastname,
            p.parent_email,
            p.parent_phone,
            p.username,
            p.is_admin,
            COUNT(s.scout_id) as scout_count
        FROM cookies_app.parents p
        LEFT JOIN cookies_app.scouts s ON s.parent_id = p.parent_id
        GROUP BY p.parent_id, p.parent_firstname, p.parent_lastname, 
                 p.parent_email, p.parent_phone, p.username, p.is_admin
        ORDER BY p.parent_lastname, p.parent_firstname
    """)


def get_all_scouts():
    """Get all scouts with parent info."""
    return fetch_all("""
        SELECT 
            s.scout_id,
            s.first_name,
            s.last_name,
            s.grade,
            s.active,
            s.goals,
            s.award_preferences,
            s.tshirt_size,
            s.gsusa_id,
            s.parent_id,
            p.parent_firstname || ' ' || p.parent_lastname as parent_name
        FROM cookies_app.scouts s
        LEFT JOIN cookies_app.parents p ON p.parent_id = s.parent_id
        ORDER BY s.last_name, s.first_name
    """)


def get_scouts_for_parent(parent_id):
    """Get all scouts for a specific parent."""
    return fetch_all("""
        SELECT 
            scout_id,
            first_name,
            last_name,
            grade,
            active,
            goals,
            award_preferences,
            tshirt_size,
            gsusa_id
        FROM cookies_app.scouts
        WHERE parent_id = :pid
        ORDER BY last_name, first_name
    """, {"pid": parent_id})


def update_scout(scout_id, first_name, last_name, grade, goals, award_preferences, 
                tshirt_size, gsusa_id, active, parent_id):
    """Update scout information."""
    execute_sql("""
        UPDATE cookies_app.scouts
        SET first_name = :fname,
            last_name = :lname,
            grade = :grade,
            goals = :goals,
            award_preferences = :awards,
            tshirt_size = :tshirt,
            gsusa_id = :gsusa,
            active = :active,
            parent_id = :pid
        WHERE scout_id = :sid
    """, {
        "sid": scout_id,
        "fname": first_name,
        "lname": last_name,
        "grade": grade,
        "goals": goals,
        "awards": award_preferences,
        "tshirt": tshirt_size,
        "gsusa": gsusa_id,
        "active": active,
        "pid": parent_id
    })


def add_scout_to_parent(parent_id, first_name, last_name, grade=None, tshirt_size=None):
    """Add a new scout to a parent."""
    scout_id = str(uuid4())
    execute_sql("""
        INSERT INTO cookies_app.scouts (
            scout_id, parent_id, first_name, last_name, grade, 
            tshirt_size, active, goals, award_preferences
        )
        VALUES (
            :sid, :pid, :fname, :lname, :grade,
            :tshirt, true, 0, ''
        )
    """, {
        "sid": scout_id,
        "pid": parent_id,
        "fname": first_name,
        "lname": last_name,
        "grade": grade,
        "tshirt": tshirt_size
    })
    return scout_id


# --------------------------------------------------
# Main Page
# --------------------------------------------------
def main():
    init_ss()
    require_admin()

    st.title("👥 User Management")

    tab_scouts, tab_parents, tab_report = st.tabs([
        "👧 Scouts",
        "👨‍👩‍👧 Parents",
        "🖨️ Print Report"
    ])

    # ==================================================
    # TAB 1 — SCOUTS
    # ==================================================
    with tab_scouts:
        st.markdown("## 👧 Scout Management")
        st.markdown("Edit scout information, goals, and award preferences.")

        scouts = get_all_scouts()
        
        if not scouts:
            st.info("No scouts in the system.")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                show_inactive = st.checkbox("Show inactive scouts", value=False)
            with col2:
                search = st.text_input("Search by name", "")
            
            # Filter scouts
            filtered_scouts = scouts
            if not show_inactive:
                filtered_scouts = [s for s in filtered_scouts if s.active]
            if search:
                search_lower = search.lower()
                filtered_scouts = [
                    s for s in filtered_scouts 
                    if search_lower in s.first_name.lower() or search_lower in s.last_name.lower()
                ]
            
            st.write(f"**Showing {len(filtered_scouts)} of {len(scouts)} scouts**")
            
            # Display scouts in expandable sections
            for scout in filtered_scouts:
                status_emoji = "✅" if scout.active else "❌"
                scout_name = f"{scout.first_name} {scout.last_name}"
                parent_info = f" ({scout.parent_name})" if scout.parent_name else " (No parent)"
                
                with st.expander(f"{status_emoji} {scout_name}{parent_info}"):
                    with st.form(key=f"scout_form_{scout.scout_id}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            first_name = st.text_input("First Name", value=scout.first_name)
                            last_name = st.text_input("Last Name", value=scout.last_name)
                            grade = st.number_input("Grade", min_value=1, max_value=12, 
                                                   value=scout.grade if scout.grade else 1)
                            active = st.checkbox("Active", value=scout.active)
                        
                        with col2:
                            goals = st.number_input("Sales Goal (boxes)", min_value=0, 
                                                   value=scout.goals if scout.goals else 0)
                            tshirt_size = st.selectbox(
                                "T-Shirt Size",
                                options=["", "YS", "YM", "YL", "AS", "AM", "AL", "AXL", "A2XL"],
                                index=0 if not scout.tshirt_size else 
                                      ["", "YS", "YM", "YL", "AS", "AM", "AL", "AXL", "A2XL"].index(scout.tshirt_size)
                            )
                            gsusa_id = st.text_input("GSUSA ID", value=scout.gsusa_id or "")
                            
                            # Parent assignment
                            parents = get_all_parents()
                            parent_options = {p.parent_id: f"{p.parent_firstname} {p.parent_lastname}" 
                                            for p in parents}
                            current_parent_idx = 0
                            if scout.parent_id:
                                parent_ids = list(parent_options.keys())
                                if scout.parent_id in parent_ids:
                                    current_parent_idx = parent_ids.index(scout.parent_id)
                            
                            parent_id = st.selectbox(
                                "Assigned Parent",
                                options=list(parent_options.keys()),
                                format_func=lambda x: parent_options[x],
                                index=current_parent_idx
                            )
                        
                        award_preferences = st.text_area(
                            "Award Preferences",
                            value=scout.award_preferences or "",
                            height=100,
                            help="Enter preferred awards or prizes (one per line)"
                        )
                        
                        col1, col2 = st.columns([1, 5])
                        with col1:
                            if st.form_submit_button("💾 Save", type="primary"):
                                update_scout(
                                    scout.scout_id, first_name, last_name, grade,
                                    goals, award_preferences, tshirt_size or None,
                                    gsusa_id or None, active, parent_id
                                )
                                st.success(f"✓ Updated {first_name} {last_name}")
                                st.rerun()

    # ==================================================
    # TAB 2 — PARENTS
    # ==================================================
    with tab_parents:
        st.markdown("## 👨‍👩‍👧 Parent Management")
        st.markdown("View parents and add scouts to them.")
        
        parents = get_all_parents()
        
        if not parents:
            st.info("No parents in the system.")
        else:
            st.write(f"**Total Parents:** {len(parents)}")
            
            for parent in parents:
                admin_badge = " 🔑" if parent.is_admin else ""
                
                with st.expander(f"{parent.parent_firstname} {parent.parent_lastname}{admin_badge} - {parent.scout_count} scout(s)"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Name:** {parent.parent_firstname} {parent.parent_lastname}")
                        st.write(f"**Email:** {parent.parent_email}")
                        st.write(f"**Phone:** {parent.parent_phone or 'N/A'}")
                    
                    with col2:
                        st.write(f"**Username:** {parent.username}")
                        st.write(f"**Admin:** {'Yes' if parent.is_admin else 'No'}")
                        st.write(f"**Parent ID:** `{parent.parent_id}`")
                    
                    # Show scouts for this parent
                    scouts = get_scouts_for_parent(parent.parent_id)
                    
                    if scouts:
                        st.markdown("**Scouts:**")
                        for scout in scouts:
                            status = "✅" if scout.active else "❌"
                            goal_info = f" (Goal: {scout.goals} boxes)" if scout.goals else ""
                            st.write(f"{status} {scout.first_name} {scout.last_name} - Grade {scout.grade or 'N/A'}{goal_info}")
                    
                    # Add scout to this parent
                    st.markdown("---")
                    st.markdown("**Add New Scout**")
                    
                    with st.form(key=f"add_scout_{parent.parent_id}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            new_first = st.text_input("First Name")
                        with col2:
                            new_last = st.text_input("Last Name")
                        with col3:
                            new_grade = st.number_input("Grade", min_value=1, max_value=12, value=1)
                        
                        new_tshirt = st.selectbox(
                            "T-Shirt Size (optional)",
                            options=["", "YS", "YM", "YL", "AS", "AM", "AL", "AXL", "A2XL"]
                        )
                        
                        if st.form_submit_button("➕ Add Scout"):
                            if not new_first or not new_last:
                                st.error("First and last name are required")
                            else:
                                add_scout_to_parent(
                                    parent.parent_id, 
                                    new_first, 
                                    new_last, 
                                    new_grade,
                                    new_tshirt or None
                                )
                                st.success(f"✓ Added {new_first} {new_last} to {parent.parent_firstname} {parent.parent_lastname}")
                                st.rerun()

    # ==================================================
    # TAB 3 — PRINT REPORT
    # ==================================================
    with tab_report:
        st.markdown("## 🖨️ Scout & Goal Report")
        
        scouts = get_all_scouts()
        active_scouts = [s for s in scouts if s.active]
        
        st.markdown(f"### Scout Summary ({len(active_scouts)} active scouts)")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        total_goals = sum(s.goals or 0 for s in active_scouts)
        scouts_with_goals = len([s for s in active_scouts if s.goals and s.goals > 0])
        scouts_with_awards = len([s for s in active_scouts if s.award_preferences])
        
        col1.metric("Total Scouts", len(active_scouts))
        col2.metric("Total Goal Boxes", total_goals)
        col3.metric("Scouts with Goals", scouts_with_goals)
        
        # Detailed table
        st.markdown("---")
        st.markdown("### Detailed Scout List")
        
        # Prepare data for display
        report_data = []
        for scout in active_scouts:
            report_data.append({
                "Scout Name": f"{scout.first_name} {scout.last_name}",
                "Grade": scout.grade or "-",
                "Parent": scout.parent_name or "Unassigned",
                "Goal (boxes)": scout.goals or 0,
                "T-Shirt": scout.tshirt_size or "-",
                "Awards": scout.award_preferences[:50] + "..." if scout.award_preferences and len(scout.award_preferences) > 50 else scout.award_preferences or "-"
            })
        
        st.dataframe(
            report_data,
            use_container_width=True,
            hide_index=True
        )
        
        # Awards detail
        st.markdown("---")
        st.markdown("### Award Preferences Detail")
        
        scouts_with_award_prefs = [s for s in active_scouts if s.award_preferences]
        
        if scouts_with_award_prefs:
            for scout in scouts_with_award_prefs:
                st.markdown(f"**{scout.first_name} {scout.last_name}** (Goal: {scout.goals or 0} boxes)")
                st.write(scout.award_preferences)
                st.markdown("---")
        else:
            st.info("No scouts have award preferences set.")
        
        # Print instructions
        st.markdown("---")
        st.info("💡 Use your browser's print dialog (Ctrl+P / Cmd+P) to print this report.")


# --------------------------------------------------
# Entry Point
# --------------------------------------------------
if __name__ == "__main__":
    setup.config_site(
        page_title="User Management",
        initial_sidebar_state="expanded"
    )
    main()
