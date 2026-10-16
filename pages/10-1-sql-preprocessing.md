
> 실제 클라우드 서비스 환경에서는 회원 정보, 건강 측정치, AI 상담 대화, 비상 SOS 알림 로그가 서로 다른 테이블에 분산되어 저장됩니다. 머신러닝 알고리즘에 데이터를 주입하려면 이 분산된 테이블들을 회원 단위로 병합하고 결측치를 정제하는 SQL 파이프라인이 필수적입니다.

---

## 1. 🎯 학습 목표
1. 관계형 데이터베이스(RDBMS)에서 1:N 관계로 분산된 다중 테이블 구조를 이해한다.
2. `LEFT JOIN`과 `GROUP BY`를 활용하여 사용자 식별자(`user_id`) 기준으로 피처를 결합·집계할 수 있다.
3. 머신러닝 결측치 처리의 핵심인 `COALESCE` 함수를 사용해 `NULL` 값을 안전하게 0으로 치환할 수 있다.

---

## 2. 💡 핵심 개념

### ① 분산 테이블과 1:N 관계의 통합
`SOS 인공지능 비서` 서비스의 데이터베이스는 다음과 같이 나뉘어 관리됩니다.
- **users**: 회원 기본 정보 (1인당 1개 행)
- **health_records**: 신체 측정치 (키, 몸무게, BMI, 수축기 혈압 등)
- **chat_logs**: AI 건강 상담 기록 (1인당 여러 건의 상담 로그)
- **emergency_logs**: 119/GPS 긴급 SOS 호출 기록 (1인당 여러 건의 발송 로그)

머신러닝 모델은 각 행(Row)이 **'한 명의 사용자'**인 2차원 피처 매트릭스를 입력으로 받기 때문에, 여러 줄로 쌓인 로그들을 사용자 단위로 묶어서 요약(COUNT/AVG)해야 합니다.

```text
[users] (기준 테이블)
   │
   ├─ LEFT JOIN ──> [health_records] (최근 BMI, 수축기 혈압 결합)
   │
   ├─ LEFT JOIN ──> [chat_logs] (GROUP BY user_id ──> 대화수/위험신호 집계)
   │
   └─ LEFT JOIN ──> [emergency_logs] (GROUP BY user_id ──> SOS 호출횟수 집계)
```

---

### ② 핵심 SQL 문법 3요소

| 문법 | 역할 | 머신러닝 파이프라인에서의 필요 이유 |
| :--- | :--- | :--- |
| **LEFT JOIN** | 왼쪽 기준 테이블의 모든 행을 보존하며 결합 | 활동 로그가 전혀 없는 신규 회원도 탈락시키지 않고 모델 분석 대상에 포함하기 위함 (INNER JOIN 사용 시 비활동 회원 데이터 유실) |
| **GROUP BY** | 특정 열(`user_id`)을 기준으로 행들을 그룹화 | 1인당 여러 건 발생하는 로그(상담 기록, SOS 알림)를 사용자 1명당 1줄의 요약 통계량으로 압축 |
| **COALESCE** | 인자 중 첫 번째로 `NULL`이 아닌 값을 반환 | 로그가 없어 생기는 `NULL`을 `0`으로 치환 (결측치가 있으면 Scikit-learn 모델 학습 시 에러 발생) |

---

## 3. 🛠️ 준비물
- Python 3.9 이상 환경 (Google Colab 또는 VS Code)
- `sqlite3` 라이브러리 (Python 표준 내장)
- `pandas` 라이브러리 (`pip install pandas`)

---

## 4. 💻 단계별 실습 코드

다음은 분산된 4개의 테이블을 모의 생성하고, 머신러닝 학습용 단일 데이터프레임(`df_ml`)으로 추출하는 완성형 파이썬 스크립트입니다.

