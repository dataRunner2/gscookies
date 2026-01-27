from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from pathlib import Path

from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3
from utils.db_utils import require_login, to_pacific

def init_ss():
    pass

def main():
    require_login()

    PDF_PATH = Path("assets/Parent_Meeting_2026.pdf")


    st.download_button(
        label="⬇️ Download Parent Meeting Slides",
        data=PDF_PATH.read_bytes(),
        file_name="Parent_Meeting_2026.pdf",
        mime="application/pdf",
    )

    st.info(
        "Tip: This slide deck covers the full cookie timeline, booth process, "
        "Digital Cookie, and Troop Cookie Tracker walkthrough."
    )

    tabs = st.tabs([
        "Overview",
        "Timeline",
        "Booths",
        "Selling Tips",
        "Cookie Tracker",
        "Resources",
        "Marketing"
    ])

    # -----------------------------
    with tabs[0]:
        st.subheader("Agenda")
        st.markdown("""
        - Cookie Program Overview  
        - Initial Orders & Booths  
        - Digital Cookie  
        - Troop Cookie Tracker App  
        - Resources & Contacts
        """)

        st.success("📢 Please use **Cookie Band** for questions so the whole Cookie Crew can help.")

        st.markdown("""
        **Cookie Band**
        GS43202 Cookies  
        https://band.us/n/acacA2j8m3f8i

        **Cookie Cupboard**
        Chhavi Jain – Maple Valley  
        📞 727-424-3076

        **Cookie Crew**
        Chhavi, Jessica, Celeste, Jennifer, Kendall, Cody
        """)

    # -----------------------------
    with tabs[1]:
        st.subheader("📅 2026 Cookie Season Timeline")

        st.markdown("""
        **Jan 5** – Digital Cookie setup email  
        **Jan 6 – Feb 1** – Pre-orders  
        **Feb 1** – Initial Orders Due  
        **Feb 14** – Cookies arrive at Maple Valley Distribution *(Volunteers Needed)*  
        **Feb 26 – Mar 15** – Cookie Booths (3 weekends)
        **Mar 9** – Last in-person delivery & initial money due  
        **Mar 15** – Digital Cookie ends  
        **Mar 17** – Family money due  
        **May–June** – Rewards distributed
        """)

    # -----------------------------
    with tabs[2]:
        st.subheader("🏪 Booth Information")

        st.warning("❌ Do NOT order your own booth cookies")

        st.markdown("""
        **Booth Rules**
        - Parent must always hold money
        - Girls must wear uniform
        - No donation bins (they’ve been stolen)
        - Square POS app required (details coming)

        **Booth Process**
        - Arrive at cupboard ~1h before booth to checkout materials and cookies
        - Do not mix booth cookies with personal orders
        - Return supplies within 30 minutes after booth
                    
        **Booth Kit**
            When you arrive at the cupboard you will receive: 
            - cookies
            - money bag with starting cash
            - if your booth allows, a folding table
            - credit card reader (more on this via band)
            - tracking sheet
        """)

    # -----------------------------
    with tabs[3]:
        st.subheader("🗣 Selling Practice")

        st.markdown("""
        **Asking for the Sale**
        - “Would you like to buy Girl Scout cookies?”
        - “What’s your favorite Girl Scout cookie?”
        - “Would you like to add a box of ___?”

        **Know Your Cookies**
        - Toffee-Tastic = gluten-free biscotti-style
        - Lemon Ups = great with tea
        - Adventurefuls, Samoas, Thin Mints are top sellers
        """)

    # -----------------------------
    with tabs[4]:
        st.subheader("📱 Troop Cookie Tracker")

        st.markdown("""
        **What’s New**
        - Update scout info (T-shirt, awards)
        - Modify/delete orders not yet picked up
        - Complete booth worksheet on your phone

        **Status**
        - Live Jan 12
        - Digital Cookie imports have 1–2 day lag
        """)

    # -----------------------------
    with tabs[5]:
        st.subheader("📞 Resources & Contacts")

        
        st.subheader('Acronyms & Definitions')
        st.markdown("""
            - Digital Cookie (DC): Digital cookie is the scouts personalized point of sale website. They can share their cookie story, set their cookie goals and create a personalized QR code to take credit card orders. 
            - Troop Cookie Tracker: This website - which is used for families to submit their delivery orders to our troop cupboard which is how we know you need cookies. 
            - Girl Delivery Digital Cookies (DOC): Digtial cookie orders that families have agreed to deliver instead of have shipped.
            
            Cookie Acronyms
            - Adv: Adventurefuls
            - DSD: Do-Si-Dos
            - TM: Thin Mints
            - LU: Lemon Ups
            - TF: Trefoils
            - SAM: Samoas
            - Tags: Tagalongs
            - EXP: Exploremores
            - TT:Toffee-tastic
            - DON: Sweet Cookie Donation
        """)
    with tabs[6]:
        st.subheader("Marketing")
        st.markdown('[Little Brownie Bakers Marketing Materials](https://www.littlebrowniebakers.com/ThemeGraphics)')
        st.write("It’s fun for kids to make signs to bring to their booths. This gives them a chance to learn about marketing.")

        st.write(f'[My GS Troop Resources](https://www.girlscoutsww.org/en/activities/cookies/for-cookie-sellers/cookie-seller-resources.html#TroopVolunteerResources)')


if __name__ == '__main__':

    setup.config_site(page_title="📣 2026 Cookie Program – Parent Meeting",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()