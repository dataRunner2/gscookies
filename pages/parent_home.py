from json import loads
import streamlit as st
from streamlit import session_state as ss,  data_editor as de, rerun as rr
# from streamlit_calendar import calendar
import streamlit.components.v1 as components
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
import time
from typing import List, Tuple
import pandas as pd
from pathlib import Path
from datetime import datetime
import base64

# import eland as ed
from utils.esutils import esu
from utils.app_utils import apputils as au, setup 
from elasticsearch import Elasticsearch  # need to also install with pip3


# Add parent path to system path so streamlit can find css & config toml
# sys.path.append(str(Path(__file__).resolve().parent.parent))
print(f'\n\n{"="*30}\n{Path().absolute()}\n{"="*30}\n')

# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# # https://docs.google.com/spreadsheets/d/1-Hl4peFJjdvpXkvoPN6eEsDoljCoIFLO/edit#gid=921650825 # parent forms
# gsDatR = conn.read(f"cookiedat43202/{fileNm}.csv", input_format="csv", ttl=600)

# print(f'The folder contents are: {os.listdir()}\n')
# print(f"Now... the current directory: {Path.cwd()}")
# from utils.mplcal import MplCalendar as mc

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

def init_ss():
    if 'authenticated' not in ss:
        ss.authenticated = False
        # if 'gsNm' not in st.session_state:
        # st.session_state['gsNm'] = gs_nms.index('zz scout not selected')
    if 'guardianNm' not in st.session_state:
        st.session_state['guardianNm'] = 'scout parent'
    if 'adminpassword_correct' not in st.session_state:
        st.session_state['adminpassword_correct'] = False
    if "scout_dat" not in st.session_state:
        st.session_state['scout_dat'] = False
    if "edited_dat" not in st.session_state:
        st.session_state['edited_dat'] = {}

# @st.cache_data
def get_connected():
    es = esu.conn_es()
    st.write(es.info())
    return es
#---------------------------------------
# Password Configuration
#---------------------------------------

## square app tracking -

# Megan
# Madeline Knudsvig - Troop 44044

def move_column_inplace(df, col, pos):
    col = df.pop(col)
    df.insert(pos, col.name, col)


def update_session(gs_nms):
    # st.write(f'gs_nm:{gs_nm}; gsNmkey: {st.session_state["gsNm"]}')
    time.sleep(1)
    scout_dat = esu.get_qry_dat(es,indexnm=ss.index_scouts,field='FullName',value=st.session_state["gsNm"])

    if len(scout_dat) > 0 and type('str'):
        sc_fn = scout_dat[0].get("_source").get("FullName")
        # st.subheader(f'Submit a Cookie Order for {sc_fn}')
        parent = scout_dat[0]['_source']['Parent']
        st.session_state["guardianNm"] = parent
        st.session_state["scout_dat"] = scout_dat[0]['_source']
    else:
        st.write('Scout Parent information not updated - please contact Jennifer')
        print(scout_dat)


