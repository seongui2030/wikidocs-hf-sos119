# 08-2. 보호자 비상 연락망 다중 SMS 긴급 문자 원터치 발송 및 백엔드 로깅

---

## 1. 🎯 학습 목표
1. 모바일 OS 표준 SMS 스키마(`sms:`) 프로토콜을 이해합니다.
2. 안드로이드와 iOS 기기 간의 다중 수신인 문자 작성 호환성을 확보합니다.
3. 비상 알림 발송 시점의 위도, 경도, 증상을 클라우드 `emergency_logs` 테이블에 실시간 저장합니다.

---

## 2. 💡 핵심 개념

```text
[🚨 SOS 전송 클릭]
         │
         ├─► [모바일 표준 sms: 스킴] ──► 기본 문자 앱 자동 실행 및 완성된 초안 작성
         │
         └─► [백엔드: log_emergency_dispatch()] ──► emergency_logs 테이블에 GPS 좌표 영구 보관
```

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `supabase` 클라이언트 모듈

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: emergency_dispatcher.py
기능: 응급 상황 발생 시 다중 보호자 SMS 링크 생성 및 클라우드 DB emergency_logs 영구 적재
"""

import os
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from supabase import create_client, Client


def get_client() -> Optional[Client]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def generate_sms_broadcast_url(
    phone_numbers: List[str],
    patient_name: str,
    symptom: str,
    lat: float,
    lng: float,
    is_ios: bool = False
) -> str:
    clean_phones = [p.replace("-", "").strip() for p in phone_numbers if p.strip()]
    phones_str = ",".join(clean_phones)
    map_url = f"https://maps.google.com/?q={lat},{lng}"

    message_body = (
        f"[스마트119 긴급 구조 요청]\n"
        f"환자: {patient_name}\n"
        f"호소 증상: {symptom}\n"
        f"현재 GPS 위치: {map_url}\n"
        f"위급 상황이오니 즉시 확인 바랍니다!"
    )
    encoded_body = quote(message_body)

    if is_ios:
        return f"sms:/open?addresses={phones_str}&body={encoded_body}"
    return f"sms:{phones_str}?body={encoded_body}"


def log_emergency_dispatch(
    user_email: str,
    symptom: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    recipients: Optional[List[str]] = None
) -> Dict[str, Any]:
    client = get_client()
    if not client:
        return {"success": False}

    payload = {
        "user_email": user_email.strip(),
        "symptom": symptom.strip(),
        "latitude": lat,
        "longitude": lng,
        "map_url": f"https://maps.google.com/?q={lat},{lng}" if lat and lng else "",
        "recipients": recipients or []
    }
    try:
        res = client.table("emergency_logs").insert(payload).execute()
        return {"success": True, "data": res.data[0] if res.data else payload}
    except Exception as e:
        print(f"[Emergency Log 저장 실패]: {e}")
        return {"success": False, "error": str(e)}
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 웹 표준 프로토콜형
웹 브라우저 하이퍼링크를 클릭했을 때 모바일 기기의 기본 문자 발송 앱을 자동으로 실행시키기 위해 사용하는 URI 스키마 이름은 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> <code>sms:</code>
</details>

---

### ## [문제 2] 객관식
`quote(message_body)`처럼 URL에 한글이나 줄바꿈 문자를 포함시킬 때 퍼센트 인코딩(URL Encoding)을 수행하는 주된 이유는?
1. 문자 발송 요금을 할인받기 위해
2. 인터넷 주소 체계에서 한글이나 특수문자가 깨지거나 브라우저 명령어가 오작동하는 것을 방지하기 위해
3. 글자 수를 10자 이내로 줄이기 위해
4. 비밀번호를 암호화하기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (URL 표준 규격에 따라 비ASCII 한글 및 개행문자를 안전한 규격으로 전송하기 위함)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 "비상 호출이 완료되었습니다"라고 안내할 때, 웹 브라우저의 기술적 한계로 인해 백그라운드에서 사용자 몰래 문자를 강제로 자동 발송할 수 없는 보안상의 이유를 설명하고, 왜 반드시 사용자가 문자 앱의 '전송' 버튼을 직접 누르는 방식으로 구현되어야 하는지 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
웹 브라우저는 샌드박스(Sandbox) 보안 원칙을 따르므로, 사용자의 명시적인 개입 없이 웹사이트가 기기의 통신망을 통해 SMS를 무단 발송하거나 유료 과금을 유발하는 것을 엄격히 금지합니다. 

따라서 브라우저는 `sms:` 스킴을 통해 수신인 번호와 본문이 완성된 문자 앱의 '초안 화면'까지만 열어줄 수 있으며, 최종 전송 여부는 스팸 및 보안 위협 방지를 위해 사용자가 직접 확인 후 '전송' 버튼을 누르도록 설계되어야 합니다.
</details>
