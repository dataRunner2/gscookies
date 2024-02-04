from json import loads
import streamlit as st
from streamlit_calendar import calendar
# import streamlit_permalink as st.
import time
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
import base64

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
    # Password Configuration
    #---------------------------------------

    ## square app tracking -

    # Megan
    # Madeline Knudsvig - Troop 44044
#---------------------------------------
# Main App Configuration
#---------------------------------------
def main():
    # container = st.container()
    # Some Basic Configuration for StreamLit - Must be the first streamlit command
    #---------------------------------------
    # Sub Functions
    #---------------------------------------
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

    def move_column_inplace(df, col, pos):
        col = df.pop(col)
        df.insert(pos, col.name, col)
        
    def order_view(df):
        col_order = ['ScoutName','OrderType','submit_dt','order_id','status','PickupT','order_qty_boxes', 'order_amount','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','comments','guardianNm','PickupNm','PickupPh',"Email"]
        # non_in_col_order = [c for c in df.columns not in col_order]
        
        # view_df = df.drop(columns=['addEbudde','digC_val'])
        view_df=df.loc[:, col_order].copy()

        view_df.rename(columns={'order_id':'Order Id','OrderType':'Order Type','comments':'Comments','guardianNm':'Guardian Name','guardianPh':'Guardian Phone','PickupT':'Pickup Date/Time','submit_dt':'Order Date','ScoutName':'Scouts Name','order_qty_boxes':'Qty Boxes','order_amount':'Order Amount','Adf':'Adventurefuls','LmUp':'Lemon-Ups','Tre':'Trefoils','DSD':'Do-Si-Do','Sam':'Samoas','Smr':"S'Mores",'Tags':'Tagalongs','Tmint':'Thin Mint','Toff':'Toffee Tastic','OpC':'Operation Cookies'},inplace=True)
        return view_df
    
    def allorder_view(df):
        # cols = df.columns()
        df=df.loc[:, ['ScoutName','OrderType','submit_dt','suOrder','addEbudde','digC_val','order_qty_boxes', 'order_amount','status','order_ready','order_pickedup','PickupT','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','PickupNm','PickupPh','Email']]
        return df

    def calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc):
        total_boxes = advf+lmup+tre+dsd+sam+tags+tmint+smr+toff+opc
        total_money = total_boxes*6
        return total_boxes, total_money

    def update_session(gs_nms):
        # Update index to be the index just selected
        time.sleep(1)
        st.session_state["index"] = gs_nms.index(st.session_state["gsNm"])
        st.session_state["updatedindex"] = gs_nms.index(st.session_state["gsNm"])

        # Update the scout data (i.e. parent) to be the name just selected
        # scout_dat = esu.get_qry_dat(es,indexnm="scouts",field='FullName',value="Ashlynn Klemisch")
        
        scout_dat = esu.get_qry_dat(es,indexnm="scouts",field='FullName',value=st.session_state["gsNm"])
        # all_orders, all_orders_cln = get_all_orders()
        if len(scout_dat) > 0:
            parent = scout_dat[0]['_source']['Parent']
            st.session_state["guardianNm"] = parent
            # container.header(st.session_state["gsNm"])
            st.session_state["scout_dat"] = scout_dat[0]['_source']

    def get_all_orders():
        orders = ed.DataFrame(es, es_index_pattern="orders2024")
        orders = ed.eland_to_pandas(orders)
        # orders.reset_index(names="index",inplace=True,drop=True)
        
        all_orders = pd.DataFrame(orders)

        all_orders_cln = allorder_view(all_orders)
        return all_orders,all_orders_cln
    
    def update_es(edited_allorders,all_orders):
        
        st.write('EDITED ROWS:')
        edited_rows = edited_allorders #['edited_dat']
        # edited_rows = st.session_state['edited_dat']['edited_rows']
        st.markdown(f'Initial Edited Rows: {edited_rows}')
        updated_edit = {}
        for key, value in edited_rows.items():
            new_key = all_orders.index[key]

            st.write(f'Updated Values to Submit to ES: {new_key}:{value}')
            resp = es.update(index="orders2024", id=new_key, doc=value)
            time.sleep(2)
            st.toast("Database updated with changes")
            all_orders, all_orders_cln = get_all_orders()
        return all_orders_cln
    
    #---------------------------------------
    # Page Functions
    #---------------------------------------
    def main_page():
        st.write('----')
        # Calendar
        st.header('Important Dates, Links and Reminders')
        st.subheader('Reminders')
        st.markdown("""
                    A few reminders:
                    - Cookies are $6 per box. There's no Raspberry Rally this year, but the rest of the lineup is the same!
                    - Cookie Season starts 1/19, and that's when digital storefronts will open and Girl Scouts can begin taking orders on their paper forms. Unfortunately we are not allowed to sell before that date.
                    - Consider setting up a QR code to link to your Girl Scout's site!
                    - Girl Scouts - Do not give out personally identifiable information, such as last name or school, but remember that Promise and Law! You will need to wear your uniform when you sell, you are representing your family and your organization! Have fun with it - this is what you make it!
                    - All in-person orders collected on digital cookie will need to be approved by the parent. After a few days, orders not approved will be automatically rejected and will not count towards sales.
                    - We are participating in Operation Cookie Drop, which donates boxes to the USO to distribute to service members. These donations will count in increments of $6 as a box your Girl Scout sold, but you will not have physical boxes for these donations. The boxes will be handled at the end of the sale at the Council level.
                    - You have 5 days in digital cookie to approve all orders
                    - Monitor your digital cookie orders - submit your orders to us as frequently as you would like
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
        st.write('1/15: Primary caregivers receive Digital Cookie Registration email')
        st.write('1/19: 2024 Cookie Program Launch')
        st.write('1/19-2/4: Initial Orders')
        st.write('2/4 - Initial Orders must be submitted by 12 Noon')
        st.write('~2/23: Pick up cookies from cookie cupboard - Volutneers Needed!')
        st.write('2/25 - 3/16: In person Delivery of Digital Cookie Orders')
        st.write('3/1 - 3/16: Booth Sales')
        st.write('3/19: Family deadline for turning in Cookie Money by 12 Noon')
        st.write('3/22: Troop wrap-up deadline')


    def order():
        st.write('----')
        # st.markdown(f"Submit a Cookie Order for {gsNm}❄️")
        # st.sidebar.markdown("# Order Cookies ❄️")
        # st.session_state['index'] = nmIndex

        st.subheader(f'Submit a Cookie Order for {st.session_state["gsNm"]}')
        
        gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout',index=st.session_state['index'], key='gsNm', on_change=update_session(gs_nms))

        with st.form('submit orders', clear_on_submit=True):
            appc1, appc2, appc3 = st.columns([3,.25,3])
            guardianNm = st.write(f'Guardian accountable for order: {st.session_state["guardianNm"]}')
            with appc1:
                # At this point the URL query string is empty / unchanged, even with data in the text field.
                ordType = st.selectbox("Order Type (Submit seperate orders for paper orders vs. Digital Cookie):",options=['Digital Cookie','Paper Order'],key='ordType')
                pickupT = st.selectbox('Pickup Slot',['Initial Order - TBD']) #,'Tuesday 5-7','Wednesday 6-9'])

            with appc3:
                PickupNm = st.text_input(label="Parent Name picking up cookies",key='PickupNm',max_chars=50)
                PickupPh = st.text_input("Person picking up cookies phone number",key='pickupph',max_chars=13)
               
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
                
                esu.add_es_doc(es,indexnm="orders2024", id=orderId, doc=order_data)

                k=order_data.keys()
                v=order_data.values()
                # st.write(k)
                # new_order = [f"{k}:[{i}]" for k,i in zip(order_data.keys(),order_data.values())]
                order_details = pd.DataFrame(v, index =k, columns =['Order'])
                new_order = order_view(order_details.T)
                st.table(new_order.T)
                st.success('Your order has been submitted!', icon="✅")
                st.balloons()

    def myorders():
        st.write('----')
        # st.session_state['index'] = nmIndex
        st.write(st.session_state['gsNm'])
        gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout', key='gsNm')

        st.subheader("All submited orders into this app's order form")
        all_orders, all_orders_cln = get_all_orders()
        all_orders.reset_index(names="index",inplace=True,drop=True)
        girl_orders = all_orders[all_orders['ScoutName'] == gsNm]
       
        girl_orders = order_view(girl_orders)
        girl_orders.reset_index(inplace=True, drop=True)
        girl_orders.loc['Total']= girl_orders.sum(numeric_only=True, axis=0)
        girl_orders.fillna(0)
        girl_orders = girl_orders.astype({"Order Amount": 'int64', "Qty Boxes": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','Operation Cookies':'int64'})
        st.dataframe(girl_orders.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))), use_container_width=True, 
                     column_config={
                        "Order Amount": st.column_config.NumberColumn(
                            "Order Amt.",
                            format="$%d",
                        )})

        st.subheader("Payments Received - EXCLUDING DIGITAL COOKIE")
        # girl_money = esu.get_dat(es,indexnm="money_received2024")
        girl_money = ed.DataFrame(es, es_index_pattern="money_received2024")
        girl_money = ed.eland_to_pandas(girl_money)
        girl_money = pd.DataFrame(girl_money)


        # st.write(girl_money.columns)
        girl_money = girl_money[girl_money['ScoutName'] == st.session_state['gsNm']]
        # st.write(dtype(girl_money['AmountReceived']))
        girl_money["AmountReceived"] = pd.to_numeric(girl_money["AmountReceived"])
        sum_money = girl_money['AmountReceived'].sum()
        st.metric(label="Total Amount Received", value=f"${sum_money}")
        # paper_money_due = girl_money[girl_money['OrderType'] == "st.session_state['gsNm']"]
        # girl_money['Order Type'].sum()
        # st.metric(label="Total Amount Due for Paper Orders", value=f"${paper_money_due}")
        girl_money.sort_values(by="amtReceived_dt")
        girl_money.rename(inplace=True, columns={'ScoutName': 'Scouts Name','AmountReceived':'Amount Received','amtReceived_dt': 'Date Money Received','orderRef':'Money Reference Note'})
        girl_money.reset_index(inplace=True, drop=True)
        st.dataframe(girl_money,use_container_width=False)

    def allorders():
        st.write('----')
        st.header('All Orders to Date')
        all_orders, all_orders_cln = get_all_orders()
        all_orders_cln.loc['Total']= all_orders_cln.sum(numeric_only=True, axis=0) 
        all_orders_cln.fillna(0)
        all_orders_cln = all_orders_cln.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
        #  "qty_boxes": 'int',

        edited_allorders = st.data_editor(
            all_orders_cln.style.applymap(lambda _: "background-color: #F0F0F0;", subset=(['Total'], slice(None))),
            column_config={
                "_index":st.column_config.TextColumn(
                    label='Order Id'
                ),
                "digC_val": st.column_config.CheckboxColumn(
                    "Validate in Dig Cookie?",
                    help="Has this order been validate in Digital Cookie",
                    default=False,
                ),
                "addEbudde": st.column_config.CheckboxColumn(
                    "Added to Ebudde?",
                    help="Has this order been added to Ebudde",
                    default=False,
                ),
                "suOrder": st.column_config.TextColumn(
                    "Service Unit Order",
                    help="Itital, or #-date",
                    default=False,
                ),
                "order_amount": st.column_config.NumberColumn(
                    "Order $",
                    format="$%d",
                )
            },
            disabled=['order_id', 'Adf', 'DSD', 'LmUp', 'OpC', 'OrderType', 'PickupNm',
                      'PickupPh', 'PickupT', 'Sam', 'ScoutName', 'Smr', 'Tags', 'Tmint',
                      'Toff', 'Tre', 'guardianNm', 'order_amount', 'order_id','order_qty_boxes', 'submit_dt'],
            hide_index=False,
            key='edited_dat'
            )
        refresh = st.button("Refresh")
        if refresh:
            update_es(st.session_state['edited_dat']['edited_rows'],all_orders)


        st.write('----')
        st.subheader('Pending Orders')
        pendingOrders = all_orders[all_orders['status']=="Pending"]
        
        edpendingOrders = st.data_editor(
            pendingOrders,
            column_config={
                "digC_val": st.column_config.CheckboxColumn(
                    "Validate in Dig Cookie?",
                    help="Has this order been validate in Digital Cookie",
                    default=False,
                ),
                "addEbudde": st.column_config.CheckboxColumn(
                    "Added to Ebudde?",
                    help="Has this order been added to Ebudde",
                    default=False,
                )
            },
            disabled=['docId', 'Adf', 'DSD', 'LmUp', 'OpC', 'OrderType', 'PickupNm',
       'PickupPh', 'PickupT', 'Sam', 'ScoutName', 'Smr', 'Tags', 'Tmint',
       'Toff', 'Tre', 'guardianNm', 'order_amount', 'order_id',
       'order_qty_boxes', 'submit_dt'],
            hide_index=True,
            )
    
        st.write('----')
        st.subheader('Booth Orders')
        BoothOrders = all_orders[all_orders['OrderType']=="Booth"]
        BoothOrders = BoothOrders.loc[:, ['ScoutName','OrderType','submit_dt','suOrder','order_qty_boxes', 'order_amount','status','order_ready','order_pickedup','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','addEbudde','PickupNm','PickupPh','Email']]
       
        edpendingOrders = st.data_editor(
            BoothOrders,
            column_config={
                "digC_val": st.column_config.CheckboxColumn(
                    "Validate in Dig Cookie?",
                    help="Has this order been validate in Digital Cookie",
                    default=False,
                ),
                "addEbudde": st.column_config.CheckboxColumn(
                    "Added to Ebudde?",
                    help="Has this order been added to Ebudde",
                    default=False,
                )
            },
            disabled=['docId', 'Adf', 'DSD', 'LmUp', 'OpC', 'OrderType', 'PickupNm',
       'PickupPh', 'PickupT', 'Sam', 'ScoutName', 'Smr', 'Tags', 'Tmint',
       'Toff', 'Tre', 'guardianNm', 'order_amount', 'order_id',
       'order_qty_boxes', 'submit_dt'],
            hide_index=True,
            )
        
    def submitBoothOrder():
        with st.form('submit orders', clear_on_submit=True):
            Booth = st.text_input(f'Booth - Location and Date:')


            st.write('----')
            ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])

            with ck1:
                advf=st.number_input(label='Adventurefuls',step=1,min_value=0, value=6) # 48 for first weekend
                tags=st.number_input(label='Tagalongs',step=1,min_value=0, value=6) # 48 for first weekend

            with ck2:
                lmup=st.number_input(label='Lemon-Ups',step=1,value=3) # 12
                tmint=st.number_input(label='Thin Mints',step=1,value=18) # 60 for first weekend
            with ck3:
                tre=st.number_input(label='Trefoils',step=1,value=3) #12
                smr=st.number_input(label="S'Mores",step=1,value=3) #12

            with ck4:
                dsd=st.number_input(label='Do-Si-Dos',step=1,min_value=3) #12
                toff=st.number_input(label='Toffee-Tastic',step=1,value=3) #12

            with ck5:
                sam=st.number_input(label='Samoas',step=1,value=18) # 60 for first weekend


            comments = st.text_area("Comments", key='comments')


            # submitted = st.form_submit_button()
            if st.form_submit_button("Submit Order to Cookie Crew"):
                opc=0
                total_boxes, order_amount=calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
                now = datetime.now()
                idTime = now.strftime("%m%d%Y%H%M")
                # st.write(idTime)
                orderId = (f'{Booth.replace(" ","").replace(".","_").lower()}{idTime}')
                # Every form must have a submit button.
                order_data = {
                    "ScoutName": Booth,
                    "OrderType": "Booth",
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
                
                esu.add_es_doc(es,indexnm="orders2024", id=orderId, doc=order_data)
                st.success('Your order has been submitted!', icon="✅")

    def pickupSlot():
        st.write("this page is in work... come back later")
        st.header("Add a Pickup Timeslot Here")
        st.write(esu.get_dat(es, indexnm="timeslots", field='timeslots'))
        new_timeslot = st.time_input('timeslot', value="today", format="MM/DD/YYYY")
        st.button("Add Timeslot")
        if st.button:
            esu.add_es_doc(es, indexnm="timeslots",doc=new_timeslot)

    
    def receiveMoney():
        st.header("Receive Money")
        gsNm = st.selectbox("Girl Scount Name:", gs_nms, placeholder='Select your scout', index=st.session_state['index'], key='gsNm', on_change=update_session(gs_nms))
        with st.form("money", clear_on_submit=True):
            amt = st.text_input("Amount Received")
            amt_date = st.date_input("Date Received",value="today",format="MM/DD/YYYY")
            orderRef = st.text_input("Order Reference (optional)")
            # from orders get all for this scout:
            # orderId = (f'{st.session_state["scout_dat"]["Concat"].replace(" ","").replace(".","_").lower()}{idTime}')
               
            if st.form_submit_button("Submit Money to Cookie Crew"):
                now = datetime.now()
                idTime = now.strftime("%m%d%Y%H%M")

                 # Every form must have a submit button.
                moneyRec_data = {
                    "ScoutName": st.session_state["scout_dat"]["FullName"],
                    "AmountReceived": amt,
                    "amtReceived_dt": amt_date,
                    "orderRef": orderRef         
                    }

                esu.add_es_doc(es,indexnm="money_received2024", id=None, doc=moneyRec_data)


    def booths():
        st.write("this page is in work... come back later")

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
    # App Content
    #---------------------------------------
    def local_css(file_name):
        with open(f'{file_name}') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    local_css('style.css')
    st.title('Troop 43202 Cookie Season')

    if not check_password():
        st.stop()  # Do not continue if check_password is not True.

    if st.session_state["adminpassword_correct"]:
        page_names_to_funcs = {
            "Dates and Information": main_page,
            "Order Cookies 🍪": order,
            "My Orders": myorders,
            "Booths": booths,
            "All Orders": allorders,
            "Add Booth Orders": submitBoothOrder,
            "Receive Money":receiveMoney,
            "Add Pickup Slots": pickupSlot,
            "Digital Cookie Instructions": dcInstructions
        }
    elif st.session_state["password_correct"]:
            page_names_to_funcs = {
            "Dates and Links": main_page,
            "Order Cookies 🍪": order,
            "My Orders": myorders,
            "Booths": booths,
            "Digital Cookie Instructions": dcInstructions
        }
    
    topc1, topc2 = st.columns([3,7])
    with topc1:
        selected_page = st.selectbox("----", page_names_to_funcs.keys())
    with topc2:
        bandurl = "https://band.us/band/93124235"
        st.info("Inital Orders due to us by 2/4")
        st.info("We expect to pick up our inital order on 2/23 or 2/24, Sign-up to help get cookies coming out soon.")
        st.info("Connect with us on [Band](%s) if you have any questions" % bandurl)
    page_names_to_funcs[selected_page]()


    # selected_page = st.sidebar.selectbox("----", page_names_to_funcs.keys())
    # page_names_to_funcs[selected_page]()

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