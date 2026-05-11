import streamlit as st
import anthropic
import time
import hashlib

from auth import (
    get_google_auth_url, handle_oauth_callback,
    is_logged_in, get_current_user, logout,
)
from database import (
    upsert_user, save_message, load_conversations,
    get_user_sessions, delete_session, get_usage_stats,
    save_tuning, load_tuning, delete_tuning,
    build_system_prompt, save_file_meta, get_user_files,
)
from file_handler import process_file, fmt_size, is_image

# ==============================================================
# 페이지 설정
# ==============================================================
st.set_page_config(
    page_title="Claude AI 학습 도우미",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================
# CSS — 채팅 UI 스타일
# ==============================================================
st.markdown("""
<style>
    /* 배경 */
    .stApp {
        background: linear-gradient(160deg, #0a0a1a 0%, #1a1a3e 50%, #0d0d2b 100%);
    }

    /* 헤더 */
    .app-header {
        text-align: center;
        padding: 1rem 0 0.3rem;
    }
    .app-header h1 {
        color: #fff;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
    }
    .app-header p {
        color: #8892b0;
        font-size: 0.9rem;
        margin: 0.2rem 0 0;
    }

    /* 채팅 컨테이너 */
    .chat-container {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 1rem;
    }

    /* 사용자 메시지 */
    .msg-user {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 1rem;
    }
    .msg-user .bubble {
        background: linear-gradient(135deg, #6366f1, #818cf8);
        color: #fff;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 4px 18px;
        max-width: 75%;
        font-size: 0.95rem;
        line-height: 1.6;
        word-break: break-word;
        box-shadow: 0 2px 12px rgba(99,102,241,0.3);
    }
    .msg-user .bubble .file-tag {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
        font-size: 0.78rem;
        margin-bottom: 0.3rem;
    }

    /* AI 메시지 */
    .msg-ai {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 1rem;
    }
    .msg-ai .avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: linear-gradient(135deg, #10b981, #34d399);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        margin-right: 0.6rem;
        flex-shrink: 0;
        margin-top: 0.2rem;
    }
    .msg-ai .bubble {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.1);
        color: #e2e8f0;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 18px 4px;
        max-width: 80%;
        font-size: 0.95rem;
        line-height: 1.75;
        word-break: break-word;
    }
    .msg-ai .bubble code {
        background: rgba(255,255,255,0.1);
        padding: 0.1rem 0.35rem;
        border-radius: 4px;
        font-size: 0.88rem;
    }
    .msg-ai .bubble pre {
        background: rgba(0,0,0,0.4);
        padding: 0.8rem;
        border-radius: 8px;
        overflow-x: auto;
        margin: 0.5rem 0;
    }

    /* 사용량 바 */
    .usage-bar {
        display: flex;
        gap: 1.5rem;
        justify-content: center;
        padding: 0.5rem 0;
        flex-wrap: wrap;
    }
    .usage-item {
        color: #8892b0;
        font-size: 0.78rem;
    }
    .usage-item span {
        color: #c7d2fe;
        font-weight: 700;
    }

    /* 환영 화면 */
    .welcome-box {
        text-align: center;
        padding: 4rem 2rem;
    }
    .welcome-box .icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    .welcome-box h2 {
        color: #fff;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .welcome-box p {
        color: #8892b0;
        font-size: 1rem;
        line-height: 1.8;
    }
    .welcome-box .hint {
        display: inline-block;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 0.6rem 1.2rem;
        margin: 0.3rem;
        color: #a5b4fc;
        font-size: 0.88rem;
        cursor: default;
    }

    /* 로그인 카드 */
    .login-card {
        max-width: 400px;
        margin: 5rem auto;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 24px;
        padding: 3rem 2rem;
        text-align: center;
        backdrop-filter: blur(12px);
    }
    .login-card h2 { color: #fff; font-size: 1.6rem; }
    .login-card p { color: #8892b0; margin: 0.5rem 0 1.5rem; }
    .google-btn {
        display: inline-block;
        background: #fff;
        color: #333;
        padding: 0.8rem 2.5rem;
        border-radius: 14px;
        text-decoration: none;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.2s;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .google-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }

    /* 사이드바 */
    section[data-testid="stSidebar"] {
        background: rgba(10, 10, 26, 0.97);
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #e2e8f0; }

    /* 버튼 */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* 입력 필드 */
    .stTextArea textarea, .stTextInput input {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px !important;
        color: #e2e8f0 !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
    }

    /* 구분선 */
    hr { border-color: rgba(255,255,255,0.06); }

    /* 튜닝 아이템 */
    .tuning-chip {
        display: inline-block;
        background: rgba(99,102,241,0.15);
        border: 1px solid rgba(99,102,241,0.3);
        color: #c7d2fe;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.82rem;
        margin: 0.2rem;
    }

    /* 스크롤바 */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# 설정
# ==============================================================
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("⚠️ ANTHROPIC_API_KEY를 Secrets에 등록해주세요.")
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
# OAuth
# ==============================================================
handle_oauth_callback()

# ==============================================================
# 로그인 전
# ==============================================================
if not is_logged_in():
    st.markdown("""
    <div class="app-header">
        <h1>🤖 Claude AI 학습 도우미</h1>
        <p>당곡고등학교 전용</p>
    </div>
    """, unsafe_allow_html=True)

    auth_url = get_google_auth_url()
    if auth_url:
        st.markdown(f"""
        <div class="login-card">
            <div style="font-size:3rem;">🎓</div>
            <h2>시작하기</h2>
            <p>Google 계정으로 로그인하세요</p>
            <a href="{auth_url}" class="google-btn">🔐 Google 로그인</a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="login-card">
            <div style="font-size:3rem;">🎓</div>
            <h2>시작하기</h2>
            <p>게스트 모드로 이용 가능합니다</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            if st.button("🚀 시작하기", use_container_width=True):
                st.session_state["user"] = {
                    "id": "guest", "email": "guest@school",
                    "name": "게스트", "picture": "",
                }
                st.rerun()
    st.stop()

# ==============================================================
# 로그인 후 초기화
# ==============================================================
user = get_current_user()
uid, uname, uemail = user["id"], user["name"], user["email"]
upic = user.get("picture", "")
upsert_user(uid, uemail, uname, upic)

for k, v in {
    "messages": [],
    "current_session": "default",
    "pending_files": [],
    "last_usage": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 처음 로드 시 DB에서 대화 불러오기
if not st.session_state.messages:
    saved = load_conversations(uid, st.session_state.current_session)
    if saved:
        st.session_state.messages = [
            {"role": m["role"], "content": m["content"],
             "display": m["content"]} for m in saved
        ]

# ==============================================================
# 사이드바
# ==============================================================
with st.sidebar:
    # 프로필
    if upic:
        st.image(upic, width=45)
    st.markdown(f"**{uname}** 님")
    st.caption(uemail)
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")

    # 모델
    sel_label = st.selectbox("🧠 모델", list(MODEL_OPTIONS.keys()), index=0)
    sel_model = MODEL_OPTIONS[sel_label]
    pricing = MODEL_PRICING[sel_model]

    st.markdown("---")

    # 대화방 관리
    st.markdown("**💬 대화방**")
    sessions = get_user_sessions(uid)
    if st.session_state.current_session not in sessions:
        sessions.append(st.session_state.current_session)
        sessions.sort()

    cur_session = st.selectbox(
        "대화방 선택", sessions,
        index=sessions.index(st.session_state.current_session),
        label_visibility="collapsed",
    )
    if cur_session != st.session_state.current_session:
        st.session_state.current_session = cur_session
        saved = load_conversations(uid, cur_session)
        st.session_state.messages = [
            {"role": m["role"], "content": m["content"],
             "display": m["content"]} for m in saved
        ]
        st.session_state.last_usage = None
        st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        new_room = st.text_input("새 대화방", label_visibility="collapsed", placeholder="이름 입력")
    with col_b:
        if st.button("➕", use_container_width=True) and new_room.strip():
            st.session_state.current_session = new_room.strip()
            st.session_state.messages = []
            st.session_state.last_usage = None
            st.rerun()

    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("🗑️ 삭제", use_container_width=True):
            delete_session(uid, st.session_state.current_session)
            st.session_state.current_session = "default"
            st.session_state.messages = []
            st.rerun()
    with col_d:
        if st.button("🧹 비우기", use_container_width=True):
            delete_session(uid, st.session_state.current_session)
            st.session_state.messages = []
            st.session_state.last_usage = None
            st.rerun()

    st.markdown("---")

    # 사용량
    stats = get_usage_stats(uid)
    st.markdown("**📊 누적 사용량**")
    st.caption(f"입력 {stats['total_input']:,} · 출력 {stats['total_output']:,} · {stats['total_messages']}회")

    st.markdown("---")

    # AI 튜닝 (사이드바에서 바로)
    with st.expander("🎯 AI 튜닝 설정"):
        st.markdown("**프로필**")
        profile_data = {d["key"]: d["value"] for d in load_tuning(uid, "profile")}
        for field, ph in [("학년","2학년"),("관심과목","수학,물리"),("진로","컴공"),("수준","수학 상위")]:
            val = st.text_input(field, value=profile_data.get(field,""),
                                placeholder=ph, key=f"t_p_{field}")
            if val.strip() != profile_data.get(field, ""):
                if val.strip():
                    save_tuning(uid, "profile", field, val.strip())
                else:
                    delete_tuning(uid, "profile", field)

        st.markdown("**답변 스타일**")
        pref_data = {d["key"]: d["value"] for d in load_tuning(uid, "preference")}
        for key, opts in [
            ("설명방식", ["쉽고 친근","학술적","예시 위주","단계별"]),
            ("답변길이", ["짧게","적당히","상세하게"]),
            ("말투", ["반말","존댓말","이모지"]),
        ]:
            cur = pref_data.get(key, opts[0])
            idx = opts.index(cur) if cur in opts else 0
            sel = st.selectbox(key, opts, index=idx, key=f"t_pr_{key}")
            if sel != cur:
                save_tuning(uid, "preference", key, sel)

        st.markdown("**특별 지시**")
        ci_data = load_tuning(uid, "custom_instruction")
        for item in ci_data:
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                st.caption(f"⚡ {item['value'][:50]}...")
            with cc2:
                if st.button("✕", key=f"dci_{item['key']}"):
                    delete_tuning(uid, "custom_instruction", item["key"])
                    st.rerun()

        new_ci = st.text_input("지시 추가", placeholder="예: 공식을 먼저 정리해줘", key="new_ci_input")
        if st.button("추가", key="add_ci_btn") and new_ci.strip():
            save_tuning(uid, "custom_instruction",
                        hashlib.md5(new_ci.encode()).hexdigest()[:8], new_ci.strip())
            st.rerun()

    # 파일 기록
    with st.expander("📁 파일 기록"):
        flist = get_user_files(uid, 10)
        if flist:
            for f in flist:
                st.caption(f"📎 {f['filename']} ({fmt_size(f.get('file_size',0))})")
        else:
            st.caption("아직 없음")

# ==============================================================
# 메인 영역
# ==============================================================
st.markdown(f"""
<div class="app-header">
    <h1>🤖 Claude AI 학습 도우미</h1>
    <p>{uname}님 · {st.session_state.current_session} · {sel_label}</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================
# 대화 표시
# ==============================================================
chat_area = st.container()

with chat_area:
    if not st.session_state.messages:
        # 환영 메시지
        st.markdown("""
        <div class="welcome-box">
            <div class="icon">💬</div>
            <h2>무엇이든 물어보세요!</h2>
            <p>학습 관련 질문, 파일 분석, 문제 풀이 등<br>무엇이든 도와드릴게요.</p>
            <br>
            <div class="hint">📐 수학 문제 풀이</div>
            <div class="hint">📖 영어 지문 해석</div>
            <div class="hint">🔬 과학 개념 설명</div>
            <div class="hint">📄 파일 분석</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 대화 기록
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                display = msg.get("display", msg["content"])
                st.markdown(f"""
                <div class="msg-user">
                    <div class="bubble">{display[:1000]}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="msg-ai">
                    <div class="avatar">🤖</div>
                    <div class="bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 마지막 사용량 표시
    if st.session_state.last_usage:
        u = st.session_state.last_usage
        st.markdown(f"""
        <div class="usage-bar">
            <div class="usage-item">입력 <span>{u['input']:,}</span></div>
            <div class="usage-item">출력 <span>{u['output']:,}</span></div>
            <div class="usage-item">시간 <span>{u['time']:.1f}s</span></div>
            <div class="usage-item">비용 <span>${u['cost']:.4f}</span></div>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================
# 하단 입력 영역
# ==============================================================
st.markdown("---")

# 파일 업로드
uploaded_files = st.file_uploader(
    "📎 파일 첨부",
    type=["jpg","jpeg","png","gif","webp","pdf","docx","xlsx",
          "txt","csv","md","json","py","js","html","css","java","c","cpp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    key="file_uploader",
)

if uploaded_files:
    file_names = [f"📎 {f.name}" for f in uploaded_files]
    st.caption(" · ".join(file_names))

# 질문 입력 + 전송 버튼
col_input, col_send = st.columns([6, 1])

with col_input:
    question = st.text_area(
        "메시지 입력",
        placeholder="메시지를 입력하세요... (Shift+Enter로 줄바꿈)",
        height=80,
        label_visibility="collapsed",
        key="user_input",
    )

with col_send:
    st.markdown("<br>", unsafe_allow_html=True)
    send = st.button("전송 ▶", use_container_width=True, type="primary")

# ==============================================================
# 메시지 전송 처리
# ==============================================================
if send and (question.strip() or uploaded_files):
    with st.spinner(""):
        try:
            # 파일 처리
            file_results = []
            if uploaded_files:
                for f in uploaded_files:
                    f.seek(0)
                    result = process_file(f)
                    file_results.append(result)
                    save_file_meta(uid, f.name, f.type or "", f.size, result[1][:50000])

            # Claude 메시지 구성
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

            combined = "\n\n".join(text_parts) if text_parts else "첨부 파일을 분석해주세요."
            content_blocks.append({"type": "text", "text": combined})

            # 표시용 텍스트
            display = question.strip()
            if file_results:
                tags = " ".join(f'<span class="file-tag">{r[2]}</span>' for r in file_results)
                display = f"{tags}<br>{display}" if display else tags

            # 메시지 추가
            st.session_state.messages.append({
                "role": "user",
                "content": combined,
                "display": display,
            })

            # API 메시지 구성 (전체 대화 맥락 유지)
            api_msgs = []
            for i, m in enumerate(st.session_state.messages):
                if i == len(st.session_state.messages) - 1 and m["role"] == "user":
                    api_msgs.append({"role": "user", "content": content_blocks})
                else:
                    api_msgs.append({"role": m["role"], "content": m["content"]})

            # API 호출
            client = anthropic.Anthropic(api_key=API_KEY)
            start = time.time()

            response = client.messages.create(
                model=sel_model,
                max_tokens=8192,
                system=build_system_prompt(uid),
                messages=api_msgs,
            )

            elapsed = time.time() - start
            answer = response.content[0].text
            inp = response.usage.input_tokens
            out = response.usage.output_tokens
            cost = (inp * pricing["input"] / 1e6) + (out * pricing["output"] / 1e6)

            # 응답 저장
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "display": answer,
            })

            st.session_state.last_usage = {
                "input": inp, "output": out,
                "time": elapsed, "cost": cost,
            }

            # DB 저장
            save_message(uid, "user",
                         question.strip() if question.strip() else "[파일 첨부]",
                         sel_model, 0, 0, st.session_state.current_session)
            save_message(uid, "assistant", answer,
                         sel_model, inp, out, st.session_state.current_session)

            st.rerun()

        except anthropic.AuthenticationError:
            st.error("❌ API 키가 올바르지 않습니다.")
        except anthropic.RateLimitError:
            st.error("⏳ API 한도 초과. 잠시 후 다시 시도하세요.")
        except Exception as e:
            st.error(f"❌ 오류: {e}")
            import traceback
            st.code(traceback.format_exc())

elif send:
    st.warning("메시지를 입력하거나 파일을 첨부해주세요!")

# 하단 안내
st.markdown("""
<div style="text-align:center;color:#4a5568;font-size:0.75rem;padding:0.5rem 0;">
    Claude AI 학습 도우미 · 학습 관련 질문을 해주세요
</div>
""", unsafe_allow_html=True)
