import os
import csv
import html
import tempfile
from datetime import datetime
from supabase import Client

def save_chat_log(supabase: Client, user_email: str, user_message: str, bot_reply: str, is_emergency: bool = False):
    """채팅 기록 1건을 Supabase public.chat_logs에 저장"""
    if not supabase or not user_email:
        return
    try:
        supabase.table("chat_logs").insert({
            "user_email": user_email,
            "user_message": user_message,
            "bot_reply": bot_reply,
            "is_emergency": is_emergency
        }).execute()
    except Exception as e:
        print(f"⚠️ chat_logs 저장 실패: {e}")


def fetch_user_chat_logs(supabase: Client, user_email: str, search_keyword: str = "") -> list:
    """계정별 대화 기록 조회 및 키워드 검색"""
    if not supabase or not user_email:
        return []
    try:
        query = supabase.table("chat_logs").select("*").eq("user_email", user_email).order("created_at", desc=False)
        res = query.execute()
        records = res.data or []

        if search_keyword and search_keyword.strip():
            kw = search_keyword.strip().lower()
            records = [
                r for r in records 
                if kw in r.get("user_message", "").lower() or kw in r.get("bot_reply", "").lower()
            ]
        return records
    except Exception as e:
        print(f"⚠️ chat_logs 조회 오류: {e}")
        return []


def delete_single_chat_log(supabase: Client, log_id: int) -> bool:
    """특정 대화 기록 1건 삭제"""
    if not supabase or not log_id:
        return False
    try:
        supabase.table("chat_logs").delete().eq("id", log_id).execute()
        return True
    except Exception as e:
        print(f"⚠️ 대화 삭제 오류: {e}")
        return False


def delete_all_user_chat_logs(supabase: Client, user_email: str) -> bool:
    """해당 계정의 모든 대화 기록 일괄 삭제"""
    if not supabase or not user_email:
        return False
    try:
        supabase.table("chat_logs").delete().eq("user_email", user_email).execute()
        return True
    except Exception as e:
        print(f"⚠️ 전체 대화 삭제 오류: {e}")
        return False


def export_logs_to_csv(logs: list, user_email: str) -> str:
    """대화 기록을 CSV 파일로 생성하고 파일 경로 반환"""
    if not logs:
        return None

    filename = f"smart119_chat_{user_email.split('@')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(tempfile.gettempdir(), filename)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["번호", "일시", "사용자 질문/증상", "스마트119 답변", "응급여부"])
        for idx, row in enumerate(logs, 1):
            writer.writerow([
                idx,
                row.get("created_at", ""),
                row.get("user_message", ""),
                row.get("bot_reply", ""),
                "응급" if row.get("is_emergency") else "일반"
            ])

    return filepath


def export_logs_to_pdf_print_html(logs: list, user_email: str) -> str:
    """
    숨김 iframe을 생성하여 브라우저 인쇄창(PDF로 저장)을 즉시 띄우는 스마트 HTML 스크립트 반환
    """
    if not logs:
        return "<script>alert('내보낼 대화 기록이 없습니다.');</script>"

    rows_html = ""
    for idx, row in enumerate(logs, 1):
        emergency_badge = '<span style="color:#d32f2f; font-weight:bold;">[🚨응급]</span>' if row.get("is_emergency") else ''
        time_str = row.get("created_at", "")[:19].replace("T", " ")
        msg = html.escape(row.get("user_message", ""))
        reply = html.escape(row.get("bot_reply", "")).replace("\n", "<br>")

        rows_html += f"""
        <div style="border-bottom:1px solid #eee; padding:12px 0;">
            <div style="font-size:12px; color:#888; margin-bottom:4px;">#{idx} {emergency_badge} {time_str}</div>
            <div style="margin-bottom:6px;"><strong>👤 학생/환자:</strong> {msg}</div>
            <div style="background-color:#f9f9f9; padding:8px 12px; border-radius:8px; border-left:3px solid #d32f2f;">
                <strong>🩺 스마트119 AI:</strong><br>{reply}
            </div>
        </div>
        """

    document_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>스마트119 상담 기록 - {user_email}</title>
        <style>
            body {{ font-family: sans-serif; padding: 24px; color: #333; }}
            h2 {{ color: #b71c1c; border-bottom: 2px solid #b71c1c; padding-bottom: 8px; }}
            .meta {{ font-size: 13px; color: #666; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h2>🚨 스마트119 응급 및 건강 상담 리포트</h2>
        <div class='meta'>
            출력일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 사용자 계정: {user_email}
        </div>
        <div>
            {rows_html}
        </div>
    </body>
    </html>
    """.replace('"', '&quot;').replace('\n', ' ')

    # 숨김 iframe 생성 후 print() 호출 스크립트
    trigger_js = f"""
    <script>
        (function() {{
            var existing = document.getElementById('smart119-print-frame');
            if (existing) existing.remove();
            
            var iframe = document.createElement('iframe');
            iframe.id = 'smart119-print-frame';
            iframe.style.position = 'fixed';
            iframe.style.right = '0';
            iframe.style.bottom = '0';
            iframe.style.width = '0';
            iframe.style.height = '0';
            iframe.style.border = '0';
            document.body.appendChild(iframe);
            
            iframe.srcdoc = "{document_content}";
            iframe.onload = function() {{
                setTimeout(function() {{
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                }}, 300);
            }};
        }})();
    </script>
    """
    return trigger_js
