# 05-1. 골든타임을 지키는 AI 응급 키워드 감지 엔진

응급 환자 발생 시 가장 중요한 것은 **골든타임(Golden Time)**입니다. "가슴이 쥐어짜듯 아파요", "숨을 못 쉬겠어요", "죽을 것 같아"와 같은 위급 신호가 입력되었을 때, AI가 평상시처럼 긴 설명을 늘어놓으면 환자의 생명이 위험해질 수 있습니다. 이번 실습에서는 사용자의 발화에서 생체 위기 신호를 0.001초 만에 포착하여 119 긴급 안내와 직결시키는 **응급 감지 엔진**을 만들어 봅니다.

---

## 1. 🎯 학습 목표
1. **문자열 패턴 매칭(String Pattern Matching)** 원리를 이해하고, 응급 상황을 식별하는 정밀 키워드 사전을 설계할 수 있습니다.
2. 띄어쓰기 불일치나 조사 결합 등 사용자의 다양한 발화 패턴을 정규화하여 감지 정확도를 높이는 알고리즘을 구현합니다.
3. 응급 상황 판별 결과(`True`/`False`)에 따라 일반 대화 모드와 긴급 모드로 즉시 분기하는 로직을 작성할 수 있습니다.

---

## 2. 💡 핵심 개념

### ① 왜 LLM에게 응급 판단을 전적으로 맡기면 안 될까요?
거대 언어 모델(LLM)은 뛰어난 문맥 이해 능력을 갖추고 있지만 두 가지 치명적인 한계가 있습니다.
- **응답 지연 시간(Latency):** 문장을 생성해 출력하기까지 1~3초 이상 소요됩니다.
- **환각(Hallucination) 위험:** 확률 기반 생성 모델이므로 위급한 순간에 엉뚱한 대처법을 조언할 위험이 존재합니다.

따라서 스마트119 앱은 LLM을 호출하기 전에 **파이썬 룰베이스(Rule-based) 엔진**이 1차 필터링을 수행합니다. 응급 단어가 발견되는 즉시 0.001초 만에 119 신고 행동 지침을 사용자 화면에 최우선으로 띄웁니다.

```text
[사용자 음성/텍스트 입력]
          │
          ▼
┌───────────────────────────────┐
│ 1단계: 룰베이스 응급 감지 엔진   │ ──(응급 감지: True)──► [🚨 119 긴급 행동 지침 즉시 출력]
└───────────────────────────────┘                        [🚨 emergency_logs 테이블 즉시 기록]
          │ (정상 일상 대화: False)
          ▼
┌───────────────────────────────┐
│ 2단계: RAG 의학 지식 검색      │
└───────────────────────────────┘
          │
          ▼
┌───────────────────────────────┐
│ 3단계: Groq 초고속 LLM 상담    │
└───────────────────────────────┘
```

### ② 형태소와 공백을 고려한 포함 검사 (`in` 연산자)
한국어는 띄어쓰기가 자주 생략되는 교착어입니다. "죽을 것 같아"와 "죽을것같아", "숨이 안 쉬어져"와 "숨안쉬어져"처럼 띄어쓰기 유무에 관계없이 감지할 수 있도록, **공백을 제거한 텍스트**와 **원본 텍스트** 양쪽을 교차 검사해야 합니다.

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- 문자열 처리 기본 라이브러리 (Python 표준 내장 모듈 사용, 별도 설치 불필요)

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: emergency_detector.py
기능: 스마트119 실시간 응급 키워드 감지 및 119 긴급 안내 모듈
"""

from typing import Tuple

# 1. 119 구급대 및 응급의학 골든타임 기준 핵심 키워드 사전
EMERGENCY_KEYWORDS = [
    # 생명 직결 위기 표현
    "죽을 것 같", "죽을것같", "살려줘", "살려주세요",
    # 호흡기 계통
    "숨을 못", "숨이 안", "숨 안", "숨차", "숨이 차", "호흡곤란", "숨막혀", "숨 막혀",
    # 순환기/뇌혈관 계통
    "가슴이 아파", "가슴 통증", "흉통", "가슴 쥐어", "심장마비", "뇌졸중",
    # 신경계 및 의식 계통
    "의식", "기절", "쓰러", "마비", "말이 안 나", "어눌",
    # 외상 및 출혈
    "피가 나", "피토", "각혈", "대량 출혈",
    # 직접적인 구조 요청
    "119", "구급차", "응급실", "응급환자"
]

# 2. 응급 상황 시 즉각 반환되는 긴급 행동 수칙 가이드
EMERGENCY_DISPATCH_GUIDE = """🚨 [긴급 상황 감지 - 즉시 119에 신고하세요!]

