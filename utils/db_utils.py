import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


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
        SELECT scout_id, first_name, last_name
        FROM cookies_app.scouts
        ORDER BY last_name, first_name
    """)


def get_all_parents():
    return fetch_all("""
        SELECT parent_id, parent_firstname, parent_lastname
        FROM cookies_app.parents
        ORDER BY parent_lastname, parent_firstname
    """)


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
