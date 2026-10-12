# 05-3. Groq 초고속 LLM 프롬프트 설계와 법적 면책 조항 결합

의료 보건 분야의 인공지능은 친절함보다 **정확성과 안전성**이 우선입니다. "어르신" 같은 호칭을 무분별하게 붙이지 않고 정중하고 단호한 어조를 유지해야 하며, 오늘 날짜와 요일을 정확히 인지하여 환자의 투약 및 진료 일정을 도와야 합니다. 또한 의료법상 AI는 의사가 아니므로 모든 답변 끝에 **법적 면책 고지(Legal Disclaimer)**를 의무적으로 첨부해야 합니다.

---

## 1. 🎯 학습 목표
1. 한국 시간(KST)과 요일 정보를 시스템 프롬프트에 동적으로 주입하여 날짜 환각을 방지할 수 있습니다.
2. RAG로 검색된 질병관리청 가이드라인을 LLM의 시스템 지침과 안전하게 합성하는 프롬프트 엔지니어링을 습득합니다.
3. 의료법 준수를 위한 **법적 면책 고지 문구 자동 결합 모듈**을 구현합니다.

---

## 2. 💡 핵심 개념

### ① 왜 KST 시간과 요일을 프롬프트에 직접 주입해야 할까요?
대다수 거대 언어 모델(LLM)은 고정 신경망이므로 실시간 날짜를 알지 못합니다. 파이썬의 `datetime` 라이브러리로 서버의 현재 한국 시간(UTC+9)을 구한 뒤 프롬프트 상단에 주입해 주어야 날짜 왜곡이 사라집니다.

---

## 3. 🛠️ 준비물
- Python 3.10 이상
- `groq` 라이브러리 (`pip install groq`)
- Groq API Key

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: medical_llm.py
기능: KST 시간 주입, 호칭 제어, RAG 문맥 합성, 면책 고지 자동 부착 LLM 엔진
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from groq import Groq


def get_current_kst_str() -> str:
    """현재 한국 표준시 기준 날짜, 요일, 시각 문자열을 생성합니다."""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    weekdays_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    weekday_str = weekdays_ko[now.weekday()]
    return now.strftime(f"%Y년 %m월 %d일 {weekday_str} %H시 %M분")


LEGAL_DISCLAIMER = """

--------------------------------------------------
⚠️ [법적 면책 고지]
본 상담 결과는 질병관리청 및 응급의학 가이드라인에 기반한 참고 정보이며, 
의사의 전문적인 진료 및 처방을 대신할 수 없습니다. 증상이 지속되거나 
악화될 경우 즉시 가까운 병원 또는 119 응급실을 방문하시기 바랍니다.
"""


def generate_medical_advice(
    user_message: str,
    rag_context: Optional[str] = None,
    api_key: Optional[str] = None
) -> str:
    """KST 시간 및 RAG 지식을 결합하여 전문적인 상담 답변을 생성합니다."""
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        return "[오류] GROQ_API_KEY가 설정되지 않았습니다."

    client = Groq(api_key=key)
    current_kst = get_current_kst_str()

    system_prompt = f"""당신은 대한민국 응급의료 및 건강 상담 전문 AI '스마트119 말벗케어'입니다.

[운영 핵심 원칙]
1. 현재 시각: 대한민국 서울 기준 {current_kst}입니다. 날짜 관련 질문 시 이 정보를 정확히 안내하세요.
2. 호칭 주의: 상대방을 절대 '어르신'이라 단정 지어 부르지 마세요. 정중한 존댓말을 사용하세요.
3. 간결성: 모바일 환경에 맞춰 3~4문장 내외로 핵심만 명확히 설명하세요.
"""

    if rag_context:
        system_prompt += f"\n[최우선 준수 가이드라인]\n{rag_context}"

    try:
        response = client.chat.completions.create(
            model="qwen-2.5-72b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=600
        )
        llm_reply = response.choices[0].message.content.strip()
    except Exception:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=600
        )
        llm_reply = response.choices[0].message.content.strip()

    return llm_reply + LEGAL_DISCLAIMER
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 단답형
의료 상담 AI 프롬프트 구성 시 LLM의 답변 창의성을 나타내는 하이퍼파라미터인 `temperature` 값을 0.8 이상 높게 설정하지 않고 0.2~0.3 수준으로 낮게 설정하는 이유는 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 환각(Hallucination) 현상을 억제하고, 정해진 의학 가이드라인에 근거한 사실적이고 일관된 답변을 생성하기 위해서
</details>

---

### ## [문제 2] 객관식
시스템 프롬프트에 한국 시간(KST)을 동적으로 주입하지 않았을 때 일어날 수 있는 현상으로 가장 적절한 것은?
1. 챗봇이 한글을 인식하지 못하고 영어로만 답한다.
2. 오늘 날짜나 요일을 묻는 질문에 과거 학습 시점의 날짜나 엉뚱한 요일을 답한다.
3. 데이터베이스의 모든 환자 정보가 삭제된다.
4. 브라우저의 마이크 녹음 기능이 중단된다.
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (정적 모델은 런타임의 실시간 날짜를 알 수 없어 요일과 날짜에 대한 환각이 발생함)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 답변을 읽어줄 때, 화면에 출력된 텍스트 중 `LEGAL_DISCLAIMER`(법적 면책 고지) 부분까지 음성으로 변환하면 사용자가 1분 이상 긴 문구를 듣느라 피로도가 극심해집니다. 이 문제를 해결하기 위해 TTS 엔진으로 텍스트를 전달하기 직전에 적용해야 할 문자열 슬라이싱 전처리 방법을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> `text.split("⚠️ [법적 면책 고지]")[0]`과 같이 파이썬 문자열 분할 기법을 사용하여, 면책 고지 이전의 핵심 상담 답변 내용만을 추출하여 TTS 음성 합성 모듈에 전달해야 합니다.
</details>