위급한 신체 이상 징후가 감지되었습니다. AI 상담을 중단하시고 즉각 조치하십시오:
1. 즉시 국번 없이 [119]로 전화하여 환자 위치를 말씀하세요.
2. 기도를 확보하고, 편안한 자세로 구급 대원을 기다리세요.
3. 상단의 [🚨 사이렌 버튼]을 누르면 등록된 보호자에게 현재 GPS 위치가 전송됩니다.
"""


def check_emergency(user_text: str) -> Tuple[bool, str]:
    """
    사용자의 입력 문장을 정밀 분석하여 응급 상황 여부를 판별합니다.
    """
    if not user_text or not isinstance(user_text, str):
        return False, ""

    raw_text = user_text.strip()
    clean_text = raw_text.replace(" ", "")

    for keyword in EMERGENCY_KEYWORDS:
        clean_kw = keyword.replace(" ", "")
        if (keyword in raw_text) or (clean_kw in clean_text):
            print(f"[🚨 응급 신호 포착] 감지 키워드: '{keyword}'")
            return True, EMERGENCY_DISPATCH_GUIDE

    return False, raw_text


if __name__ == "__main__":
    test_cases = [
        "어깨가 결리고 조금 뻐근해요.",
        "갑자기 가슴이 너무 아파요... 죽을 것 같아요!",
        "할머니가 숨을못쉬어요 빨리 와주세요"
    ]
    for msg in test_cases:
        is_sos, reply = check_emergency(msg)
        print(f"\n입력: '{msg}' -> 응급 여부: {is_sos}")
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 단답형
스마트119 시스템에서 응급 환자 발화 시 LLM보다 먼저 룰베이스 감지 엔진을 실행하여 골든타임을 확보하려는 가장 주된 이유 2가지는 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 빠른 응답 속도(Latency 단축)와 허위 정보를 방지하는 안전성(환각 현상 방지)
</details>

---

### ## [문제 2] 코드 분석형
위 코드에서 `clean_text = raw_text.replace(" ", "")` 처리를 추가한 이유는 무엇일까요?
1. 영어 알파벳 대소문자를 구분하기 위해서
2. 사용자가 "숨을 못 쉬어"를 "숨을못쉬어"처럼 띄어쓰기 없이 입력해도 정확히 감지하기 위해서
3. 특수문자를 제거하여 데이터베이스 저장 용량을 줄이기 위해서
4. 문장의 길이를 10자 이내로 제한하기 위해서
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (한국어 음성 인식이나 타이핑 시 자주 발생하는 띄어쓰기 오류를 방어하여 감지율을 극대화하기 위함)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 응급 상황임을 안내하기 전에, 사전에 등록된 단순 두통("머리가 아파")과 뇌졸중 의심 징후("벼락 두통", "두통 마비")를 명확히 구분하여 과잉 감지를 방어해야 하는 이유를 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
단순 일상 통증에까지 무분별하게 119 신고 안내가 나가면 불필요한 공포감을 조성하고 실제 위급 환자를 구조해야 할 응급의료 체계에 혼선을 초래할 수 있습니다. 따라서 "망치로 맞은 듯한 두통", "마비", "어눌" 등 신경학적 응급 징후 단어가 복합 결합된 경우에만 119 비상 체계가 가동되도록 사전을 정밀화해야 합니다.
</details>

---

# 05-2. 질병관리청 가이드라인 기반 신뢰도 높은 RAG 지식 검색기

인공지능이 그럴듯하게 거짓말을 하는 현상을 **환각(Hallucination)**이라고 부릅니다. 일반적인 챗봇이라면 가벼운 실수로 넘길 수 있지만, 사람의 건강과 생명을 다루는 헬스케어 서비스에서는 잘못된 의학 정보가 치명적인 사고로 이어질 수 있습니다. 이번 실습에서는 공신력 있는 질병관리청(KDCA) 및 119 응급처치 표준 가이드라인을 기반으로, AI가 정확한 근거 문서에 기반해서만 답변하도록 돕는 **RAG(검색 증강 생성, Retrieval-Augmented Generation)** 모듈을 구현해 봅니다.

---

## 1. 🎯 학습 목표
1. **RAG(검색 증강 생성)**의 기본 원리와 헬스케어 AI에서의 필수성을 이해합니다.
2. 질병관리청과 소방청 표준 매뉴얼을 구조화된 파이썬 의학 지식 사전(Knowledge Base)으로 구축합니다.
3. 사용자의 증상 질문에서 핵심 질환 키워드를 추출하여 가장 관련도 높은 응급 가이드라인을 실시간 검색하는 알고리즘을 작성합니다.

---

## 2. 💡 핵심 개념

### ① RAG(Retrieval-Augmented Generation, 검색 증강 생성)란?
RAG는 LLM에게 질문을 바로 던지는 대신, **공식 문서에서 검증된 정답 자료를 먼저 찾아낸 뒤 프롬프트에 '참고자료'로 함께 제공**하여 답변을 생성하게 만드는 첨단 AI 엔지니어링 기법입니다.

```text
[사용자 질문: "가슴이 쥐어짜듯 아파요"]
                  │
                  ▼
┌──────────────────────────────────────┐
│  RAG 의학 지식 검색기 (retrieve)        │
│  - "흉통", "가슴" 키워드 스캔          │
│  - 질병관리청 심근경색 가이드라인 추출    │
└──────────────────────────────────────┘
                  │
                  ▼ [관련 의학 지식 문맥 주입]
┌──────────────────────────────────────┐
│  Groq 초고속 LLM 프롬프트              │
│  "아래 질병관리청 가이드라인에 근거하여  │
│   환자에게 119 신고 및 응급처치를 안내하라" │
└──────────────────────────────────────┘
                  │
                  ▼
[환각 없는 100% 안전하고 정확한 의료 상담 답변]
```

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- 질병관리청 / 소방청 119 응급처치 표준 가이드라인 데이터

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: medical_rag.py
기능: 질병관리청 및 119 표준 가이드라인 기반 경량 RAG 지식 검색 엔진
"""

