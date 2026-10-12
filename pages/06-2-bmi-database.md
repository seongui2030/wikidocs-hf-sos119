# 06-2. 신체 건강 지표 클라우드 데이터베이스 연동과 이력 관리

---

## 1. 🎯 학습 목표
1. 신체 데이터(`bmi` 테이블)와 사용자 계정 간의 외래키 관계를 이해합니다.
2. 계산된 지표를 클라우드 DB에 안전하게 `INSERT`하는 함수를 구현합니다.
3. 가장 최근의 신체 데이터를 날짜 내림차순으로 조회하는 쿼리를 작성합니다.

---

## 2. 💡 핵심 개념

```text
┌───────────────────────────────┐          ┌──────────────────────────────────────────┐
│      public.app_users         │          │               public.bmi                 │
├───────────────────────────────┤          ├──────────────────────────────────────────┤
│ id (UUID, PK)                 │ ◄───┐    │ id (BIGINT, PK)                          │
│ email (TEXT)                  │     │    │ user_id (UUID, FK -> app_users.id)       │
│ name (TEXT)                   │     └────┼─ user_email (TEXT)                       │
│ created_at (TIMESTAMPTZ)      │          │ height (NUMERIC), weight (NUMERIC)       │
└───────────────────────────────┘          │ bmi (NUMERIC), bmr (NUMERIC)             │
                                           │ memo (TEXT)                              │
                                           │ created_at (TIMESTAMPTZ)                 │
                                           └──────────────────────────────────────────┘
```

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `supabase` 패키지 (`pip install supabase`)

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: health_database.py
기능: BMI/BMR 계산 결과의 클라우드 데이터베이스 저장 및 최근 이력 조회 모듈
"""

import os
from typing import Dict, Any, Optional
from supabase import create_client, Client
from health_calculator import calculate_health_metrics


def get_db_client() -> Optional[Client]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def save_bmi_record(
    user_email: str,
    height_cm: float,
    weight_kg: float,
    age: int,
    gender: str = "male",
    memo: str = ""
) -> Dict[str, Any]:
    metrics = calculate_health_metrics(height_cm, weight_kg, age, gender)
    client = get_db_client()
    if not client:
        return {"success": False, "data": metrics}

    payload = {
        "user_email": user_email,
        "height": height_cm,
        "weight": weight_kg,
        "bmi": metrics["bmi"],
        "bmr": metrics["bmr_kcal"],
        "memo": memo.strip()
    }

    try:
        res = client.table("bmi").insert(payload).execute()
        return {"success": True, "data": res.data[0] if res.data else payload}
    except Exception:
        # memo 컬럼이 없는 스키마 환경 대비 폴백
        payload.pop("memo", None)
        res = client.table("bmi").insert(payload).execute()
        return {"success": True, "data": res.data[0] if res.data else payload}


def fetch_latest_bmi_record(user_email: str) -> Optional[Dict[str, Any]]:
    client = get_db_client()
    if not client:
        return None
    try:
        res = client.table("bmi") \
            .select("*") \
            .eq("user_email", user_email) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception:
        return None
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 쿼리 분석형
위 코드에서 가장 최근에 측정한 신체 기록 단 1건만을 정확하게 가져오기 위해 사용된 체이닝 메서드 2가지는 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> <code>.order("created_at", desc=True)</code>와 <code>.limit(1)</code>
</details>

---

### ## [문제 2] 객관식
데이터베이스에 신체 정보를 `INSERT`할 때 `memo` 필드를 포함한 1차 시도가 실패했을 때 `payload.pop("memo", None)`을 거쳐 재시도하도록 설계한 주된 이유는?
1. 사용자의 비밀번호 유출을 막기 위해
2. 실제 운영 DB 테이블에 아직 `memo` 컬럼이 추가되지 않은 환경에서도 신체 지표(키, 몸무게, BMI)가 중단 없이 저장되도록 보장하기 위해
3. 파이썬 메모리를 비우기 위해
4. 인터넷 연결을 재설정하기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (스키마 버전 불일치로 인한 런타임 오류 방어)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 최근 건강 분석 결과를 다시 안내하고자 할 때, 만약 사용자가 앱을 처음 설치하여 `fetch_latest_bmi_record()` 조회 결과가 `None`으로 반환될 경우 발생할 수 있는 오류를 진단하고, 이에 대처하는 사용자 친화적 예외 처리 방안을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
조회 결과가 `None`인 상태에서 딕셔너리 키에 직접 접근하면 `TypeError: 'NoneType' object is not subscriptable` 에러가 발생하여 앱 전체가 다운됩니다. 

이를 방지하기 위해 `if latest is None:` 분기를 마련하고, <i>"등록된 신체 측정 기록이 없습니다. 상단의 건강 버튼을 눌러 먼저 키와 몸무게를 입력해 주세요."</i>라는 안내 멘트를 반환하도록 방어해야 합니다.
</details>