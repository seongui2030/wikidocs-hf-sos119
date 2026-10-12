# 04-2. 목소리로 전달하는 따뜻한 위로: gTTS 음성 합성 엔진

시각 장애인, 노안으로 글씨가 잘 안 보이는 어르신, 혹은 극심한 통증으로 눈을 뜨기조차 힘든 환자는 화면의 작은 글씨를 읽을 수 없습니다. AI가 생성한 전문 의료 상담과 119 대처 요령을 **자연스러운 인간의 목소리로 합성하여 스피커로 들려주는 기술**을 **TTS(Text-to-Speech)**라고 부릅니다. 이번 실습에서는 구글 음성 합성 엔진(gTTS)을 파이썬에 연동하여 화면 밖으로 음성을 송출하는 파이프라인을 구축합니다.

---

## 1. 🎯 학습 목표
1. 텍스트 문자열이 발음 기호와 음향 파형으로 변환되는 음성 합성(TTS)의 동작 원리를 이해합니다.
2. 마크다운 기호(`*`, `#`), 이모지(`🚨`, `💡`), 불필요한 서식을 음성 변환 전에 정제하는 전처리 필터를 구현합니다.
3. 여러 사용자가 동시 접속해도 음성 파일이 덮어쓰여 충돌하지 않도록 고유 임시 파일(`uuid`, `tempfile`) 기법을 습득합니다.

---

## 2. 💡 핵심 개념

### ① 음성 합성(TTS) 파이프라인과 텍스트 정제
화면에 예쁘게 표시하기 위해 넣은 이모티콘이나 마크다운 볼드체 기호(`**`, `##`)를 그대로 TTS 엔진에 넣으면 "샵 샵 느낌표 별 별"처럼 엉뚱한 발음으로 읽어버립니다. 음성 엔진에 전달하기 전에 **특수 서식을 완벽히 정제**하는 과정이 필수적입니다.

```text
[화면 표기용 텍스트]
"🚨 **급성 심근경색** 의심 징후입니다! 즉시 119에 신고하십시오."
                   │
                   ▼ [정제 필터: 이모지 및 마크다운 특수기호 제거]
[정제된 음성 합성용 텍스트]
"급성 심근경색 의심 징후입니다. 즉시 일일구에 신고하십시오."
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  gTTS (Google Text-to-Speech) 엔진           │
│  - 한국어 자연스러운 억양과 발음 합성 (lang='ko')│
└──────────────────────────────────────────────┘
                   │
                   ▼
[동적 고유 임시 파일 저장: /tmp/voice_7f8a9b.mp3] ──► [브라우저 오디오 재생]
```

### ② 동시 접속 환경에서의 파일명 충돌 방지
서버에서 고정된 이름(예: `output.mp3`)으로 음성 파일을 저장하면, A 사용자가 상담 중일 때 B 사용자가 질문을 하면 A 사용자의 목소리 파일이 덮어써져 남의 답변이 재생되는 치명적인 버그가 발생합니다. `uuid4().hex`를 붙여 **모든 요청마다 독립된 고유 파일 경로**를 발급해야 합니다.

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `gTTS` 라이브러리 (`pip install gTTS`)

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: text_to_speech.py
기능: 특수서식 정제, 한국어 음성 합성(gTTS), 동시성 안전 고유 파일 생성 모듈
"""

import os
import re
import uuid
import tempfile
from typing import Optional
from gtts import gTTS


def sanitize_text_for_speech(raw_text: str) -> str:
    """
    마크다운 특수기호, 이모지, 구분선 등을 깨끗이 제거하여 음성 합성에 최적화합니다.
    """
    if not raw_text:
        return ""

    # 1. 법적 면책 고지 및 하단 안내선 이전의 본문만 남김
    text = raw_text.split("⚠️ [법적 면책 고지]")[0]
    text = text.split("---")[0]

    # 2. 마크다운 서식 기호 제거 (#, *, _, `, >, [ ], ( ))
    text = re.sub(r"[#*_`>\[\]\(\)]", " ", text)

    # 3. 이모지 및 특수 그림문자 제거 (유니코드 서로게이트 및 기호)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[🚨💡⚠️✨👉📋🖨️📊🛰️📍❌💪🕒]", "", text)

    # 4. 숫자 '119'를 명확하게 '일일구'로 읽도록 전처리 (선택적 가독성 개선)
    text = text.replace("119", "일일구")

    # 5. 연속된 공백 및 줄바꿈을 단일 공백으로 치환
    clean_text = re.sub(r"\s+", " ", text).strip()
    return clean_text


def text_to_speech(text_content: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    텍스트를 자연스러운 한국어 MP3 음성 파일로 합성하여 저장 경로를 반환합니다.

    매개변수:
        text_content (str): 소리로 변환할 본문 텍스트
        output_dir (str, optional): 저장할 디렉토리 (생략 시 시스템 임시 폴더 사용)

    반환값:
        Optional[str]: 생성된 MP3 파일의 절대 경로 (실패 시 None)
    """
    clean_text = sanitize_text_for_speech(text_content)
    if not clean_text:
        print("[TTS 경고] 음성으로 변환할 내용이 비어 있습니다.")
        return None

    # 동시 접속자 충돌을 방지하기 위한 고유 파일명 생성
    target_dir = output_dir or tempfile.gettempdir()
    os.makedirs(target_dir, exist_ok=True)
    unique_filename = f"smart119_voice_{uuid.uuid4().hex[:8]}.mp3"
    saved_filepath = os.path.join(target_dir, unique_filename)

    try:
        # gTTS 객체 생성 (한국어 'ko', 표준 속도)
        tts = gTTS(text=clean_text, lang="ko", slow=False)
        tts.save(saved_filepath)
        print(f"[TTS 생성 완료] 파일 경로: {saved_filepath} (글자 수: {len(clean_text)})")
        return saved_filepath

    except Exception as e:
        print(f"[TTS 생성 실패]: {e}")
        return None


