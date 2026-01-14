import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import json
from typing import IO
import bcrypt
import secrets
from datetime import datetime, timedelta
import pandas as pd



# ==================================================
# Database connection
# ==================================================
def get_engine() -> Engine:
    """
    Central Postgres engine.
    Uses Streamlit secrets.
    """
    return create_engine(
        f"postgresql+psycopg2://"
        f"{st.secrets['general']['DB_USER']}:"
        f"{st.secrets['general']['DB_PASSWORD']}@"
        f"{st.secrets['general']['DB_HOST']}:"
        f"{st.secrets['general'].get('DB_PORT', 5432)}/"
        f"{st.secrets['general']['DB_NAME']}",
        pool_pre_ping=True
    )

_ENGINE = None


def engine() -> Engine:
    """
    Cached engine getter (safe for Streamlit reruns).
    """
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE


# ==================================================
# Query helpers
# ==================================================
def fetch_all(sql: str, params: dict | None = None):
    """
    Execute SELECT and return list of dict rows.
    """
    params = params or {}
    with engine().connect() as conn:
        return conn.execute(text(sql), params).mappings().all()


def fetch_one(sql: str, params: dict | None = None):
    """
    Execute SELECT and return single row or None.
    """
    params = params or {}
    with engine().connect() as conn:
        return conn.execute(text(sql), params).mappings().first()


def execute_sql(sql: str, params: dict | None = None):
    """
    Execute INSERT / UPDATE / DELETE inside transaction.
    """
    params = params or {}
    with engine().begin() as conn:
        conn.execute(text(sql), params)

def execute_many_sql(sql: str, params_list: list[dict]):
    """
    Execute bulk INSERT / UPDATE inside a single transaction.
    """
    if not params_list:
        return

    with engine().begin() as conn:
        conn.execute(text(sql), params_list)



# ==================================================
# Auth guards (matches your app)
# ==================================================
def require_admin():
    ss = st.session_state
    if not ss.get("authenticated") or not ss.get("is_admin"):
        st.error("Admin access required.")
        st.stop()


def require_login():
    ss = st.session_state
    if not ss.get("authenticated"):
        st.error("Please log in.")
        st.stop()

# ==================================================
# Upload Data
# ==================================================
def to_pacific(ts):
    return (
        pd.to_datetime(ts, utc=True)
          .tz_convert("US/Pacific")
    )


def show_engine_conn():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                current_database() AS db,
                current_user       AS user,
                current_schema()   AS schema;
        """)).mappings().first()

    st.write("Connected DB info:", result)

def mk_sql_table(table_name='stg_es_scouts_docs'):
    with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.{table_name} (
                    doc jsonb NOT NULL,
                    loaded_at timestamp without time zone DEFAULT now()
                );
            """))

def load_jsonl_to_staging(
    *,
    engine: Engine,
    uploaded_file: IO,
    table_name: str = "stg_es_scouts_docs",
    ) -> int:
    """
    Load a JSONL (newline-delimited JSON) file into a staging table
    with a single jsonb column named `doc`.

    Uses existing SQLAlchemy engine utilities.
    Transaction-safe and reusable.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        SQLAlchemy engine from db_utils
    uploaded_file : file-like
        Streamlit uploaded_file or any file-like yielding bytes/str per line
    table_name : str
        Target staging table name

    Returns
    -------
    int
        Number of rows inserted
    """

    insert_stmt = text(f"""
        INSERT INTO public.{table_name} (doc)
        VALUES (:doc)
    """)

    count = 0

    with engine.begin() as conn:  # auto-commit / rollback
        for line in uploaded_file:
            if isinstance(line, bytes):
                line = line.decode("utf-8")

            payload = json.loads(line)

            conn.execute(
                insert_stmt,
                {"doc": json.dumps(payload)}
            )
            count += 1

    return count



RESET_EXPIRY_MINUTES = 15


def generate_reset_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def set_password_reset(identifier: str):
    """
    identifier = email OR phone
    """
    engine = get_engine()
    reset_code = generate_reset_code()
    reset_hash = bcrypt.hashpw(reset_code.encode(), bcrypt.gensalt()).decode()
    expires = datetime.utcnow() + timedelta(minutes=RESET_EXPIRY_MINUTES)

    query = text("""
        UPDATE cookies_app.parents
        SET reset_code_hash = :hash,
            reset_code_expires = :expires
        WHERE parent_email = :id
           OR parent_phone = :id
        RETURNING parent_email, parent_phone
    """)

    with engine.begin() as conn:
        result = conn.execute(
            query,
            {"hash": reset_hash, "expires": expires, "id": identifier}
        ).fetchone()

    if not result:
        return None, None, None

    return reset_code, result.parent_email, result.parent_phone


def verify_reset_code(identifier: str, code: str) -> bool:
    engine = get_engine()

    query = text("""
        SELECT reset_code_hash, reset_code_expires
        FROM cookies_app.parents
        WHERE parent_email = :id
           OR parent_phone = :id
    """)

    with engine.begin() as conn:
        row = conn.execute(query, {"id": identifier}).fetchone()

    if not row:
        return False

    if not row.reset_code_expires or row.reset_code_expires < datetime.utcnow():
        return False

    return bcrypt.checkpw(code.encode(), row.reset_code_hash.encode())


def update_password(identifier: str, new_password: str):
    engine = get_engine()
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    query = text("""
        UPDATE cookies_app.parents
        SET parent_password = :pw,
            reset_code_hash = NULL,
            reset_code_expires = NULL
        WHERE parent_email = :id
           OR parent_phone = :id
    """)

    with engine.begin() as conn:
        conn.execute(query, {"pw": hashed, "id": identifier})


def verify_username_and_phone(username: str, phone: str) -> bool:
    engine = get_engine()

    query = text("""
        SELECT 1
        FROM cookies_app.parents
        WHERE username = :username
          AND parent_phone = :phone
    """)

    with engine.begin() as conn:
        row = conn.execute(
            query,
            {"username": username, "phone": phone}
        ).fetchone()

    return row is not None


def verify_username_and_phone(username: str, phone: str) -> bool:
    engine = get_engine()

    query = text("""
        SELECT 1
        FROM cookies_app.parents
        WHERE username = :username
          AND parent_phone = :phone
    """)

    with engine.begin() as conn:
        row = conn.execute(
            query,
            {"username": username, "phone": phone}
        ).fetchone()

    return row is not None


# app_utils.py (or db_utils.py)
import re

def normalize_phone(phone: str) -> str:
    """
    Strip all non-digits.
    Keeps country code if present.
    """
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)

def verify_username_and_phone(username: str, phone: str) -> bool:
    engine = get_engine()
    phone_norm = normalize_phone(phone)

    query = text("""
        SELECT 1
        FROM cookies_app.parents
        WHERE username = :username
          AND regexp_replace(parent_phone, '\\D', '', 'g') = :phone
    """)

    with engine.begin() as conn:
        row = conn.execute(
            query,
            {
                "username": username,
                "phone": phone_norm,
            }
        ).fetchone()

    return row is not None

def reset_password_with_username_phone(
    username: str,
    phone: str,
    new_password: str
):
    engine = get_engine()
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    query = text("""
        UPDATE cookies_app.parents
        SET parent_password = :pw
        WHERE username = :username
          AND parent_phone = :phone
    """)

    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "pw": hashed,
                "username": username,
                "phone": phone,
            }
        )
