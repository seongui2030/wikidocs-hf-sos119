import os
from datetime import datetime, timezone
import gradio as gr
from supabase import Client

def sync_google_user_to_supabase(supabase: Client, user_data: dict) -> dict:
    """
    실제 구글 로그인 사용자 정보를 Supabase public.app_users 테이블에 기록/갱신
    (id, email, name, created_at, updated_at 동기화)
    """
    if not supabase or not user_data:
        return user_data

    email = user_data.get("email")
    name = user_data.get("name") or user_data.get("preferred_username") or email.split("@")[0]
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # 기존 사용자 확인
        existing = supabase.table("app_users").select("*").eq("email", email).execute()
        
        if existing.data and len(existing.data) > 0:
            # 기존 사용자 -> updated_at 갱신
            supabase.table("app_users").update({
                "name": name,
                "updated_at": now_iso
            }).eq("email", email).execute()
        else:
            # 신규 가입 -> created_at, updated_at 동시 생성
            supabase.table("app_users").insert({
                "email": email,
                "name": name,
                "created_at": now_iso,
                "updated_at": now_iso
            }).execute()

        print(f"✅ Supabase app_users 연동 완료: {email} ({name})")
    except Exception as e:
        print(f"⚠️ app_users DB 연동 오류: {e}")

    return {"email": email, "name": name}


def render_auth_header(user_profile: dict) -> str:
    """로그인 상태에 따른 상단 헤더 렌더링"""
    if not user_profile or not user_profile.get("email"):
        return """
        <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 4px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:36px; height:36px; background-color:#d32f2f; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:18px;">🚨</div>
                <div style="font-weight:bold; font-size:17px; color:#b71c1c;">스마트119</div>
            </div>
            <span style="font-size:12px; color:#888;">로그인이 필요합니다</span>
        </div>
        """

    name = user_profile.get("name", "사용자")
    email = user_profile.get("email", "")
    return f"""
    <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 4px;">
        <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:36px; height:36px; background-color:#d32f2f; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:18px;">🚨</div>
            <div>
                <div style="font-weight:bold; font-size:16px; color:#b71c1c;">스마트119</div>
                <div style="font-size:12px; color:#555;">{name} ({email})</div>
            </div>
        </div>
        <span style="background-color:#d32f2f; color:white; padding:6px 12px; border-radius:20px; font-size:12px; font-weight:bold;">● 온라인</span>
    </div>
    """