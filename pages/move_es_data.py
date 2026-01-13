import streamlit as st
from streamlit import session_state as ss
from elasticsearch import Elasticsearch
import json
import tempfile
import psycopg2
import csv
from pathlib import Path
from pathlib import Path
from utils.app_utils import setup
from utils.esutils import esu
from utils.db_utils import get_engine, load_jsonl_to_staging, show_engine_conn, mk_sql_table


def main():


    st.markdown(
        """
        This tool exports **data** from Elasticsearch  
        (`scouts*` index) into a **newline-delimited JSON (NDJSON)** file.

        Each line = one ES document  
        Safe for Postgres ingestion later.
        """
    )
    es_host = 'https://gs-cookies-2025-c01bb8.es.us-east-1.aws.elastic.cloud:443'
            # Less common way to connect
            # CLOUD_ID = "GS_Cookies_2025:dXM...
            
    api_key= st.secrets['general']['transfer_key']
    # st.write(api_key)
    # conn = Elasticsearch(
    #         hosts=[elastic_url],
    #         api_key=st.secrets['general']['api_key'],
    #         request_timeout=30
    #     )
    # ---------------------------
    # Connection Inputs
    # ---------------------------
    with st.form("es_config"):
        st.subheader("Elasticsearch Connection")

        

        index_name = st.text_input(
            "Index pattern",
            value="scouts*",
            key='index_nm'
        )

        try:
            if api_key:
                es = Elasticsearch(
                    es_host,
                    api_key=api_key,
                    request_timeout=60
                )
            else:
                st.write('no connection - try again')

            # Test connection
            if not es.ping():
                st.error("Could not connect to Elasticsearch")
                st.stop()

            st.success("Connected to Elasticsearch")
        except Exception as e:
            st.exception(e)
            st.write('unable to connect to es')

        page_size = st.number_input(
            "Page size",
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            key='page_size'
        )

        submitted = st.form_submit_button("Connect & Export")

    # ---------------------------
    # Export Logic
    # ---------------------------
    if submitted:
        if not es_host:
            st.error("Elasticsearch URL is required")
            st.stop()

        if es.ping():
            get_index_dat, response = esu.get_dat(es, ss.index_nm, field=None,size=ss.page_size)
            
            st.write(f'Got data: the len is {len(get_index_dat)}')
            # st.write(get_index_dat)
            total = response["hits"]["total"]["value"]

            st.info(f"Found {total} documents in `{index_name}`")
            # st.write(get_index_dat)

            # Temp file for export
            tmp_dir = Path(tempfile.mkdtemp())
            output_path = tmp_dir / "scouts_export.jsonl"

            # progress = st.progress(0)
            status = st.empty()

            count = 0
            hits = get_index_dat
            last_sort = None

            with open(output_path, "w") as f:
                for x,h in enumerate(hits):
                    if x < 2: st.write(h)
                    f.write(json.dumps(h["_source"]) + "\n")
                    count += 1


            # progress.progress(1.0)
            status.text(f"Export complete: {count} documents")

            st.success("✅ Export complete")

            # Download button
            with open(output_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download scouts_export.jsonl",
                    data=f,
                    file_name="scouts_export.jsonl",
                    mime="application/json"
                )

            st.markdown("### Sample Record")
            with open(output_path) as f:
                sample = json.loads(next(f))
                st.json(sample)


    if st.button("Create CSV data"):
        # -----------------------
        # CONFIG
        # -----------------------
        INPUT_JSONL = "scouts_export_all.jsonl"

        OUT_PARENTS = "parents.csv"
        OUT_SCOUTS = "scouts.csv"

        # -----------------------
        # LOAD JSONL
        # -----------------------
        rows = []
        with open(INPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))

        st.write(f"Loaded {len(rows)} parent documents")

        # -----------------------
        # WRITE PARENTS CSV
        # -----------------------
        parent_fields = [
            "username",
            "parent_email",
            "parent_phone",
            "parent_password",
            "parent_firstname",
            "parent_lastname",
            "verify_trp",
            "is_admin"
        ]

        with open(OUT_PARENTS, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=parent_fields)
            writer.writeheader()

            for r in rows:
                writer.writerow({
                    "username": r.get("username"),
                    "parent_email": r.get("parent_email"),
                    "parent_phone": r.get("parent_phone"),
                    "parent_password": r.get("parent_password_b64"),
                    "parent_firstname": r.get("parent_firstname"),
                    "parent_lastname": r.get("parent_lastname"),
                    "verify_trp": "43202",
                    "is_admin":False
                    
                })

        st.write(f"Wrote {OUT_PARENTS}")

        # -----------------------
        # WRITE SCOUTS CSV
        # -----------------------
        with open(INPUT_JSONL, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

        with open(
            OUT_SCOUTS,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:
            writer = csv.writer(
                f,
                delimiter=",",
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL
            )

            # HEADER — REQUIRED
            writer.writerow(["first_name", "last_name", "es_scout_id"])

            for r in rows:
                for s in r.get("scout_details", []):
                    writer.writerow([
                        s.get("fn", ""),
                        s.get("ln", ""),
                        s.get("nameId", ""),
                    ])

        print("scouts.csv regenerated")

    # ---------------------------
    # Push to SQL Logic
    # ---------------------------
    
    if st.button("Create staging table"):
        mk_sql_table()
    st.success("stg_es_scouts_docs table created")

    # ---------------------------
    # Postgres connection
    # ---------------------------
    with st.form("pg_config"):
        st.subheader("Postgres Connection")
        uploaded_file = st.file_uploader(
            "Upload scouts_export.jsonl",
            type=["jsonl"]
        )

        push = st.form_submit_button("Upload to Postgres")

    # ---------------------------
    # Load logic
    # ---------------------------
    if push:
        if not uploaded_file:
            st.error("Please upload scouts_export.jsonl")
            st.stop()

        try:
            engine = get_engine()

            count = load_jsonl_to_staging(
                engine=engine,
                uploaded_file=uploaded_file,
                table_name="stg_es_scouts_docs",
            )
            

            st.success(f"✅ Loaded {count} documents into stg_es_scouts_docs")
        except Exception as e:
            st.exception(e) 

if __name__ == "__main__":
    setup.config_site(
        page_title="Girl Order Summary",
        initial_sidebar_state="expanded",
    )
    main()
