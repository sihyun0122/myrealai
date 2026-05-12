import streamlit as st
import anthropic
import time
import hashlib
from datetime import datetime

from auth import (
    get_google_auth_url, handle_oauth_callback,
    is_logged_in, get_current_user, logout,
)
from database import (
    upsert_user, save_message, load_conversations,
    get_user_sessions, delete_session, get_usage_stats,
    save_tuning, load_tuning, delete_tuning,
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
# Apple-style CSS
# ==============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    
    .stApp {
        background: #f5f5f7;
    }

    /* ── 헤더 ── */
    .top-bar {
        background: rgba(255,255,255,0.72);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 0.5px solid rgba(0,0,0,0.08);
        padding: 0.7rem 1.5rem;
        margin: -1rem -1rem 1rem -1rem;
        display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        position: sticky; top: 0; z-index: 100;
    }
    .top-bar .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: linear-gradient(135deg, #ff6b35, #f7418f);
    }
    .top-bar .name {
        font-size: 0.9rem; font-weight: 600; color: #1d1d1f;
        letter-spacing: -0.01em;
    }
    .top-bar .info {
        font-size: 0.72rem; color: #86868b; margin-left: 0.3rem;
    }

    /* ── 환영 화면 ── */
    .welcome {
        text-align: center;
        padding: 5rem 2rem 3rem;
    }
    .welcome .icon-wrap {
        width: 80px; height: 80px;
        background: linear-gradient(135deg, #ff6b35, #f7418f);
        border-radius: 22px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 2.2rem; color: #fff;
        margin-bottom: 1.5rem;
        box-shadow: 0 12px 40px rgba(255,107,53,0.25);
    }
    .welcome h2 {
        color: #1d1d1f; font-size: 2rem; font-weight: 700;
        letter-spacing: -0.03em; margin-bottom: 0.3rem;
    }
    .welcome p {
        color: #86868b; font-size: 1rem; font-weight: 400;
        margin-bottom: 2rem;
    }
    .chips {
        display: flex; flex-wrap: wrap; justify-content: center;
        gap: 0.5rem; max-width: 480px; margin: 0 auto 1.5rem;
    }
    .chips .c {
        background: #ffffff; border: 1px solid #d2d2d7;
        color: #1d1d1f; padding: 0.45rem 0.9rem;
        border-radius: 980px; font-size: 0.82rem; font-weight: 500;
        transition: all 0.2s;
    }
    .chips .c:hover { background: #f5f5f7; }

    .cmd-box {
        background: #ffffff;
        border: 1px solid #d2d2d7;
        border-radius: 16px;
        padding: 1rem 1.3rem;
        max-width: 400px;
        margin: 0 auto;
        text-align: left;
    }
    .cmd-box h4 {
        color: #1d1d1f; font-size: 0.82rem; font-weight: 600;
        margin: 0 0 0.6rem; letter-spacing: -0.01em;
    }
    .cmd-row {
        display: flex; align-items: center; gap: 0.5rem;
        margin-bottom: 0.35rem;
    }
    .cmd-tag {
        background: #f5f5f7; color: #1d1d1f;
        padding: 0.15rem 0.5rem; border-radius: 6px;
        font-size: 0.75rem; font-weight: 600;
        font-family: 'SF Mono', monospace;
        white-space: nowrap;
    }
    .cmd-desc { color: #86868b; font-size: 0.78rem; }

    /* ── 채팅 ── */
    .chat-area {
        max-width: 780px;
        margin: 0 auto;
        padding: 0 0.5rem;
    }

    .u-wrap {
        display: flex; justify-content: flex-end;
        margin-bottom: 0.6rem;
    }
    .u-bubble {
        background: #007aff;
        color: #fff;
        padding: 0.6rem 1rem;
        border-radius: 18px 18px 4px 18px;
        max-width: 70%;
        font-size: 0.88rem;
        line-height: 1.55;
        word-break: break-word;
        font-weight: 400;
    }

    .a-wrap {
        display: flex; justify-content: flex-start;
        margin-bottom: 0.6rem;
        align-items: flex-start;
    }
    .a-icon {
        width: 28px; height: 28px;
        background: linear-gradient(135deg, #ff6b35, #f7418f);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.7rem; color: #fff; font-weight: 700;
        margin-right: 0.5rem; flex-shrink: 0; margin-top: 0.1rem;
    }
    .a-bubble {
        background: #ffffff;
        border: 0.5px solid #d2d2d7;
        color: #1d1d1f;
        padding: 0.6rem 1rem;
        border-radius: 18px 18px 18px 4px;
        max-width: 78%;
        font-size: 0.88rem;
        line-height: 1.7;
        word-break: break-word;
        font-weight: 400;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .a-bubble code {
        background: #f5f5f7; padding: 0.1rem 0.3rem;
        border-radius: 4px; font-size: 0.82rem; color: #e73c3e;
    }
    .a-bubble pre {
        background: #1d1d1f; color: #f5f5f7;
        padding: 0.8rem; border-radius: 10px;
        overflow-x: auto; margin: 0.5rem 0; font-size: 0.8rem;
    }

    /* 시스템 메시지 */
    .sys-msg { text-align: center; margin: 0.5rem 0; }
    .sys-ok {
        display: inline-block;
        background: #e8faf0; color: #1a7f37;
        padding: 0.3rem 0.8rem; border-radius: 980px;
        font-size: 0.78rem; font-weight: 600;
    }
    .sys-del {
        display: inline-block;
        background: #fef1f1; color: #d1242f;
        padding: 0.3rem 0.8rem; border-radius: 980px;
        font-size: 0.78rem; font-weight: 600;
    }
    .sys-info {
        display: inline-block;
        background: #eef6ff; color: #0969da;
        padding: 0.3rem 0.8rem; border-radius: 980px;
        font-size: 0.78rem; font-weight: 600;
    }

    /* 사용량 */
    .usage {
        display: flex; gap: 1rem; justify-content: center;
        padding: 0.3rem 0;
    }
    .usage .t { color: #86868b; font-size: 0.7rem; }
    .usage .t b { color: #6e6e73; font-weight: 600; }

    /* 파일 칩 */
    .f-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.3rem; }
    .f-chip {
        background: #fff; border: 1px solid #d2d2d7; color: #1d1d1f;
        padding: 0.2rem 0.5rem; border-radius: 8px;
        font-size: 0.72rem; font-weight: 500;
    }

    /* ── 로그인 ── */
    .login-card {
        max-width: 360px; margin: 7rem auto;
        background: #ffffff;
        border: 1px solid #d2d2d7;
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06);
    }
    .login-card .logo {
        width: 56px; height: 56px;
        background: linear-gradient(135deg, #ff6b35, #f7418f);
        border-radius: 16px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.5rem; color: #fff; margin-bottom: 1rem;
    }
    .login-card h2 {
        color: #1d1d1f; font-size: 1.4rem; font-weight: 700;
        letter-spacing: -0.02em; margin-bottom: 0.2rem;
    }
    .login-card p { color: #86868b; font-size: 0.85rem; margin-bottom: 1.5rem; }
    .g-btn {
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: #1d1d1f; color: #fff;
        padding: 0.7rem 1.8rem; border-radius: 980px;
        text-decoration: none; font-weight: 600; font-size: 0.88rem;
        transition: all 0.2s;
    }
    .g-btn:hover { background: #424245; color: #fff; }
    .or-text { color: #86868b; font-size: 0.78rem; margin: 1rem 0 0; }

    /* ── 사이드바 ── */
    section[data-testid="stSidebar"] {
        background: rgba(255,255,255,0.72);
        backdrop-filter: blur(20px);
        border-right: 0.5px solid rgba(0,0,0,0.08);
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #1d1d1f; }
    section[data-testid="stSidebar"] hr { border-color: #e5e5ea; }

    .pref-tag {
        display: inline-block;
        background: #f5f5f7; color: #1d1d1f;
        padding: 0.2rem 0.55rem; border-radius: 6px;
        font-size: 0.73rem; font-weight: 500; margin: 0.1rem;
        border: 0.5px solid #d2d2d7;
    }

    .stat-card {
        background: #ffffff; border: 0.5px solid #d2d2d7;
        border-radius: 12px; padding: 0.7rem 0.8rem;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 0.2rem 0; }
    .stat-l { color: #86868b; font-size: 0.75rem; }
    .stat-v { color: #1d1d1f; font-size: 0.75rem; font-weight: 600; }

    /* ── 버튼 스타일 ── */
    .stButton > button {
        border-radius: 980px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        transition: all 0.2s !important;
    }

    /* ── 입력창 ── */
    .stTextArea textarea {
        background: #ffffff !important;
        border: 0.5px solid #d2d2d7 !important;
        border-radius: 14px !important;
        color: #1d1d1f !important;
        font-size: 0.9rem !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    .stTextArea textarea:focus {
        border-color: #007aff !important;
        box-shadow: 0 0 0 3px rgba(0,122,255,0.15) !important;
    }
    .stTextArea textarea::placeholder { color: #aeaeb2 !important; }

    hr { border-color: #e5e5ea; }
    .footer { text-align: center; color: #aeaeb2; font-size: 0.68rem; padding: 0.5rem 0 1rem; }

    /* 스크롤바 */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-thumb { background: #d2d2d7; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# API
# ==============================================================
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("⚠️ ANTHROPIC_API_KEY를 Secrets에 등록해주세요.")
    st.stop()

MODEL_OPTIONS = {
    "Sonnet 4.6 ⚡": "claude-sonnet-4-6",
    "Opus 4.7 🧠": "claude-opus-4-7",
}
MODEL_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
}


# ==============================================================
# 설정 → 시스템 프롬프트
# ==============================================================
def build_user_system_prompt(uid):
    data = load_tuning(uid, "user_preference")
    if not data:
        return ""
    parts = ["[사용자가 설정한 지시사항 - 반드시 모든 답변에 적용]"]
    for item in data:
        parts.append(f"- {item['value']}")
    return "\n".join(parts)


# ==============================================================
# 명령어 처리
# ==============================================================
def handle_command(uid, text):
    s = text.strip()

    if s.startswith("/저장 ") or s.startswith("/저장\n"):
        content = s[3:].strip()
        if not content:
            return True, "빈 내용은 저장할 수 없어요.", "info"
        key = hashlib.md5(content.encode()).hexdigest()[:10]
        save_tuning(uid, "user_preference", key, content)
        return True, f"✅ 저장됨 — {content}", "ok"

    if s == "/목록":
        data = load_tuning(uid, "user_preference")
        if not data:
            return True, "저장된 설정이 없습니다.", "info"
        lines = ["📋 설정 목록\n"]
        for i, item in enumerate(data, 1):
            lines.append(f"{i}. {item['value']}")
        lines.append(f"\n총 {len(data)}개")
        return True, "\n".join(lines), "info"

    if s.startswith("/삭제 "):
        arg = s[3:].strip()
        data = load_tuning(uid, "user_preference")
        try:
            idx = int(arg) - 1
            if 0 <= idx < len(data):
                d = data[idx]
                delete_tuning(uid, "user_preference", d["key"])
                return True, f"🗑 삭제됨 — {d['value']}", "del"
            return True, f"1~{len(data)} 사이 번호를 입력하세요.", "info"
        except ValueError:
            for item in data:
                if arg in item["value"]:
                    delete_tuning(uid, "user_preference", item["key"])
                    return True, f"🗑 삭제됨 — {item['value']}", "del"
            return True, "해당 설정을 찾을 수 없어요.", "info"

    if s == "/초기화":
        data = load_tuning(uid, "user_preference")
        for item in data:
            delete_tuning(uid, "user_preference", item["key"])
        return True, f"🔄 {len(data)}개 설정 초기화 완료", "del"

    if s in ["/도움말", "/help", "/?"]:
        return True, """**명령어 안내**

`/저장 내용` — 설정 저장
`/목록` — 설정 보기
`/삭제 번호` — 삭제
`/초기화` — 전체 삭제
`/도움말` — 이 안내""", "info"

    return False, None, None


# ==============================================================
# 인증
# ==============================================================
handle_oauth_callback()

if not is_logged_in():
    auth_url = get_google_auth_url()
    if not auth_url:
        st.session_state["user"] = {"id": "guest", "email": "guest", "name": "사용자", "picture": ""}
        st.rerun()
    else:
        st.markdown(f"""
        <div class="login-card">
            <div class="logo">✦</div>
            <h2>Claude AI</h2>
            <p>로그인하면 대화와 설정이 저장됩니다</p>
            <a href="{auth_url}" class="g-btn">Google로 계속하기 →</a>
            <div class="or-text">또는</div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.3, 1, 1.3])
        with c2:
            if st.button("게스트로 시작", use_container_width=True):
                st.session_state["user"] = {"id": "guest", "email": "guest", "name": "사용자", "picture": ""}
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
    st.session_state.input_key = 0
    st.session_state.app_init = True

for k, v in {"messages": [], "last_usage": None, "input_key": 0}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================
# 사이드바
# ==============================================================
with st.sidebar:
    if upic:
        st.image(upic, width=32)
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

    if st.button("✦ 새 대화", use_container_width=True, type="primary"):
        st.session_state.current_session = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages = []
        st.session_state.last_usage = None
        st.rerun()

    st.markdown("---")

    st.markdown("**설정**")
    user_prefs = load_tuning(uid, "user_preference")
    if user_prefs:
        for i, item in enumerate(user_prefs, 1):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'<span class="pref-tag">{item["value"]}</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"dp_{item['key']}"):
                    delete_tuning(uid, "user_preference", item["key"])
                    st.rerun()
    else:
        st.caption("/저장 내용 으로 추가")

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
            if is_cur:
                st.markdown(f"● **{sess}**")
            else:
                if st.button(sess, key=f"s_{sess}", use_container_width=True):
                    st.session_state.current_session = sess
                    saved = load_conversations(uid, sess)
                    st.session_state.messages = [
                        {"role": m["role"], "content": m["content"],
                         "display": m["content"], "msg_type": "normal"} for m in saved
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
    stats = get_usage_stats(uid)
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-row"><span class="stat-l">대화</span><span class="stat-v">{stats['total_messages']}회</span></div>
        <div class="stat-row"><span class="stat-l">입력</span><span class="stat-v">{stats['total_input']:,}</span></div>
        <div class="stat-row"><span class="stat-l">출력</span><span class="stat-v">{stats['total_output']:,}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================
# 헤더
# ==============================================================
st.markdown(f"""
<div class="top-bar">
    <div class="dot"></div>
    <span class="name">Claude AI</span>
    <span class="info">{st.session_state.current_session} · {sel_label}</span>
</div>
""", unsafe_allow_html=True)

# ==============================================================
# 대화 표시
# ==============================================================
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome">
        <div class="icon-wrap">✦</div>
        <h2>무엇이든 물어보세요</h2>
        <p>Claude AI가 도와드립니다</p>
        <div class="chips">
            <div class="c">💬 대화</div>
            <div class="c">💻 코딩</div>
            <div class="c">📝 글쓰기</div>
            <div class="c">🌐 번역</div>
            <div class="c">📊 분석</div>
            <div class="c">📄 요약</div>
        </div>
        <div class="cmd-box">
            <h4>⌘ 명령어</h4>
            <div class="cmd-row"><span class="cmd-tag">/저장 내용</span><span class="cmd-desc">설정 저장</span></div>
            <div class="cmd-row"><span class="cmd-tag">/목록</span><span class="cmd-desc">설정 보기</span></div>
            <div class="cmd-row"><span class="cmd-tag">/삭제 번호</span><span class="cmd-desc">설정 삭제</span></div>
            <div class="cmd-row"><span class="cmd-tag">/초기화</span><span class="cmd-desc">전체 삭제</span></div>
            <div class="cmd-row"><span class="cmd-tag">/도움말</span><span class="cmd-desc">안내 보기</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown('<div class="chat-area">', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        mt = msg.get("msg_type", "normal")
        if msg["role"] == "user":
            d = msg.get("display", msg["content"])
            st.markdown(f'<div class="u-wrap"><div class="u-bubble">{d[:2000]}</div></div>', unsafe_allow_html=True)
        elif mt == "ok":
            st.markdown(f'<div class="sys-msg"><span class="sys-ok">{msg["content"]}</span></div>', unsafe_allow_html=True)
        elif mt == "del":
            st.markdown(f'<div class="sys-msg"><span class="sys-del">{msg["content"]}</span></div>', unsafe_allow_html=True)
        elif mt == "info":
            st.markdown(f'<div class="sys-msg"><span class="sys-info">{msg["content"]}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="a-wrap"><div class="a-icon">✦</div>'
                f'<div class="a-bubble">{msg["content"]}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.last_usage:
    u = st.session_state.last_usage
    st.markdown(f"""
    <div class="usage">
        <div class="t">입력 <b>{u['input']:,}</b></div>
        <div class="t">출력 <b>{u['output']:,}</b></div>
        <div class="t"><b>{u['time']:.1f}s</b></div>
        <div class="t"><b>${u['cost']:.4f}</b></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================
# 입력 (자동 초기화)
# ==============================================================
st.markdown("---")

uploaded_files = st.file_uploader(
    "파일",
    type=["jpg","jpeg","png","gif","webp","pdf","docx","xlsx",
          "txt","csv","md","json","py","js","html","css","java","c","cpp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)
if uploaded_files:
    chips = "".join(f'<span class="f-chip">📎 {f.name}</span>' for f in uploaded_files)
    st.markdown(f'<div class="f-chips">{chips}</div>', unsafe_allow_html=True)

col_in, col_btn = st.columns([6, 1])
with col_in:
    question = st.text_area(
        "입력",
        placeholder="메시지를 입력하세요... ( /도움말 )",
        height=68,
        label_visibility="collapsed",
        key=f"input_{st.session_state.input_key}",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    send = st.button("↑", use_container_width=True, type="primary")

# ==============================================================
# 전송
# ==============================================================
if send and (question.strip() or uploaded_files):

    # ── 명령어 ──
    if question.strip().startswith("/"):
        is_cmd, resp, mtype = handle_command(uid, question)
        if is_cmd:
            st.session_state.messages.append(
                {"role": "user", "content": question, "display": question, "msg_type": "normal"})
            st.session_state.messages.append(
                {"role": "assistant", "content": resp, "display": resp, "msg_type": mtype})
            save_message(uid, "user", question, "", 0, 0, st.session_state.current_session)
            save_message(uid, "assistant", resp, "", 0, 0, st.session_state.current_session)
            st.session_state.input_key += 1
            st.rerun()

    # ── 일반 대화 ──
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

    st.session_state.messages.append(
        {"role": "user", "content": combined, "display": display, "msg_type": "normal"})

    api_msgs = []
    for i, m in enumerate(st.session_state.messages):
        if m.get("msg_type", "normal") in ("ok", "del", "info"):
            continue
        if i == len(st.session_state.messages) - 1 and m["role"] == "user":
            api_msgs.append({"role": "user", "content": content_blocks})
        else:
            api_msgs.append({"role": m["role"], "content": m["content"]})

    system_prompt = build_user_system_prompt(uid)

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        start = time.time()

        placeholder = st.empty()
        full = ""

        kw = {"model": sel_model, "max_tokens": 16384, "messages": api_msgs}
        if system_prompt.strip():
            kw["system"] = system_prompt

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with client.messages.stream(**kw) as stream:
                    for text in stream.text_stream:
                        full += text
                        placeholder.markdown(
                            f'<div class="chat-area"><div class="a-wrap"><div class="a-icon">✦</div>'
                            f'<div class="a-bubble">{full}▌</div></div></div>',
                            unsafe_allow_html=True,
                        )
                break
            except anthropic.APIStatusError as e:
                if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                    st.warning(f"⏳ 재시도 중... ({attempt+2}/{max_retries})")
                    time.sleep(3)
                    full = ""
                else:
                    raise e

        elapsed = time.time() - start
        final = stream.get_final_message()
        inp = final.usage.input_tokens
        out = final.usage.output_tokens
        cost = (inp * pricing["input"] / 1e6) + (out * pricing["output"] / 1e6)

        st.session_state.messages.append(
            {"role": "assistant", "content": full, "display": full, "msg_type": "normal"})
        st.session_state.last_usage = {"input": inp, "output": out, "time": elapsed, "cost": cost}

        save_message(uid, "user", display or "[파일]", sel_model, 0, 0, st.session_state.current_session)
        save_message(uid, "assistant", full, sel_model, inp, out, st.session_state.current_session)

        st.session_state.input_key += 1
        st.rerun()

    except anthropic.AuthenticationError:
        st.error("❌ API 키 오류")
    except anthropic.RateLimitError:
        st.error("⏳ 한도 초과")
    except Exception as e:
        st.error(f"❌ {e}")

elif send:
    st.warning("메시지를 입력해주세요")

st.markdown('<div class="footer">Claude AI · Anthropic · Supabase · Streamlit</div>', unsafe_allow_html=True)
