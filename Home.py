from json import loads
import streamlit as st
from streamlit_calendar import calendar
# import streamlit_permalink as st.

from typing import List, Tuple
import pandas as pd
from elasticsearch import Elasticsearch  # need to also install with pip3
import sys
from pathlib import Path
import hmac
import os
import eland as ed
from datetime import datetime
from utils.esutils import esu

# Add parent path to system path so streamlit can find css & config toml
# sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')

# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)

environment = os.getenv('ENV')

# print(f'The folder contents are: {os.listdir()}\n')
# print(f"Now... the current directory: {Path.cwd()}")
# from utils.mplcal import MplCalendar as mc

# @st.cache_data
es = esu.conn_es()

gs_nms = esu.get_dat(es,"scouts", "FullName")
#---------------------------------------
# LOADS THE SCOUT NAME, ADDRESS, PARENT AND REWARD INFO to Elastic
# Uncomment and re-do if changes to sheet
#---------------------------------------
# conn = st.connection("gsinfo", type=GSheetsConnection)
# df = conn.read()
# df.dropna(axis=1,how="all",inplace=True)
# df.dropna(axis=0,how="all",inplace=True)
# df.reset_index(inplace=True,drop=True)
# df.rename(columns={"Unnamed: 6":"Address"},inplace=True)
# df['FullName'] = [f"{f} {l}" for f,l in zip(df['First'],df['Last'])]

# df = df.fillna('None')
# type(df)

# ed.pandas_to_eland(pd_df = df, es_client=es,  es_dest_index='scouts', es_if_exists="replace", es_refresh=True) # index field 'H' as text not keyword

# # SLOW
# # for i,row in df.iterrows():
# #     rowdat = json.dupmp
# #     esu.add_es_doc(es,indexnm='scouts', doc=row)

