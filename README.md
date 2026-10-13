# [스마트 119]
> **"스마트 119"**는 Qwen과 Whisper를 활용해 음성·텍스트 기반 건강
> 상담을 제공하고, 응급 상황에서는 GPS 위치 확인 및 보호자 SMS 발송
> 링크를 준비하는 스마트119 웹앱입니다.

## 1. 시스템 동작 흐름도

![Flow-chart](assets\wikidocs-hf-sos119-mermaid.svg)
<img alt="시스템 동작 흐름도" decoding="async" loading="lazy" src="https://raw.githubusercontent.com/seongui2030/wikidocs_hf_sos119/main/assets/wikidocs-hf-sos119-mermaid.svg">

``` mermaid
flowchart TD
    Start(["사용자 앱 접속"]) --> CheckAuth{"로그인 여부 확인"}

    CheckAuth -->|Google 계정 로그인| OAuth["Google OAuth 2.0 인증"]
    OAuth --> SyncUser["auth_manager.py: app_users 테이블 동기화"]
    CheckAuth -->|체험용 게스트| Guest["guest@smart119.local 임시 세션"]

    SyncUser --> MainUI["스마트119 메인 대시보드"]
    Guest --> MainUI

    MainUI --> InputVoice["플로팅 마이크: 원터치 음성 입력"]
    MainUI --> InputText["텍스트 입력창: 글로 질문하기"]
    MainUI --> ClickBMI["신체 건강 입력"]
    MainUI --> ClickSOS["사이렌 버튼: 긴급 구조 요청"]
    MainUI --> ClickHistory["대화 기록 관리"]

    InputVoice --> STT["Groq Whisper-large-v3: 음성을 한글 텍스트로 변환"]
    STT --> CheckEmerg{"응급 키워드 판별<br/>check_emergency"}
    InputText --> CheckEmerg

    CheckEmerg -->|위급 상황: 흉통·호흡곤란 등| EmerDetect["응급 대처 프로토콜 발동"]
    EmerDetect --> SaveEmerLog1["emergency_logs 테이블에 즉시 기록"]
    EmerDetect --> ShowAlertBtn["대화창에 SOS 전송 버튼 표시"]

    CheckEmerg -->|일반 건강 상담| RAG["의학 가이드라인 RAG 지식 검색"]
    RAG --> LLM["Groq Qwen-2.5-72B: 맞춤 상담 생성"]
    LLM --> TTS["gTTS: 음성 답변 MP3 합성"]

    ShowAlertBtn --> SaveChat["chat_manager.py: chat_logs 테이블 저장"]
    TTS --> SaveChat
    SaveChat --> PlayAudio["화면 말풍선 출력 및 음성 재생"]

    ClickBMI --> CalcBMI["BMI 및 BMR 자동 계산"]
    CalcBMI --> SaveBMI["bmi 테이블에 사용자 정보 연동 저장"]

    ClickSOS --> GetGPS["브라우저 Geolocation: 위도·경도 측정"]
    GetGPS --> MakeMap["Google Maps / KakaoMap 좌표 링크 생성"]
    MakeMap --> SendSMS["보호자에게 보낼 긴급 알림 SMS 링크"]
    MakeMap --> SaveEmerLog2["emergency_logs 테이블에 위치·수신자 기록"]

    ClickHistory --> SearchLogs["대화 검색 및 개별 삭제"]
    ClickHistory --> ExportFiles["CSV 다운로드 / PDF 인쇄"]
```

## 2. 단계별 한 줄 설명

1.  **사용자 접속 및 인증**: Google 계정으로 로그인하거나 게스트로
    접속합니다.
2.  **음성·텍스트 입력**: 사용자는 마이크로 말하거나 텍스트로 건강
    질문을 입력합니다.
3.  **음성 인식(STT)**: Whisper 모델이 음성을 한국어 텍스트로
    변환합니다.
4.  **응급 상황 판별**: 응급 키워드를 확인하고, 위급 상황이면 응급 대처
    안내와 SOS 전송 버튼을 표시합니다.
5.  **의료 지식 검색 및 AI 상담**: 일반 상담은 의료 가이드라인 기반 RAG
    검색 후 Qwen 모델을 통해 답변을 생성합니다.
6.  **음성 답변(TTS)**: gTTS로 답변 음성을 생성해 화면에 표시하고
    재생합니다.
