import streamlit as st
from datetime import datetime

try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False


def get_client():
    if not SUPABASE_OK:
        return None
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception:
        return None


# ── 사용자 ──

def upsert_user(user_id, email, name, picture=""):
    c = get_client()
    if not c:
        return
    try:
        c.table("users").upsert({
            "id": user_id, "email": email, "name": name,
            "picture": picture, "last_login": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        st.warning(f"사용자 저장 오류: {e}")


# ── 대화 저장/로드 ──

def save_message(user_id, role, content, model="",
                 input_tokens=0, output_tokens=0, session_name="default"):
    c = get_client()
    if not c:
        return
    try:
        c.table("conversations").insert({
            "user_id": user_id, "session_name": session_name,
            "role": role, "content": content, "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
        }).execute()
    except Exception:
        pass


def load_conversations(user_id, session_name="default", limit=50):
    c = get_client()
    if not c:
        return []
    try:
        r = (c.table("conversations")
             .select("*")
             .eq("user_id", user_id)
             .eq("session_name", session_name)
             .order("created_at", desc=False)
             .limit(limit)
             .execute())
        return r.data or []
    except Exception:
        return []


def get_user_sessions(user_id):
    c = get_client()
    if not c:
        return ["default"]
    try:
        r = (c.table("conversations")
             .select("session_name")
             .eq("user_id", user_id)
             .execute())
        if r.data:
            s = sorted(set(row["session_name"] for row in r.data))
            return s if s else ["default"]
        return ["default"]
    except Exception:
        return ["default"]


def delete_session(user_id, session_name):
    c = get_client()
    if not c:
        return
    try:
        c.table("conversations").delete().eq(
            "user_id", user_id).eq("session_name", session_name).execute()
    except Exception:
        pass


def get_usage_stats(user_id):
    c = get_client()
    if not c:
        return {"total_input": 0, "total_output": 0, "total_messages": 0}
    try:
        r = (c.table("conversations")
             .select("input_tokens, output_tokens")
             .eq("user_id", user_id)
             .eq("role", "assistant")
             .execute())
        if r.data:
            return {
                "total_input": sum(x.get("input_tokens", 0) for x in r.data),
                "total_output": sum(x.get("output_tokens", 0) for x in r.data),
                "total_messages": len(r.data),
            }
        return {"total_input": 0, "total_output": 0, "total_messages": 0}
    except Exception:
        return {"total_input": 0, "total_output": 0, "total_messages": 0}


# ── 튜닝 데이터 ──

def save_tuning(user_id, tuning_type, key, value):
    c = get_client()
    if not c:
        return
    try:
        c.table("user_tuning").upsert({
            "user_id": user_id, "tuning_type": tuning_type,
            "key": key, "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }, on_conflict="user_id,tuning_type,key").execute()
    except Exception:
        pass


def load_tuning(user_id, tuning_type=None):
    c = get_client()
    if not c:
        return []
    try:
        q = c.table("user_tuning").select("*").eq("user_id", user_id)
        if tuning_type:
            q = q.eq("tuning_type", tuning_type)
        r = q.order("updated_at", desc=True).execute()
        return r.data or []
    except Exception:
        return []


def delete_tuning(user_id, tuning_type, key):
    c = get_client()
    if not c:
        return
    try:
        c.table("user_tuning").delete().eq(
            "user_id", user_id).eq(
            "tuning_type", tuning_type).eq("key", key).execute()
    except Exception:
        pass


def build_system_prompt(user_id):
    base = (
        "너는 당곡고등학교 학생들의 학습을 돕는 친절한 AI 도우미야. "
        "학생이 스스로 생각하고 탐구할 수 있도록 도와줘. "
        "설명은 고등학생 눈높이에 맞춰 쉽고 친근하게 해줘. "
        "한국어로 답변해줘.\n\n"
    )
    data = load_tuning(user_id)
    if not data:
        return base

    profile, pref, know, custom = [], [], [], []
    for d in data:
        t, k, v = d.get("tuning_type", ""), d.get("key", ""), d.get("value", "")
        if t == "profile":
            profile.append(f"- {k}: {v}")
        elif t == "preference":
            pref.append(f"- {k}: {v}")
        elif t == "knowledge":
            know.append(f"- {k}: {v}")
        elif t == "custom_instruction":
            custom.append(v)

    parts = [base]
    if profile:
        parts.append("【학생 프로필】\n" + "\n".join(profile))
    if pref:
        parts.append("【학습 선호】\n" + "\n".join(pref))
    if know:
        parts.append("【배경 지식】\n" + "\n".join(know))
    if custom:
        parts.append("【특별 지시】\n" + "\n".join(f"- {c}" for c in custom))
    return "\n\n".join(parts)


# ── 파일 메타데이터 ──

def save_file_meta(user_id, filename, file_type, file_size, text=""):
    c = get_client()
    if not c:
        return
    try:
        c.table("uploaded_files").insert({
            "user_id": user_id, "filename": filename,
            "file_type": file_type, "file_size": file_size,
            "extracted_text": text[:50000],
        }).execute()
    except Exception:
        pass


def get_user_files(user_id, limit=20):
    c = get_client()
    if not c:
        return []
    try:
        r = (c.table("uploaded_files")
             .select("*")
             .eq("user_id", user_id)
             .order("created_at", desc=True)
             .limit(limit)
             .execute())
        return r.data or []
    except Exception:
        return []