from typing import Dict, List, Optional

MEDICAL_KNOWLEDGE_BASE: Dict[str, Dict[str, any]] = {
    "myocardial_infarction": {
        "title": "급성 심근경색 및 흉통",
        "keywords": ["가슴", "흉통", "쥐어짜", "심장", "가슴 통증", "가슴 답답"],
        "guideline": (
            "[질병관리청 급성 심근경색 표준 지침]\n"
            "1. 흉통이 15분 이상 지속되고 턱, 어깨, 팔로 통증이 퍼질 경우 즉시 119에 신고해야 합니다.\n"
            "2. 환자를 편안히 앉히고 옷의 단추를 풀어 호흡을 돕습니다.\n"
            "3. 절대 환자 혼자 걷거나 운전하여 병원에 가지 않도록 합니다."
        )
    },
    "stroke": {
        "title": "뇌졸중 (중풍) 의심 징후",
        "keywords": ["마비", "팔 힘", "발음", "어눌", "얼굴 마비", "편마비"],
        "guideline": (
            "[소방청 뇌졸중 FAST 대응 지침]\n"
            "1. Face(얼굴): 한쪽 입꼬리 처짐 확인.\n"
            "2. Arms(팔): 한쪽 팔이 툭 떨어지는지 확인.\n"
            "3. Speech(말): 발음이 어눌한지 확인.\n"
            "4. Time(골든타임): 1개라도 관찰되면 지체 없이 119에 신고 (골든타임 3~4.5시간)."
        )
    },
    "burn": {
        "title": "응급 화상 처치",
        "keywords": ["화상", "뜨거운", "데였", "물집", "불에", "기름"],
        "guideline": (
            "[응급의학 화상 1차 대응 표준]\n"
            "1. 즉시 흐르는 미지근하거나 시원한 수돗물에 15~20분간 식힙니다.\n"
            "2. 얼음을 직접 대면 조직 손상이 악화되므로 금지합니다.\n"
            "3. 물집은 감염 위험이 있으므로 터뜨리지 않습니다.\n"
            "4. 된장, 소주 등 민간요법 물질은 절대 바르지 않습니다."
        )
    }
}