#---------------------------------------
# Streamlit Configuration
#---------------------------------------
def main():
    # container = st.container()
    # Some Basic Configuration for StreamLit - Must be the first streamlit command


    def local_css(file_name):
        with open(f'{file_name}') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    local_css('style.css')

    #---------------------------------------
    # Password Configuration
    #---------------------------------------

    ## square app tracking -

    # Megan
    # Madeline Knudsvig - Troop 44044

    def check_password():
        """Returns `True` if the user had the correct password."""

        def password_entered():
            """Checks whether a password entered by the user is correct."""
            if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # Don't store the password.
            elif hmac.compare_digest(st.session_state["password"], st.secrets["adminpassword"]):
                st.session_state["adminpassword_correct"] = True
                del st.session_state["password"]  # Don't store the password.
            else:
                st.session_state["password_correct"] = False
                st.session_state["adminpassword_correct"] = False

        # Return True if the password is validated.
        if st.session_state.get("password_correct", False):
            return True
        elif st.session_state.get("adminpassword_correct",False):
            return True

        # Show input for password.
        st.text_input("Who is our leader (capitilized, 5 letters)", type="password", on_change=password_entered, key="password")

        if "password_correct" in st.session_state:
            st.error("😕 Password incorrect")
            st.session_state.get("password_correct",False)
        return False

    if not check_password():
        st.stop()  # Do not continue if check_password is not True.


    #---------------------------------------
    # Functions
    #---------------------------------------

    def clean_df(df):
        # st.write(df.columns)
        df=df.loc[:, ['ScoutName','OrderType','submit_dt','order_id','status','PickupT','order_qty_boxes', 'order_amount','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','PickupNm','PickupPh']]
        df.rename(columns={'order_id':'Order Id','ScoutName':'Scouts Name','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Do','Sam':'Samoas','Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic','OpC':'Operation Cookies'},inplace=True)
        return df

    def calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc):
        total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
        total_money = total_boxes*6
        return total_boxes, total_money


    def update_session(gs_nms):
        # Update index to be the index just selected

        st.session_state["index"] = gs_nms.index(st.session_state["gsNm"])
        st.session_state["updatedindex"] = gs_nms.index(st.session_state["gsNm"])

        # Update the scout data (i.e. parent) to be the name just selected
        scout_dat = esu.get_qry_dat(es,indexnm="scouts",field='FullName',value=st.session_state["gsNm"])
        if len(scout_dat) > 0:
            parent = scout_dat[0]['_source']['Parent']
            st.session_state["guardianNm"] = parent
            # container.header(st.session_state["gsNm"])
            st.session_state["scout_dat"] = scout_dat[0]['_source']


    #---------------------------------------
    # Select GS Name
    #---------------------------------------


    def main_page():
        # st.markdown("# Main page 🎈")
        # st.sidebar.markdown("# Home 🎈")

        #---------------------------------------
        # Calendar
        #---------------------------------------

        st.title("GS Troop 43202 Cookie Tracker")
        st.write('')

        # jan = mc(2024,1)
        # feb = mc(2024,2)
        # mar = mc(2024,3)
        # jan.add_event(15, "Digital Cookie Emails to Volunteers")
        # jan.add_event(19,"In-person Sales Begin")
        # feb.add_event(4,"Initial Orders Submitted")
        # feb.add_event(16,"Booth Sales")
        # mar.add_event(19,"Family deadline for turning in Cookie Money")
        # st.pyplot(fig=jan)

        st.header('Important Dates')
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

        st.subheader('Reminders')
        st.write('- You have 5 days in digital cookie to approve all orders\n')
        st.write('- Monitor your digital cookie orders - submit your orders to us as frequently as you would like')

    def order():
        # st.markdown(f"Submit a Cookie Order for {gsNm}❄️")
        # st.sidebar.markdown("# Order Cookies ❄️")
        # st.session_state['index'] = nmIndex

        st.subheader(f'Submit a Cookie Order for {st.session_state["gsNm"]}')
        st.warning('Submit seperate orders for paper orders vs. Digital Cookie\n')
        gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout',index=st.session_state['index'], key='gsNm', on_change=update_session(gs_nms))

        with st.form('submit orders', clear_on_submit=True):
            appc1, appc2, appc3 = st.columns([3,.25,3])

            with appc1:
                # At this point the URL query string is empty / unchanged, even with data in the text field.
                ordType = st.selectbox("Order Type:",options=['Digital Cookie','Paper Order'],key='ordType')
                guardianNm = st.write(f'Guardian accountable for order: {st.session_state["guardianNm"]}')


            with appc3:
                PickupNm = st.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
                PickupPh = st.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)
                pickupT = st.selectbox('Pickup Slot',['Tuesday 5-7','Wednesday 6-9'])

            st.write('----')
            ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])

            with ck1:
                advf=st.number_input(label='Adventurefuls',step=1,min_value=0)
                tags=st.number_input(label='Tagalongs',step=1,min_value=0)

            with ck2:
                lmup=st.number_input(label='Lemon-Ups',step=1,min_value=0)
                tmint=st.number_input(label='Thin Mints',step=1,min_value=0)
            with ck3:
                tre=st.number_input(label='Trefoils',step=1,min_value=0)
                smr=st.number_input(label="S'Mores",step=1,min_value=0)

            with ck4:
                dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=0)
                toff=st.number_input(label='Toffee-Tastic',step=1,min_value=0)

            with ck5:
                sam=st.number_input(label='Samoas',step=1,min_value=0)
                opc=st.number_input(label='Operation Cookie Drop',step=1,min_value=0)

            comments = st.text_area("Comments", key='comments')


            # submitted = st.form_submit_button()
            if st.form_submit_button("Submit Order to Cookie Crew"):
                total_boxes, order_amount=calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
                now = datetime.now()
                idTime = now.strftime("%m%d%Y%H%M")
                # st.write(idTime)
                orderId = (f'{st.session_state["scout_dat"]["Concat"].replace(" ","").replace(".","_").lower()}_{idTime}')
                # Every form must have a submit button.
                order_data = {
                    "ScoutName": gsNm,
                    "OrderType": ordType,
                    "guardianNm":st.session_state["guardianNm"],
                    "PickupNm": PickupNm,
                    "PickupPh": PickupPh,
                    "PickupT": pickupT ,
                    "Adf": advf,
                    "LmUp": lmup,
                    "Tre": tre,
                    "DSD": dsd,
                    "Sam": sam,
                    "Tags": tags,
                    "Tmint": tmint,
                    "Smr": smr,
                    "Toff": toff,
                    "OpC": opc,
                    "order_qty_boxes": total_boxes,
                    "order_amount": order_amount,
                    "submit_dt": datetime.now(),
                    "status": "Pending",
                    "order_id": orderId
                    }
                st.text(f" {total_boxes} boxes were submitted for {gsNm}'s order\n Total amount owed for order = ${order_amount} \n your pickup slot is: {pickupT}")        # get latest push of orders:
                
                esu.add_es_doc(es,indexnm="orders2024", doc=order_data)

                k=order_data.keys()
                v=order_data.values()
                st.write(k)
                # new_order = [f"{k}:[{i}]" for k,i in zip(order_data.keys(),order_data.values())]
                order_details = pd.DataFrame(v, index =k, columns =['Order'])
                new_order = clean_df(order_details.T)
                st.table(new_order.T)
                st.success('Your order has been submitted!', icon="✅")
                st.balloons()

    def myorders():
        # st.session_state['index'] = nmIndex

        gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout', index=st.session_state['index'], key='gsNm', on_change=update_session(gs_nms))

        girl_orders = ed.DataFrame(es, es_index_pattern="orders2024")
        girl_orders = ed.eland_to_pandas(girl_orders)
        girl_orders.reset_index(inplace=True, names='docId')
        girl_orders = girl_orders[girl_orders['ScoutName'] == st.session_state["gsNm"]]
        # orders.set_index(keys=['appName'],inplace=True)

        # girl_orders = get_qry_dat(es,"orders2024",field='ScoutName',value=gsNm)
        girl_orders = clean_df(girl_orders)
        st.dataframe(girl_orders, use_container_width=True)

    def allorders():
        orders = ed.DataFrame(es, es_index_pattern="orders2024")
        orders = ed.eland_to_pandas(orders)
        orders.reset_index(inplace=True, names='docId')
        # orders.set_index(keys=['appName'],inplace=True)
        ordersDF = loads(orders.to_json(orient='index'))
        ds_app_names = list(ordersDF.keys())
        st.dataframe(orders)
    def booths():
        st.write("this page is in work... come back later")

    if st.session_state["adminpassword_correct"]:
        page_names_to_funcs = {
            "Dates and Links": main_page,
            "Order Cookies": order,
            "My Orders": myorders,
            "Booths": booths,
            "All Orders": allorders,
            
        }


    elif st.session_state["password_correct"]:
            page_names_to_funcs = {
            "Dates and Links": main_page,
            "Orders": order,
            "My Orders": myorders,
            "Booths": booths
        }

    st.sidebar.markdown("Select Page")
    selected_page = st.sidebar.selectbox("----", page_names_to_funcs.keys())
    page_names_to_funcs[selected_page]()

    # st.sidebar.markdown(st.session_state)


if __name__ == '__main__':

    st.set_page_config(
        page_title="Troop 43202 Cookies",
        page_icon="samoas.jpg",
        layout="wide",
        # initial_sidebar_state="collapsed"
    )
    # Initialization
    if 'index' not in st.session_state:
        st.session_state['index'] = 47
    if 'gsNm' not in st.session_state:
        st.session_state['gsNm'] = gs_nms[st.session_state['index']]
    if 'guardianNm' not in st.session_state:
        st.session_state['guardianNm'] = 'scout parent'
    if 'adminpassword_correct' not in st.session_state:
        st.session_state['adminpassword_correct'] = False
    if "scout_dat" not in st.session_state:
        st.session_state['scout_dat'] = False

    main()