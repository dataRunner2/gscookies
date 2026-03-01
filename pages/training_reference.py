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

        st.subheader("💵 Cookie Math")
        st.caption("Quick totals and change examples for booths and in-person sales.")

        # st.markdown("**Standard Cookies ($6 each)**")
        standard_totals = pd.DataFrame({
            "Boxes": list(range(1, 11)),
            "Total Due": [f"${boxes * 6}" for boxes in range(1, 11)],
        })
        # # st.table(standard_totals)

        st.markdown("**Common Change Amounts (Standard $6 boxes)**")
        standard_change_rows = []
        for boxes in range(1, 9):
            due = boxes * 6
            standard_change_rows.append({
                "Boxes": boxes,
                "Total Due": f"${due}",
                "$10": f"${10 - due}" if due <= 10 else "—",
                "$20": f"${20 - due}" if due <= 20 else "—",
                "$50": f"${50 - due}" if due <= 50 else "—",
            })
        st.table(pd.DataFrame(standard_change_rows))
        st.caption("Example: If a customer gives $20 for 1 box, change is $14.")

        st.markdown("---")
        st.markdown("**Toffee-Tastic Math ($7 each)**")
        tt_totals = pd.DataFrame({
            "Toffee-Tastic Boxes": list(range(1, 9)),
            "Total Due": [f"${boxes * 7}" for boxes in range(1, 9)],
        })
        st.table(tt_totals)

        st.markdown("**Common Change Amounts (Toffee-Tastic $7 boxes)**")
        tt_change_rows = []
        for boxes in range(1, 7):
            due = boxes * 7
            tt_change_rows.append({
                "TT Boxes": boxes,
                "Total Due": f"${due}",
                "$10": f"${10 - due}" if due <= 10 else "—",
                "$20": f"${20 - due}" if due <= 20 else "—",
                "$50": f"${50 - due}" if due <= 50 else "—",
            })
        tt_change_df = pd.DataFrame(tt_change_rows)
        st.table(tt_change_df)

        standard_change_df = pd.DataFrame(standard_change_rows)

        cookie_math_html = f"""
        <html>
            <head>
                <meta charset=\"utf-8\" />
                <title>Cookie Math</title>
                <style>
                    body {{
                        font-family: 'Trebuchet MS', Arial, sans-serif;
                        background: #fff8f3;
                        color: #2d2d2d;
                        margin: 0;
                        padding: 24px;
                    }}
                    .sheet {{
                        max-width: 900px;
                        margin: 0 auto;
                    }}
                    .title {{
                        text-align: center;
                        color: #8d3b72;
                        font-size: 38px;
                        margin: 0 0 8px 0;
                    }}
                    .subtitle {{
                        text-align: center;
                        color: #5c5c5c;
                        margin: 0 0 24px 0;
                    }}
                    .card {{
                        background: #ffffff;
                        border: 2px solid #ffd5ec;
                        border-radius: 14px;
                        padding: 16px;
                        margin-bottom: 16px;
                        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
                    }}
                    .section-title {{
                        color: #d65191;
                        margin: 0 0 10px 0;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 14px;
                    }}
                    th, td {{
                        border: 1px solid #f1c3de;
                        padding: 8px 10px;
                        text-align: center;
                    }}
                    th {{
                        background: #ffe6f4;
                        color: #7f2d66;
                    }}
                    .note {{
                        margin-top: 8px;
                        color: #5c5c5c;
                        font-style: italic;
                    }}
                    @media print {{
                        body {{ background: white; padding: 0; }}
                        .card {{ box-shadow: none; break-inside: avoid; }}
                    }}
                </style>
            </head>
            <body>
                <div class=\"sheet\">
                    <h1 class=\"title\">🍪 Cookie Math</h1>
                    <p class=\"subtitle\">Quick booth cash helper for totals and change.</p>

                    <div class=\"card\">
                        <h2 class=\"section-title\">Common Change Amounts (Standard $6 boxes)</h2>
                        {standard_change_df.to_html(index=False, border=0)}
                        <p class=\"note\">Example: Customer gives $20 for 1 box, change is $14.</p>
                    </div>

                    <div class=\"card\">
                        <h2 class=\"section-title\">Toffee-Tastic ($7 each)</h2>
                        {tt_totals.to_html(index=False, border=0)}
                    </div>

                    <div class=\"card\">
                        <h2 class=\"section-title\">Common Change Amounts (Toffee-Tastic $7 boxes)</h2>
                        {tt_change_df.to_html(index=False, border=0)}
                    </div>
                </div>
            </body>
        </html>
        """

        st.download_button(
            label="🖨️ Download & Print Cookie Math",
            data=cookie_math_html,
            file_name="cookie_math_printable.html",
            mime="text/html",
            help="Downloads just the Cookie Math sheet with print-friendly formatting."
        )
        st.caption("Open the downloaded HTML in your browser and print.")
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