def retrieve_medical_context(user_query: str) -> Optional[str]:
    """사용자의 입력 문장을 분석하여 관련도 높은 의학 지침을 검색합니다."""
    if not user_query:
        return None

    matched_guidelines: List[str] = []
    for condition_id, data in MEDICAL_KNOWLEDGE_BASE.items():
        for kw in data["keywords"]:
            if kw in user_query:
                matched_guidelines.append(data["guideline"])
                break

    if not matched_guidelines:
        return None

    return "\n\n".join(matched_guidelines)


if __name__ == "__main__":
    sample = "라면 끓이다가 냄비에 손을 심하게 데였는데 물집이 생겼어요."
    print("검색 결과:\n", retrieve_medical_context(sample))
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 객관식
의료 헬스케어 인공지능 챗봇에서 RAG(검색 증강 생성) 기술을 도입하는 가장 주된 목적은 무엇일까요?
1. 챗봇의 캐릭터 목소리를 더 예쁘게 바꾸기 위해
2. 사용자의 인터넷 속도를 2배 빠르게 향상시키기 위해
3. 검증된 공식 의료 문헌을 주입하여 LLM의 허위 진단 및 환각(Hallucination)을 방지하기 위해
4. 데이터베이스의 저장 용량을 무제한으로 늘리기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 3번 (검증된 질병청/119 공식 문헌을 근거로 제시함으로써 거짓된 의료 답변 위험을 최소화함)
</details>

---

### ## [문제 2] 코드 분석형
위 코드의 `retrieve_medical_context` 함수에서 `break` 문이 사용된 이유는 무엇일까요?
1. 검색 도중 에러가 발생하면 전체 프로그램을 즉시 종료하기 위해
2. 한 질환(예: 화상)의 키워드 중 "데였"과 "물집"이 둘 다 포함되어 있어도 같은 가이드라인이 중복 출력되는 것을 방지하기 위해
3. 사용자의 질문을 영구적으로 삭제하기 위해
4. 파이썬의 메모리를 초기화하기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (동일 질환 카테고리 내에서 키워드가 중복 매칭되어도 안내문이 두 번 중복 추가되지 않도록 방어)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 화상 처치 요령을 들려줄 때, RAG 엔진이 질병관리청 표준 수칙을 검색하여 전달하지 못했을 경우 발생할 수 있는 환각 사례를 1가지 제시하고, RAG의 필요성을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
공식 지침이 주입되지 않으면 LLM이 인터넷 상의 민간요법을 학습한 기억을 되살려 "얼음을 환부에 직접 대라"거나 "된장, 치약을 발라라"는 치명적인 오답을 생성할 수 있습니다. 

RAG를 통해 공신력 있는 표준 문헌을 사전 주입함으로써 이러한 왜곡된 답변을 원천 차단하고 환자의 안전을 보장할 수 있습니다.
</details>

---

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

---

# 05-4. [종합 실습 Lab] 골든타임 사수! AI 응급 의료 파이프라인 통합 구축

---

