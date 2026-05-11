import streamlit as st
import requests
import secrets
from urllib.parse import urlencode


def get_google_auth_url() -> str:
    try:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        redirect_uri = st.secrets["GOOGLE_REDIRECT_URI"]
    except Exception:
        return ""

    state = secrets.token_urlsafe(32)
    st.session_state["oauth_state"] = state

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    try:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
        redirect_uri = st.secrets["GOOGLE_REDIRECT_URI"]
    except Exception:
        return {}

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
    return resp.json() if resp.status_code == 200 else {}


def get_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, timeout=10)
    return resp.json() if resp.status_code == 200 else {}


def handle_oauth_callback():
    params = st.query_params
    code = params.get("code", "")
    if not code:
        return False

    token_data = exchange_code_for_token(code)
    if not token_data:
        return False

    access_token = token_data.get("access_token", "")
    if not access_token:
        return False

    user_info = get_user_info(access_token)
    if not user_info or "email" not in user_info:
        return False

    st.session_state["user"] = {
        "id": user_info.get("id", ""),
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
    }
    st.query_params.clear()
    return True


def is_logged_in() -> bool:
    return "user" in st.session_state and st.session_state["user"] is not None


def get_current_user() -> dict:
    return st.session_state.get("user", None)


def logout():
    keys_to_remove = ["user", "oauth_state", "messages", "current_session",
                       "total_input", "total_output", "total_cost",
                       "tuning_profile", "tuning_preferences",
                       "tuning_knowledge", "tuning_instructions"]
    for k in keys_to_remove:
        if k in st.session_state:
            del st.session_state[k]
