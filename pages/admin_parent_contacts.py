import pandas as pd
import streamlit as st

from utils.app_utils import setup
from utils.db_utils import fetch_all, require_admin


def get_parent_contacts():
    return fetch_all(
        """
        SELECT
            parent_firstname,
            parent_lastname,
            parent_email,
            parent_phone
        FROM cookies_app.parents
        ORDER BY parent_lastname, parent_firstname
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
            "parent_email": "Email",
            "parent_phone": "Phone",
        }
    )
    data = data[["First Name", "Last Name", "Email", "Phone"]]

    st.dataframe(data, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    setup.config_site(
        page_title="Parent Contacts",
        initial_sidebar_state="expanded",
    )
    main()