## 1. 🎯 학습 목표
1. 룰베이스 엔진, RAG 검색기, LLM 생성기를 하나의 파이프라인 함수로 결합할 수 있습니다.
2. 입력 발화의 긴급도에 따라 처리 분기(응급 직행 vs 일반 상담 RAG)를 제어합니다.
3. 화면 텍스트 출력용 전체 답변과 음성 안내(TTS)용 정제 텍스트를 분리 가공합니다.

---

## 2. 💡 핵심 개념

```text
[사용자 입력 발화]
       │
       ▼
[1단계: check_emergency()] ──(응급 감지: True)──► [119 즉시 행동 지침 + DB 긴급 로그 기록]
       │ (정상: False)
       ▼
[2단계: retrieve_medical_context()] ──► [질병관리청 공식 지침 검색 (RAG)]
       │
       ▼
[3단계: Groq 초고속 LLM 추론] ──► [KST 시간 주입 + 3~4문장 핵심 요약 답변 생성]
       │
       ▼
[4단계: 텍스트 이원화 가공]
       ├─► 화면 출력용: LLM 답변 + 법적 면책 고지(Disclaimer)
       └─► 음성 변환용(TTS): 면책 고지 제외 순수 핵심 답변만 추출
```

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `groq` 라이브러리 및 유효한 `GROQ_API_KEY`

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: integrated_medical_pipeline.py
기능: 응급 감지 -> RAG -> LLM -> 면책 고지 결합 및 TTS 텍스트 분리 종합 실습
"""

from typing import Dict, Any
from emergency_detector import check_emergency
from medical_rag import retrieve_medical_context
from medical_llm import generate_medical_advice


def run_smart119_pipeline(user_query: str, api_key: str = None) -> Dict[str, Any]:
    clean_query = user_query.strip() if user_query else ""
    if not clean_query:
        return {
            "is_emergency": False,
            "display_text": "질문하실 내용을 입력해 주세요.",
            "speech_text": "질문하실 내용을 입력해 주세요."
        }

    # 1단계: 룰베이스 응급 감지
    is_emergency, emergency_guide = check_emergency(clean_query)
    if is_emergency:
        return {
            "is_emergency": True,
            "display_text": emergency_guide,
            "speech_text": "위급한 신체 이상 징후가 감지되었습니다. 즉시 119에 신고하십시오."
        }

    # 2단계: RAG 의학 지식 검색
    rag_context = retrieve_medical_context(clean_query)

    # 3단계: LLM 답변 생성
    llm_full_result = generate_medical_advice(clean_query, rag_context, api_key)

    # 4단계: TTS용 텍스트 분리
    if "⚠️ [법적 면책 고지]" in llm_full_result:
        pure_speech = llm_full_result.split("⚠️ [법적 면책 고지]")[0].strip()
        pure_speech = pure_speech.replace("--------------------------------------------------", "").strip()
    else:
        pure_speech = llm_full_result.strip()

    return {
        "is_emergency": False,
        "display_text": llm_full_result,
        "speech_text": pure_speech
    }
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 객관식
위 종합 파이프라인에서 응급 키워드가 감지되었을 때(`is_emergency == True`), LLM API를 호출하지 않고 곧바로 119 안내문을 반환하도록 설계한 이유로 가장 적절한 것은?
1. LLM API 사용 요금을 절약하기 위해
2. 단 1초의 지체도 없이 즉각적인 119 신고 행동 수칙을 전달하기 위해
3. 사용자의 스마트폰 배터리를 보호하기 위해
4. 파이썬의 재귀 호출 에러를 방지하기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (골든타임이 중요한 응급 상황에서는 지연시간 없이 즉각 표준 지침을 노출해야 함)
</details>

---

### ## [문제 2] 단답형
종합 파이프라인의 결과값 중 `display_text`에는 법적 면책 고지를 포함시키고, `speech_text`에서는 법적 면책 고지를 잘라내어 분리 저장한 주된 목적은 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 시각적으로는 법적 고지 의무를 준수하면서, 청각적으로는 길고 지루한 안내 방송으로 인한 사용자 피로도를 줄이고 핵심 대처 요령만 빠르게 듣게 하기 위함
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 장문의 의료 답변을 들려줄 때 발생할 수 있는 사용성 문제점을 제시하고, 본 실습 코드에서 이를 기술적으로 어떻게 해결했는지 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> 
화면에 표기되는 법적 면책 조항까지 음성으로 읽어주게 되면 불필요한 법률 문구를 청취해야 하는 피로감과 시간 낭비가 발생합니다. 

본 실습에서는 문자열 분할 기법(`split("⚠️ [법적 면책 고지]")[0]`)을 적용하여 화면 표기용 텍스트와 음성 합성용 텍스트를 이원화함으로써, 사용자가 실제 필요한 핵심 조언만을 간결하게 들을 수 있도록 해결하였습니다.
</details>

---

# 06-1. 체질량지수(BMI)와 기초대사량(BMR) 자동 계산 알고리즘

---

## 1. 🎯 학습 목표
1. 신체 질량 지수(BMI)와 기초대사량(BMR)의 과학적 산출 공식을 이해합니다.
2. 성별과 나이에 따라 분기되는 조건 연산 알고리즘을 파이썬 함수로 구현합니다.
3. 입력값의 유효성을 검증하는 방어 코드를 작성합니다.

---

## 2. 💡 핵심 개념

### ① 체질량지수 (BMI) 공식
\[ \text{BMI} = \frac{\text{몸무게}(\text{kg})}{\left(\frac{\text{키}(\text{cm})}{100}\right)^2} \]

### ② 기초대사량 (BMR, Mifflin-St Jeor) 공식
- **남성:** \( 10 \times \text{체중}(\text{kg}) + 6.25 \times \text{신장}(\text{cm}) - 5 \times \text{나이} + 5 \)
- **여성:** \( 10 \times \text{체중}(\text{kg}) + 6.25 \times \text{신장}(\text{cm}) - 5 \times \text{나이} - 161 \)

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: health_calculator.py
기능: 키, 몸무게, 나이, 성별 기반 BMI 및 BMR 정밀 계산 모듈
"""

