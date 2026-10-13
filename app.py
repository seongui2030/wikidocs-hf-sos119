"""
SOS인공지능 - AI 건강 상담 & 신체측정(BMI/BMR) & 긴급 SOS & 대화기록 관리 (app.py)
- 주요 기능:
  1) 💪 팔뚝 아이콘: 키/몸무게/나이/성별/메모 입력 ➔ BMI & BMR 자동 계산 ➔ app_users(id) FK 연동 저장
  2) 🎙️ 플로팅 마이크 (image-6.png): 화면 상시 고정 + 원터치 즉시 음성 녹음
  3) 🕒 대화 기록 모달 (image-5.png): 실시간 검색, 개별 삭제, CSV/PDF 내보내기
  4) 🚨 응급 SOS 모달 (image-4.png): 119 즉시전화, GPS 측정, 구글맵/카카오맵 긴급 SMS 브로드캐스트
  5) Groq LLM: "어르신" 호칭 제외 + 실시간 KST 요일/시각 주입 + Whisper-large-v3 STT + gTTS
"""

import os
import re
import json
import base64
import tempfile
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

import gradio as gr
from groq import Groq
from gtts import gTTS
from supabase import create_client, Client

from admin import (
    is_admin_user, make_admin_modal_html, 
    admin_delete_user, admin_toggle_ban_user, admin_export_table_csv
)

# ============================================================
# 1. 환경 설정 및 한국 표준시(KST) 정의
# ============================================================
load_dotenv()

KST = timezone(timedelta(hours=9))
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

def now_kst() -> datetime:
    """현재 한국 시각 반환"""
    return datetime.now(KST)

def now_kst_iso() -> str:
    """한국 시간 기준 ISO 문자열 반환 (+09:00 오프셋 포함)"""
    return now_kst().isoformat()

# 환경 변수 로드
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SPACE_HOST = os.getenv("SPACE_HOST", "")
PUBLIC_APP_URL = f"https://{SPACE_HOST}" if SPACE_HOST else "https://lilyjeongwon-sos119.hf.space"

# Supabase 클라이언트 초기화
supabase_client: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[Supabase 초기화 오류]: {e}")

# Groq 클라이언트 초기화
groq_client: Groq = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"[Groq 초기화 오류]: {e}")

PRIMARY_MODEL = "qwen/qwen3.8-27b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

# ============================================================
# 2. 응급 키워드 및 의료 가이드라인 (RAG & 법적 고지)
# ============================================================
EMERGENCY_KEYWORDS = [
    "가슴이 아파", "숨을 못", "숨이 안", "의식", "기절", "마비",
    "119", "쓰러", "흉통", "살려줘", "피가 나", "호흡곤란"
]

def check_emergency(text: str) -> bool:
    """응급 상황 키워드 감지"""
    return any(kw in text for kw in EMERGENCY_KEYWORDS)

OFFICIAL_MEDICAL_GUIDELINES = {
    "흉통": "질병관리청: 갑작스러운 흉통, 턱이나 팔로 뻗치는 방사통은 심근경색 의심 신호입니다. 즉시 안정을 취하고 119에 연락하세요.",
    "두통": "119 응급처치: 벼락 맞은 듯한 극심한 두통이나 시야 장애, 편마비가 동반되면 뇌졸중 의심 증상입니다.",
    "화상": "응급의학 가이드라인: 흐르는 찬물에 15~20분간 환부를 식히고 물집은 터뜨리지 마세요. 얼음 직접 접촉은 금지입니다.",
    "호흡": "질병관리청: 입술이 파래지거나 숨소리가 거칠어지는 호흡곤란은 즉각적인 기도 확보 및 119 신고가 필요합니다.",
    "어지럼": "응급의료센터: 갑작스러운 회전성 어지럼증과 균형 장애가 발생하면 낙상에 주의하고 즉시 눕혀 안정을 취하게 하세요."
}

def retrieve_medical_context(text: str) -> str:
    """맞춤형 공식 지침 반환 (RAG)"""
    matched = []
    for kw, guide in OFFICIAL_MEDICAL_GUIDELINES.items():
        if kw in text:
            matched.append(guide)
    if matched:
        return "\n[공식 응급/의료 가이드라인 참고]\n" + "\n".join(matched) + "\n"
    return ""

LEGAL_DISCLAIMER = (
    "\n\n⚠️ **[안내]** 본 상담은 건강 정보 참고용이며 전문의의 진단을 대신하지 않습니다. "
    "위급 상황 시 즉시 119에 연락하십시오."
)

# ============================================================
# 3. 데이터베이스 헬퍼 함수 (app_users, bmi, chat_logs, emergency_logs)
# ============================================================
def sync_user_to_db(user) -> str:
    """구글 로그인 사용자 정보를 app_users 테이블에 KST 기준으로 동기화하고 user_id(UUID) 반환"""
    if not supabase_client or not user:
        return ""
    try:
        user_meta = getattr(user, "user_metadata", {}) or {}
        email = getattr(user, "email", "") or ""
        name = user_meta.get("full_name") or user_meta.get("name") or email.split("@")[0]
        user_id = str(getattr(user, "id", ""))
        
        data = {
            "id": user_id,
            "email": email,
            "name": name,
            "updated_at": now_kst_iso()
        }
        supabase_client.table("app_users").upsert(data, on_conflict="id").execute()
        return user_id
    except Exception as e:
        print(f"[Supabase sync_user 오류]: {e}")
        return ""

def ensure_guest_user_in_db() -> str:
    """게스트 체험 시 외래키(app_users.id) 충돌 방지를 위한 기본 게스트 계정 확보"""
    if not supabase_client:
        return ""
    try:
        guest_email = "guest@smart119.local"
        res = supabase_client.table("app_users").select("id").eq("email", guest_email).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["id"]
        
        insert_res = supabase_client.table("app_users").insert({
            "email": guest_email,
            "name": "체험용게스트",
            "updated_at": now_kst_iso()
        }).execute()
        if insert_res.data:
            return insert_res.data[0]["id"]
    except Exception as e:
        print(f"[게스트 유저 확인/생성 오류]: {e}")
    return ""

def save_bmi_record(user_id: str, age: int, height: float, weight: float, gender: str, memo: str = "") -> dict:
    """
    ④ 신체 데이터 자동 계산 및 연동:
    - BMI = weight / (height/100)^2
    - BMR = 해리스-베네딕트/미플린 공식
    ⑤ 사용자 계정 관리 연동: bmi.user_id ➔ app_users.id (UUID FK)
    """
    if not supabase_client or not user_id:
        return {"success": False, "message": "데이터베이스 또는 사용자 계정 정보가 없습니다."}
    
    try:
        # BMI 계산
        h_m = height / 100.0
        bmi_val = round(weight / (h_m * h_m), 2)
        
        # BMR 계산 (Mifflin-St Jeor 공식)
        if "여" in gender or gender.lower() in ["female", "f"]:
            bmr_val = round((10 * weight) + (6.25 * height) - (5 * age) - 161, 2)
        else:
            bmr_val = round((10 * weight) + (6.25 * height) - (5 * age) + 5, 2)
            
        data = {
            "user_id": user_id,
            "age": int(age),
            "height": float(height),
            "weight": float(weight),
            "gender": gender,
            "bmi_value": float(bmi_val),
            "bmr_value": float(bmr_val),
            "created_at": now_kst_iso(),
            "updated_at": now_kst_iso()
        }
        
        # memo 컬럼이 테이블에 존재하는지 확인하여 저장 시도
        try:
            data_with_memo = dict(data)
            data_with_memo["memo"] = memo or ""
            supabase_client.table("bmi").insert(data_with_memo).execute()
        except Exception:
            # memo 컬럼이 없는 기존 스키마일 경우 memo 제외하고 재시도
            supabase_client.table("bmi").insert(data).execute()
            
        return {
            "success": True,
            "bmi": bmi_val,
            "bmr": bmr_val,
            "message": "BMI 및 BMR 신체 데이터가 안전하게 저장되었습니다!"
        }
    except Exception as e:
        print(f"[BMI 저장 오류]: {e}")
        return {"success": False, "message": f"저장 실패: {str(e)}"}

