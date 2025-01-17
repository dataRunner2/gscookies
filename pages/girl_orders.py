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
    st.sidebar.write(ss)
    gs_nms = [scout['fn'] for scout in ss['scout_dat']['scout_details']]


    # selection box can not default to none because the form defaults will fail. 
    gsNm = st.selectbox("Select Girl Scount:", gs_nms, key='gsNm') # index=noscouti, key='gsNm', on_change=update_session(gs_nms))
    # # st.write('----')
    orderck, summary = st.tabs(['Order Cookies','Summary of Orders'])

    with orderck:        
        st.markdown(f"Ready to submit a Cookie Order for **{gsNm}**")

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
                total_boxes, order_amount=au.calc_tots(advf,lmup,tre,dsd,sam,tags,tmint,smr,toff,opc)
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

                esu.add_es_doc(es,indexnm=ss.orders_index, id=orderId, doc=order_data)

                k=order_data.keys()
                v=order_data.values()
                # st.write(k)
                # new_order = [f"{k}:[{i}]" for k,i in zip(order_data.keys(),order_data.values())]
                order_details = pd.DataFrame(v, index =k, columns =['Order'])
                new_order = au.order_view(order_details.T)
                st.table(new_order.T)
                st.success('Your order has been submitted!', icon="✅")
                st.balloons()

    # def myorders(gs_nms):
    with summary:
        st.write('----')
        
        st.markdown(f"{gsNm} Cookie Order Summary")
       
        # st.subheader("All submited orders into this app's order form")
        all_orders, all_orders_cln = au.get_all_orders()
        all_orders.reset_index(names="index",inplace=True,drop=True)
        girl_orders = all_orders[all_orders['ScoutName'] == gsNm]
        girl_orders.sort_values(by=['OrderType','submit_dt'],ascending=[False, True], inplace=True)

        girl_orders = au.order_view(girl_orders)
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
        # girl_money = ed.DataFrame(es, es_index_pattern=ss.index_money)
        # girl_money = ed.eland_to_pandas(girl_money)
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

if __name__ == '__main__':

    setup.config_site(page_title="Login")
    # Initialization
    init_ss()

    main()