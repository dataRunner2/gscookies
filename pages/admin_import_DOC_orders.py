from json import loads
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import json
from datetime import datetime
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3

def init_ss():
    pass

def main():
    pass

if __name__ == '__main__':

    setup.config_site(page_title="Session State",initial_sidebar_state='expanded')
    main()