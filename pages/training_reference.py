from json import loads
import streamlit as st
from streamlit import session_state as ss
# from streamlit_calendar import calendar
import time
from typing import List, Tuple
import pandas as pd
import random
from pathlib import Path

import os
from datetime import datetime
from utils.esutils import esu
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


if __name__ == '__main__':

    setup.config_site(page_title="Training Reference",initial_sidebar_state='expanded')
    # Initialization
    init_ss()

    main()