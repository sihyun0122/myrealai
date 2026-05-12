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
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================
# 밝은 테마 CSS
# ==============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .stApp {
        background: #ffffff;
    }

    /* ── 헤더 ── */
    .header-bar {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-bottom: 1px solid #dee2e6;
        padding: 0.8rem 1.5rem;
        border-radius: 0 0 16px 16px;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.6rem;
    }
    .header-bar .logo {
        width: 32px; height: 32px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-weight: 800; font-size: 1rem;
    }
    .header-bar .title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #212529;
    }
    .header-bar .sub {
        font-size: 0.75rem;
        color: #868e96;
        margin-left: 0.5rem;
    }

    /* ── 환영 화면 ── */
    .welcome-screen {
        text-align: center;
        padding: 4rem 2rem 2rem;
    }
    .welcome-screen .big-icon {
        width: 72px; height: 72px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 20px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 2rem; color: #fff;
        margin-bottom: 1.2rem;
        box-shadow: 0 8px 24px rgba(232,89,12,0.2);
    }
    .welcome-screen h2 {
        color: #212529;
        font-size: 1.6rem;
        font-weight: 800;
        margin-bottom: 0.4rem;
    }
    .welcome-screen p {
        color: #868e96;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .welcome-chips {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 0.5rem;
        max-width: 500px;
        margin: 0 auto;
    }
    .welcome-chips .chip {
        background: #f1f3f5;
        border: 1px solid #dee2e6;
        color: #495057;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* ── 채팅 말풍선 ── */
    .chat-wrap {
        max-width: 820px;
        margin: 0 auto;
        padding: 0 0.5rem;
    }

    .msg-user-wrap {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 0.8rem;
    }
    .msg-user-bubble {
        background: #E8590C;
        color: #ffffff;
        padding: 0.7rem 1.1rem;
        border-radius: 16px 16px 4px 16px;
        max-width: 70%;
        font-size: 0.9rem;
        line-height: 1.6;
        word-break: break-word;
        box-shadow: 0 2px 8px rgba(232,89,12,0.15);
    }

    .msg-ai-wrap {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 0.8rem;
        align-items: flex-start;
    }
    .msg-ai-avatar {
        width: 30px; height: 30px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.75rem; color: #fff; font-weight: 800;
        margin-right: 0.6rem; flex-shrink: 0; margin-top: 0.15rem;
    }
    .msg-ai-bubble {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        color: #212529;
        padding: 0.7rem 1.1rem;
        border-radius: 16px 16px 16px 4px;
        max-width: 78%;
        font-size: 0.9rem;
        line-height: 1.8;
        word-break: break-word;
    }
    .msg-ai-bubble code {
        background: #e9ecef;
        padding: 0.1rem 0.3rem;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #c92a2a;
    }
    .msg-ai-bubble pre {
        background: #212529;
        color: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        overflow-x: auto;
        margin: 0.5rem 0;
        font-size: 0.82rem;
    }

    /* ── 사용량 바 ── */
    .usage-strip {
        display: flex;
        gap: 1.2rem;
        justify-content: center;
        padding: 0.4rem 0;
        margin-bottom: 0.5rem;
    }
    .usage-strip .item {
        color: #adb5bd;
        font-size: 0.72rem;
        font-weight: 500;
    }
    .usage-strip .item span {
        color: #868e96;
        font-weight: 700;
    }

    /* ── 입력 영역 ── */
    .input-section {
        max-width: 820px;
        margin: 0 auto;
    }

    /* ── 파일 뱃지 ── */
    .file-chips {
        display: flex; flex-wrap: wrap; gap: 0.3rem;
        margin-bottom: 0.4rem;
    }
    .file-chip {
        background: #fff4e6;
        border: 1px solid #ffe8cc;
        color: #E8590C;
        padding: 0.2rem 0.6rem;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* ── 로그인 ── */
    .login-screen {
        max-width: 380px;
        margin: 6rem auto;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
    }
    .login-screen .icon-box {
        width: 56px; height: 56px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 16px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.5rem; color: #fff;
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(232,89,12,0.2);
    }
    .login-screen h2 {
        color: #212529; font-size: 1.3rem;
        font-weight: 800; margin-bottom: 0.3rem;
    }
    .login-screen p {
        color: #868e96; font-size: 0.88rem; margin-bottom: 1.5rem;
    }
    .google-login-btn {
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: #ffffff; color: #333;
        padding: 0.7rem 1.8rem;
        border-radius: 12px; border: 1px solid #dee2e6;
        text-decoration: none;
        font-weight: 700; font-size: 0.9rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: all 0.2s;
    }
    .google-login-btn:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-color: #adb5bd;
    }
    .guest-text {
        color: #adb5bd; font-size: 0.8rem; margin-top: 1rem;
    }

    /* ── 사이드바 ── */
    section[data-testid="stSidebar"] {
        background: #f8f9fa;
        border-right: 1px solid #e9ecef;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #495057;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #e9ecef;
    }

    /* ── 사이드바 프로필 ── */
    .sb-profile {
        display: flex; align-items: center; gap: 0.6rem;
        padding: 0.5rem 0;
    }
    .sb-profile img {
        width: 36px; height: 36px; border-radius: 50%;
    }
    .sb-profile .name {
        font-weight: 700; color: #212529; font-size: 0.9rem;
    }
    .sb-profile .email {
        font-size: 0.72rem; color: #adb5bd;
    }

    /* ── 사이드바 세션 버튼 ── */
    .sb-session {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 0.5rem 0.8rem;
        margin-bottom: 0.35rem;
        color: #495057;
        font-size: 0.82rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s;
    }
    .sb-session:hover {
        background: #fff4e6;
        border-color: #ffe8cc;
        color: #E8590C;
    }
    .sb-session-active {
        background: #fff4e6 !important;
        border-color: #E8590C !important;
        color: #E8590C !important;
        font-weight: 700 !important;
    }

    /* ── 사이드바 통계 ── */
    .sb-stats {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 0.8rem;
    }
    .sb-stats .row {
        display: flex; justify-content: space-between;
        padding: 0.25rem 0;
    }
    .sb-stats .label { color: #868e96; font-size: 0.78rem; }
    .sb-stats .val { color: #212529; font-size: 0.78rem; font-weight: 700; }

    /* ── 버튼 ── */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* ── 텍스트 입력 ── */
    .stTextArea textarea {
        background: #f8f9fa !important;
        border: 1px solid #dee2e6 !important;
        border-radius: 12px !important;
        color: #212529 !important;
        font-size: 0.9rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #E8590C !important;
        box-shadow: 0 0 0 2px rgba(232,89,12,0.1) !important;
    }
    .stTextArea textarea::placeholder {
        color: #adb5bd !important;
    }

    /* 일반 구분선 */
    hr { border-color: #e9ecef; }

    /* 하단 */
    .footer-text {
        text-align: center;
        color: #ced4da;
        font-size: 0.7rem;
        padding: 0.5rem 0 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# API 키
# ==============================================================
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("⚠️ ANTHROPIC_API_KEY를 Secrets에 등록해주세요.")
    st.stop()

MODEL_OPTIONS = {
    "Sonnet 4.6 ⚡ 빠른 응답": "claude-sonnet-4-6",
    "Opus 4.7 🚀 최고 성능": "claude-opus-4-7",
}
MODEL_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
}

# ==============================================================
# 인증
# ==============================================================
handle_oauth_callback()

if not is_logged_in():
    auth_url = get_google_auth_url()

    if not auth_url:
        st.session_state["user"] = {
            "id": "guest", "email": "guest",
            "name": "사용자", "picture": "",
        }
        st.rerun()
    else:
        st.markdown(f"""
        <div class="login-screen">
            <div class="icon-box">✦</div>
            <h2>Claude AI</h2>
            <p>로그인하면 대화가 자동 저장됩니다</p>
            <a href="{auth_url}" class="google-login-btn">
                <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/><path fill="#FBBC05" d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71s.102-1.17.282-1.71V4.958H.957C.347 6.173 0 7.548 0 9s.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/></svg>
                Google로 시작하기
            </a>
            <div class="guest-text">또는</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1.2, 1, 1.2])
        with c2:
            if st.button("로그인 없이 사용하기", use_container_width=True):
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
    st.session_state.current_session = datetime.now().strftime("%Y-%m-%d %H:%M")
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
    # 프로필
    if upic:
        st.markdown(f"""
        <div class="sb-profile">
            <img src="{upic}">
            <div>
                <div class="name">{uname}</div>
                <div class="email">{user['email']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"**👤 {uname}**")

    if uid != "guest":
        if st.button("로그아웃", use_container_width=True):
            logout()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    st.markdown("---")

    # 모델 선택
    st.markdown("**🧠 AI 모델**")
    sel_label = st.selectbox("모델", list(MODEL_OPTIONS.keys()),
                              index=0, label_visibility="collapsed")
    sel_model = MODEL_OPTIONS[sel_label]
    pricing = MODEL_PRICING[sel_model]

    if "sonnet" in sel_model:
        st.caption("⚡ 빠른 응답 · 저렴한 비용")
    else:
        st.caption("🧠 최고 품질 · 복잡한 작업에 적합")

    st.markdown("---")

    # 새 대화
    if st.button("✨ 새 대화 시작", use_container_width=True, type="primary"):
        st.session_state.current_session = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages = []
        st.session_state.last_usage = None
        st.rerun()

    st.markdown("---")

    # 대화 기록
    st.markdown("**📂 대화 기록**")

    sessions = get_user_sessions(uid)
    if st.session_state.current_session not in sessions:
        sessions.append(st.session_state.current_session)
    sessions.sort(reverse=True)

    if not sessions:
        st.caption("아직 대화가 없습니다")
    else:
        for sess in sessions:
            is_cur = sess == st.session_state.current_session
            c1, c2 = st.columns([5, 1])
            with c1:
                if is_cur:
                    st.markdown(f'<div class="sb-session sb-session-active">💬 {sess}</div>',
                                unsafe_allow_html=True)
                else:
                    if st.button(f"📝 {sess}", key=f"s_{sess}", use_container_width=True):
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
                        st.session_state.current_session = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.session_state.messages = []
                    st.rerun()

    st.markdown("---")

    # 사용량 통계
    st.markdown("**📊 사용량**")
    stats = get_usage_stats(uid)
    st.markdown(f"""
    <div class="sb-stats">
        <div class="row">
            <span class="label">총 대화</span>
            <span class="val">{stats['total_messages']}회</span>
        </div>
        <div class="row">
            <span class="label">입력 토큰</span>
            <span class="val">{stats['total_input']:,}</span>
        </div>
        <div class="row">
            <span class="label">출력 토큰</span>
            <span class="val">{stats['total_output']:,}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 기능 안내
    with st.expander("ℹ️ 기능 안내"):
        st.markdown("""
        **🤖 AI 대화**
        Claude API로 구동됩니다.
        어떤 질문이든 자유롭게 가능합니다.

        **⚡ 모델 선택**
        - **Sonnet 4**: 빠르고 저렴
        - **Opus 4**: 더 똑똑하고 정확

        **📎 파일 첨부**
        이미지, PDF, Word, Excel, 코드 등
        다양한 파일을 분석할 수 있습니다.

        **💾 대화 저장**
        Supabase DB에 자동 저장됩니다.
        이전 대화를 선택해서 이어할 수 있어요.

        **🔐 로그인**
        Google OAuth로 계정을 연동하면
        어디서든 내 대화 기록을 볼 수 있습니다.
        """)

# ==============================================================
# 메인 영역 - 헤더
# ==============================================================
st.markdown(f"""
<div class="header-bar">
    <div class="logo">✦</div>
    <span class="title">Claude AI</span>
    <span class="sub">{st.session_state.current_session} · {sel_label.split(' ')[0]} {sel_label.split(' ')[1]}</span>
</div>
""", unsafe_allow_html=True)

# ==============================================================
# 대화 표시
# ==============================================================
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-screen">
        <div class="big-icon">✦</div>
        <h2>무엇이든 물어보세요</h2>
        <p>Claude AI가 도와드립니다</p>
        <div class="welcome-chips">
            <div class="chip">💡 아이디어 브레인스토밍</div>
            <div class="chip">📝 글쓰기 도움</div>
            <div class="chip">💻 코드 작성</div>
            <div class="chip">📊 데이터 분석</div>
            <div class="chip">🌐 번역</div>
            <div class="chip">📄 문서 요약</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            d = msg.get("display", msg["content"])
            st.markdown(f"""
            <div class="msg-user-wrap">
                <div class="msg-user-bubble">{d[:2000]}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="msg-ai-wrap">
                <div class="msg-ai-avatar">✦</div>
                <div class="msg-ai-bubble">{msg["content"]}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 사용량 바
if st.session_state.last_usage:
    u = st.session_state.last_usage
    st.markdown(f"""
    <div class="usage-strip">
        <div class="item">입력 <span>{u['input']:,}</span></div>
        <div class="item">출력 <span>{u['output']:,}</span></div>
        <div class="item">⏱ <span>{u['time']:.1f}s</span></div>
        <div class="item">💰 <span>${u['cost']:.4f}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================
# 입력 영역
# ==============================================================
st.markdown("---")
st.markdown('<div class="input-section">', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "파일 첨부",
    type=["jpg","jpeg","png","gif","webp","pdf","docx","xlsx",
          "txt","csv","md","json","py","js","html","css","java","c","cpp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    chips = "".join(f'<span class="file-chip">📎 {f.name}</span>' for f in uploaded_files)
    st.markdown(f'<div class="file-chips">{chips}</div>', unsafe_allow_html=True)

col_in, col_btn = st.columns([6, 1])
with col_in:
    question = st.text_area(
        "메시지",
        placeholder="메시지를 입력하세요...",
        height=72,
        label_visibility="collapsed",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    send = st.button("전송 ▶", use_container_width=True, type="primary")

st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================
# 전송 + 스트리밍
# ==============================================================
if send and (question.strip() or uploaded_files):

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
            text_parts.append(f"[첨부 파일]\n{extracted}")
    if question.strip():
        text_parts.append(question.strip())

    combined = "\n\n".join(text_parts) if text_parts else "첨부된 파일을 분석해주세요."
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
                    f'<div class="chat-wrap"><div class="msg-ai-wrap">'
                    f'<div class="msg-ai-avatar">✦</div>'
                    f'<div class="msg-ai-bubble">{full}▌</div>'
                    f'</div></div>',
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
        st.error("❌ API 키가 올바르지 않습니다. Secrets를 확인해주세요.")
    except anthropic.RateLimitError:
        st.error("⏳ API 호출 한도를 초과했습니다. 잠시 후 다시 시도하세요.")
    except Exception as e:
        st.error(f"❌ 오류가 발생했습니다: {e}")

elif send:
    st.warning("메시지를 입력하거나 파일을 첨부해주세요!")

# 하단
st.markdown("""
<div class="footer-text">
    Claude AI · Anthropic API · Supabase · Google OAuth · Streamlit Cloud
</div>
""", unsafe_allow_html=True)
