from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup

def booth_checkin():
    st.write('----')

    data_orders, data_cln = get_all_orders()

    booth_dat = data_cln[data_cln['OrderType'] == 'Booth']
    booth_names = booth_dat['ScoutName']
    booth_name = st.selectbox("Booth:", booth_names, placeholder='Select the Booth', key='boothNm')


    # all_orders_cln.fillna(0)
    booth = booth_dat.astype({"order_qty_boxes":"int","order_amount": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
    booth=booth.loc[:, ['ScoutName','OrderType','submit_dt','order_qty_boxes', 'order_amount','comments','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC','guardianNm','guardianPh','PickupNm','PickupPh','status']]
    booth.rename(inplace=True, columns={'ScoutName': 'Booth','submit_dt':"Date",'order_qty_boxes':'Qty','order_amount':'Amt'})
    booth = booth.astype({"Amt": 'int', "Qty": 'int', 'Adf':'int','LmUp': 'int','Tre':'int','DSD':'int','Sam':'int',"Smr":'int','Tags':'int','Tmint':'int','Toff':'int','OpC':'int'})
    booth.loc['Total']= booth.sum(numeric_only=True, axis=0)
    booth = booth[booth['Booth'] == booth_name]
    with st.expander('Filter'):
        order_content = filter_dataframe(booth)
    st.write(order_content)
    st.dataframe(order_content, use_container_width=True,
                    column_config={
                    "Amt": st.column_config.NumberColumn(
                        format="$%d",
                        width='small'
                    ),
                    "Date": st.column_config.DateColumn(
                        format="MM-DD-YY",
                    )})

    if st.form_submit_button("Submit Booth Money"):
            now = datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")

            # Every form must have a submit button.
            moneyRec_data = {
                "Booth": st.session_state["scout_dat"]["FullName"],
                "AmountReceived": amt,
                "amtReceived_dt": amt_date,
                "orderRef": booth_name
                }

            esu.add_es_doc(es,indexnm="money_received2024", id=None, doc=moneyRec_data)
            st.toast("Database updated with changes")

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


        comments = st.text_area("Comments to us or your ref notes", key='comments')


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
                "inEbudde": False,
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

def inventory():
    st.write('----')
    st.header('THIS PAGE IS STILL IN WORK')
    all_orders, all_orders_cln = get_all_orders()
    all_orders.reset_index(names="index",inplace=True,drop=True)

    all_orders = order_view(all_orders)
    all_orders.reset_index(inplace=True, drop=True)
    all_orders.fillna(0)
    all_orders = all_orders.astype({"Amt": 'int64', "Qty": 'int64', 'Adventurefuls':'int64','Lemon-Ups': 'int64','Trefoils':'int64','Do-Si-Do':'int64','Samoas':'int64',"S'Mores":'int64','Tagalongs':'int64','Thin Mint':'int64','Toffee Tastic':'int64','Operation Cookies':'int64'})
    all_orders.loc['Total']= all_orders.sum(numeric_only=True, axis=0)
    st.write(all_orders)

    all_total = all_orders.iloc[-1,:]
    st.write(all_total)

    pending_ready = all_orders.loc[:, ['order_qty_boxes', 'order_amount','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC']]
    pending_ready.loc['Total']= pending_ready.sum(numeric_only=True, axis=0)
    st.write(pending_ready)

    pickedup = all_orders[all_orders['status']=='Order Pickedup'].copy()
    pickedup = pickedup.loc[:, ['order_qty_boxes', 'order_amount','Adf','LmUp','Tre','DSD','Sam','Tags','Tmint','Smr','Toff','OpC']]
    pickedup.loc['Total']= pickedup.sum(numeric_only=True, axis=0)
    st.write(pickedup)


def booths():
    st.write("this page is in work... come back later")
