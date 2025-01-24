from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd

from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3

def init_ss():
    pass

def main():
    st.subheader('Acronyms & Definations')
    st.markdown("""
        - Digital Cookie (DC): Digital cookie is the scouts personalized point of sale website. They can share their cookie story, set their cookie goals and create a personalized QR code to take credit card orders. 
        - Troop Cookie Tracker: This website - which is used for families to submit their delivery orders to our troop cupboard which is how we know you need cookies. 
        - Girl Delivery Digital Cookies (DOC): Digtial cookie orders that families have agreed to deliver instead of have shipped.
        
        Cookie Acronyms
        - Adv: Adventurefuls
        - DD: Do-Si-Dos
        - TM: Thin Mints
        - LU: Lemon Ups
        - TF: Trefoils
        - SAM: Samoas
        - Tags: Tagalongs
        - Smr: S’mores
        - TT:Toffee-tastic
        - OpC: Operation Cookie Donation
    """)
    st.subheader("Marketing")
    st.markdown('[Little Brownie Bakers Marketing Materials](https://www.littlebrowniebakers.com/ThemeGraphics)')
    st.write("It’s fun for kids to make signs to bring to their booths. This gives them a chance to learn about marketing.")

    st.subheader("Booths")
    st.markdown("""
        - Booth Requests – tell us via band which locations you’d like us to request if outside our usual spot
        - Booth Kit Pickup
        - Booth Safety
            - Parent must always hold money
            - Do not set out “Donation” bin, they have been getting stolen
            - Girls must wear uniform
            - Please download the Square POS app & set it up before booths start
        - Arrive at our troop cupboard in time to collect cookies, supplies and then get to the booth by start time. We can lose the spot if we are not on time.  It is recommended to arrive at the cupboard an hour and 15 minutes before cookie booth start time. 
        - When you arrive at the cupboard you will receive: 
            - cookies
            - money bag with starting cash
            - if your booth allows, a folding table
            - credit card reader (more on this below)
            - tracking sheet
        - During/Immediatly after the sale you/scouts will complete the inventory tracking sheet:
            - There are several calculations:
        """)
    st.latex('''Starting.cookies.by.type - sold.cookies.by.type = returned.cookies''')
    st.latex('''sold.cookies.total * 6 = total.cash.from.sales''')
    st.latex('''Ending.Cash  - total.cash.from.sales - begining.cash = donations.cash''')

    st.markdown("""
        - After your booth you’ll return all the supplies within 30 min (if your booth is further away let the cookie crew know when you can get back). We have limited tables, so we need to do a quick turn on those. 
            - We will do a "booth checkin" to count money, cookies and return supplies
        """
    )
if __name__ == '__main__':

    setup.config_site(page_title="Training Reference",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()