def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns
    Args:
        df (pd.DataFrame): Original dataframe
    Returns   pd.DataFrame: Filtered dataframe
    """
    # modify = st.checkbox("Add filters")

    # if not modify:
    #     return df

    df = df.copy()
    modification_container = st.container()
    with modification_container:
        to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("↳")
            # Treat columns with < 10 unique values as categorical
            if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = (df[column].min())
                _max = (df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                f"Values for {column}",
                min_value=_min,
                max_value=_max,
                value=(_min, _max),
                step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring or regex in {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]
        df.loc['Total']= df.sum(numeric_only=True, axis=0)
    return df

#---------------------------------------
# Page Functions
#---------------------------------------
    def general_info():
        st.write('----')
        # Calendar
        st.header('Important Dates, Links and Reminders')
        st.subheader('Reminders')
        st.warning("!! You will continue to use this app to submit orders to us through 3/17 !!")
        st.markdown("""
                    A few reminders:
                    - Cookies are $6 per box. There's no Raspberry Rally this year, but the rest of the lineup is the same!
                    - Consider setting up a QR code to link to your Girl Scout's site!
                    - Do not give out your personally identifiable information, such as last name or school, but remember that Promise and Law!
                    - You will need to wear your uniform when you sell, you are representing your family and your organization!
                    - All in-person orders collected on digital cookie will need to be approved by the parent. After a few days, orders not approved will be automatically rejected and will not count towards sales.
                    - We are participating in Operation Cookie Drop, which donates boxes to the USO to distribute to service members. These donations will count in increments of $6 as a box your Girl Scout sold, but you will not have physical boxes for these donations. The boxes will be handled at the end of the sale at the Council level.
                    - You have 5 days in digital cookie to approve all orders
                    - Monitor your digital cookie orders - submit your orders to us via this site as frequently as you would like
                    - Have fun with it - this is what you make it!
                    """)
        # jan = mc(2024,1)
        # feb = mc(2024,2)
        # mar = mc(2024,3)
        # jan.add_event(15, "Digital Cookie Emails to Volunteers")
        # jan.add_event(19,"In-person Sales Begin")
        # feb.add_event(4,"Initial Orders Submitted")
        # feb.add_event(16,"Booth Sales")
        # mar.add_event(19,"Family deadline for turning in Cookie Money")
        # st.pyplot(fig=jan)

        st.subheader('Important Dates')
        st.write('2/25 - 3/16: In person Delivery of Digital Cookie Orders')
        st.write('3/1 - 3/16: Booth Sales - Sign up on Band')
        st.write('3/19: Family deadline for turning in Cookie Money by 12 Noon')
        st.write('3/22: Troop wrap-up deadline')

    def girl_orders():
        noscouti=gs_nms.index('zz scout not selected')
        if 'gsNm' not in ss:
            st.session_state['gsNm'] = gs_nms[noscouti]
            update_session(gs_nms)
            rr()
        noscout = gs_nms[noscouti]

        # selection box can not default to none because the form defaults will fail. 
        gsNm = st.selectbox("Select Girl Scount:", gs_nms, index=noscouti, key='gsNm', on_change=update_session(gs_nms))
        # st.write('----')
        orderck, summary = st.tabs(['Order Cookies','Summary of Orders'])

        with orderck:
            # st.write('----')
            if gsNm == st.session_state["scout_dat"]["FullName"]:
                st.markdown(f"Ready to submit a Cookie Order for {gsNm}❄️")

            with st.form('submit orders', clear_on_submit=True):
                appc1, appc2, appc3 = st.columns([3,.25,3])
                guardianNm = st.write(f'Guardian accountable for order: {st.session_state["guardianNm"]}')
                with appc1:
                    # At this point the URL query string is empty / unchanged, even with data in the text field.
                    ordType = st.selectbox("Order Type (Submit seperate orders for paper orders vs. Digital Cookie):",options=['Digital Cookie','Paper Order'],key='ordType')
                    pickupT = st.selectbox('Pickup Slot', ['Tues Feb 27 9-12','Wed Feb 28 10-4:30','Thurs Feb 29 10am-5:30pm','Fri Mar 1 10am-8:30pm','Sat Mar 2 10am-4:30pm','Mon Mar 4 10am-4:30pm','Tues Mar 5 10am-4:30pm','Mon Mar 6 10am-4:30pm','Mon Mar 7 10am-8:30pm'])

                with appc3:
                    PickupNm = st.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
                    PickupPh = st.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)

                st.write('----')
                ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])

                with ck1:
                    advf=st.number_input(label='Adventurefuls',step=1,min_value=-5, value=0)
                    tags=st.number_input(label='Tagalongs',step=1,min_value=-5, value=0)

                with ck2:
                    lmup=st.number_input(label='Lemon-Ups',step=1,min_value=-5, value=0)
                    tmint=st.number_input(label='Thin Mints',step=1,min_value=-5, value=0)
                with ck3:
                    tre=st.number_input(label='Trefoils',step=1,min_value=-5, value=0)
                    smr=st.number_input(label="S'Mores",step=1,min_value=-5, value=0)

                with ck4:
                    dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=-5, value=0)
                    toff=st.number_input(label='Toffee-Tastic',step=1,min_value=-5, value=0)

                with ck5:
                    sam=st.number_input(label='Samoas',step=1,min_value=-5, value=0)
                    opc=st.number_input(label='Operation Cookie Drop',step=1,min_value=-5, value=0)

                comments = st.text_area("Note to us or your ref comment", key='comments')


                # submitted = st.form_submit_button()
                if st.form_submit_button("Submit Order to Cookie Crew"):
                    total_boxes, order_amount=calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
                    now = datetime.now()
                    idTime = now.strftime("%m%d%Y%H%M")
                    # st.write(idTime)
                    orderId = (f'{st.session_state["scout_dat"]["Concat"].replace(" ","").replace(".","_").lower()}{idTime}')
                    # Every form must have a submit button.
                    order_data = {
                        "ScoutName": st.session_state["scout_dat"]["FullName"],
                        "OrderType": ordType,
                        "guardianNm":st.session_state["guardianNm"],
                        "guardianPh":st.session_state["scout_dat"]["Phone"],
                        "Email":st.session_state["scout_dat"]["Email"],
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
                        "comments": comments,
                        "status": "Pending",
                        "order_id": orderId,
                        "digC_val": False,
                        "addEbudde": False,
                        "order_pickedup": False,
                        "order_ready": False
                        }
                    st.text(f" {total_boxes} boxes were submitted\n Total amount owed for order = ${order_amount} \n your pickup slot is: {pickupT}")        # get latest push of orders:

                    esu.add_es_doc(es,indexnm=ss.index_orders, id=orderId, doc=order_data)

                    k=order_data.keys()
                    v=order_data.values()
                    # st.write(k)
                    # new_order = [f"{k}:[{i}]" for k,i in zip(order_data.keys(),order_data.values())]
                    order_details = pd.DataFrame(v, index =k, columns =['Order'])
                    new_order = order_view(order_details.T)
                    st.table(new_order.T)
                    st.success('Your order has been submitted!', icon="✅")
                    st.balloons()

        # def myorders(gs_nms):
        with summary:
            st.write('----')
            if gsNm == st.session_state["scout_dat"]["FullName"]:
                st.markdown(f"{gsNm} Cookie Order Summary")
            # if 'index' not in st.session_state:
            #     st.session_state['index'] = len(gs_nms)
            # st.write(st.session_state['gsNm'])
            # gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout', index=st.session_state['index'], key='gsNm')

            # st.subheader("All submited orders into this app's order form")
            all_orders, all_orders_cln = get_all_orders()
            all_orders.reset_index(names="index",inplace=True,drop=True)
            girl_orders = all_orders[all_orders['ScoutName'] == gsNm]
            girl_orders.sort_values(by=['OrderType','submit_dt'],ascending=[False, True], inplace=True)

            girl_orders = order_view(girl_orders)
            girl_orders.reset_index(inplace=True, drop=True)
            girl_orders.fillna(0)
            girl_ord_md=girl_orders[['Scouts Name','Order Type','Date','status','Comments']]

            just_cookies = girl_orders[['Adventurefuls','Lemon-Ups','Trefoils','Do-Si-Do','Samoas',"S'Mores",'Tagalongs','Thin Mint','Toffee Tastic','Operation Cookies']]
            just_cookies['Qty']= just_cookies.sum(axis=1)
            just_cookies['Amt']=just_cookies['Qty']*6
            col = just_cookies.pop('Qty')
            just_cookies.insert(0, col.name, col)
            col = just_cookies.pop('Amt')
            just_cookies.insert(0, col.name, col)
            cookie_orders = pd.concat([girl_ord_md, just_cookies], axis=1)
            # st.write(cookie_orders)

            st.write("Paper Orders")
            paper_orders = cookie_orders[cookie_orders['Order Type']=='Paper Order'].copy()
            paper_orders.pop('status')
            paper_orders.loc['Total']= paper_orders.sum(numeric_only=True, axis=0)
            paper_orders = paper_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','Operation Cookies':'int64'})

            st.dataframe(paper_orders.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))), use_container_width=True,
                        column_config={
                            "Amount": st.column_config.NumberColumn(
                                "Amt.",
                                format="$%d",
                            ),
                            "Date": st.column_config.DateColumn(
                                "Order Date",
                                format="MM-DD-YY",
                            )})
            total_due_po = paper_orders.loc['Total','Amt']

            st.write("Digital Orders")
            digital_orders = cookie_orders[cookie_orders['Order Type']=='Digital Cookie'].copy()
            digital_orders.loc['Total']= digital_orders.sum(numeric_only=True, axis=0)
            digital_orders.pop('status')
            digital_orders = digital_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','Operation Cookies':'int64'})
            st.dataframe(digital_orders.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))), use_container_width=True,
                        column_config={
                            "Amt": st.column_config.NumberColumn(
                                "Order Amt.",
                                format="$%d",
                            )})

            # metrics
            st.write('----')
            # girl_money = esu.get_dat(es,indexnm=ss.index_money)
            # girl_money = ed.DataFrame(es, es_index_pattern = index_money) #=ss.index_money)
            # girl_money = ed.eland_to_pandas(girl_money)
            girl_money = pd.DataFrame()
            # girl_money = pd.DataFrame(girl_money)

            tot_boxes_pending = cookie_orders[cookie_orders['status']=='Pending'].copy()
            tot_boxes_pending = tot_boxes_pending[['status','Qty']]
            tot_boxes_pending.loc['Total']= tot_boxes_pending.sum(numeric_only=True, axis=0)
            total_pending = tot_boxes_pending.loc['Total','Qty'].astype('int')

            tot_boxes_ready = cookie_orders[cookie_orders['status']=='Order Ready for Pickup'].copy()
            tot_boxes_ready = tot_boxes_ready[['status','Qty']]
            tot_boxes_ready.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
            total_ready = tot_boxes_ready.loc['Total','Qty'].astype('int')

            # tot_boxes = girl_orders[girl_orders['status']=='Order Ready for Pickup'].copy()
            tot_boxes = girl_orders[['status','Qty']]
            tot_boxes.loc['Total']= tot_boxes_ready.sum(numeric_only=True, axis=0)
            total_boxes = tot_boxes_ready.loc['Total','Qty'].astype('int')


            mc1, mc2,mc3,mc4,mc5 = st.columns([2,2,2,2,2])
            girl_money = girl_money[girl_money['ScoutName'] == st.session_state['gsNm']]
            # st.write(dtype(girl_money['AmountReceived']))
            girl_money["AmountReceived"] = pd.to_numeric(girl_money["AmountReceived"])
            sum_money = girl_money['AmountReceived'].sum()
            with mc1: st.metric(label="Total Amount Received", value=f"${sum_money}")
            with mc2: st.metric(label="Total Due for Paper Orders", value=f"${total_due_po}")
            with mc3: st.metric(label='Pending Boxes', value=total_pending)
            with mc4: st.metric(label='Boxes Ready for Pickup', value=total_ready)
            with mc5: st.metric(label="Total Boxes",value=total_boxes)
            # st.metric(label="Total Amount Due for Paper Orders", value=f"${paper_money_due}")

            st.subheader("Payments Received - EXCLUDING DIGITAL COOKIE")
            girl_money.sort_values(by="amtReceived_dt")
            girl_money.rename(inplace=True, columns={'ScoutName': 'Scouts Name','AmountReceived':'Amount Received','amtReceived_dt': 'Date Money Received','orderRef':'Money Reference Note'})
            girl_money.reset_index(inplace=True, drop=True)
            st.dataframe(girl_money,use_container_width=False)

    def dcInstructions():
        def displayPDF(file):
            # Opening file from file path
            with open(file, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')

            # Embedding PDF in HTML
            pdf_display =  f"""<embed
            class="pdfobject"
            type="application/pdf"
            title="Embedded PDF"
            src="data:application/pdf;base64,{base64_pdf}"
            style="overflow: auto; width: 100%; height: 1000px;">"""

            # Displaying File
            st.markdown(pdf_display, unsafe_allow_html=True)
        displayPDF('how-to-DigitalCookie.pdf')

#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    st.session_state
    # @st.cache_data
    es=get_connected()

    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page.")
        st.page_link("./Home.py",label='Login')
        st.stop()

    
    st.write(ss.gs_nms)

    st.write('----')
    # Calendar
    st.header('Important Dates, Links and Reminders')
    st.subheader('Reminders')
    st.warning("!! You will continue to use this app to submit orders to us through 3/17 !!")
    st.markdown("""
                A few reminders:
                - Cookies are $6 per box. There's no Raspberry Rally this year, but the rest of the lineup is the same!
                - Consider setting up a QR code to link to your Girl Scout's site!
                - Do not give out your personally identifiable information, such as last name or school, but remember that Promise and Law!
                - You will need to wear your uniform when you sell, you are representing your family and your organization!
                - All in-person orders collected on digital cookie will need to be approved by the parent. After a few days, orders not approved will be automatically rejected and will not count towards sales.
                - We are participating in Operation Cookie Drop, which donates boxes to the USO to distribute to service members. These donations will count in increments of $6 as a box your Girl Scout sold, but you will not have physical boxes for these donations. The boxes will be handled at the end of the sale at the Council level.
                - You have 5 days in digital cookie to approve all orders
                - Monitor your digital cookie orders - submit your orders to us via this site as frequently as you would like
                - Have fun with it - this is what you make it!
                """)
    # jan = mc(2024,1)
    # feb = mc(2024,2)
    # mar = mc(2024,3)
    # jan.add_event(15, "Digital Cookie Emails to Volunteers")
    # jan.add_event(19,"In-person Sales Begin")
    # feb.add_event(4,"Initial Orders Submitted")
    # feb.add_event(16,"Booth Sales")
    # mar.add_event(19,"Family deadline for turning in Cookie Money")
    # st.pyplot(fig=jan)

    st.subheader('Important Dates')
    st.write('2/25 - 3/16: In person Delivery of Digital Cookie Orders')
    st.write('3/1 - 3/16: Booth Sales - Sign up on Band')
    st.write('3/19: Family deadline for turning in Cookie Money by 12 Noon')
    st.write('3/22: Troop wrap-up deadline')

    # st.write(gs_nms)
    # page_names_to_funcs = {
    #             "Dates and Links": general_info,
    #             "Order Cookies 🍪": girl_orders,
    #             # "Digital Cookie Instructions": dcInstructions
    #         }
    topc1, topc2 = st.columns([3,7])
    with topc1:
        pass
        # selected_page = st.selectbox("----", page_names_to_funcs.keys())
    with topc2:
        bandurl = "https://band.us/band/93124235"
        st.info("Connect with us on [Band](%s) if you have any questions" % bandurl)
        st.warning("Note - All Cookie Money Due 3/19")
    # page_names_to_funcs[selected_page]()


    # selected_page = st.sidebar.selectbox("----", page_names_to_funcs.keys())
    # page_names_to_funcs[selected_page]()

    # st.sidebar.markdown(st.session_state)


if __name__ == '__main__':

    setup.config_site(page_title="Cookie Portal")
    # Initialization
    init_ss()
    main()