```python
# 10-1-sql-preprocessing.py
import sqlite3
import pandas as pd

# 1. 인메모리 SQLite 데이터베이스 연결
conn = sqlite3.connect(":memory:")
cursor = conn.cursor()

# 2. 실무 환경 모의 테이블 생성 (DDL)
cursor.executescript("""
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    age INTEGER,
    gender TEXT
);

CREATE TABLE health_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    bmi REAL,
    systolic_bp INTEGER
);

CREATE TABLE chat_logs (
    chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    message TEXT,
    is_risk INTEGER  -- 1: 응급의심 키워드 포함, 0: 일반상담
);

CREATE TABLE emergency_logs (
    sos_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    created_at TEXT
);
""")

# 3. 실습용 데이터 삽입 (일부 회원은 로그가 없는 현실적인 상황 반영)
cursor.executescript("""
INSERT INTO users VALUES 
    ('U001', '김철수', 72, 'M'),
    ('U002', '이영희', 68, 'F'),
    ('U003', '박영수', 81, 'M'),
    ('U004', '정미경', 65, 'F');

INSERT INTO health_records VALUES 
    (1, 'U001', 28.5, 145),
    (2, 'U002', 22.1, 118),
    (3, 'U003', 29.8, 158),
    (4, 'U004', 21.4, 120);

-- U001: 일반 상담 2회, 위험 상담 1회 / U003: 위험 상담 2회 / U004: 상담 없음
INSERT INTO chat_logs VALUES 
    (1, 'U001', '어제부터 가슴이 조금 답답해요', 0),
    (2, 'U001', '숨쉬기가 힘들고 가슴 통증이 심해요', 1),
    (3, 'U001', '혈압약 복용 시간 문의', 0),
    (4, 'U003', '의식이 흐려지고 어지러워요 쓰러질것같아', 1),
    (5, 'U003', '119 불러주세요 마비 증세가 와요', 1);

-- U001: SOS 1회 발송 / U003: SOS 2회 발송 / U002, U004: SOS 발송 없음
INSERT INTO emergency_logs VALUES 
    (1, 'U001', '2026-10-12 14:20:00'),
    (2, 'U003', '2026-10-14 09:15:00'),
    (3, 'U003', '2026-10-15 03:40:00');
""")
conn.commit()

# 4. 머신러닝용 단일 피처 테이블 추출 SQL 쿼리 (핵심 영역)
#    - LEFT JOIN으로 모든 사용자(users) 유지
#    - GROUP BY로 사용자별 요약 통계량 생성
#    - COALESCE로 로그가 없는 회원의 NULL 값을 0으로 정제
sql_query = """
SELECT 
    u.user_id,
    u.age,
    CASE WHEN u.gender = 'M' THEN 1 ELSE 0 END AS is_male,
    h.bmi,
    h.systolic_bp,
    COALESCE(COUNT(DISTINCT c.chat_id), 0) AS total_chat_count,
    COALESCE(SUM(CASE WHEN c.is_risk = 1 THEN 1 ELSE 0 END), 0) AS risk_chat_count,
    COALESCE(COUNT(DISTINCT e.sos_id), 0) AS sos_call_count
FROM users u
LEFT JOIN health_records h ON u.user_id = h.user_id
LEFT JOIN chat_logs c ON u.user_id = c.user_id
LEFT JOIN emergency_logs e ON u.user_id = e.user_id
GROUP BY u.user_id;
"""

# 5. Pandas DataFrame으로 적재 및 확인
df_ml = pd.read_sql_query(sql_query, conn)
print("=== [과제 1] 전처리 완료된 머신러닝 피처 매트릭스 ===")
print(df_ml)

conn.close()
```

### 실행 결과 예시
```text
=== [과제 1] 전처리 완료된 머신러닝 피처 매트릭스 ===
  user_id  age  is_male   bmi  systolic_bp  total_chat_count  risk_chat_count  sos_call_count
0    U001   72        1  28.5          145                 3                1               1
1    U002   68        0  22.1          118                 0                0               0
2    U003   81        1  29.8          158                 2                2               2
3    U004   65        0  21.4          120                 0                0               0
```

---

## 5. ✅ 확인 문제

### [문제 1] 개념 확인
머신러닝 데이터 전처리 쿼리에서 `INNER JOIN` 대신 `LEFT JOIN`을 사용해야 하는 결정적인 이유는 무엇인가요?
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> `INNER JOIN`을 사용하면 상담 기록(`chat_logs`)이나 비상 알림 기록(`emergency_logs`)이 한 번도 없는 건강한 사용자나 신규 회원의 행이 결과에서 완전히 누락됩니다. 모든 회원을 평가 및 분류 대상으로 유지하기 위해 기준이 되는 `users` 테이블의 모든 레코드를 보존하는 `LEFT JOIN`을 사용해야 합니다.
</details>

---

### [문제 2] 코드 이해
아래 SQL 구문에서 `COALESCE` 함수가 수행하는 역할과, 이를 생략했을 때 머신러닝 모델 학습 과정에서 발생할 수 있는 문제는 무엇인가요?
```sql
COALESCE(COUNT(DISTINCT e.sos_id), 0) AS sos_call_count
```
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> SOS 호출 이력이 전혀 없는 회원의 경우 집계 결과가 `NULL(결측치)`이 됩니다. `COALESCE` 함수는 `NULL`을 숫자 `0`으로 변환해 줍니다. 만약 이를 생략하여 데이터에 `NULL(NaN)`이 남아있으면 Scikit-learn의 `DecisionTreeClassifier`나 `KMeans` 모델이 입력 데이터 유효성 검사 단계에서 `ValueError`를 발생시키며 학습이 중단됩니다.
</details>

---

### [문제 3] 서술형 탐구
사용자 1명당 여러 개의 채팅 로그가 존재하는 1:N 관계에서 `GROUP BY u.user_id` 절을 적용하지 않고 쿼리를 실행하면 어떤 문제가 발생하는지 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> `GROUP BY` 없이 다중 테이블을 조인하면 사용자 1명에 대해 채팅 로그 수만큼 행이 복제(Cartesian Product 효과)되어 반환됩니다. 결과적으로 '사용자 1명 = 1개의 데이터 행'이라는 머신러닝 샘플 단위의 일관성이 깨지며, 데이터가 중복 왜곡되어 정확한 분석과 예측이 불가능해집니다.
</details>