# --- 단독 실행 테스트 ---
if __name__ == "__main__":
    print("=" * 60)
    print("스마트119 고유 음성 합성(TTS) 엔진 테스트")
    print("=" * 60)

    sample_markdown = """
    🚨 **[긴급 상황 감지]**
    현재 환자분은 **급성 호흡곤란** 증상이 의심됩니다! 
    즉시 119에 전화하십시오.
    
    ⚠️ [법적 면책 고지]
    본 상담은 의사의 진료를 대신할 수 없습니다.
    """

    audio_path = text_to_speech(sample_markdown)
    if audio_path:
        print(f"\n성공적으로 생성된 음성 파일:\n👉 {audio_path}")
        print("정제된 텍스트 확인:", sanitize_text_for_speech(sample_markdown))
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 객관식
음성 합성(TTS) 모듈에서 `uuid.uuid4().hex`를 파일명에 부착하여 저장하는 가장 주된 이유는 무엇일까요?
1. 음성 파일의 음질을 320kbps 초고음질로 올리기 위해
2. 파일 용량을 90% 이상 압축하기 위해
3. 여러 사용자가 동시에 챗봇을 이용할 때 동일한 파일명을 덮어써서 타인의 음성이 재생되는 레이스 컨디션(Race Condition)을 원천 방지하기 위해
4. 해커의 바이러스 침투를 감지하기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 3번 (다중 접속 환경에서 사용자 간 파일 덮어쓰기 충돌 및 음성 데이터 오염을 방지하기 위함)
</details>

---

### ## [문제 2] 정규표현식 분석형
위 코드의 `re.sub(r"[#*_`>\[\]\(\)]", " ", text)` 정규식이 수행하는 역할은 무엇일까요?
1. 영어 알파벳을 모두 한글로 번역한다.
2. 텍스트에 포함된 마크다운 제목, 볼드체, 인라인 코드, 링크 등의 서식 특수기호를 공백으로 치환하여 자연스러운 발음을 유도한다.
3. 숫자를 모두 0으로 바꾼다.
4. 문맥의 오탈자를 자동으로 맞춤법 검사한다.
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (마크다운 특수기호가 기호 이름 그대로 낭독되는 현상을 막기 위해 서식을 제거함)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 위급 안내를 송출할 때, "119로 즉시 전화하세요"라는 문장을 엔진에 전달할 때 아라비아 숫자 "119"를 "백십구"가 아닌 "일일구"로 명확히 발음하도록 유도해야 하는 이유와 이를 구현한 전처리 방식을 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
일반적인 음성 합성 엔진은 세 자리 숫자를 기본적으로 수사(Cardinals)인 "백십구"로 발음합니다. 그러나 비상 신고 전화번호는 고유의 식별 번호이므로 "일일구"로 또렷하게 읽어주어야 위급 환자가 번호를 혼동하지 않고 정확히 인식할 수 있습니다. 

이를 위해 TTS 생성 전 텍스트 정제 단계에서 `text.replace("119", "일일구")`와 같이 사전 치환 처리를 적용해야 합니다.
</details>

---