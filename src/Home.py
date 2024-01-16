from json import loads
import streamlit as st
from streamlit_calendar import calendar
# from streamlit_searchbox import st_searchbox
from typing import List, Tuple
import pandas as pd
from elasticsearch import Elasticsearch  # need to also install with pip3
import sys
from pathlib import Path
# from PIL import Image
import os
from datetime import datetime

# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)
environment = os.getenv('ENV')

print(f'The folder contents are: {os.listdir()}\n')

# if environment in ('None', None, 'local'):
#     p = Path.cwd()
#     if p.parts[-1] != 'src':
#         os.chdir('src')
#     print(f"Now... the current directory: {Path.cwd()}")
from utils import esutils as eu


print(os.getcwd())

# es = Elasticsearch("http://localhost:9200")

# @st.cache_data
es = eu.esu.conn_es()
# es = conn_es()

# resp = es.get(index="test-index", id=1)
# print(resp["_source"])

# es.indices.refresh(index="test-index")

# resp = es.search(index="test-index", query={"match_all": {}})
# print("Got {} hits:".format(resp["hits"]["total"]["value"]))
# for hit in resp["hits"]["hits"]:
#     print("{timestamp} {author} {text}".format(**hit["_source"]))

# doc = {
#     "author": "kimchy",
#     "text": "Elasticsearch: cool. bonsai cool.",
#     "timestamp": datetime.now(),
# }

# Add parent path to system path so streamlit can find css & config toml
# sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')


# {'name': 'instance-0000000000', 'cluster_name': ...

########## Streamlit Configuration ##########
# Some Basic Configuration for StreamLit - Must be the first streamlit command

st.set_page_config(
    page_title="Troop 43202 Cookies",
    page_icon="samoas.jpg",
    layout="wide",
    # initial_sidebar_state="collapsed"
)

# SA frorm streamlit cloud to sa account


#---------------------------------------
# Functions
def local_css(file_name):
    with open(f'{file_name}') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css('style.css')

def get_my_data(fileNm, gsNm=None):
    gsDat = pd.read_csv(fileNm)
    gsDat.dropna(axis=1,how='all',inplace=True)
    gsDat.dropna(axis=0,how='all',inplace=True)

    if gsNm:
        gsDat = gsDat[gsDat['gsName'] == gsNm]
    return gsDat

# def get_dat(fileNm):
#     gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)
#     # pass
#     return gsDatR


############ DATA CONNECTION ##############
# conn = st.connection("gsheets", type=GSheetsConnection)
# conn = st.connection('gcs', type=FilesConnection)

# ebudde = get_dat('ebudde')

# pickupSlots = get_dat('pickupSlots')

# st.table(ebudde)
# ebudde.columns
# gs_nms = ebudde['Girl']

## square app tracking -

# Megan
# Madeline Knudsvig - Troop 44044

############ ORDERS ###############

st.title("GS Troop 43202 Cookie Tracker")
st.write('')

st.header('Important Dates, Reminders and Links')
st.write('REMINDER: You have 5 days in digital cookie to approve all orders\n')


calendar_options = {
    "editable": "false",
    "navLinks": "false",
    "selectable": "false",
    "initialDate": "2024-01-01",
            # "end": "2024-04-01",
    "initialView": "gridMonth"
}

calendar_events = [
        {
        "title": "Digital Cookie Emails to Volunteers",
        "start": "2024-01-15"
        # "backgroundColor": '#FF6C6C'
    },
    {
        "title": "In-Person Sales Begin",
        "start": "2024-01-19",
        "backgroundColor": '#FF6C6C'
    },
    {
        "title": "Initial Orders",
        "start": "2024-01-19",
        "end": "2024-02-04",
        "backgroundColor": '#FF6C6C'
    },
    {
        "title": "Booth Sales",
        "start": "2024-02-16",
        "end": "2024-03-16",
        "backgroundColor": '#FF6C6C'
    },
    {
        "title": "Family deadline for turning in Cookie Money",
        "start": "2024-03-19",
        "backgroundColor": '#FF6C6C'
    },
]
custom_css="""
    .fc-event-past {
        opacity: 0.8;
    }
    .fc-event-time {
        font-style: italic;
    }
    .fc-event-title {
        font-weight: 500;
    }
    .fc-toolbar-title {
        font-size: .7rem;
    }
    .fc-
"""

calendar = calendar(events=calendar_events, options=calendar_options, custom_css=custom_css)
st.write(calendar)

st.write('12/7: Volunteer eBudde access')
st.write('1/15: Primary caregivers receive Digital Cookie Registration email')
st.write('1/19: 2024 Cookie Program Launch')
st.write('1/19-2/4: Initial Orders')
st.write('2/4 - 3/11: In person Delivery of Digital Cookie Orders')
st.write('~2/9: Pick up cookies from cookie cupboard - Volutneers Needed')
st.write('1/30: Booth site picks begin at 6:30 pm')
st.write('2/4: Girl Scout inital orders due to Troop')
st.write('2/16-3/16: Booth Sales')
st.write('3/19: Family deadline for turning in Cookie Money')
st.write('3/22: Troop wrap-up deadline')



# with myorders:
