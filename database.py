"""
database.py
- Supabase를 사용한 사용자별 대화 기록 및 튜닝 데이터 관리
"""

import json
import streamlit as st
from datetime import datetime

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


def get_supabase_client() -> "Client":
    """Supabase 클라이언트 생성"""
    if not SUPABASE_AVAILABLE:
        return None
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None


def init_database():
    """
    Supabase 대시보드의 SQL Editor에서 아래 SQL을 실행하세요:
    
    -- 사용자 테이블
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        picture TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_login TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- 대화 기록 테이블
    CREATE TABLE IF NOT EXISTS conversations (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT REFERENCES users(id),
        session_name TEXT DEFAULT 'default',
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        model TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- 사용자별 튜닝 데이터 테이블
    CREATE TABLE IF NOT EXISTS user_tuning (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT REFERENCES users(id),
        tuning_type TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, tuning_type, key)
    );
    
    -- 파일 메타데이터 테이블
    CREATE TABLE IF NOT EXISTS uploaded_files (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT REFERENCES users(id),
        filename TEXT NOT NULL,
        file_type TEXT,
        file_size BIGINT,
        extracted_text TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- 인덱스
    CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(user_id, session_name);
    CREATE INDEX IF NOT EXISTS idx_tuning_user ON user_tuning(user_id);
    CREATE INDEX IF NOT EXISTS idx_files_user ON uploaded_files(user_id);
    """
    pass


# ==============================================================
# 사용자 관리
# ==============================================================

def upsert_user(user_id: str, email: str, name: str, picture: str = ""):
    """사용자 등록 또는 업데이트"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("users").upsert({
            "id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "last_login": datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception as e:
        st.warning(f"사용자 저장 오류: {e}")
        return False


def get_user(user_id: str):
    """사용자 조회"""
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = client.table("users").select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception:
        return None


# ==============================================================
# 대화 기록 관리
# ==============================================================

def save_message(user_id: str, role: str, content: str,
                 model: str = "", input_tokens: int = 0,
                 output_tokens: int = 0, session_name: str = "default"):
    """메시지 저장"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("conversations").insert({
            "user_id": user_id,
            "session_name": session_name,
            "role": role,
            "content": content,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }).execute()
        return True
    except Exception as e:
        st.warning(f"메시지 저장 오류: {e}")
        return False


def load_conversations(user_id: str, session_name: str = "default", limit: int = 50):
    """대화 기록 불러오기"""
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = (
            client.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .eq("session_name", session_name)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data if result.data else []
    except Exception:
        return []


def get_user_sessions(user_id: str):
    """사용자의 세션(대화방) 목록"""
    client = get_supabase_client()
    if not client:
        return ["default"]
    try:
        result = (
            client.table("conversations")
            .select("session_name")
            .eq("user_id", user_id)
            .execute()
        )
        if result.data:
            sessions = list(set(row["session_name"] for row in result.data))
            return sorted(sessions) if sessions else ["default"]
        return ["default"]
    except Exception:
        return ["default"]


def delete_session(user_id: str, session_name: str):
    """세션 삭제"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("conversations").delete().eq(
            "user_id", user_id
        ).eq("session_name", session_name).execute()
        return True
    except Exception:
        return False


def get_usage_stats(user_id: str):
    """사용자 총 사용량 통계"""
    client = get_supabase_client()
    if not client:
        return {"total_input": 0, "total_output": 0, "total_messages": 0}
    try:
        result = (
            client.table("conversations")
            .select("input_tokens, output_tokens")
            .eq("user_id", user_id)
            .eq("role", "assistant")
            .execute()
        )
        if result.data:
            total_in = sum(r.get("input_tokens", 0) for r in result.data)
            total_out = sum(r.get("output_tokens", 0) for r in result.data)
            return {
                "total_input": total_in,
                "total_output": total_out,
                "total_messages": len(result.data),
            }
        return {"total_input": 0, "total_output": 0, "total_messages": 0}
    except Exception:
        return {"total_input": 0, "total_output": 0, "total_messages": 0}


# ==============================================================
# 튜닝 데이터 관리
# ==============================================================

def save_tuning_data(user_id: str, tuning_type: str, key: str, value: str):
    """튜닝 데이터 저장(upsert)"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("user_tuning").upsert({
            "user_id": user_id,
            "tuning_type": tuning_type,
            "key": key,
            "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }, on_conflict="user_id,tuning_type,key").execute()
        return True
    except Exception as e:
        st.warning(f"튜닝 데이터 저장 오류: {e}")
        return False


def load_tuning_data(user_id: str, tuning_type: str = None):
    """튜닝 데이터 불러오기"""
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = client.table("user_tuning").select("*").eq("user_id", user_id)
        if tuning_type:
            query = query.eq("tuning_type", tuning_type)
        result = query.order("updated_at", desc=True).execute()
        return result.data if result.data else []
    except Exception:
        return []


def delete_tuning_data(user_id: str, tuning_type: str, key: str):
    """튜닝 데이터 삭제"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("user_tuning").delete().eq(
            "user_id", user_id
        ).eq("tuning_type", tuning_type).eq("key", key).execute()
        return True
    except Exception:
        return False


def build_user_system_prompt(user_id: str) -> str:
    """
    사용자의 튜닝 데이터를 기반으로 시스템 프롬프트 생성
    """
    base_prompt = (
        "너는 당곡고등학교 학생들의 학습을 돕는 친절한 AI 도우미야. "
        "학생이 스스로 생각하고 탐구할 수 있도록 도와줘. "
        "설명은 고등학생 눈높이에 맞춰 쉽고 친근하게 해줘. "
        "한국어로 답변해줘.\n\n"
    )

    tuning_data = load_tuning_data(user_id)
    if not tuning_data:
        return base_prompt

    # 카테고리별 정리
    profile_items = []
    preference_items = []
    knowledge_items = []
    custom_items = []

    for item in tuning_data:
        t = item.get("tuning_type", "")
        k = item.get("key", "")
        v = item.get("value", "")
        if t == "profile":
            profile_items.append(f"- {k}: {v}")
        elif t == "preference":
            preference_items.append(f"- {k}: {v}")
        elif t == "knowledge":
            knowledge_items.append(f"- {k}: {v}")
        elif t == "custom_instruction":
            custom_items.append(v)

    parts = [base_prompt]

    if profile_items:
        parts.append("【이 학생의 프로필 정보】\n" + "\n".join(profile_items))
    if preference_items:
        parts.append("【학습 선호 설정】\n" + "\n".join(preference_items))
    if knowledge_items:
        parts.append("【학생이 제공한 배경 지식 / 메모】\n" + "\n".join(knowledge_items))
    if custom_items:
        parts.append("【특별 지시사항】\n" + "\n".join(custom_items))

    return "\n\n".join(parts)


# ==============================================================
# 파일 메타데이터 저장
# ==============================================================

def save_file_metadata(user_id: str, filename: str, file_type: str,
                       file_size: int, extracted_text: str = ""):
    """업로드 파일 정보 저장"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("uploaded_files").insert({
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "extracted_text": extracted_text[:50000],  # 최대 50K 문자
        }).execute()
        return True
    except Exception:
        return False


def get_user_files(user_id: str, limit: int = 20):
    """사용자 파일 목록"""
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = (
            client.table("uploaded_files")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data if result.data else []
    except Exception:
        return []