from typing import Dict, Any


def calculate_health_metrics(
    height_cm: float,
    weight_kg: float,
    age: int,
    gender: str = "male"
) -> Dict[str, Any]:
    if height_cm <= 50 or height_cm >= 250:
        raise ValueError("신장은 50cm 이상 250cm 이하의 유효한 값이어야 합니다.")
    if weight_kg <= 20 or weight_kg >= 300:
        raise ValueError("체중은 20kg 이상 300kg 이하의 유효한 값이어야 합니다.")
    if age <= 0 or age >= 130:
        raise ValueError("나이는 1세 이상 130세 이하의 정수여야 합니다.")

    height_m = height_cm / 100.0
    bmi_value = round(weight_kg / (height_m ** 2), 1)

    if bmi_value < 18.5:
        bmi_status = "저체중"
    elif bmi_value < 23.0:
        bmi_status = "정상"
    elif bmi_value < 25.0:
        bmi_status = "비만 전단계 (과체중)"
    else:
        bmi_status = "비만"

    gender_lower = gender.lower()
    if gender_lower in ["남", "남성", "male", "m"]:
        gender_code = "남성"
        bmr_value = round((10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5, 1)
    else:
        gender_code = "여성"
        bmr_value = round((10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161, 1)

    return {
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "age": age,
        "gender": gender_code,
        "bmi": bmi_value,
        "bmi_status": bmi_status,
        "bmr_kcal": bmr_value
    }
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 계산형
키 180cm, 몸무게 72kg인 남성의 BMI 수치를 소수점 둘째 자리에서 반올림하여 계산하시오.
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 22.2 (계산식: \( 72 / (1.8 \times 1.8) \approx 22.22 \))
</details>

---

### ## [문제 2] 코드 분석형
BMR을 계산할 때 사용자의 성별에 따라 마지막 상수가 다르게 적용됩니다. Mifflin-St Jeor 공식에서 남성과 여성에게 적용되는 상수는 각각 얼마입니까?
1. 남성 +50, 여성 -50
2. 남성 +5, 여성 -161
3. 남성 +100, 여성 -100
4. 남성 +10, 여성 -10
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (남성은 +5, 여성은 -161)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS) 또는 챗봇 화면으로 건강 분석 결과를 안내할 때, 사용자가 키를 미터(m) 단위(예: 1.75)가 아닌 센티미터(cm) 단위(예: 175)로 입력하지 않았을 때 발생할 수 있는 치명적인 계산 오류 현상을 기술하고, 이를 방어하는 코드 검증 기법을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
사용자가 키를 미터 단위(1.75)로 입력했는데 알고리즘이 이를 센티미터로 가정하고 다시 100으로 나누어 계산하면 키가 0.0175m로 인식되어 BMI 값이 비정상적으로 수만 단위로 폭증하게 됩니다. 

이를 방어하기 위해 `if height < 3.0: height = height * 100`과 같이 3.0 이하의 입력은 미터(m) 단위로 간주하여 자동 보정하거나 사전에 유효 범위를 체크해야 합니다.
</details>

---

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

---

# 07-1. 상담 기록 저장 및 안전한 계정별 이력 관리

---

## 1. 🎯 학습 목표
1. 사용자의 질문과 AI의 답변 쌍을 DB에 저장하는 원리를 이해합니다.
2. 타인의 상담 기록을 열람할 수 없도록 계정 이메일 기반의 데이터 격리 쿼리를 작성합니다.
3. 개별 상담 기록 삭제 시 고유 일련번호(`id`)를 활용한 안전한 삭제 트랜잭션을 구현합니다.

---

## 2. 💡 핵심 개념

```sql
CREATE TABLE IF NOT EXISTS public.chat_logs (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_email TEXT NOT NULL,
    user_message TEXT NOT NULL,
    bot_reply TEXT NOT NULL,
    is_emergency BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
```

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `supabase` 클라이언트 모듈

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: chat_manager.py
기능: 상담 기록 저장, 계정별 이력 격리 조회, 개별 삭제 관리 모듈
"""

import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client


def get_client() -> Optional[Client]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def save_chat_log(
    user_email: str,
    user_message: str,
    bot_reply: str,
    is_emergency: bool = False
) -> bool:
    client = get_client()
    if not client:
        return False

    payload = {
        "user_email": user_email.strip(),
        "user_message": user_message.strip(),
        "bot_reply": bot_reply.strip(),
        "is_emergency": is_emergency
    }
    try:
        client.table("chat_logs").insert(payload).execute()
        return True
    except Exception as e:
        print(f"[chat_logs 저장 실패]: {e}")
        return False


def fetch_user_chat_logs(user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
    client = get_client()
    if not client:
        return []
    try:
        res = client.table("chat_logs") \
            .select("*") \
            .eq("user_email", user_email.strip()) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception:
        return []


def delete_single_chat_log(log_id: int, user_email: str) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        client.table("chat_logs") \
            .delete() \
            .eq("id", log_id) \
            .eq("user_email", user_email.strip()) \
            .execute()
        return True
    except Exception:
        return False
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 보안 쿼리 분석형
`delete_single_chat_log` 함수에서 단순히 `.eq("id", log_id)`로만 삭제하지 않고 `.eq("user_email", user_email.strip())` 조건을 함께 붙인 보안상의 이유는 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 타인의 상담 기록 번호(ID)를 임의로 넘겨 다른 사용자의 민감한 의료 상담 기록을 무단 삭제하는 취약점(IDOR)을 방지하기 위함
</details>

---

### ## [문제 2] 단답형
관계형 데이터베이스에서 각 레코드(행)를 유일하게 식별하기 위해 자동으로 부여되는 고유 번호 컬럼을 무엇이라고 부를까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 기본키 (Primary Key, PK)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 이전 상담 기록을 복기해 주는 기능을 제공할 때, 환자가 며칠에 걸쳐 수십 건의 대화를 나누었다면 전체 기록을 다 읽어주는 것은 비효율적입니다. 위 코드에서 사용된 파라미터를 기반으로 음성 재생에 적합하도록 최신 기록을 간결하게 선별하는 방법을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
`.order("created_at", desc=True)`로 정렬된 상태에서 `limit=1` 또는 `limit=3`을 지정하여, 가장 최근에 나눈 1~3건의 핵심 질의응답만을 슬라이싱하여 TTS 엔진에 전달함으로써 청취 시간을 단축해야 합니다.
</details>

---

# 08-1. 모바일 브라우저 HTML5 Geolocation 정밀 GPS 측정

---

## 1. 🎯 학습 목표
1. 웹 브라우저 표준 `navigator.geolocation` API의 구조를 이해합니다.
2. 실내외 환경에서 높은 정확도의 좌표를 얻기 위한 `enableHighAccuracy` 옵션을 구성합니다.
3. 위치 수신 실패 시 사용자에게 친절히 조치법을 안내하는 방어 로직을 작성합니다.

---

## 2. 💡 핵심 개념

```text
[🚨 사이렌 버튼 클릭]
         │
         ▼
[navigator.geolocation.getCurrentPosition()]
         │
         ├─► [권한 허용] ──► (위도, 경도 좌표 산출) ──► 구글맵 링크 생성
         │
         └─► [권한 거부] ──► "브라우저 설정에서 위치 권한을 허용해 주세요" 경고
```

---

## 3. 🛠️ 준비물
- GPS 지원 브라우저 (Chrome, Edge 등)
- HTTPS 보안 연결 환경

---

## 4. 💻 단계별 실습 코드

```javascript
// 파일명: gps_tracker.js
// 기능: 고정밀 GPS 위치 측정 및 지도 링크 생성

function measureCurrentGPS(callback) {
  if (!navigator.geolocation) {
    alert("이 브라우저는 위치 측정을 지원하지 않습니다.");
    return;
  }

  const options = {
    enableHighAccuracy: true,
    timeout: 10000,
    maximumAge: 0
  };

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;
      const accuracy = Math.round(position.coords.accuracy);
      const mapUrl = `https://maps.google.com/?q=${lat},${lng}`;

      console.log(`[측정 완료] 위도: ${lat}, 경도: ${lng}, 오차: ${accuracy}m`);
      if (callback) callback({ lat, lng, accuracy, mapUrl });
    },
    (error) => {
      console.error("[GPS 오류]:", error.message);
      alert("위치 측정에 실패했습니다. 스마트폰 설정에서 위치 권한을 켜주세요.");
    },
    options
  );
}
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 웹 표준 보안형
모바일 브라우저에서 HTML5 Geolocation API를 호출할 때 반드시 필요한 웹 보안 통신 규격은 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> HTTPS (또는 localhost 개발 환경)
</details>

---

### ## [문제 2] 단답형
기기의 실제 위성 GPS 하드웨어를 직접 가동하여 오차를 줄이도록 지정하는 설정 파라미터는 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> <code>enableHighAccuracy: true</code>
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 "현재 위치가 측정되었습니다"라고 안내한 뒤, 위도 경도 숫자 자체를 음성으로 읽어주는 방식의 문제점을 짚어보고, 시각 지도 링크(URL)와 결합하여 전달하는 방식이 왜 더 효과적인지 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
위도와 경도는 소수점 여섯 자리 이상의 긴 숫자이므로, 이를 음성으로 받아 적는 것은 긴급한 위기 상황에서 청취자에게 극심한 혼란을 초래합니다. 

따라서 음성으로는 <i>"현재 위치가 보호자에게 전송되었습니다"</i>라고 간결히 안심시키고, 실제 데이터는 원터치로 카카오맵이나 구글맵이 열리는 지도 링크로 가공해 전달해야 신속한 출동이 가능해집니다.
</details>

---

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
