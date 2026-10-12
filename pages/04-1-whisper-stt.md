# 04-1. 인공지능 청각 신경망: Groq Whisper 기반 초고속 음성인식(STT)

응급 환자나 어르신, 혹은 손을 다쳐 스마트폰 자판을 두드리기 어려운 위급 상황에서는 자판 입력보다 **음성 발화**가 환자의 생명을 구하는 가장 빠른 수단입니다. 사람이 내뱉은 목소리(음향 파형)를 컴퓨터가 이해할 수 있는 텍스트 데이터로 변환하는 과정을 **STT(Speech-to-Text)**라고 부릅니다. 이번 실습에서는 세계 최고 수준의 다국어 음성 인식 신경망인 OpenAI Whisper 모델을 Groq의 LPU(초고속 추론 엔진) 위에서 구동하여, 1초 이내에 음성을 정밀 텍스트로 전환하는 음성인식 엔진을 제작합니다.

---

## 1. 🎯 학습 목표
1. 소리(Analog/Acoustic Wave)가 디지털 오디오 데이터(WAV/M4A/WebM)로 캡처되는 기본 구조를 이해합니다.
2. Whisper 신경망 모델의 다국어 음성 인식 원리와 한국어(`language="ko"`) 최적화 옵션을 학습합니다.
3. 임시 오디오 파일의 안전한 생성 및 메모리 누수 없는 자동 소멸(Garbage Collection) 파이프라인을 구축합니다.

---

## 2. 💡 핵심 개념

### ① 음성 신호의 디지털 변환과 Whisper 신경망
스마트폰 마이크는 공기의 떨림(음압)을 전기 신호로 바꾸고, 이를 초당 수만 번 샘플링(Sampling)하여 디지털 바이트 스트림으로 저장합니다. Whisper는 이 오디오 파형을 스펙트로그램(Log-Mel Spectrogram)이라는 시각적 주파수 이미지로 변환한 뒤, 트랜스포머(Transformer) 인코더-디코더 신경망을 통해 가장 가능성 높은 단어 연속(Text)으로 디코딩합니다.

```text
[환자의 다급한 목소리: "숨이 차요"] 
                │ (마이크 캡처: 16,000Hz 샘플링)
                ▼
[오디오 파일 버퍼 (audio.wav / audio.webm)]
                │
                ▼
┌───────────────────────────────────────────────┐
│  Groq Cloud Whisper Large v3 LPU 인퍼런스       │
│  - Log-Mel 주파수 스펙트로그램 변환              │
│  - 다국어 중 한국어(ko) 자동 정렬 및 노이즈 필터링 │
└───────────────────────────────────────────────┘
                │ (평균 지연시간: 0.3~0.5초)
                ▼
[정제된 텍스트 출력: "숨이 차요"]
                │
                ▼
[다음 단계: 룰베이스 응급 감지 엔진 check_emergency()]
```

### ② 왜 Groq Whisper를 사용할까요?
일반 CPU 서버에서 Whisper 대형 모델(`whisper-large-v3`)을 돌리면 5초 분량의 음성을 텍스트로 바꾸는 데 2~4초가 걸립니다. 하지만 Groq의 전용 하드웨어(LPU)를 이용하면 동일 모델을 **0.3초 안팎**으로 처리하여, 응급 상황에서 환자가 체감하는 지연시간(Latency)을 '제로'에 가깝게 단축할 수 있습니다.

---

## 3. 🛠️ 준비물
- Python 3.10 이상 실행 환경
- `groq` 라이브러리 (`pip install groq`)
- 테스트용 음성 녹음 파일 (WAV, MP3, M4A 등 25MB 이하)

---

## 4. 💻 단계별 실습 코드

