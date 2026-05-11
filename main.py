import streamlit as st
import anthropic
import time
from datetime import datetime

from auth import (
    get_google_auth_url, handle_oauth_callback,
    is_logged_in, get_current_user, logout,
)
from database import (
    upsert_user, save_message, load_conversations,
    get_user_sessions, delete_session, get_usage_stats,
)
from file_handler import process_file, fmt_size, is_image

# ==============================================================
# 페이지 설정
# ==============================================================
st.set_page_config(
    page_title="Claude AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================
# CSS
# ==============================================================
st.markdown("""
<style>
    .stApp { background: #0d0d0d; }
    
    .app-header {
        text-align: center;
        padding: 0.5rem 0 0.2rem;
    }
    .app-header h1 {
        color: #d4d4d4;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
    }
    .app-header p {
        color: #555;
        font-size: 0.75rem;
        margin: 0;
    }

    .msg-user {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 0.7rem;
    }
    .msg-user .bubble {
        background: #1e1e1e;
        color: #e0e0e0;
        padding: 0.65rem 1rem;
        border-radius: 14px 14px 4px 14px;
        max-width: 70%;
        font-size: 0.9rem;
        line-height: 1.6;
        word-break: break-word;
        border: 1px solid #2a2a2a;
    }

    .msg-ai {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 0.7rem;
        align-items: flex-start;
    }
    .msg-ai .av {
        width: 26px; height: 26px;
        border-radius: 50%;
        background: #d97706;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.75rem; color: #fff; font-weight: 700;
        margin-right: 0.5rem; flex-shrink: 0; margin-top: 0.1rem;
    }
    .msg-ai .bubble {
        color: #d4d4d4;
        max-width: 80%;
        font-size: 0.9rem;
        line-height: 1.75;
        word-break: break-word;
    }

    .usage-bar {
        display: flex; gap: 1rem; justify-content: center;
        padding: 0.2rem 0;
    }
    .usage-bar .u { color: #444; font-size: 0.7rem; }
    .usage-bar .u span { color: #777; font-weight: 600; }

    .welcome {
        text-align: center; padding: 6rem 2rem 3rem;
    }
    .welcome h2 { color: #ccc; font-size: 1.4rem; font-weight: 600; }
    .welcome p { color: #555; font-size: 0.9rem; }

    .login-box {
        max-width: 360px; margin: 7rem auto;
        background: #141414; border: 1px solid #262626;
        border-radius: 18px; padding: 2.5rem 2rem; text-align: center;
    }
    .login-box h2 { color: #d4d4d4; font-size: 1.3rem; margin-bottom: 0.3rem; }
    .login-box p { color: #666; margin-bottom: 1.5rem; font-size: 0.9rem; }
    .g-btn {
        display: inline-block; background: #fff; color: #222;
        padding: 0.65rem 2rem; border-radius: 10px;
        text-decoration: none; font-weight: 700; font-size: 0.9rem;
    }

    section[data-testid="stSidebar"] {
        background: #0a0a0a; border-right: 1px solid #1a1a1a;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #bbb; }

    .stButton > button { border-radius: 8px; font-weight: 600; }

    .stTextArea textarea {
        background: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 10px !important;
        color: #d4d4d4 !important;
        font-size: 0.9rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #d97706 !important;
        box-shadow: none !important;
    }

    hr { border-color: #1a1a1a; }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# API
# ==============================================================
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("⚠️ ANTHROPIC_API_KEY 필요")
    st.stop()

MODEL_OPTIONS = {
    "Sonnet 4 ⚡": "claude-sonnet-4-20250514",
    "Opus 4 🧠": "claude-opus-4-20250514",
}
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}

# ==============================================================
# 자동 로그인 처리
# ==============================================================

# 1) OAuth 콜백 처리 (Google 로그인 후 돌아왔을 때)
handle_oauth_callback()

# 2) 자동 로그인: 로그인 안 되어있으면 자동으로 게스트 진입
#    Google 로그인이 설정되어 있으면 Google 로그인 시도
#    설정 안 되어있으면 바로 게스트로 들어감
if not is_logged_in():
    auth_url = get_google_auth_url()

    if not auth_url:
        # Google 미설정 → 자동 게스트 로그인
        st.session_state["user"] = {
            "id": "guest", "email": "guest",
            "name": "사용자", "picture": "",
        }
        st.rerun()
    else:
        # Google 설정됨 → 로그인 화면 표시
        st.markdown("""
        <div class="login-box">
            <h2>Claude AI</h2>
            <p>로그인하면 대화가 저장됩니다</p>
        """, unsafe_allow_html=True)

        st.markdown(f'<a href="{auth_url}" class="g-btn">🔐 Google 로그인</a>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # 게스트 옵션
        st.markdown("")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            if st.button("로그인 없이 시작", use_container_width=True):
                st.session_state["user"] = {
                    "id": "guest", "email": "guest",
                    "name": "사용자", "picture": "",
                }
                st.rerun()
        st.stop()

# ==============================================================
# 초기화
# ==============================================================
user = get_current_user()
uid, uname = user["id"], user["name"]
upic = user.get("picture", "")
upsert_user(uid, user["email"], uname, upic)

if "app_init" not in st.session_state:
    st.session_state.current_session = datetime.now().strftime("%m/%d %H:%M")
    st.session_state.messages = []
    st.session_state.last_usage = None
    st.session_state.app_init = True

for k, v in {"messages": [], "last_usage": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================
# 사이드바
# ==============================================================
with st.sidebar:
    if upic:
        st.image(upic, width=36)
    st.markdown(f"**{uname}**")

    if uid != "guest":
        if st.button("로그아웃", use_container_width=True):
            logout()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    st.markdown("---")

    sel_label = st.selectbox("모델", list(MODEL_OPTIONS.keys()), index=0)
    sel_model = MODEL_OPTIONS[sel_label]
    pricing = MODEL_PRICING[sel_model]

    st.markdown("---")

    if st.button("✨ 새 대화", use_container_width=True, type="primary"):
        st.session_state.current_session = datetime.now().strftime("%m/%d %H:%M:%S")
        st.session_state.messages = []
        st.session_state.last_usage = None
        st.rerun()

    st.markdown("---")
    st.markdown("**대화 기록**")

    sessions = get_user_sessions(uid)
    if st.session_state.current_session not in sessions:
        sessions.append(st.session_state.current_session)
    sessions.sort(reverse=True)

    for sess in sessions:
        is_cur = sess == st.session_state.current_session
        c1, c2 = st.columns([5, 1])
        with c1:
            label = f"● {sess}" if is_cur else sess
            if st.button(label, key=f"s_{sess}", use_container_width=True,
                         disabled=is_cur):
                st.session_state.current_session = sess
                saved = load_conversations(uid, sess)
                st.session_state.messages = [
                    {"role": m["role"], "content": m["content"],
                     "display": m["content"]} for m in saved
                ]
                st.session_state.last_usage = None
                st.rerun()
        with c2:
            if st.button("✕", key=f"d_{sess}"):
                delete_session(uid, sess)
                if is_cur:
                    st.session_state.current_session = datetime.now().strftime("%m/%d %H:%M:%S")
                    st.session_state.messages = []
                st.rerun()

    st.markdown("---")
    stats = get_usage_stats(uid)
    st.caption(f"입력 {stats['total_input']:,} · 출력 {stats['total_output']:,} · {stats['total_messages']}회")

# ==============================================================
# 헤더
# ==============================================================
st.markdown(f"""
<div class="app-header">
    <h1>Claude AI</h1>
    <p>{st.session_state.current_session} · {sel_label}</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================
# 대화 표시
# ==============================================================
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome">
        <h2>무엇이든 물어보세요</h2>
        <p>Claude가 도와드립니다</p>
    </div>
    """, unsafe_allow_html=True)
else:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            d = msg.get("display", msg["content"])
            st.markdown(f'<div class="msg-user"><div class="bubble">{d[:2000]}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="msg-ai"><div class="av">C</div><div class="bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)

if st.session_state.last_usage:
    u = st.session_state.last_usage
    st.markdown(f"""
    <div class="usage-bar">
        <div class="u">입력 <span>{u['input']:,}</span></div>
        <div class="u">출력 <span>{u['output']:,}</span></div>
        <div class="u"><span>{u['time']:.1f}s</span></div>
        <div class="u"><span>${u['cost']:.4f}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================
# 입력
# ==============================================================
st.markdown("---")

uploaded_files = st.file_uploader(
    "파일",
    type=["jpg","jpeg","png","gif","webp","pdf","docx","xlsx",
          "txt","csv","md","json","py","js","html","css"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)
if uploaded_files:
    st.caption(" · ".join(f"📎 {f.name}" for f in uploaded_files))

c_in, c_btn = st.columns([6, 1])
with c_in:
    question = st.text_area("입력", placeholder="메시지 입력...",
                             height=68, label_visibility="collapsed")
with c_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    send = st.button("▶", use_container_width=True, type="primary")

# ==============================================================
# 전송 + 스트리밍 응답
# ==============================================================
if send and (question.strip() or uploaded_files):

    # 파일
    file_results = []
    if uploaded_files:
        for f in uploaded_files:
            f.seek(0)
            file_results.append(process_file(f))

    content_blocks = []
    for block, _, _ in file_results:
        if block:
            content_blocks.append(block)

    text_parts = []
    for block, extracted, _ in file_results:
        if block is None and extracted:
            text_parts.append(f"[첨부]\n{extracted}")
    if question.strip():
        text_parts.append(question.strip())

    combined = "\n\n".join(text_parts) if text_parts else "파일을 분석해주세요."
    content_blocks.append({"type": "text", "text": combined})

    display = question.strip()
    if file_results:
        tags = ", ".join(r[2] for r in file_results)
        display = f"[{tags}] {display}" if display else f"[{tags}]"

    st.session_state.messages.append({
        "role": "user", "content": combined, "display": display,
    })

    api_msgs = []
    for i, m in enumerate(st.session_state.messages):
        if i == len(st.session_state.messages) - 1 and m["role"] == "user":
            api_msgs.append({"role": "user", "content": content_blocks})
        else:
            api_msgs.append({"role": m["role"], "content": m["content"]})

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        start = time.time()

        placeholder = st.empty()
        full = ""

        with client.messages.stream(
            model=sel_model,
            max_tokens=16384,
            messages=api_msgs,
        ) as stream:
            for text in stream.text_stream:
                full += text
                placeholder.markdown(
                    f'<div class="msg-ai"><div class="av">C</div>'
                    f'<div class="bubble">{full}▌</div></div>',
                    unsafe_allow_html=True,
                )

        elapsed = time.time() - start
        final = stream.get_final_message()
        inp = final.usage.input_tokens
        out = final.usage.output_tokens
        cost = (inp * pricing["input"] / 1e6) + (out * pricing["output"] / 1e6)

        st.session_state.messages.append({
            "role": "assistant", "content": full, "display": full,
        })
        st.session_state.last_usage = {
            "input": inp, "output": out, "time": elapsed, "cost": cost,
        }

        save_message(uid, "user", display or "[파일]",
                     sel_model, 0, 0, st.session_state.current_session)
        save_message(uid, "assistant", full,
                     sel_model, inp, out, st.session_state.current_session)

        st.rerun()

    except anthropic.AuthenticationError:
        st.error("❌ API 키 오류")
    except anthropic.RateLimitError:
        st.error("⏳ 한도 초과")
    except Exception as e:
        st.error(f"❌ {e}")

elif send:
    st.warning("메시지를 입력해주세요")
