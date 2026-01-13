import streamlit as st
import bcrypt
import hmac

def check_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compares a plaintext password against a bcrypt hash.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def constant_time_compare(val1: str, val2: str) -> bool:
    """
    Prevents timing attacks.
    """
    return hmac.compare_digest(val1, val2)


def require_login():
    """
    Enforce login across pages.
    """
    if not st.session_state.get("authenticated", False):
        st.warning("Please log in")
        st.stop()
