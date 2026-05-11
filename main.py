"""
main.py — Claude AI 학습 도우미 (풀 버전)
- Google 로그인
- 파일/이미지 업로드 (용량 무제한)
- 사용자별 대화 저장
- AI 개인 튜닝
"""

import streamlit as st
import anthropic
import time
import json

from auth import (
    get_google_auth_url, handle_oauth_callback,
    is_logged_in, get_current_user, logout,
)
from database import (
    upsert_user, save_message, load_conversations,
    get_user_sessions, delete_session, get_usage_stats,
    save_tuning_data, load_tuning_data, delete_tuning_data,
    build_user_system_prompt, save_file_metadata,
    get_supabase_client,
)
from file_handler import (
    process_uploaded_file, build_claude_messages,
    format_file_size, get_file_type_label, is_image,
    IMAGE_TYPES, DOCUMENT_TYPES, ALL_TYPES,
)

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
# 파일 업로드 용량 제한 해제 설정 안내
# .streamlit/config.toml에 다음 추가:
# [server]
# maxUploadSize = 2000
# ==============================================================

# ==============================================================
# CSS 스타일
# ==============================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    }

    .main-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .main-header p {
        color: #a0aec0;
        font-size: 1rem;
    }

    .glass-card {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
    }

    .user-msg {
        background: rgba(99,102,241,0.15);
        border-left: 3px solid #6366f1;
        border-radius: 0 12px 12px 0;
        padding: 0.8rem 1.2rem;
        margin-bottom: 0.5rem;
        color: #c7d2fe;
        font-weight: 600;
    }
    .ai-msg {
        background: rgba(255,255,255,0.04);
        border-left: 3px solid #10b981;
        border-radius: 0 12px 12px 0;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1.2rem;
        color: #e2e8f0;
        line-height: 1.7;
    }

    .metric-row {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
    }
    .metric-box {
        flex: 1;
        min-width: 100px;
        background: rgba(255,255,255,0.04);
        border-radius: 12px;
        padding: 0.8rem;
        text-align: center;
    }
    .metric-box .label { color: #a0aec0; font-size: 0.75rem; }
    .metric-box .value { color: #fff; font-size: 1.3rem; font-weight: 700; }
    .metric-box .sub { color: #718096; font-size: 0.7rem; }

    .login-card {
        max-width: 450px;
        margin: 3rem auto;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 2.5rem;
        text-align: center;
        backdrop-filter: blur(12px);
    }
    .login-card h2 { color: #ffffff; margin-bottom: 0.5rem; }
    .login-card p { color: #a0aec0; margin-bottom: 1.5rem; }

    .google-btn {
        display: inline-block;
        background: #ffffff;
        color: #333333;
        padding: 0.75rem 2rem;
        border-radius: 12px;
        text-decoration: none;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .google-btn:hover {
        background: #f0f0f0;
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    .file-badge {
        display: inline-block;
        background: rgba(99,102,241,0.2);
        color: #c7d2fe;
        padding: 0.3rem 0.8rem;
        border-radius: 8px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }

    .tuning-item {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.5rem;
        color: #e2e8f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    section[data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.95);
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# 모델 설정
# ==============================================================
MODEL_OPTIONS = {
    "Claude Sonnet 4 (빠르고 효율적)": "claude-sonnet-4-20250514",
    "Claude Opus 4 (최고 성능)": "claude-opus-4-20250514",
}
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}

# ==============================================================
# API 키 확인
# ==============================================================
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("⚠️ `ANTHROPIC_API_KEY`가 Secrets에 설정되지 않았습니다.")
    st.stop()

# ==============================================================
# OAuth 콜백 처리
# ==============================================================
handle_oauth_callback()

# ==============================================================
# 로그인 전 화면
# ==============================================================
if not is_logged_in():
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Claude AI 학습 도우미</h1>
        <p>당곡고등학교 전용 AI 학습 플랫폼</p>
    </div>
    """, unsafe_allow_html=True)

    auth_url = get_google_auth_url()

    if auth_url:
        st.markdown(f"""
        <div class="login-card">
            <h2>👋 환영합니다!</h2>
            <p>Google 계정으로 로그인하면<br>대화 기록 저장, AI 개인 튜닝 등<br>모든 기능을 사용할 수 있어요.</p>
            <a href="{auth_url}" class="google-btn">
                🔐 Google 계정으로 로그인
            </a>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Google OAuth 미설정 시 → 게스트 모드
        st.markdown("""
        <div class="login-card">
            <h2>👋 환영합니다!</h2>
            <p>Google 로그인이 설정되지 않았습니다.<br>게스트 모드로 사용할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🚀 게스트로 시작하기", use_container_width=True):
                st.session_state["user"] = {
                    "id": "guest",
                    "email": "guest@danggok.hs.kr",
                    "name": "게스트",
                    "picture": "",
                }
                st.rerun()

    st.stop()

# ==============================================================
# 로그인 후 — 메인 앱
# ==============================================================
user = get_current_user()
user_id = user["id"]
user_name = user["name"]
user_email = user["email"]
user_picture = user.get("picture", "")

# DB에 사용자 등록
upsert_user(user_id, user_email, user_name, user_picture)

# 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_session" not in st.session_state:
    st.session_state.current_session = "default"
if "total_input_tokens" not in st.session_state:
    st.session_state.total_input_tokens = 0
if "total_output_tokens" not in st.session_state:
    st.session_state.total_output_tokens = 0

# ==============================================================
# 사이드바
# ==============================================================
with st.sidebar:
    # 사용자 프로필
    st.markdown("### 👤 내 계정")
    if user_picture:
        st.image(user_picture, width=60)
    st.markdown(f"**{user_name}**")
    st.markdown(f"`{user_email}`")

    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")

    # 모델 선택
    st.markdown("### 🧠 AI 모델")
    selected_label = st.selectbox(
        "모델 선택", list(MODEL_OPTIONS.keys()), index=0, label_visibility="collapsed"
    )
    selected_model = MODEL_OPTIONS[selected_label]
    pricing = MODEL_PRICING[selected_model]

    st.markdown("---")

    # 대화 세션 관리
    st.markdown("### 💬 대화방 관리")

    sessions = get_user_sessions(user_id)
    current = st.selectbox(
        "대화방 선택",
        sessions,
        index=sessions.index(st.session_state.current_session) if st.session_state.current_session in sessions else 0,
        label_visibility="collapsed",
    )

    # 세션 변경 시 대화 기록 로드
    if current != st.session_state.current_session:
        st.session_state.current_session = current
        saved = load_conversations(user_id, current)
        st.session_state.messages = [
            {"role": m["role"], "content": m["content"]} for m in saved
        ]
        st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        new_name = st.text_input("새 대화방", placeholder="이름 입력", label_visibility="collapsed")
    with col_b:
        if st.button("➕ 만들기", use_container_width=True):
            if new_name.strip():
                st.session_state.current_session = new_name.strip()
                st.session_state.messages = []
                st.rerun()

    if st.button("🗑️ 현재 대화방 삭제", use_container_width=True):
        delete_session(user_id, st.session_state.current_session)
        st.session_state.current_session = "default"
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")

    # 사용량 통계
    st.markdown("### 📊 사용량")
    stats = get_usage_stats(user_id)
    st.markdown(f"- 총 입력: **{stats['total_input']:,}** 토큰")
    st.markdown(f"- 총 출력: **{stats['total_output']:,}** 토큰")
    st.markdown(f"- 총 응답: **{stats['total_messages']}**회")

    st.markdown("---")

    # === 앱 내 네비게이션 ===
    st.markdown("### 📌 메뉴")
    app_page = st.radio(
        "페이지",
        ["💬 채팅", "🎯 AI 튜닝", "📁 파일 기록"],
        index=0,
        label_visibility="collapsed",
    )

# ==============================================================
# 헤더
# ==============================================================
st.markdown(f"""
<div class="main-header">
    <h1>🤖 Claude AI 학습 도우미</h1>
    <p>안녕하세요, {user_name}님! | 대화방: {st.session_state.current_session} | 모델: {selected_model}</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================
# PAGE: 채팅
# ==============================================================
if app_page == "💬 채팅":

    # DB에서 대화 기록 로드 (첫 로드)
    if not st.session_state.messages:
        saved = load_conversations(user_id, st.session_state.current_session)
        if saved:
            st.session_state.messages = [
                {"role": m["role"], "content": m["content"]} for m in saved
            ]

    # 대화 기록 표시
    if st.session_state.messages:
        st.markdown("### 💬 대화 기록")
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="user-msg">🙋 {msg["content"][:500]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="ai-msg">{msg["content"]}</div>', unsafe_allow_html=True)
        st.markdown("---")

    # 파일 업로드
    st.markdown("### 📎 파일 첨부 (선택사항)")
    uploaded_files = st.file_uploader(
        "이미지, PDF, Word, Excel, 텍스트 등 자유롭게 첨부하세요",
        type=["jpg", "jpeg", "png", "gif", "webp",
              "pdf", "docx", "xlsx", "txt", "csv", "md", "json",
              "py", "js", "html", "css", "java", "c", "cpp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    # 첨부 파일 미리보기
    if uploaded_files:
        st.markdown("**첨부된 파일:**")
        for uf in uploaded_files:
            label = get_file_type_label(uf.type or "")
            size = format_file_size(uf.size)
            st.markdown(f'<span class="file-badge">{label} {uf.name} ({size})</span>', unsafe_allow_html=True)

            # 이미지 미리보기
            if uf.type and is_image(uf.type):
                st.image(uf, width=300)

    # 질문 입력
    st.markdown("### ✏️ 질문 입력")
    user_question = st.text_area(
        "질문",
        placeholder="질문을 입력하세요... (파일을 첨부하면 AI가 분석합니다)",
        height=120,
        label_visibility="collapsed",
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        send = st.button("🚀 질문하기", use_container_width=True)

    # API 호출
    if send and (user_question.strip() or uploaded_files):
        with st.spinner("🤔 AI가 생각하고 있어요..."):
            try:
                # 파일 처리
                file_contents = []
                if uploaded_files:
                    for uf in uploaded_files:
                        uf.seek(0)
                        result = process_uploaded_file(uf)
                        file_contents.append(result)

                        # 파일 메타데이터 DB 저장
                        save_file_metadata(
                            user_id, uf.name, uf.type or "",
                            uf.size, result[1][:50000]
                        )

                # Claude 메시지 구성
                content_blocks = build_claude_messages(user_question, file_contents)

                # 대화 기록용 메시지 (텍스트만)
                display_text = user_question.strip()
                if file_contents:
                    file_names = [fc[2] for fc in file_contents]
                    display_text = f"[📎 {', '.join(f.split('|')[1].strip() for f in file_names)}]\n{display_text}"

                # 세션 메시지에 추가
                st.session_state.messages.append({"role": "user", "content": display_text})

                # API 호출용 메시지 (content blocks 포함)
                api_messages = []
                for msg in st.session_state.messages[:-1]:
                    api_messages.append({"role": msg["role"], "content": msg["content"]})
                api_messages.append({"role": "user", "content": content_blocks})

                # 시스템 프롬프트 (튜닝 데이터 포함)
                system_prompt = build_user_system_prompt(user_id)

                client = anthropic.Anthropic(api_key=API_KEY)
                start_time = time.time()

                response = client.messages.create(
                    model=selected_model,
                    max_tokens=8192,
                    system=system_prompt,
                    messages=api_messages,
                )

                elapsed = time.time() - start_time

                answer = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost = (input_tokens * pricing["input"] / 1_000_000) + \
                       (output_tokens * pricing["output"] / 1_000_000)

                # 세션 상태 업데이트
                st.session_state.messages.append({"role": "assistant", "content": answer})

                # DB에 저장
                save_message(user_id, "user", display_text, selected_model,
                             0, 0, st.session_state.current_session)
                save_message(user_id, "assistant", answer, selected_model,
                             input_tokens, output_tokens, st.session_state.current_session)

                # 답변 표시
                st.markdown("### 💡 AI 답변")
                st.markdown(answer)

                # 사용량 표시
                st.markdown(f"""
                <div class="glass-card">
                    <div style="color:#a0aec0; font-size:0.8rem; font-weight:600; margin-bottom:0.5rem;">
                        📊 이번 응답 사용량
                    </div>
                    <div class="metric-row">
                        <div class="metric-box">
                            <div class="label">입력 토큰</div>
                            <div class="value">{input_tokens:,}</div>
                        </div>
                        <div class="metric-box">
                            <div class="label">출력 토큰</div>
                            <div class="value">{output_tokens:,}</div>
                        </div>
                        <div class="metric-box">
                            <div class="label">응답 시간</div>
                            <div class="value">{elapsed:.1f}s</div>
                        </div>
                        <div class="metric-box">
                            <div class="label">예상 비용</div>
                            <div class="value">${cost:.4f}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            except anthropic.AuthenticationError:
                st.error("❌ API 키가 올바르지 않습니다.")
            except anthropic.RateLimitError:
                st.error("⏳ API 호출 한도 초과. 잠시 후 다시 시도하세요.")
            except anthropic.APIError as e:
                st.error(f"❌ API 오류: {e}")
            except Exception as e:
                st.error(f"❌ 오류: {e}")
                import traceback
                st.code(traceback.format_exc())

    elif send:
        st.warning("⚠️ 질문을 입력하거나 파일을 첨부해주세요!")


# ==============================================================
# PAGE: AI 튜닝
# ==============================================================
elif app_page == "🎯 AI 튜닝":
    st.markdown("### 🎯 나만의 AI 튜닝")
    st.markdown("""
    <div class="glass-card">
        <p style="color:#e2e8f0;">
            여기서 설정한 정보를 바탕으로 AI가 <b>나에게 맞춤 답변</b>을 해줍니다.<br>
            프로필, 학습 선호, 배경 지식 등을 등록하면 AI가 기억하고 활용합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "👤 프로필", "📚 학습 선호", "🧠 배경 지식", "✏️ 특별 지시"
    ])

    # --- 프로필 ---
    with tab1:
        st.markdown("**나의 학습 프로필을 등록하세요**")
        profile_fields = {
            "학년": "예: 2학년",
            "관심 과목": "예: 수학, 물리",
            "진로 희망": "예: 컴퓨터공학과",
            "학습 수준": "예: 수학 상위권, 영어 중위권",
            "약점 과목": "예: 국어 비문학",
        }
        for field, placeholder in profile_fields.items():
            existing = ""
            data = load_tuning_data(user_id, "profile")
            for d in data:
                if d["key"] == field:
                    existing = d["value"]
                    break
            val = st.text_input(f"{field}", value=existing, placeholder=placeholder, key=f"profile_{field}")
            if val != existing:
                if val.strip():
                    save_tuning_data(user_id, "profile", field, val.strip())
                elif existing:
                    delete_tuning_data(user_id, "profile", field)

    # --- 학습 선호 ---
    with tab2:
        st.markdown("**AI의 답변 스타일을 설정하세요**")

        pref_options = {
            "설명 방식": ["쉽고 친근하게", "학술적으로 정확하게", "예시 위주로", "단계별로 상세하게"],
            "답변 길이": ["짧고 핵심만", "적당한 길이", "길고 상세하게"],
            "언어 스타일": ["반말 (친근)", "존댓말 (정중)", "이모지 많이"],
            "수학 표현": ["텍스트로", "LaTeX 수식으로"],
        }

        for pref_key, options in pref_options.items():
            existing_val = ""
            data = load_tuning_data(user_id, "preference")
            for d in data:
                if d["key"] == pref_key:
                    existing_val = d["value"]
                    break
            default_idx = options.index(existing_val) if existing_val in options else 0
            selected = st.selectbox(pref_key, options, index=default_idx, key=f"pref_{pref_key}")
            if selected != existing_val:
                save_tuning_data(user_id, "preference", pref_key, selected)

    # --- 배경 지식 ---
    with tab3:
        st.markdown("**AI가 기억할 배경 지식이나 메모를 추가하세요**")
        st.markdown("예: '현재 미적분 단원 학습 중', '영어 문법에서 관계대명사가 어려움'")

        existing_knowledge = load_tuning_data(user_id, "knowledge")
        for item in existing_knowledge:
            col_k1, col_k2 = st.columns([5, 1])
            with col_k1:
                st.markdown(f"""
                <div class="tuning-item">
                    <span>📌 <b>{item['key']}</b>: {item['value']}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_k2:
                if st.button("❌", key=f"del_know_{item['key']}"):
                    delete_tuning_data(user_id, "knowledge", item["key"])
                    st.rerun()

        st.markdown("---")
        know_key = st.text_input("제목", placeholder="예: 수학 학습 현황", key="new_know_key")
        know_val = st.text_area("내용", placeholder="예: 현재 수학2 미적분 단원 진행 중, 극한의 개념은 이해했으나 미분법 적용이 어려움", key="new_know_val", height=100)
        if st.button("💾 배경 지식 추가", key="add_knowledge"):
            if know_key.strip() and know_val.strip():
                save_tuning_data(user_id, "knowledge", know_key.strip(), know_val.strip())
                st.success("✅ 저장되었습니다!")
                st.rerun()
            else:
                st.warning("제목과 내용을 모두 입력해주세요.")

    # --- 특별 지시 ---
    with tab4:
        st.markdown("**AI에게 내릴 특별 지시사항을 작성하세요**")
        st.markdown("예: '답변할 때 항상 관련 공식을 먼저 정리해줘', '영어 문제는 해석과 문법 포인트를 같이 설명해줘'")

        existing_custom = load_tuning_data(user_id, "custom_instruction")
        for item in existing_custom:
            col_c1, col_c2 = st.columns([5, 1])
            with col_c1:
                st.markdown(f"""
                <div class="tuning-item">
                    <span>⚡ {item['value']}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_c2:
                if st.button("❌", key=f"del_ci_{item['key']}"):
                    delete_tuning_data(user_id, "custom_instruction", item["key"])
                    st.rerun()

        custom_text = st.text_area(
            "특별 지시",
            placeholder="AI에게 전달할 특별 지시사항을 입력하세요...",
            key="new_custom_instruction",
            height=100,
            label_visibility="collapsed",
        )
        if st.button("💾 지시사항 추가", key="add_custom"):
            if custom_text.strip():
                import hashlib
                ci_key = hashlib.md5(custom_text.strip().encode()).hexdigest()[:8]
                save_tuning_data(user_id, "custom_instruction", ci_key, custom_text.strip())
                st.success("✅ 저장되었습니다!")
                st.rerun()
            else:
                st.warning("내용을 입력해주세요.")

    # 현재 시스템 프롬프트 미리보기
    st.markdown("---")
    with st.expander("🔍 현재 AI에게 전달되는 시스템 프롬프트 미리보기"):
        prompt = build_user_system_prompt(user_id)
        st.code(prompt, language="text")


# ==============================================================
# PAGE: 파일 기록
# ==============================================================
elif app_page == "📁 파일 기록":
    st.markdown("### 📁 업로드 파일 기록")

    from database import get_user_files
    files = get_user_files(user_id, limit=50)

    if files:
        for f in files:
            with st.expander(f"📎 {f['filename']} — {format_file_size(f.get('file_size', 0))} | {f.get('created_at', '')[:16]}"):
                st.markdown(f"- **타입:** {f.get('file_type', 'N/A')}")
                st.markdown(f"- **크기:** {format_file_size(f.get('file_size', 0))}")
                if f.get("extracted_text"):
                    st.text_area(
                        "추출된 텍스트",
                        f["extracted_text"][:5000],
                        height=200,
                        key=f"file_text_{f['id']}",
                        disabled=True,
                    )
    else:
        st.info("📭 아직 업로드한 파일이 없습니다. 채팅에서 파일을 첨부해보세요!")


# ==============================================================
# 하단
# ==============================================================
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#718096; font-size:0.85rem; padding:1rem 0;">
    🏫 당곡고등학교 AI 학습 도우미 | Claude API 기반<br>
    학습과 관련된 질문을 해주세요!
</div>
""", unsafe_allow_html=True)