```python
"""
파일명: speech_to_text.py
기능: Groq Whisper-large-v3 모델을 활용한 초고속 한국어 음성인식(STT) 모듈
"""

import os
from typing import Optional
from groq import Groq


def speech_to_text(audio_file_path: str, api_key: Optional[str] = None) -> str:
    """
    녹음된 오디오 파일 경로를 받아 Whisper 모델로 텍스트를 추출합니다.

    매개변수:
        audio_file_path (str): 분석할 음성 파일 경로 (wav, mp3, webm, m4a 등)
        api_key (str, optional): Groq API 키 (생략 시 환경변수에서 로드)

    반환값:
        str: 인식된 한국어 텍스트 문장 (실패 시 빈 문자열 또는 에러 메시지)
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        print("[STT 에러] GROQ_API_KEY 환경변수가 설정되지 않았습니다.")
        return ""

    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"[STT 에러] 오디오 파일이 존재하지 않습니다: {audio_file_path}")
        return ""

    client = Groq(api_key=key)

    try:
        # 오디오 파일을 바이너리 읽기(rb) 모드로 열어 Whisper 모델에 전달
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model="whisper-large-v3",
                language="ko",          # 한국어 인식률 극대화 명시
                response_format="text", # JSON 대신 순수 텍스트로 바로 수신
                temperature=0.0         # 인식 일관성을 위해 0으로 고정
            )

        recognized_text = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
        print(f"[STT 변환 완료]: \"{recognized_text}\"")
        return recognized_text

    except Exception as e:
        print(f"[STT 처리 중 예외 발생]: {e}")
        return ""


# --- 단독 실행 테스트 ---
if __name__ == "__main__":
    print("=" * 60)
    print("스마트119 초고속 Whisper STT 음성 변환 테스트")
    print("=" * 60)

    # 마이크 녹음 파일 가상 경로 테스트
    sample_audio = "test_sample.wav"
    
    if os.path.exists(sample_audio):
        result = speech_to_text(sample_audio)
        print(f"\n최종 변환 결과:\n👉 {result}")
    else:
        print(f"\n[안내] 테스트용 '{sample_audio}' 파일이 없어 모의 가이드를 출력합니다.")
        print("실제 마이크 녹음이 완료되면 speech_to_text(filepath) 형태로 즉시 호출됩니다.")
```

---

## 5. ✍️ 확인 문제

### ## [문제 1] 객관식
Groq Whisper API 호출 시 `language="ko"` 매개변수를 명시적으로 전달하는 주된 기술적 이유는 무엇일까요?
1. 영어 오디오 파일의 용량을 절반으로 압축하기 위해
2. 모델이 입력 언어를 탐지(Language Detection)하느라 소모하는 수백 밀리초의 지연시간을 줄이고, 한국어 음소에 가중치를 두어 인식 정확도를 높이기 위해
3. 사용자의 스마트폰 요금제 데이터를 무료로 전환하기 위해
4. 마이크 볼륨 크기를 2배로 증폭시키기 위해
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 2번 (언어 자동 감지 단계를 생략하여 지연시간을 단축하고 한국어 전용 가중치를 부여해 정확도를 극대화함)
</details>

---

### ## [문제 2] 단답형
Whisper와 같은 인공신경망이 음향 파형을 시간-주파수 2차원 시각 데이터로 변환할 때 사용하는 신호 처리 표현 기법의 명칭은 무엇일까요?
<details>
<summary>정답 확인하기</summary>
<b>정답:</b> 스펙트로그램 (Log-Mel Spectrogram)
</details>

---

### ## [문제 3] 서술형 탐구
> 사용자에게 음성(TTS)으로 답변하기에 앞서, 환자가 마이크 버튼을 누르고 말하지 않고 침묵을 지키거나 주변의 작은 바람 소리만 녹음되어 `speech_to_text()` 결과가 빈 문자열(`""`)로 반환되었을 때, 이를 그대로 LLM에 넘기지 않고 사전 차단해야 하는 이유와 올바른 대처 코드를 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b>
빈 문자열이 그대로 LLM에 전달되면 LLM이 아무런 맥락 없는 엉뚱한 환각 문장을 생성하거나 API 호출 비용과 서버 자원을 무의미하게 낭비하게 됩니다.

따라서 `if not recognized_text.strip(): return "목소리가 잘 들리지 않았습니다. 마이크를 가까이 대고 다시 말씀해 주세요."`와 같이 사전 유효성 검사 분기를 두어 무음 입력을 걸러내야 합니다.
</details>

---


