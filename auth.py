"""
auth.py
- Google OAuth 2.0 로그인 처리
"""

import streamlit as st
import requests
import json
import hashlib
import secrets
from urllib.parse import urlencode


def get_google_auth_url() -> str:
    """Google OAuth 인증 URL 생성"""
    try:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        redirect_uri = st.secrets["GOOGLE_REDIRECT_URI"]
    except Exception:
        return ""

    # CSRF 방지용 state 토큰
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
    """Authorization code를 access token으로 교환"""
    try:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
        redirect_uri = st.secrets["GOOGLE_REDIRECT_URI"]
    except Exception:
        return {}

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=data, timeout=10)
    if response.status_code == 200:
        return response.json()
    return {}


def get_user_info(access_token: str) -> dict:
    """Google API에서 사용자 정보 가져오기"""
    url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.json()
    return {}


def handle_oauth_callback():
    """
    URL 쿼리 파라미터에서 OAuth 콜백 처리
    """
    params = st.query_params
    code = params.get("code", "")
    state = params.get("state", "")

    if not code:
        return False

    # state 검증 (CSRF 방지)
    saved_state = st.session_state.get("oauth_state", "")
    if saved_state and state != saved_state:
        st.error("⚠️ 보안 검증 실패. 다시 로그인해주세요.")
        return False

    # 토큰 교환
    token_data = exchange_code_for_token(code)
    if not token_data:
        st.error("❌ 로그인 처리 실패. 다시 시도해주세요.")
        return False

    access_token = token_data.get("access_token", "")
    if not access_token:
        return False

    # 사용자 정보 가져오기
    user_info = get_user_info(access_token)
    if not user_info or "email" not in user_info:
        st.error("❌ 사용자 정보를 가져올 수 없습니다.")
        return False

    # 세션에 저장
    st.session_state["user"] = {
        "id": user_info.get("id", ""),
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
    }

    # URL에서 code 파라미터 제거
    st.query_params.clear()
    return True


def is_logged_in() -> bool:
    """로그인 상태 확인"""
    return "user" in st.session_state and st.session_state["user"] is not None


def get_current_user() -> dict:
    """현재 로그인 사용자"""
    return st.session_state.get("user", None)


def logout():
    """로그아웃"""
    for key in ["user", "oauth_state", "messages", "current_session"]:
        if key in st.session_state:
            del st.session_state[key]
