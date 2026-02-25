import pandas as pd
import streamlit as st

from utils.app_utils import setup
from utils.db_utils import fetch_all, require_admin


def get_parent_contacts():
    return fetch_all(
        """
        SELECT
            p.parent_firstname,
            p.parent_lastname,
            p.parent_email,
            p.parent_phone,
            COALESCE(
                STRING_AGG(
                    TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')),
                    ', ' ORDER BY s.last_name, s.first_name
                ),
                ''
            ) AS scouts
        FROM cookies_app.parents p
        LEFT JOIN cookies_app.scouts s ON s.parent_id = p.parent_id
        GROUP BY p.parent_id, p.parent_firstname, p.parent_lastname, p.parent_email, p.parent_phone
        ORDER BY p.parent_lastname, p.parent_firstname
        """
    )


def main():
    require_admin()

    st.subheader("Parent Contacts")

    rows = get_parent_contacts()
    if not rows:
        st.info("No parent records found.")
        return

    data = pd.DataFrame(rows)
    data = data.rename(
        columns={
            "parent_firstname": "First Name",
            "parent_lastname": "Last Name",
            "parent_phone": "Phone",
            "parent_email": "Email",
            "scouts": "Scouts",
        }
    )
    data = data[["First Name", "Last Name", "Email", "Phone", "Scouts"]]

    st.dataframe(data, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    setup.config_site(
        page_title="Parent Contacts",
        initial_sidebar_state="expanded",
    )
    main()
