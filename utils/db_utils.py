import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import json
from typing import IO
import bcrypt
import secrets
from datetime import datetime, timedelta



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
# Common data lookups
# ==================================================
def get_all_scouts():
    return fetch_all("""
        SELECT scout_id, first_name, last_name, gsusa_id, parent_id
        FROM cookies_app.scouts
        ORDER BY last_name, first_name
    """)

def fetch_scout_aliases(conn):
    query = "SELECT alias_name, scout_id FROM scout_aliases"
    rows = conn.execute(query).fetchall()
    return {r[0].lower(): r[1] for r in rows}

def insert_scout_alias(conn, alias_name: str, scout_id: int):
    conn.execute(
        """
        INSERT INTO scout_aliases (alias_name, scout_id)
        VALUES (%s, %s)
        ON CONFLICT (alias_name) DO NOTHING
        """,
        (alias_name, scout_id),
    )
    conn.commit()

def get_all_parents():
    return fetch_all("""
        SELECT parent_id, parent_firstname, parent_lastname
        FROM cookies_app.parents
        ORDER BY parent_lastname, parent_firstname
    """)

def update_scout_gsusa_id(scout_id, gsusa_id):
    with engine().begin() as conn:
        conn.execute(
            text("""
                UPDATE scouts
                SET gsusa_id = :gsusa_id
                WHERE scout_id = :scout_id
                  AND gsusa_id IS NULL
            """),
            {
                "scout_id": scout_id,
                "gsusa_id": str(gsusa_id),
            },
        )

def get_outstanding_non_booth_orders(program_year=None):
    params = {}
    year_filter = ""

    if program_year:
        year_filter = "AND o.program_year = :year"
        params["year"] = program_year

    return fetch_all(f"""
        SELECT
            o.order_id,
            o.parent_id,
            o.program_year,
            o.submit_dt,
            p.parent_firstname,
            p.parent_lastname,
            p.parent_phone
        FROM cookies_app.orders o
        JOIN cookies_app.parents p ON p.parent_id = o.parent_id
        WHERE o.order_type <> 'BOOTH'
          AND o.status <> 'PICKED_UP'
          {year_filter}
        ORDER BY p.parent_lastname, p.parent_firstname, o.submit_dt
    """, params)


def fetch_orders_for_scout(scout_id):
    return fetch_all("""
        SELECT
            o.order_id,
            o.scout_id,
            o.order_qty_boxes,
            o.order_type,
            o.order_source,
            o.submit_date,
            o.program_year,
            o.status
        FROM orders o
        WHERE o.scout_id = {scout_id}
    """)

def fetch_orders_for_scout_with_fallback(
    scout_id,
    scout_first_name: str,
    scout_last_name: str,
):
    """
    Fetch cookie-level order items for a scout.

    Priority:
    1) Match on scout_id
    2) Fallback to first + last name for legacy rows
    """

    sql = """
        SELECT
            oi.cookie_name,
            oi.qty_boxes,
            o.order_type,
            o.submit_dt,
            o.order_id
        FROM order_items oi
        JOIN orders o
          ON o.order_id = oi.order_id
        WHERE o.scout_id = :scout_id

        UNION ALL

        SELECT
            oi.cookie_name,
            oi.qty_boxes,
            o.order_type,
            o.submit_dt,
            o.order_id
        FROM order_items oi
        JOIN orders o
          ON o.order_id = oi.order_id
        WHERE o.scout_id IS NULL
          
    """

    return fetch_all(
        sql,
        {
            "scout_id": scout_id,
            "first_name": scout_first_name,
            "last_name": scout_last_name,
        },
    )

# ==================================================
# Upload Data
# ==================================================


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