def fetch_latest_bmi_record(user_id: str) -> dict:
    """사용자의 가장 최근 BMI/BMR 측정 기록 조회"""
    if not supabase_client or not user_id:
        return None
    try:
        res = (
            supabase_client.table("bmi")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        print(f"[최신 BMI 조회 오류]: {e}")
    return None

def save_chat_log(user_email: str, user_msg: str, bot_reply: str, is_emergency: bool):
    """대화 기록을 Supabase chat_logs 테이블에 KST 기준으로 저장"""
    if not supabase_client or not user_email:
        return
    try:
        data = {
            "user_email": user_email,
            "user_message": user_msg,
            "bot_reply": bot_reply,
            "is_emergency": is_emergency,
            "created_at": now_kst_iso()
        }
        supabase_client.table("chat_logs").insert(data).execute()
    except Exception as e:
        print(f"[Supabase save_chat 오류]: {e}")

def fetch_user_chat_logs(user_email: str) -> list:
    """Supabase chat_logs 조회"""
    if not supabase_client or not user_email:
        return []
    try:
        res = (
            supabase_client.table("chat_logs")
            .select("id, user_message, bot_reply, is_emergency, created_at")
            .eq("user_email", user_email)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[Supabase fetch_chat_logs 오류]: {e}")
        return []

def delete_single_chat_log(log_id: int):
    """단일 대화 기록 삭제"""
    if not supabase_client or not log_id:
        return
    try:
        supabase_client.table("chat_logs").delete().eq("id", log_id).execute()
    except Exception as e:
        print(f"[대화 삭제 실패]: {e}")

def fetch_emergency_contacts(email: str) -> list:
    """비상연락망 조회"""
    if not supabase_client or not email or "guest" in email:
        return []
    try:
        res = supabase_client.table("emergency_contacts").select("contact_name, relationship, phone_number").eq("user_email", email).execute()
        return res.data or []
    except Exception as e:
        return []

def log_emergency_dispatch(user_email: str, symptom: str, lat: float, lng: float, map_url: str, recipients: list):
    """응급 발송 기록 저장"""
    if not supabase_client:
        return
    try:
        supabase_client.table("emergency_logs").insert({
            "user_email": user_email or "guest@smart119.local",
            "symptom": symptom or "긴급 SOS 사이렌 호출",
            "latitude": lat,
            "longitude": lng,
            "map_url": map_url,
            "recipients": recipients,
            "created_at": now_kst_iso()
        }).execute()
    except Exception as e:
        print(f"[Emergency Log 저장 실패]: {e}")

# ============================================================
# 4. 음성 처리 (STT & TTS) 및 Groq LLM ('어르신' 호칭 제거 프롬프트)
# ============================================================
def speech_to_text(audio_path: str) -> str:
    """Groq Whisper-large-v3 음성인식"""
    if not audio_path or not groq_client:
        return ""
    try:
        with open(audio_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=f,
                model="whisper-large-v3",
                language="ko",
                response_format="text"
            )
        return str(transcription).strip()
    except Exception as e:
        print(f"[STT 오류]: {e}")
        return ""

def text_to_speech(text: str) -> str:
    """gTTS 음성 합성"""
    if not text:
        return None
    try:
        clean_text = re.sub(r"\[.*?\]", "", text)
        clean_text = re.sub(r"[\*\_#`🚨⚠️<>]", "", clean_text)
        clean_text = clean_text.split("본 상담은 건강")[0].strip()[:150]
        # 음성에서만 앱 이름의 발음을 변경
        clean_text = re.sub(r"스마트\s*119", "스마트 일일구", clean_text)
        if not clean_text:
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tts = gTTS(text=clean_text, lang="ko")
            tts.save(tmp.name)
            return tmp.name
    except Exception as e:
        print(f"[TTS 오류]: {e}")
        return None

def call_groq_llm(user_message: str, history: list, user_name: str = "") -> str:
    """Groq API 호출 ('어르신' 호칭 제외 + 존댓말 + 실시간 KST 시간 주입)"""
    if not groq_client:
        return "현재 AI 상담 서비스가 점검 중입니다. 급한 증상은 119 또는 1339에 문의하세요."

    now = now_kst()
    weekday_str = WEEKDAY_KO[now.weekday()]
    date_info = (
        f"현재 한국 시각은 {now.year}년 {now.month}월 {now.day}일 {weekday_str}요일 "
        f"{now.hour}시 {now.minute}분입니다. 날짜, 요일, 시간을 질문하면 이 정보를 기준으로 답하세요."
    )

    med_ctx = retrieve_medical_context(user_message)
    name_guide = f"'{user_name}님'이라고 부르거나 호칭 없이" if user_name and user_name != "게스트" else "불필요한 호칭 없이"

    # [수정] '어르신' 호칭을 쓰지 않도록 시스템 프롬프트 규칙 명시
    system_prompt = (
        "당신은 사용자의 건강을 따뜻하게 돌보는 119 건강 비서 'SOS인공지능'입니다.\n"
        f"{date_info}\n"
        f"{med_ctx}\n"
        "지침:\n"
        f"1. 상대방을 절대 '어르신'이라고 부르지 마세요. {name_guide} 다정하고 공손한 존댓말(~해요, ~하세요, ~입니다)로 2~3문장 이내로 답변하세요.\n"
        "2. 절대 자의적으로 병명을 단정하지 말고, 일상 속 관리 요령이나 병원 진료를 권유하세요.\n"
        "3. 증상이 위험해 보이면 즉시 119 구급대 호출을 안내하세요."
    )

    messages = [{"role": "system", "content": system_prompt}]

    for h in history[-6:]:
        content = h.get("content", "")
        if isinstance(content, list):
            content = " ".join([str(x) for x in content])
        messages.append({"role": h.get("role", "user"), "content": str(content)})
    messages.append({"role": "user", "content": user_message})

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        try:
            resp = groq_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.5,
                max_tokens=500
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            continue

    return "죄송합니다. 일시적인 통신 지연이 발생했습니다. 잠시 후 다시 말씀해 주세요."

# ============================================================
# 5. UI 스타일 (CSS) - 💪 신체측정(BMI) 모달 스타일 추가
# ============================================================
CUSTOM_CSS = """
.gradio-container {
    max-width: 440px !important;
    margin: 0 auto !important;
    padding: 0 !important;
    background: #f1f5f9 !important;
    min-height: 100vh !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", sans-serif !important;
    color: #1e293b !important;
    touch-action: manipulation;
    position: relative !important;
}

#header-container, #header-container > div, #header-container .prose {
    overflow: visible !important;
    position: relative !important;
    z-index: 99999 !important;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    position: sticky;
    top: 0;
    z-index: 99999 !important;
    overflow: visible !important;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 8px;
}
.header-app-name {
    font-size: 17px;
    font-weight: 800;
    color: #059669;
}
.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
}
.header-icon-btn {
    background: transparent;
    border: none;
    font-size: 19px;
    cursor: pointer;
    padding: 4px;
}
.sos-btn {
    font-size: 20px;
    animation: pulse-sos 2s infinite;
}
@keyframes pulse-sos {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.18); }
}

.profile-dropdown-wrapper {
    position: relative !important;
    display: inline-block !important;
    z-index: 100000 !important;
}
.profile-trigger {
    cursor: pointer;
    border-radius: 50%;
}
.profile-avatar-img {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #059669;
}
.profile-avatar-fallback {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #059669;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    border: 2px solid #047857;
}

.profile-menu {
    display: none;
    position: absolute !important;
    right: 0 !important;
    top: 42px !important;
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    min-width: 130px !important;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15) !important;
    z-index: 999999 !important;
    overflow: hidden;
}
.profile-menu.show { display: block !important; }
.menu-user-info {
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 700;
    color: #334155;
    border-bottom: 1px solid #f1f5f9;
}
.menu-logout-btn {
    width: 100%;
    padding: 10px 14px;
    background: transparent;
    border: none;
    color: #ef4444;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
}
.menu-logout-btn:hover { background: #fee2e2; }

#main-chatbot {
    background: #f1f5f9 !important;
    border: none !important;
    padding-bottom: 180px !important;
    min-height: calc(100vh - 240px) !important;
}

/* 플로팅 마이크 컨테이너 */
.floating-bottom-container {
    position: fixed !important;
    bottom: 0 !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: 100% !important;
    max-width: 440px !important;
    background: linear-gradient(180deg, rgba(241,245,249,0) 0%, rgba(241,245,249,0.95) 20%, #f1f5f9 100%) !important;
    padding: 10px 16px 14px 16px !important;
    box-sizing: border-box !important;
    z-index: 9999 !important;
    display: flex;
    flex-direction: column;
    align-items: center;
}
.floating-mic-btn {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    background: #00875a;
    border: 3px solid #ffffff;
    box-shadow: 0 8px 24px rgba(0, 135, 90, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    margin-bottom: 6px;
    outline: none;
}
.floating-mic-btn:active { transform: scale(0.92); }
.floating-mic-btn.recording {
    background: #ef4444 !important;
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.3) !important;
    animation: mic-pulsing 1.2s infinite;
}
@keyframes mic-pulsing {
    0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
    50% { transform: scale(1.08); box-shadow: 0 0 0 14px rgba(239, 68, 68, 0); }
    100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
.floating-mic-btn svg { width: 32px; height: 32px; fill: #ffffff; }
.floating-mic-label {
    font-size: 13px;
    font-weight: 700;
    color: #475569;
    margin-bottom: 8px;
}
.bottom-input-row {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}
#chat-msg-input textarea, #chat-msg-input input {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 25px !important;
    padding: 10px 18px !important;
    font-size: 14px !important;
}
#chat-msg-input textarea:focus, #chat-msg-input input:focus { border-color: #00875a !important; }
#chat-send-btn {
    border-radius: 50% !important;
    width: 44px !important;
    height: 44px !important;
    min-width: 44px !important;
    padding: 0 !important;
    background: #00875a !important;
    border: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: #ffffff !important;
}
.intro-card { padding: 40px 20px; text-align: center; }
.google-login-link-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    width: 100%;
    padding: 14px 16px;
    background: #ffffff;
    color: #1f2937;
    font-weight: 600;
    font-size: 15px;
    border-radius: 14px;
    text-decoration: none;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
    margin-bottom: 12px;
}
.hidden-box { display: none !important; }

/* ============================================================
   [신규] 💪 신체 데이터(BMI / BMR) 모달 스타일
   ============================================================ */
.bmi-modal-overlay {
    display: none;
    position: fixed !important;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(4px);
    z-index: 9999999 !important;
    justify-content: center;
    align-items: center;
    padding: 16px;
    box-sizing: border-box;
}
.bmi-modal-overlay.active { display: flex !important; }

.bmi-modal-card {
    width: 100%;
    max-width: 410px;
    max-height: 88vh;
    background: #ffffff;
    border-radius: 28px;
    padding: 24px 20px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    position: relative;
    overflow-y: auto;
    box-sizing: border-box;
}
.bmi-modal-close-btn {
    position: absolute;
    top: 18px;
    right: 18px;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 1.5px solid #0284c7;
    background: #ffffff;
    color: #0284c7;
    font-size: 16px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}
.bmi-modal-header {
    text-align: center;
    margin-top: 6px;
    margin-bottom: 16px;
}
.bmi-modal-title {
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
    margin: 0 0 4px 0;
}
.bmi-modal-desc {
    font-size: 12px;
    color: #64748b;
    margin: 0;
}
.bmi-result-card {
    background: #f0fdf4;
    border: 1.5px solid #86efac;
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 16px;
    text-align: center;
}
.bmi-result-badge {
    font-size: 22px;
    font-weight: 800;
    color: #15803d;
}
.bmi-result-sub {
    font-size: 12px;
    color: #166534;
    margin-top: 4px;
}
.bmi-form-group {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 14px;
}
.bmi-form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}
.bmi-input-label {
    font-size: 12px;
    font-weight: 700;
    color: #334155;
    margin-bottom: 4px;
}
.bmi-input-field {
    width: 100%;
    padding: 10px 12px;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    font-size: 14px;
    box-sizing: border-box;
    outline: none;
}
.bmi-input-field:focus { border-color: #0284c7; }
.bmi-save-btn {
    background: #0284c7;
    color: #ffffff;
    font-size: 15px;
    font-weight: 800;
    padding: 13px;
    border-radius: 16px;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35);
    margin-top: 6px;
}
.bmi-save-btn:active { transform: scale(0.98); }

/* 기존 SOS 및 대화기록 모달 스타일 */
.sos-modal-overlay, .history-modal-overlay {
    display: none;
    position: fixed !important;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(4px);
    z-index: 9999999 !important;
    justify-content: center;
    align-items: center;
    padding: 16px;
    box-sizing: border-box;
}
.sos-modal-overlay.active, .history-modal-overlay.active { display: flex !important; }
.sos-modal-card, .history-modal-card {
    background: #fdfbf7;
    width: 100%;
    max-width: 410px;
    max-height: 88vh;
    border-radius: 28px;
    padding: 22px 18px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: relative;
    box-sizing: border-box;
}
.sos-modal-close, .history-modal-close-btn {
    position: absolute;
    top: 18px; right: 18px;
    background: none; border: none; font-size: 20px; color: #94a3b8; cursor: pointer;
}
.sos-call-119-btn {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    background: #be123c; color: #ffffff !important; text-decoration: none !important;
    font-size: 16px; font-weight: 800; padding: 14px 20px; border-radius: 50px;
}
.sos-section-box {
    background: #ffffff; border: 1px solid #f1f5f9; border-radius: 18px; padding: 14px;
}
.sos-send-sms-btn {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    background: #be123c; color: #ffffff !important; text-decoration: none !important;
    font-size: 15px; font-weight: 800; padding: 14px 20px; border-radius: 50px; cursor: pointer;
}
.history-item-card {
    background: #e6f7ef; border: 1.5px solid #a7f3d0; border-radius: 16px;
    padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;
}
.history-item-text { font-size: 13px; font-weight: 700; color: #065f46; }
.history-item-time { font-size: 11px; color: #059669; }
.history-item-del-btn { background: none; border: none; color: #ef4444; font-size: 16px; cursor: pointer; }
.export-section-card { background: #ffffff; border-radius: 18px; padding: 14px; }
.export-btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.export-action-btn {
    background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 14px;
    padding: 9px 8px; font-size: 12px; font-weight: 700; color: #065f46; cursor: pointer;
}
"""

# ============================================================
# 6. JavaScript 통합 스크립트 (BMI 계산 & 브릿지)
# ============================================================
APP_CLIENT_JS = """
() => {
    // 1. Google OAuth 해시 감지
    const hash = window.location.hash;
    if (hash && hash.includes("access_token=")) {
        const params = new URLSearchParams(hash.substring(1));
        const token = params.get("access_token");
        if (token) {
            setTimeout(() => {
                const tokenInput = document.querySelector("#oauth-token-bridge textarea, #oauth-token-bridge input");
                if (tokenInput) {
                    tokenInput.value = token;
                    tokenInput.dispatchEvent(new Event("input", { bubbles: true }));
                    tokenInput.dispatchEvent(new Event("change", { bubbles: true }));
                    window.history.replaceState(null, null, window.location.pathname);
                }
            }, 400);
        }
    }

    // 2. 프로필 메뉴 바깥 클릭 닫기
    document.addEventListener("click", (e) => {
        const menu = document.getElementById("profile-menu");
        const trigger = document.querySelector(".profile-trigger");
        if (menu && menu.classList.contains("show")) {
            if (!menu.contains(e.target) && !trigger.contains(e.target)) {
                menu.classList.remove("show");
            }
        }
    });

    // 채팅 응답의 SOS 버튼은 헤더의 응급 사이렌 버튼으로 연결합니다.
    // 응답이 나중에 추가되어도 동작하도록 클릭 이벤트를 위임합니다.
    document.addEventListener("click", (e) => {
        const sosButton = e.target.closest("#main-chatbot .chat-sos-btn");
        if (!sosButton) return;
        e.preventDefault();
        const headerSosButton = document.querySelector("#header-container .sos-btn");
        if (headerSosButton) headerSosButton.click();
    });

    // 3. 플로팅 마이크 녹음
    let mediaRecorder = null;
    let audioChunks = [];

    window.toggleVoiceRecording = async function() {
        const micBtn = document.getElementById("floating-mic-button");
        const micLabel = document.getElementById("floating-mic-status-label");

        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            if (micBtn) micBtn.classList.remove("recording");
            if (micLabel) micLabel.innerText = "음성을 분석하고 있습니다...";
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64Data = reader.result.split(",")[1];
                    const bridge = document.querySelector("#voice-base64-bridge textarea, #voice-base64-bridge input");
                    if (bridge) {
                        bridge.value = base64Data;
                        bridge.dispatchEvent(new Event("input", { bubbles: true }));
                        bridge.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                    if (micLabel) micLabel.innerText = "오늘 컨디션은 어떠세요!";
                };
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            if (micBtn) micBtn.classList.add("recording");
            if (micLabel) micLabel.innerText = "듣고 있어요... 끝나면 다시 누르세요";

        } catch (err) {
            alert("마이크 사용 권한을 허용해 주세요.");
            if (micLabel) micLabel.innerText = "오늘 컨디션은 어떠세요!";
        }
    };

    // 4. [신규] 💪 신체측정(BMI / BMR) 모달 제어
    window.openBmiModal = function() {
        const modal = document.getElementById("bmi-modal-overlay");
        if (modal) modal.classList.add("active");
    };

    window.closeBmiModal = function() {
        const modal = document.getElementById("bmi-modal-overlay");
        if (modal) modal.classList.remove("active");
    };

    // BMI/BMR 클라이언트 실시간 프리뷰 및 저장 요청
    window.submitBmiData = function() {
        const height = parseFloat(document.getElementById("bmi-height-input")?.value);
        const weight = parseFloat(document.getElementById("bmi-weight-input")?.value);
        const age = parseInt(document.getElementById("bmi-age-input")?.value, 10);
        const gender = document.getElementById("bmi-gender-input")?.value || "남성";
        const memo = document.getElementById("bmi-memo-input")?.value || "";

        if (!height || !weight || !age) {
            alert("키, 몸무게, 나이를 모두 올바르게 입력해 주세요.");
            return;
        }

        const payload = JSON.stringify({
            height: height,
            weight: weight,
            age: age,
            gender: gender,
            memo: memo
        });

        const bridge = document.querySelector("#bmi-data-bridge textarea, #bmi-data-bridge input");
        if (bridge) {
            bridge.value = payload;
            bridge.dispatchEvent(new Event("input", { bubbles: true }));
            bridge.dispatchEvent(new Event("change", { bubbles: true }));
        }
    };

    // 5. 응급 SOS 모달 제어
    window.openEmergencyModal = function(userName) {
        const modal = document.getElementById("sos-modal-overlay");
        if (!modal) return;
        modal.classList.add("active");

        const coordEl = document.getElementById("sos-coords");
        const accEl = document.getElementById("sos-accuracy");
        const gmapLinkEl = document.getElementById("sos-gmap-link");
        const kmapLinkEl = document.getElementById("sos-kmap-link");
        const smsBtn = document.getElementById("sos-sms-btn");
        const contactBox = document.getElementById("sos-contact-list");

        let contacts = [];
        try {
            if (contactBox && contactBox.dataset.contacts) contacts = JSON.parse(contactBox.dataset.contacts);
        } catch(e) {}

        const uName = userName || "보호대상자";
        if (!navigator.geolocation) {
            if (coordEl) coordEl.innerText = "GPS 미지원 기기입니다.";
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                const acc = Math.round(pos.coords.accuracy);
                const gmapUrl = `https://maps.google.com/?q=${lat},${lng}`;
                const kmapUrl = `https://map.kakao.com/link/map/긴급위치,${lat},${lng}`;

                if (coordEl) coordEl.innerText = `위도 ${lat.toFixed(6)} / 경도 ${lng.toFixed(6)}`;
                if (accEl) accEl.innerText = `정확도 약 ±${acc}m · 위치 확정`;
                if (gmapLinkEl) { gmapLinkEl.href = gmapUrl; gmapLinkEl.innerText = gmapUrl; }
                if (kmapLinkEl) { kmapLinkEl.href = kmapUrl; kmapLinkEl.innerText = kmapUrl; }

                const phoneNumbers = contacts.map(c => c.phone_number).filter(Boolean);
                const recipientStr = phoneNumbers.join(",");
                const msgBody = encodeURIComponent(`🚨 [스마트119 긴급알림] ${uName}님이 위급합니다!\n구글지도: ${gmapUrl}\n카카오맵: ${kmapUrl}`);
                const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                const separator = isIOS ? "&" : "?";
                if (smsBtn) smsBtn.href = recipientStr ? `sms:${recipientStr}${separator}body=${msgBody}` : `sms:${separator}body=${msgBody}`;

                const bridge = document.querySelector("#emergency-log-bridge textarea, #emergency-log-bridge input");
                if (bridge) {
                    bridge.value = JSON.stringify({ lat, lng, map_url: gmapUrl, recipients: phoneNumbers });
                    bridge.dispatchEvent(new Event("input", { bubbles: true }));
                    bridge.dispatchEvent(new Event("change", { bubbles: true }));
                }
            },
            () => { if (coordEl) coordEl.innerText = "위치 권한을 허용해 주세요."; },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    };

    window.closeEmergencyModal = () => { document.getElementById("sos-modal-overlay")?.classList.remove("active"); };
    window.copyMapLink = () => {
        const link = document.getElementById("sos-gmap-link")?.href;
        if (link && link !== "#") navigator.clipboard.writeText(link).then(() => alert("구글 지도 링크 복사 완료!"));
    };

    // 6. 대화 기록 모달 제어
    window.openHistoryModal = () => { document.getElementById("history-modal-overlay")?.classList.add("active"); };
    window.closeHistoryModal = () => { document.getElementById("history-modal-overlay")?.classList.remove("active"); };
    window.filterChatHistory = (query) => {
        const q = (query || "").trim().toLowerCase();
        document.querySelectorAll(".history-item-card").forEach(c => {
            const txt = c.querySelector(".history-item-text")?.innerText.toLowerCase() || "";
            c.style.display = txt.includes(q) ? "flex" : "none";
        });
    };
    window.downloadCSV = (filename, content) => {
        const blob = new Blob(["\\uFEFF" + content], { type: "text/csv;charset=utf-8;" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
    };
    window.exportCSVHandler = (isLatest) => {
        const card = document.querySelector(".history-modal-card");
        if (!card) return;
        let logs = JSON.parse(card.getAttribute("data-logs") || "[]");
        if (!logs.length) { alert("대화 기록이 없습니다."); return; }
        if (isLatest) logs = logs.slice(0, 1);
        let csv = "ID,작성일시,사용자메시지,AI답변,응급여부\\n";
        logs.forEach(l => {
            csv += `"${l.id}","${l.created_at}","${(l.user_message||'').replace(/"/g,'""')}","${(l.bot_reply||'').replace(/"/g,'""')}","${l.is_emergency}"\\n`;
        });
        window.downloadCSV(isLatest ? "최근대화.csv" : "전체대화기록.csv", csv);
    };
    window.exportPDFHandler = (isLatest) => {
        const card = document.querySelector(".history-modal-card");
        if (!card) return;
        let logs = JSON.parse(card.getAttribute("data-logs") || "[]");
        if (!logs.length) { alert("대화 기록이 없습니다."); return; }
        if (isLatest) logs = logs.slice(0, 1);
        let html = "<html><head><title>대화기록</title></head><body><h2>스마트119 상담 기록</h2>";
        logs.forEach(l => {
            html += `<div style="border-bottom:1px solid #ccc;padding:10px 0;"><p>${l.created_at}</p><p><strong>Q:</strong> ${l.user_message}</p><p><strong>A:</strong> ${l.bot_reply}</p></div>`;
        });
        html += "</body></html>";
        const f = document.createElement("iframe");
        f.style.display = "none";
        document.body.appendChild(f);
        f.contentWindow.document.write(html);
        f.contentWindow.document.close();
        setTimeout(() => { f.contentWindow.print(); document.body.removeChild(f); }, 400);
    };
    window.requestDeleteChatLog = (id) => {
        if (!confirm("이 대화를 삭제하시겠습니까?")) return;
        const b = document.querySelector("#delete-log-bridge textarea, #delete-log-bridge input");
        if (b) { b.value = String(id); b.dispatchEvent(new Event("input", { bubbles: true })); }
    };
}
"""

# ============================================================
# 7. HTML 뷰 생성기 (헤더 💪 아이콘, BMI 모달 추가)
# ============================================================
def get_google_oauth_url() -> str:
    if not SUPABASE_URL:
        return "#"
    return f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={PUBLIC_APP_URL}"

def make_header_html(user_name="게스트", avatar_url="", user_email="") -> str:
    """헤더 HTML: 관리자 계정일 때 SOS인공지능 텍스트 클릭 시 관리자 대시보드 팝업"""
    if avatar_url:
        avatar_markup = f'<img src="{avatar_url}" alt="프로필" class="profile-avatar-img" />'
    else:
        initial = (user_name[0] if user_name else "G").upper()
        avatar_markup = f'<span class="profile-avatar-fallback">{initial}</span>'

    # 관리자 여부에 따라 SOS인공지능 텍스트 스타일 및 클릭 이벤트 부여
    if is_admin_user(user_email):
        app_title_html = """
        <span class="header-app-name" style="cursor:pointer;" onclick="window.openAdminModal()" title="관리자 대시보드 열기">
            SOS인공지능 <span style="font-size:11px; background:#047857; color:white; padding:2px 6px; border-radius:10px; vertical-align:middle;">ADMIN</span>
        </span>
        """
    else:
        app_title_html = '<span class="header-app-name">SOS인공지능</span>'

    return f"""
    <div class="app-header">
      <div class="header-left">
        {app_title_html}
      </div>
      <div class="header-right">
        <!-- 🚨 응급 사이렌 -->
        <button class="header-icon-btn sos-btn" title="응급 호출" onclick="window.openEmergencyModal('{user_name}')">🚨</button>
        <!-- 💪 신체 건강 (BMI/BMR) -->
        <button class="header-icon-btn" title="신체 건강 (BMI/BMR)" onclick="window.openBmiModal()">💪</button>
        <!-- 🕒 상담 기록 -->
        <button class="header-icon-btn" title="상담 기록" onclick="window.openHistoryModal()">🕒</button>
        <div class="profile-dropdown-wrapper">
          <div class="profile-trigger" onclick="document.getElementById('profile-menu')?.classList.toggle('show')">
            {avatar_markup}
          </div>
          <div id="profile-menu" class="profile-menu">
            <div class="menu-user-info">{user_name}</div>
            <button class="menu-logout-btn" onclick="document.getElementById('logout-action')?.click()">로그아웃</button>
          </div>
        </div>
      </div>
    </div>
    """

def make_bmi_modal_html(latest_record: dict = None) -> str:
    """④, ⑤ 신체 데이터 입력 및 자동 계산 모달 (image-5 스타일 기반)"""
    if latest_record:
        bmi_v = latest_record.get("bmi_value", 0.0)
        bmr_v = latest_record.get("bmr_value", 0.0)
        
        # BMI 등급 판정
        if bmi_v < 18.5:
            bmi_grade = "저체중 (영양 관리가 필요해요)"
        elif bmi_v < 23.0:
            bmi_grade = "정상 체중 (아주 건강해요! 🎉)"
        elif bmi_v < 25.0:
            bmi_grade = "비만 전단계 (과체중 주의)"
        else:
            bmi_grade = "비만 (가벼운 유산소 운동 권장)"
            
        result_box = f"""
        <div class="bmi-result-card">
            <div style="font-size:12px; color:#15803d; font-weight:700;">최근 측정 결과</div>
            <div class="bmi-result-badge">BMI {bmi_v} · {bmr_v} kcal</div>
            <div class="bmi-result-sub">{bmi_grade} (기초대사량: {bmr_v} kcal)</div>
        </div>
        """
        def_h = latest_record.get("height", 165)
        def_w = latest_record.get("weight", 60)
        def_a = latest_record.get("age", 65)
        def_g = latest_record.get("gender", "남성")
        def_m = latest_record.get("memo", "")
    else:
        result_box = """
        <div class="bmi-result-card" style="background:#f8fafc; border-color:#cbd5e1;">
            <div style="font-size:13px; color:#64748b;">신체 정보를 입력하면 BMI와 기초대사량이 자동 계산됩니다.</div>
        </div>
        """
        def_h, def_w, def_a, def_g, def_m = 165, 60, 65, "남성", ""

    return f"""
    <div id="bmi-modal-overlay" class="bmi-modal-overlay" onclick="if(event.target===this) window.closeBmiModal();">
        <div class="bmi-modal-card">
            <button class="bmi-modal-close-btn" onclick="window.closeBmiModal()">✕</button>

            <div class="bmi-modal-header">
                <h2 class="bmi-modal-title">💪 신체 건강 (BMI & BMR)</h2>
                <p class="bmi-modal-desc">신체 수치를 바탕으로 체질량과 기초대사량을 자동 분석합니다.</p>
            </div>

            {result_box}

            <div class="bmi-form-group">
                <div class="bmi-form-row">
                    <div>
                        <div class="bmi-input-label">키 (cm)</div>
                        <input type="number" id="bmi-height-input" class="bmi-input-field" value="{def_h}" placeholder="예: 165" />
                    </div>
                    <div>
                        <div class="bmi-input-label">몸무게 (kg)</div>
                        <input type="number" id="bmi-weight-input" class="bmi-input-field" value="{def_w}" placeholder="예: 62.5" />
                    </div>
                </div>

                <div class="bmi-form-row">
                    <div>
                        <div class="bmi-input-label">나이 (세)</div>
                        <input type="number" id="bmi-age-input" class="bmi-input-field" value="{def_a}" placeholder="예: 68" />
                    </div>
                    <div>
                        <div class="bmi-input-label">성별</div>
                        <select id="bmi-gender-input" class="bmi-input-field">
                            <option value="남성" {"selected" if def_g=="남성" else ""}>남성</option>
                            <option value="여성" {"selected" if def_g=="여성" else ""}>여성</option>
                        </select>
                    </div>
                </div>

                <div>
                    <div class="bmi-input-label">건강 메모 (혈압, 복용 약, 특이사항)</div>
                    <input type="text" id="bmi-memo-input" class="bmi-input-field" value="{def_m}" placeholder="예: 아침 고혈압 약 복용 중, 관절 통증" />
                </div>

                <button class="bmi-save-btn" onclick="window.submitBmiData()">
                    계산 및 Supabase에 저장
                </button>
            </div>
        </div>
    </div>
    """

def make_sos_modal_html(user_name="보호대상자", contacts=[]) -> str:
    contacts_json = json.dumps(contacts)
    return f"""
    <div id="sos-modal-overlay" class="sos-modal-overlay" onclick="if(event.target===this) window.closeEmergencyModal();">
        <div class="sos-modal-card">
            <button class="sos-modal-close" onclick="window.closeEmergencyModal()">✕</button>
            <a href="tel:119" class="sos-call-119-btn"><span>📞</span> 119 지금 전화하기</a>
            <div class="sos-section-box">
                <div style="font-weight:800; margin-bottom:8px;">📍 내 위치 (GPS)</div>
                <div id="sos-coords" style="font-size:12px; color:#334155;">위치 측정 대기 중...</div>
                <div id="sos-accuracy" style="font-size:11px; color:#0284c7; margin-bottom:8px;">정확도 측정 중...</div>
                <div style="font-size:11px;">구글맵: <a id="sos-gmap-link" href="#" target="_blank">측정 후 생성</a></div>
                <div style="font-size:11px;">카카오맵: <a id="sos-kmap-link" href="#" target="_blank">측정 후 생성</a></div>
            </div>
            <div id="sos-contact-list" data-contacts='{contacts_json}' data-username='{user_name}'></div>
            <a id="sos-sms-btn" href="sms:?body=긴급상황" class="sos-send-sms-btn" onclick="window.closeEmergencyModal()"><span>✈️</span> 보호자에게 위치 전송</a>
        </div>
    </div>
    """

def make_history_modal_html(logs: list, user_email: str) -> str:
    items_html = ""
    for item in logs:
        items_html += f"""
        <div class="history-item-card">
            <div>
                <div class="history-item-text">{item.get('user_message')}</div>
                <div class="history-item-time">{item.get('created_at')[:19].replace('T',' ')}</div>
            </div>
            <button class="history-item-del-btn" onclick="window.requestDeleteChatLog({item.get('id')})">🗑️</button>
        </div>
        """
    logs_json = json.dumps(logs, ensure_ascii=False).replace('"', '&quot;')
    return f"""
    <div id="history-modal-overlay" class="history-modal-overlay" onclick="if(event.target===this) window.closeHistoryModal();">
        <div class="history-modal-card" data-logs="{logs_json}">
            <button class="history-modal-close-btn" onclick="window.closeHistoryModal()">✕</button>
            <h2 style="font-size:20px; font-weight:800; text-align:center; margin:4px 0;">대화 기록</h2>
            <input type="text" class="history-search-box" placeholder="🔍 전체 기록 검색" oninput="window.filterChatHistory(this.value)" />
            <div style="display:flex; flex-direction:column; gap:8px; max-height:220px; overflow-y:auto;">{items_html or '<div style="text-align:center;color:#94a3b8;padding:20px;">기록이 없습니다.</div>'}</div>
            <div class="export-section-card">
                <div style="font-weight:800; font-size:14px; margin-bottom:8px;">내보내기</div>
                <div class="export-btn-grid">
                    <button class="export-action-btn" onclick="window.exportCSVHandler(true)">📥 이 대화 CSV</button>
                    <button class="export-action-btn" onclick="window.exportCSVHandler(false)">📥 전체 CSV</button>
                    <button class="export-action-btn" onclick="window.exportPDFHandler(true)">📄 이 대화 PDF</button>
                    <button class="export-action-btn" onclick="window.exportPDFHandler(false)">📄 전체 PDF</button>
                </div>
            </div>
        </div>
    </div>
    """

# ============================================================
# 8. Gradio UI 레이아웃 및 이벤트 바인딩
# ============================================================
# CSS 및 JS 병합
FULL_CSS = CUSTOM_CSS + "\n" + ADMIN_CSS
FULL_JS = APP_CLIENT_JS + "\n" + ADMIN_CLIENT_JS

with gr.Blocks(title="SOS인공지능", css=CUSTOM_CSS, js=APP_CLIENT_JS) as demo:
    
    # user_state: id, email, name, avatar_url, contacts
    user_state = gr.State(value={"id": "", "email": "", "name": "게스트", "avatar_url": "", "contacts": []})

    # 상단 고정 헤더 (💪 알통 팔뚝 포함)
    header_view = gr.HTML(value=make_header_html("게스트", ""), elem_id="header-container")

    # 모달 3종 (BMI/BMR 신체건강 모달, 응급 SOS 모달, 대화기록 모달)
    bmi_modal_view = gr.HTML(value=make_bmi_modal_html(None))
    sos_modal_view = gr.HTML(value=make_sos_modal_html("게스트", []))
    history_modal_view = gr.HTML(value=make_history_modal_html([], ""))

    # 🛡️ 관리자 대시보드 모달 컴포넌트 추가
    admin_modal_view = gr.HTML(value="", elem_id="admin-modal-container")
    
    # 관리자 명령 통신용 숨김 브릿지
    admin_action_bridge = gr.Textbox(visible=False, elem_id="admin-action-bridge")
    admin_csv_download = gr.File(label="CSV 다운로드", visible=False)

    # --- [A] 로그인 화면 ---
    with gr.Column(visible=True) as intro_view:
        gr.HTML(f"""
        <div class="intro-card">
          <div style="font-size: 52px; margin-bottom: 12px;">👵💚🤖</div>
          <h2 style="font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 6px;">SOS인공지능</h2>
          <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin-bottom: 24px;">
            어르신의 건강 상태를 따뜻하게 챙겨드리고<br/>
            신체 측정 및 응급 증상 대처를 도와드립니다.
          </p>
          <a href="{get_google_oauth_url()}" target="_blank" class="google-login-link-btn">
            <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.66v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.15z"/><path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.27v3.15C3.25 21.36 7.35 24 12 24z"/><path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.27C.46 8.2 0 10.04 0 12s.46 3.8 1.27 5.42l4.01-3.15z"/><path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.35 0 3.25 2.64 1.27 6.58l4.01 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/></svg>
            Google 계정으로 시작하기
          </a>
        </div>
        """)
        guest_btn = gr.Button("체험용 게스트로 바로 시작하기", variant="secondary")

    # --- [B] 건강 상담 메인 화면 (플로팅 마이크) ---
    with gr.Column(visible=False) as chat_view:
        chatbot = gr.Chatbot(
            elem_id="main-chatbot",
            type="messages",
            show_label=False,
            bubble_full_width=False,
        )

        with gr.Column(elem_classes=["floating-bottom-container"]):
            gr.HTML("""
                <button id="floating-mic-button" class="floating-mic-btn" onclick="window.toggleVoiceRecording()" title="음성으로 말하기">
                    <svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
                </button>
                <div id="floating-mic-status-label" class="floating-mic-label">오늘 컨디션은 어떠세요!</div>
            """)

            with gr.Row(elem_classes=["bottom-input-row"]):
                msg_input = gr.Textbox(
                    placeholder="✉ 글로 물어보기",
                    show_label=False,
                    scale=9,
                    container=False,
                    elem_id="chat-msg-input"
                )
                send_btn = gr.Button("✈", variant="primary", scale=1, elem_id="chat-send-btn")

        audio_player = gr.Audio(
            label="AI 음성 답변",
            type="filepath",
            autoplay=True,
            visible=True,
            # visible=False,
            show_download_button=True,
            show_share_button=False,
        )

    # --- [C] 숨김 브릿지 ---
    oauth_token_bridge = gr.Textbox(elem_id="oauth-token-bridge", elem_classes=["hidden-box"])
    logout_trigger_btn = gr.Button(elem_id="logout-action", elem_classes=["hidden-box"])
    emergency_log_bridge = gr.Textbox(elem_id="emergency-log-bridge", elem_classes=["hidden-box"])
    delete_log_bridge = gr.Textbox(elem_id="delete-log-bridge", elem_classes=["hidden-box"])
    voice_base64_bridge = gr.Textbox(elem_id="voice-base64-bridge", elem_classes=["hidden-box"])
    bmi_data_bridge = gr.Textbox(elem_id="bmi-data-bridge", elem_classes=["hidden-box"])

    # amdin:
    admin_action_bridge = gr.Textbox(elem_id="admin-action-bridge", elem_classes=["hidden-box"])
    admin_csv_download = gr.File(visible=False, label="관리자 CSV 다운로드")


    # ============================================================
    # 9. 이벤트 핸들러 로직
    # ============================================================
    def process_consultation(user_text: str, chat_history: list, u_state: dict):
        if not user_text.strip():
            return chat_history, "", gr.update(visible=False), gr.update()

        chat_history = chat_history or []
        chat_history.append({"role": "user", "content": user_text})

        user_name = u_state.get("name", "보호대상자")
        user_email = u_state.get("email", "guest@smart119.local")

        is_emerg = check_emergency(user_text)
        if is_emerg:
            speech_reply = (
                "🚨 **[응급 감지] 즉시 119에 신고해야 하는 위험 증상입니다!**\n\n"
                "- 무리하게 움직이지 마시고 편안한 자세로 안정을 취하세요.\n"
                "- 아래 버튼을 눌러 등록된 보호자에게 현재 구글맵 위치를 즉시 알리세요.\n\n"
            )
            bot_reply = speech_reply + (
                '<button type="button" class="chat-sos-btn" style="background:#be123c; color:white; padding:10px 18px; border-radius:20px; border:none; font-weight:bold; cursor:pointer; margin-top:8px;">🚨 보호자에게 내 위치 전송하기</button>'
            )
        else:
            # [수정] '어르신' 호칭 제외된 LLM 호출
            bot_reply = call_groq_llm(user_text, chat_history, user_name)
            speech_reply = bot_reply

        full_reply = bot_reply + LEGAL_DISCLAIMER
        chat_history.append({"role": "assistant", "content": full_reply})

        save_chat_log(user_email, user_text, full_reply, is_emerg)
        updated_logs = fetch_user_chat_logs(user_email)
        new_history_modal = make_history_modal_html(updated_logs, user_email)

        audio_file = text_to_speech(speech_reply)
        # audio_update = gr.update(value=audio_file, visible=bool(audio_file))
        audio_update = gr.update(value=audio_file)

        return chat_history, "", audio_update, new_history_modal

    send_btn.click(
        process_consultation,
        inputs=[msg_input, chatbot, user_state],
        outputs=[chatbot, msg_input, audio_player, history_modal_view],
        api_name=False
    )
    msg_input.submit(
        process_consultation,
        inputs=[msg_input, chatbot, user_state],
        outputs=[chatbot, msg_input, audio_player, history_modal_view],
        api_name=False
    )

    def handle_voice_recording(b64_str: str, chat_history: list, u_state: dict):
        if not b64_str:
            return chat_history, "", gr.update(visible=False), gr.update()
        try:
            audio_bytes = base64.b64decode(b64_str)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            recognized_text = speech_to_text(tmp_path)
            try:
                os.remove(tmp_path)
            except:
                pass

            if not recognized_text:
                recognized_text = "음성을 정확히 인식하지 못했습니다. 다시 말씀해 주세요."

            return process_consultation(recognized_text, chat_history, u_state)
        except Exception as e:
            return chat_history, "", gr.update(visible=False), gr.update()

    voice_base64_bridge.change(
        handle_voice_recording,
        inputs=[voice_base64_bridge, chatbot, user_state],
        outputs=[chatbot, msg_input, audio_player, history_modal_view],
        api_name=False
    )

    # [핵심] ④, ⑤ 신체 데이터 자동 계산 및 Supabase bmi 테이블 연동 핸들러
    def handle_bmi_submission(json_payload: str, u_state: dict):
        if not json_payload:
            return gr.update()
        try:
            data = json.loads(json_payload)
            user_id = u_state.get("id") or ensure_guest_user_in_db()
            
            res = save_bmi_record(
                user_id=user_id,
                age=data.get("age", 65),
                height=data.get("height", 165),
                weight=data.get("weight", 60),
                gender=data.get("gender", "남성"),
                memo=data.get("memo", "")
            )
            
            # 저장 후 최신 기록을 읽어 모달 뷰 갱신
            latest = fetch_latest_bmi_record(user_id)
            return make_bmi_modal_html(latest)
        except Exception as e:
            print(f"[BMI 핸들러 오류]: {e}")
            return gr.update()

    bmi_data_bridge.change(
        handle_bmi_submission,
        inputs=[bmi_data_bridge, user_state],
        outputs=[bmi_modal_view],
        api_name=False
    )

    # OAuth 로그인 완료 처리
    def on_token_received(token: str):
        if not token or not supabase_client:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), {}
        try:
            res = supabase_client.auth.get_user(token)
            user = res.user
            if not user:
                return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), {}

            user_id = sync_user_to_db(user)
            user_meta = getattr(user, "user_metadata", {}) or {}
            email = getattr(user, "email", "") or ""
            name = user_meta.get("full_name") or user_meta.get("name") or email.split("@")[0]
            avatar_url = user_meta.get("avatar_url") or user_meta.get("picture") or ""

            contacts = fetch_emergency_contacts(email)
            logs = fetch_user_chat_logs(email)
            latest_bmi = fetch_latest_bmi_record(user_id)

            u_state = {"id": user_id, "email": email, "name": name, "avatar_url": avatar_url, "contacts": contacts}

            return (
                gr.update(visible=False),
                gr.update(visible=True),
                make_header_html(name, avatar_url),
                make_bmi_modal_html(latest_bmi),
                make_sos_modal_html(name, contacts),
                make_history_modal_html(logs, email),
                u_state
            )
        except Exception as e:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), {}

    oauth_token_bridge.change(
        on_token_received,
        inputs=[oauth_token_bridge],
        outputs=[intro_view, chat_view, header_view, bmi_modal_view, sos_modal_view, history_modal_view, user_state],
        api_name=False
    )

    # 게스트 로그인
    def on_guest_login():
        guest_id = ensure_guest_user_in_db()
        u_state = {"id": guest_id, "email": "guest@smart119.local", "name": "게스트", "avatar_url": "", "contacts": []}
        logs = fetch_user_chat_logs("guest@smart119.local")
        latest_bmi = fetch_latest_bmi_record(guest_id)
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            make_header_html("게스트", ""),
            make_bmi_modal_html(latest_bmi),
            make_sos_modal_html("게스트", []),
            make_history_modal_html(logs, "guest@smart119.local"),
            u_state
        )

    guest_btn.click(
        on_guest_login,
        outputs=[intro_view, chat_view, header_view, bmi_modal_view, sos_modal_view, history_modal_view, user_state],
        api_name=False
    )

    # 로그아웃
    def on_logout():
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            make_header_html("게스트", ""),
            make_bmi_modal_html(None),
            make_sos_modal_html("게스트", []),
            make_history_modal_html([], ""),
            {"id": "", "email": "", "name": "게스트", "avatar_url": "", "contacts": []},
            []
        )

    logout_trigger_btn.click(
        on_logout,
        outputs=[intro_view, chat_view, header_view, bmi_modal_view, sos_modal_view, history_modal_view, user_state, chatbot],
        api_name=False
    )

    # 긴급 SOS 로그 처리
    def handle_emergency_log(json_str: str, u_state: dict):
        if not json_str:
            return
        try:
            data = json.loads(json_str)
            user_email = u_state.get("email", "guest@smart119.local")
            log_emergency_dispatch(
                user_email=user_email,
                symptom="긴급 SOS 사이렌 위치 전송",
                lat=data.get("lat"),
                lng=data.get("lng"),
                map_url=data.get("map_url", ""),
                recipients=data.get("recipients", [])
            )
        except Exception as e:
            pass

    emergency_log_bridge.change(
        handle_emergency_log,
        inputs=[emergency_log_bridge, user_state],
        outputs=[],
        api_name=False
    )

    # ============================================================
    # 👇 관리자 액션 핸들러 및 브릿지
    # ============================================================
    def handle_admin_action(action_json: str, u_state: dict):
        if not is_admin_user(u_state.get("email")):
            return gr.update(), None
        try:
            req = json.loads(action_json)
            act = req.get("action")
            
            if act == "delete_user":
                admin_delete_user(supabase_client, req.get("user_id"))
            elif act == "toggle_ban":
                admin_toggle_ban_user(supabase_client, req.get("user_id"), req.get("status"))
            elif act == "export_csv":
                csv_path = admin_export_table_csv(supabase_client, req.get("table"))
                return make_admin_modal_html(supabase_client, u_state.get("email")), gr.update(value=csv_path, visible=True)
            
            # 변경 후 모달 뷰 최신 상태로 갱신
            updated_html = make_admin_modal_html(supabase_client, u_state.get("email"))
            return updated_html, gr.update()
        except Exception as e:
            print(f"[관리자 처리 에러]: {e}")
            return gr.update(), gr.update()

    admin_action_bridge.change(
        handle_admin_action,
        inputs=[admin_action_bridge, user_state],
        outputs=[admin_modal_view, admin_csv_download],
        api_name=False
    )
    # 대화 삭제
    def handle_delete_chat_log(log_id_str: str, u_state: dict):
        if not log_id_str:
            return gr.update()
        try:
            log_id = int(log_id_str.strip())
            delete_single_chat_log(log_id)
            user_email = u_state.get("email", "guest@smart119.local")
            updated_logs = fetch_user_chat_logs(user_email)
            return make_history_modal_html(updated_logs, user_email)
        except Exception:
            return gr.update()

    delete_log_bridge.change(
        handle_delete_chat_log,
        inputs=[delete_log_bridge, user_state],
        outputs=[history_modal_view],
        api_name=False
    )

# ============================================================
# 10. 앱 실행
# ============================================================
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        ssr=False,
        show_error=True
    )