7.  **신체 건강 관리**: 키와 몸무게 등의 입력을 바탕으로 BMI와 BMR을
    계산하고 저장합니다.
8.  **GPS 기반 SOS**: 브라우저 위치 정보를 이용해 지도 좌표 링크를
    만들고 보호자에게 보낼 SMS 링크를 준비합니다.
9.  **상담 기록 관리**: 대화 기록을 검색·삭제하고 CSV 또는 PDF로
    내보냅니다.

## 3. 주요 기능별 기술 구성

| 기능 | 관련 기술·모듈 | 설명 |
|---|---|---|
| **웹 대시보드** | Python, Gradio Blocks, `app.py` | 사용자 화면 및 기능 진입점 |
| **환경 설정 및 데이터베이스** | Supabase, SQL, `.env`, `sql.sql` | 데이터 저장 및 API 키 등 환경변수 관리 |
| **소셜 로그인** | Google OAuth 2.0, Supabase Auth, `auth_manager.py` | 로그인 및 사용자 정보 동기화 |
| **음성 인식(STT)** | Groq Whisper-large-v3, MediaRecorder | 음성을 텍스트로 변환 |
| **의료 상담** | Groq API, Qwen-2.5, RAG | 의료 가이드라인 검색을 참고한 답변 생성 |
| **음성 합성(TTS)** | gTTS | 답변을 음성으로 변환 |
| **건강 데이터 계산** | BMI, BMR, SQL Foreign Key | 건강 지표 계산 및 사용자 데이터 연결 |
| **상담 기록** | Supabase CRUD, CSV, PDF, `chat_manager.py` | 상담 기록 검색·삭제·내보내기 |
| **GPS 및 SOS** | HTML5 Geolocation, 지도 URL, SMS URI | 위치 링크 생성 및 보호자 문자 작성 지원 |
| **배포** | Hugging Face Spaces, Git, Space Secrets | 웹앱 배포 및 운영 |

---

## 4. 프로젝트 소스코드 구조

| 대단원 | 핵심 주제 | 관련 소스 파일 | 주요 기술 |
|---|---|---|---|
| **01. 웹 개발 기초 및 환경 구축** | 파이썬 가상환경, 웹 프레임워크, 대시보드 | `app.py` | Python, Gradio Blocks, CSS, Git |
| **02. 클라우드 백엔드 및 환경변수** | 데이터베이스, API 키 보안, 테이블 설계 | `sql.sql`, `.env` | Supabase, SQL DDL, Python dotenv |
| **03. 소셜 인증** | Google 로그인 및 사용자 정보 동기화 | `auth_manager.py` | OAuth 2.0, Supabase Auth |
| **04. 음성 AI 파이프라인** | 음성 인식 및 음성 합성 | `app.py` | Groq Whisper STT, MediaRecorder, gTTS |
| **05. 의료 RAG 및 LLM** | 가이드라인 검색 및 AI 답변 생성 | `app.py` | Groq API, Qwen-2.5, 프롬프트 엔지니어링, RAG |
| **06. 건강 데이터 분석** | BMI/BMR 계산 및 계정 연결 | `app.py`, `sql.sql` | 수학 공식, SQL Foreign Key, 데이터 검증 |
| **07. 상담 기록 관리** | 기록 검색·삭제 및 보고서 내보내기 | `chat_manager.py` | Supabase CRUD, CSV, PDF |
| **08. GPS 및 긴급 알림** | 위치 좌표, 지도 링크, SMS 연동 | `app.py`, `sql.sql` | Geolocation API, SMS URI, 응급 로그 |
| **09. 배포 및 운영** | 웹앱 배포 및 로그 모니터링 | `app.py`, `README.md` | Hugging Face Spaces, Git Push, Secrets |


## 5. 실행 및 안전 관련 참고

-   GPS 기능은 브라우저 권한과 보안 컨텍스트(일반적으로 HTTPS 또는
    localhost)가 필요할 수 있습니다.
-   SMS 링크는 사용자의 문자 앱을 열어 메시지 작성을 돕는 방식일 수
    있으며, 환경에 따라 자동 발송되지 않습니다.
-   이 앱의 AI 상담은 의료진의 진단이나 응급 서비스 이용을 대체하지
    않습니다. 실제 응급 상황에서는 즉시 119에 연락하세요.
-   실제 서비스에 배포하기 전에는 응급 키워드 감지, 개인정보 처리,
    인증·권한, 로그 보관, API 키 보안을 충분히 테스트하세요.
