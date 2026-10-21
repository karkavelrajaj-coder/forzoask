"""Simple login: one username and password, set in Streamlit secrets.

    APP_USERNAME = "Forzo"
    APP_PASSWORD = "Forzo123"
Both must match exactly (case-sensitive).
"""
from __future__ import annotations

import hmac
import time

import streamlit as st

MAX_ATTEMPTS = 5
LOCK_SECONDS = 60


def _credentials() -> tuple[str, str]:
    try:
        return str(st.secrets.get("APP_USERNAME", "")), str(st.secrets.get("APP_PASSWORD", ""))
    except Exception:
        return "", ""


def check_login(username: str, password: str) -> bool:
    expected_user, expected_password = _credentials()
    if not expected_user or not expected_password:
        return False
    user_ok = hmac.compare_digest(username, expected_user)  # exact, case-sensitive
    password_ok = hmac.compare_digest(password, expected_password)
    return user_ok and password_ok


def login_gate(render_header) -> str | None:
    """Show the login screen until the user signs in. Returns the username."""
    if st.session_state.get("user"):
        return st.session_state["user"]

    expected_user, expected_password = _credentials()
    render_header()
    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        st.markdown("#### Sign in")
        if not expected_user or not expected_password:
            st.error("Login is not set up. Add APP_USERNAME and APP_PASSWORD in Streamlit secrets.")
            return None

        locked_until = st.session_state.get("locked_until", 0)
        if time.time() < locked_until:
            st.warning(f"Too many attempts. Try again in {int(locked_until - time.time())} seconds.")
            return None

        with st.form("login", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", width="stretch", type="primary")
        if submitted:
            if check_login(username, password):
                st.session_state["user"] = username
                st.session_state["attempts"] = 0
                st.rerun()
            else:
                st.session_state["attempts"] = st.session_state.get("attempts", 0) + 1
                if st.session_state["attempts"] >= MAX_ATTEMPTS:
                    st.session_state["locked_until"] = time.time() + LOCK_SECONDS
                    st.session_state["attempts"] = 0
                st.error("Wrong username or password.")
        st.caption("Internal tool for the Forzo Techlabs marketing team.")
    return None


def logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
