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
# CSS
# ==============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: #ffffff; }

    .header-bar {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-bottom: 1px solid #dee2e6;
        padding: 0.8rem 1.5rem;
        border-radius: 0 0 16px 16px;
        margin-bottom: 1rem;
        display: flex; align-items: center; justify-content: center; gap: 0.6rem;
    }
    .header-bar .logo {
        width: 32px; height: 32px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-weight: 800; font-size: 1rem;
    }
    .header-bar .title { font-size: 1.1rem; font-weight: 700; color: #212529; }
    .header-bar .sub { font-size: 0.75rem; color: #868e96; margin-left: 0.5rem; }

    .welcome-screen { text-align: center; padding: 3rem 2rem 2rem; }
    .welcome-screen .big-icon {
        width: 72px; height: 72px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 20px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 2rem; color: #fff; margin-bottom: 1.2rem;
        box-shadow: 0 8px 24px rgba(232,89,12,0.2);
    }
    .welcome-screen h2 { color: #212529; font-size: 1.6rem; font-weight: 800; margin-bottom: 0.4rem; }
    .welcome-screen p { color: #868e96; font-size: 0.95rem; margin-bottom: 1rem; }
    .welcome-chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.5rem; max-width: 520px; margin: 0 auto; }
    .welcome-chips .chip {
        background: #f1f3f5; border: 1px solid #dee2e6; color: #495057;
        padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.85rem; font-weight: 500;
    }
    .cmd-guide {
        background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 14px;
        padding: 1rem 1.5rem; max-width: 480px; margin: 1.5rem auto 0;
        text-align: left;
    }
    .cmd-guide h4 { color: #495057; font-size: 0.88rem; margin: 0 0 0.5rem; }
    .cmd-row { display: flex; gap: 0.5rem; margin-bottom: 0.3rem; align-items: center; }
    .cmd-tag {
        background: #e7f5ff; border: 1px solid #a5d8ff; color: #1971c2;
        padding: 0.15rem 0.5rem; border-radius: 6px; font-size: 0.78rem;
        font-weight: 700; font-family: monospace; white-space: nowrap;
    }
    .cmd-desc { color: #868e96; font-size: 0.8rem; }

    .msg-user-wrap { display: flex; justify-content: flex-end; margin-bottom: 0.8rem; }
    .msg-user-bubble {
        background: #E8590C; color: #fff;
        padding: 0.7rem 1.1rem; border-radius: 16px 16px 4px 16px;
        max-width: 70%; font-size: 0.9rem; line-height: 1.6; word-break: break-word;
        box-shadow: 0 2px 8px rgba(232,89,12,0.15);
    }
    .msg-ai-wrap { display: flex; justify-content: flex-start; margin-bottom: 0.8rem; align-items: flex-start; }
    .msg-ai-avatar {
        width: 30px; height: 30px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.75rem; color: #fff; font-weight: 800;
        margin-right: 0.6rem; flex-shrink: 0; margin-top: 0.15rem;
    }
    .msg-ai-bubble {
        background: #f8f9fa; border: 1px solid #e9ecef; color: #212529;
        padding: 0.7rem 1.1rem; border-radius: 16px 16px 16px 4px;
        max-width: 78%; font-size: 0.9rem; line-height: 1.8; word-break: break-word;
    }

    .msg-system {
        text-align: center; margin: 0.5rem 0;
    }
    .msg-system .badge {
        display: inline-block;
        background: #d3f9d8; border: 1px solid #8ce99a; color: #2b8a3e;
        padding: 0.35rem 0.8rem; border-radius: 10px;
        font-size: 0.82rem; font-weight: 600;
    }
    .msg-system .badge-red {
        display: inline-block;
        background: #ffe3e3; border: 1px solid #ffa8a8; color: #c92a2a;
        padding: 0.35rem 0.8rem; border-radius: 10px;
        font-size: 0.82rem; font-weight: 600;
    }
    .msg-system .badge-blue {
        display: inline-block;
        background: #e7f5ff; border: 1px solid #a5d8ff; color: #1971c2;
        padding: 0.35rem 0.8rem; border-radius: 10px;
        font-size: 0.82rem; font-weight: 600;
    }

    .usage-strip { display: flex; gap: 1.2rem; justify-content: center; padding: 0.4rem 0; }
    .usage-strip .item { color: #adb5bd; font-size: 0.72rem; font-weight: 500; }
    .usage-strip .item span { color: #868e96; font-weight: 700; }

    .file-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.4rem; }
    .file-chip {
        background: #fff4e6; border: 1px solid #ffe8cc; color: #E8590C;
        padding: 0.2rem 0.6rem; border-radius: 8px; font-size: 0.75rem; font-weight: 600;
    }

    .login-screen {
        max-width: 380px; margin: 6rem auto; background: #f8f9fa;
        border: 1px solid #dee2e6; border-radius: 20px; padding: 2.5rem 2rem; text-align: center;
    }
    .login-screen .icon-box {
        width: 56px; height: 56px;
        background: linear-gradient(135deg, #E8590C, #D9480F);
        border-radius: 16px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.5rem; color: #fff; margin-bottom: 1rem;
    }
    .login-screen h2 { color: #212529; font-size: 1.3rem; font-weight: 800; }
    .login-screen p { color: #868e96; font-size: 0.88rem; margin-bottom: 1.5rem; }
    .google-login-btn {
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: #fff; color: #333; padding: 0.7rem 1.8rem;
        border-radius: 12px; border: 1px solid #dee2e6;
        text-decoration: none; font-weight: 700; font-size: 0.9rem;
    }

    .pref-badge {
        display: inline-block;
        background: #e7f5ff; border: 1px solid #a5d8ff; color: #1971c2;
        padding: 0.2rem 0.6rem; border-radius: 8px;
        font-size: 0.75rem; font-weight: 600; margin: 0.15rem;
    }

    section[data-testid="stSidebar"] { background: #f8f9fa; border-right: 1px solid #e9ecef; }
    section[data-testid="stSidebar"] .stMarkdown { color: #495057; }
    section[data-testid="stSidebar"] hr { border-color: #e9ecef; }

    .sb-stats {
        background: #fff; border: 1px solid #e9ecef; border-radius: 12px; padding: 0.8rem;
    }
    .sb-stats .row { display: flex; justify-content: space-between; padding: 0.25rem 0; }
    .sb-stats .label { color: #868e96; font-size: 0.78rem; }
    .sb-stats .val { color: #212529; font-size: 0.78rem; font-weight: 700; }

    .stButton > button { border-radius: 10px; font-weight: 600; }
    .stTextArea textarea {
        background: #f8f9fa !important; border: 1px solid #dee2e6 !important;
        border-radius: 12px !important; color: #212529 !important; font-size: 0.9rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #E8590C !important; box-shadow: 0 0 0 2px rgba(232,89,12,0.1) !important;
    }
    hr { border-color: #e9ecef; }
    .footer-text { text-align: center; color: #ced4da; font-size: 0.7rem; padding: 0.5rem 0 1rem; }
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
    "Sonnet 4.6 ⚡ 빠른 응답": "claude-sonnet-4-6",
    "Opus 4.7 🚀 최고 성능": "claude-opus-4-7",
}
MODEL_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
}

# ==============================================================
# 사용자 설정 → 시스템 프롬프트
# ==============================================================
def build_user_system_prompt(uid):
    data = load_tuning(uid, "user_preference")
    if not data:
        return ""
    parts = ["[사용자가 설정한 지시사항 - 반드시 모든 답변에 적용하세요]"]
    for item in data:
        parts.append(f"- {item['value']}")
    return "\n".join(parts)

# ==============================================================
# 명령어 처리
# ==============================================================
def handle_command(uid, text):
    """
    명령어 처리. 명령어면 (True, 응답메시지) 반환.
    일반 대화면 (False, None) 반환.
    """
    stripped = text.strip()

    # /저장 명령어
    if stripped.startswith("/저장 ") or stripped.startswith("/저장\n"):
        content = stripped[3:].strip()
        if not content:
            return True, "❌ 저장할 내용을 입력해주세요.\n\n예: `/저장 반말로 대답해`"
        key = hashlib.md5(content.encode()).hexdigest()[:10]
        save_tuning(uid, "user_preference", key, content)
        return True, f'✅ **설정 저장됨**\n\n> {content}\n\n이제부터 모든 대화에 적용됩니다.'

    # /목록 명령어
    if stripped == "/목록":
        data = load_tuning(uid, "user_preference")
        if not data:
            return True, "📋 저장된 설정이 없습니다.\n\n`/저장 내용`으로 추가해보세요."
        lines = ["📋 **저장된 설정 목록**\n"]
        for i, item in enumerate(data, 1):
            lines.append(f"{i}. {item['value']}")
        lines.append(f"\n총 {len(data)}개 · 삭제하려면 `/삭제 번호`")
        return True, "\n".join(lines)

    # /삭제 명령어 (번호로)
    if stripped.startswith("/삭제 "):
        arg = stripped[3:].strip()
        data = load_tuning(uid, "user_preference")

        # 번호로 삭제
        try:
            idx = int(arg) - 1
            if 0 <= idx < len(data):
                deleted = data[idx]
                delete_tuning(uid, "user_preference", deleted["key"])
                return True, f'🗑️ **설정 삭제됨**\n\n> ~~{deleted["value"]}~~'
            else:
                return True, f"❌ 1~{len(data)} 사이 번호를 입력해주세요."
        except ValueError:
            pass

        # 내용으로 삭제
        for item in data:
            if arg in item["value"]:
                delete_tuning(uid, "user_preference", item["key"])
                return True, f'🗑️ **설정 삭제됨**\n\n> ~~{item["value"]}~~'

        return True, "❌ 해당 설정을 찾을 수 없습니다. `/목록`으로 확인해보세요."

    # /초기화 명령어
    if stripped == "/초기화":
        data = load_tuning(uid, "user_preference")
        count = len(data)
        for item in data:
            delete_tuning(uid, "user_preference", item["key"])
        return True, f"🔄 **설정 초기화 완료**\n\n{count}개의 설정이 삭제되었습니다."

    # /도움말 명령어
    if stripped in ["/도움말", "/help", "/?"]:
        return True, """📖 **명령어 안내**

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/저장 내용` | 설정 저장 | `/저장 반말로 대답해` |
| `/목록` | 저장된 설정 보기 | `/목록` |
| `/삭제 번호` | 설정 삭제 | `/삭제 1` |
| `/초기화` | 전체 설정 삭제 | `/초기화` |
| `/도움말` | 이 안내 보기 | `/도움말` |

저장된 설정은 **모든 대화에 자동 적용**됩니다!"""

    # 일반 대화
    return False, None

# ==============================================================
# 인증
# ==============================================================
handle_oauth_callback()

if not is_logged_in():
    auth_url = get_google_auth_url()
    if not auth_url:
        st.session_state["user"] = {
            "id": "guest", "email": "guest", "name": "사용자", "picture": "",
        }
        st.rerun()
    else:
        st.markdown(f"""
        <div class="login-screen">
            <div class="icon-box">✦</div>
            <h2>Claude AI</h2>
            <p>로그인하면 대화와 설정이 저장됩니다</p>
            <a href="{auth_url}" class="google-login-btn">🔐 Google로 시작하기</a>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.2, 1, 1.2])
        with c2:
            if st.button("로그인 없이 사용하기", use_container_width=True):
                st.session_state["user"] = {
                    "id": "guest", "email": "guest", "name": "사용자", "picture": "",
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

    sel_label = st.selectbox("🧠 모델", list(MODEL_OPTIONS.keys()), index=0)
    sel_model = MODEL_OPTIONS[sel_label]
    pricing = MODEL_PRICING[sel_model]

    st.markdown("---")

    if st.button("✨ 새 대화", use_container_width=True, type="primary"):
        st.session_state.current_session = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages = []
        st.session_state.last_usage = None
        st.rerun()

    st.markdown("---")

    # 저장된 설정
    st.markdown("**⚙️ 나의 설정**")
    user_prefs = load_tuning(uid, "user_preference")
    if user_prefs:
        for i, item in enumerate(user_prefs, 1):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'<span class="pref-badge">{i}. {item["value"]}</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"dp_{item['key']}"):
                    delete_tuning(uid, "user_preference", item["key"])
                    st.rerun()
    else:
        st.caption('`/저장 내용`으로 추가')

    st.markdown("---")

    # 대화 기록
    st.markdown("**📂 대화 기록**")
    sessions = get_user_sessions(uid)
    if st.session_state.current_session not in sessions:
        sessions.append(st.session_state.current_session)
    sessions.sort(reverse=True)

    for sess in sessions:
        is_cur = sess == st.session_state.current_session
        c1, c2 = st.columns([5, 1])
        with c1:
            if is_cur:
                st.markdown(f"**💬 {sess}**")
            else:
                if st.button(f"📝 {sess}", key=f"s_{sess}", use_container_width=True):
                    st.session_state.current_session = sess
                    saved = load_conversations(uid, sess)
                    st.session_state.messages = [
                        {"role": m["role"], "content": m["content"],
                         "display": m["content"],
                         "msg_type": m.get("msg_type", "normal")} for m in saved
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
    <div class="sb-stats">
        <div class="row"><span class="label">총 대화</span><span class="val">{stats['total_messages']}회</span></div>
        <div class="row"><span class="label">입력 토큰</span><span class="val">{stats['total_input']:,}</span></div>
        <div class="row"><span class="label">출력 토큰</span><span class="val">{stats['total_output']:,}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================
# 헤더
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
        <p>대화도 하고, 설정도 저장할 수 있어요</p>
        <div class="welcome-chips">
            <div class="chip">💬 자유 대화</div>
            <div class="chip">💻 코드 작성</div>
            <div class="chip">📝 글쓰기</div>
            <div class="chip">🌐 번역</div>
            <div class="chip">📄 파일 분석</div>
            <div class="chip">📊 데이터 분석</div>
        </div>
        <div class="cmd-guide">
            <h4>⚙️ 설정 명령어</h4>
            <div class="cmd-row"><span class="cmd-tag">/저장 내용</span><span class="cmd-desc">설정 저장 (예: /저장 반말로 대답해)</span></div>
            <div class="cmd-row"><span class="cmd-tag">/목록</span><span class="cmd-desc">저장된 설정 보기</span></div>
            <div class="cmd-row"><span class="cmd-tag">/삭제 번호</span><span class="cmd-desc">설정 삭제 (예: /삭제 1)</span></div>
            <div class="cmd-row"><span class="cmd-tag">/초기화</span><span class="cmd-desc">전체 설정 삭제</span></div>
            <div class="cmd-row"><span class="cmd-tag">/도움말</span><span class="cmd-desc">명령어 안내</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    for msg in st.session_state.messages:
        mt = msg.get("msg_type", "normal")
        if msg["role"] == "user":
            d = msg.get("display", msg["content"])
            st.markdown(f'<div class="msg-user-wrap"><div class="msg-user-bubble">{d[:2000]}</div></div>', unsafe_allow_html=True)
        elif mt == "system_ok":
            st.markdown(f'<div class="msg-system"><div class="badge">{msg["content"]}</div></div>', unsafe_allow_html=True)
        elif mt == "system_del":
            st.markdown(f'<div class="msg-system"><div class="badge-red">{msg["content"]}</div></div>', unsafe_allow_html=True)
        elif mt == "system_info":
            st.markdown(f'<div class="msg-system"><div class="badge-blue">{msg["content"]}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="msg-ai-wrap"><div class="msg-ai-avatar">✦</div>'
                f'<div class="msg-ai-bubble">{msg["content"]}</div></div>',
                unsafe_allow_html=True,
            )

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
# 입력
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
    chips = "".join(f'<span class="file-chip">📎 {f.name}</span>' for f in uploaded_files)
    st.markdown(f'<div class="file-chips">{chips}</div>', unsafe_allow_html=True)

col_in, col_btn = st.columns([6, 1])
with col_in:
    question = st.text_area("입력", placeholder="메시지 입력... (/도움말 로 명령어 확인)",
                             height=72, label_visibility="collapsed")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    send = st.button("전송 ▶", use_container_width=True, type="primary")

# ==============================================================
# 전송 처리
# ==============================================================
if send and (question.strip() or uploaded_files):

    # ── 1. 명령어 체크 ──
    if question.strip().startswith("/"):
        is_cmd, cmd_response = handle_command(uid, question)
        if is_cmd:
            # 명령어 유형 판단
            if "저장됨" in cmd_response:
                msg_type = "system_ok"
            elif "삭제" in cmd_response or "초기화" in cmd_response:
                msg_type = "system_del"
            else:
                msg_type = "system_info"

            st.session_state.messages.append(
                {"role": "user", "content": question, "display": question, "msg_type": "normal"})
            st.session_state.messages.append(
                {"role": "assistant", "content": cmd_response, "display": cmd_response, "msg_type": msg_type})

            save_message(uid, "user", question, "", 0, 0, st.session_state.current_session)
            save_message(uid, "assistant", cmd_response, "", 0, 0, st.session_state.current_session)
            st.rerun()

    # ── 2. 일반 대화 ──
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

    st.session_state.messages.append(
        {"role": "user", "content": combined, "display": display, "msg_type": "normal"})

    # API 메시지 (명령어 메시지 제외, 일반 대화만)
    api_msgs = []
    for i, m in enumerate(st.session_state.messages):
        if m.get("msg_type", "normal") not in ("system_ok", "system_del", "system_info"):
            if i == len(st.session_state.messages) - 1 and m["role"] == "user":
                api_msgs.append({"role": "user", "content": content_blocks})
            else:
                api_msgs.append({"role": m["role"], "content": m["content"]})

    # 시스템 프롬프트 (저장된 설정)
    system_prompt = build_user_system_prompt(uid)

    # 스트리밍
    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        start = time.time()

        placeholder = st.empty()
        full = ""

        stream_kwargs = {
            "model": sel_model,
            "max_tokens": 16384,
            "messages": api_msgs,
        }
        if system_prompt.strip():
            stream_kwargs["system"] = system_prompt

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with client.messages.stream(**stream_kwargs) as stream:
                    for text in stream.text_stream:
                        full += text
                        placeholder.markdown(
                            f'<div class="msg-ai-wrap">'
                            f'<div class="msg-ai-avatar">✦</div>'
                            f'<div class="msg-ai-bubble">{full}▌</div></div>',
                            unsafe_allow_html=True,
                        )
                break
            except anthropic.APIStatusError as e:
                if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                    st.warning(f"⏳ 서버 과부하... 재시도 중 ({attempt+2}/{max_retries})")
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

        st.rerun()

    except anthropic.AuthenticationError:
        st.error("❌ API 키 오류")
    except anthropic.RateLimitError:
        st.error("⏳ 한도 초과")
    except Exception as e:
        st.error(f"❌ 오류: {e}")

elif send:
    st.warning("메시지를 입력해주세요!")

st.markdown('<div class="footer-text">Claude AI · Anthropic API · Supabase · Streamlit</div>', unsafe_allow_html=True)
