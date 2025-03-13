from json import loads
import streamlit as st
import pandas as pd
import io
import time
from pathlib import Path
from streamlit import session_state as ss
from utils.esutils import esu
from utils.app_utils import apputils as au, setup
from datetime import datetime
from streamlit_extras.row import row as strow

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

    
def submitBoothOrder(es):
    with st.form('submit orders', clear_on_submit=True):
        topcols = st.columns(3)
        topcols[0].date_input('Select Booth Date', format="MM/DD/YYYY", key='booth_date')
        topcols[1].text_input(f'Booth - Time & Location:', key='booth')
        topcols[2].text_input('Assigned Scouts', key='comments')
        

        row1 = strow(5, vertical_align="center")
        row1.number_input(label='Adventurefuls',step=1,min_value=-5, value=12,key='bth_advf')
        row1.number_input(label='Lemon-Ups',step=1,min_value=-5, value=6, key='bth_lmup')
        row1.number_input(label='Trefoils',step=1,min_value=-5, value=6, key='bth_tre')
        row1.number_input(label='Do-Si_Dos',step=1,min_value=-5, value=8, key='bth_dsd')

        row2 = strow(5, vertical_align="center")
        row2.number_input(label='Samoas',step=1,min_value=-5, value=24, key='bth_sam')
        row2.number_input(label='Tagalongs',step=1,min_value=-5, value=24, key='bth_tags')
        row2.number_input(label='Thin Mints',step=1,min_value=-5, value=36, key='bth_tmint')
        row2.number_input(label="S'mores",step=1,min_value=-5, value=0, key='bth_smr')
        row2.number_input(label='Toffee-Tastic',step=1,min_value=-5, value=0, key='bth_toff')


        # submitted = st.form_submit_button()
        if st.form_submit_button("Submit Order to Cookie Crew"):
            opc=0
            total_boxes, order_amount=au.calc_tots(ss.bth_advf,ss.bth_lmup,ss.bth_tre,ss.bth_dsd,ss.bth_sam,ss.bth_tags,ss.bth_tmint,ss.bth_smr,ss.bth_toff,0)
            now = datetime.now()
            idTime = now.strftime("%m%d%Y%H%M")
            # st.write(idTime)
            orderId = (f'{ss.booth.replace(" ","_").replace("/","_").replace("-","_").replace(".","_").replace("(","_").replace(")","_").lower()}{idTime}')
            booth_dt_str = pd.to_datetime(ss.booth_date, format="%m/%d/%Y").strftime("%d %b")
            boothName = f'{booth_dt_str}_{ss.booth}'
            st.write(boothName)
            # Every form must have a submit button.
            order_data = {
                "scoutName": boothName,
                "orderType": "Booth",
                "Adf": ss.bth_advf,
                "LmUp": ss.bth_lmup,
                "Tre": ss.bth_tre,
                "DSD": ss.bth_dsd,
                "Sam": ss.bth_sam,
                "Tags": ss.bth_tags,
                "Tmint": ss.bth_tmint,
                "Smr": ss.bth_smr,
                "Toff": ss.bth_toff,
                "OpC": 0,
                "orderQtyBoxes": total_boxes,
                "orderAmount": order_amount,
                "submit_dt": ss.booth_date,
                "comments": ss.comments,
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
    booth_orders = booth_orders[booth_orders['orderPickedup'] == False].copy()
    booth_orders.reindex()

    if "booths_list" not in ss:
        ss.booths_list = ss.booth_orders["scoutName"].tolist()
        ss.booths_list.sort()
    
    st.selectbox("Booth:", ss.booths_list, index=None,key='del_booth')
    
    st.write(ss.del_booth)
    
    get_booth = f'FROM {ss.indexes["index_orders"]}| WHERE scoutName LIKE """{ss.del_booth}""" | LIMIT 5'
    # st.write(girl_order_qry)
    response = es.esql.query(
        query=get_booth,
        format="csv")
    found_booths = pd.read_csv(io.StringIO(response.body))
    st.write(found_booths)
    # row_index = booth_orders.index[booth_orders["scoutName"] == ss.del_booth].tolist()  # Get index
    del_boothid = found_booths["orderId"].tolist()
    st.write(del_boothid)
    
    # Button to trigger deletion
    if st.button("Delete Selected Booth"):
        st.write(f'Deleting booth: {del_boothid}')
        index_nm = ss.indexes['index_orders']
        if index_nm and del_boothid:
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