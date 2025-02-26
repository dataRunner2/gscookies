from json import loads
import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from datetime import datetime

@st.cache_resource
def get_connected():
    es = esu.conn_es()
    return es

def booth_checkin():
    st.write('----')
    es = get_connected()

    all_orders_dat = esu.get_all_orders(es)
    all_orders_cln = au.allorder_view(all_orders_dat)

    booth_dat = all_orders_cln[all_orders_cln['OrderType'] == 'Booth']
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
        order_content = au.filter_dataframe(booth)
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

            esu.add_es_doc(es,indexnm=ss.indexes['index_money'], id=None, doc=moneyRec_data)
            st.toast("Database updated with changes")

def submitBoothOrder(es):
    with st.form('submit orders', clear_on_submit=True):
        Booth = st.text_input(f'Booth - Location and Date:')


        st.write('----')
        ck1,ck2,ck3,ck4,ck5 = st.columns([1.5,1.5,1.5,1.5,1.5])

        with ck1:
            advf=st.number_input(label='Adventurefuls (24)',step=1,min_value=0, value=6) # 24 for first weekend
            tags=st.number_input(label='Tagalongs (36)',step=1,min_value=0, value=6) # 48 for first weekend

        with ck2:
            lmup=st.number_input(label='Lemon-Ups (12)',step=1,value=3) # 12
            tmint=st.number_input(label='Thin Mints (60)',step=1,value=18) # 60 for first weekend
        with ck3:
            tre=st.number_input(label='Trefoils(12)',step=1,value=3) #12
            smr=st.number_input(label="S'Mores (18)",step=1,value=3) #18

        with ck4:
            dsd=st.number_input(label='Do-Si-Dos (12)',step=1,min_value=3) #12
            toff=st.number_input(label='Toffee-Tastic (12)',step=1,value=3) #12

        with ck5:
            sam=st.number_input(label='Samoas (48)',step=1,value=18) # 48 for first weekend


        comments = st.text_area("Comments to us or your ref notes", key='comments')


        # submitted = st.form_submit_button()
        if st.form_submit_button("Submit Order to Cookie Crew"):
            opc=0
            total_boxes, order_amount=au.calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
            now = datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")
            # st.write(idTime)
            orderId = (f'{Booth.replace(" ","").replace("/","_").replace("-","_").replace(".","_").lower()}{idTime}')
            # Every form must have a submit button.
            order_data = {
                "scoutName": Booth,
                "orderType": "Booth",
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
                "orderQtyBoxes": total_boxes,
                "orderAmount": order_amount,
                "submit_dt": datetime.now(),
                "comments": comments,
                "status": "Pending",
                "orderId": orderId,
                "digC_val": False,
                "addEbudde": False,
                "orderPickedup": False,
                "orderReady": True,
                "initialOrder": False,
                "orderPaid": True
                }

            esu.add_es_doc(es,indexnm=ss.indexes['index_orders'], id=orderId, doc=order_data)
            st.success('Your order has been submitted!', icon="✅")

def pickupSlot(es):
    st.write("this page is in work... come back later")
    st.header("Add a Pickup Timeslot Here")
    st.write(esu.get_dat(es, indexnm="timeslots", field='timeslots'))
    new_timeslot = st.time_input('timeslot', value="today", format="MM/DD/YYYY")
    st.button("Add Timeslot")
    if st.button:
        esu.add_es_doc(es, indexnm="timeslots",doc=new_timeslot)

def main():
    st.write('Booths')
    es = get_connected()
    
    submitBoothOrder(es)
    # booth_checkin()

    st.divider()
    st.subheader('Delete Booth')
    booth_orders = esu.get_booth_orders(es)

    booths = booth_orders["scoutName"]
    del_booth = st.selectbox("Booth:", booths, key='del_booth')

    row_index = booth_orders.index[booth_orders["scoutName"] == del_booth].tolist()[0]  # Get index
    del_boothid = booth_orders.at[row_index, "orderId"]
    
    # Button to trigger deletion
    if st.button("Delete Selected Booth"):
        st.write(f'Deleting booth: {del_boothid}')
        index_nm = ss.indexes['index_orders']
        if index_nm and del_booth:
            try:
                response = es.delete(index=index_nm, id=del_boothid)
                st.success(f"Document {del_boothid} deleted successfully!")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Please enter both Index Name and Document ID.")

if __name__ == '__main__':

    setup.config_site(page_title="Booth Admin",initial_sidebar_state='expanded')
    # Initialization
    # init_ss()
    main()