# 10. 백엔드 분산 데이터 전처리 및 머신러닝 파이프라인

> 클라우드 데이터베이스에 분산되어 실시간으로 누적되는 건강 측정 데이터, AI 대화 로그, 비상 SOS 호출 이력을 관계형 SQL로 통합 추출하고, 지도학습(Decision Tree)과 비지도학습(K-Means & PCA)을 결합하여 고령자 응급 예방 및 맞춤형 코호트 관리 시스템을 완성합니다.

---

## 1. 🎯 학습 목표
1. 실무 백엔드(Supabase/PostgreSQL)에 분산 저장된 다중 테이블을 SQL로 단일 머신러닝 피처 매트릭스로 결합하는 아키텍처를 이해한다.
2. 규칙 기반(Rule-based) 의사결정나무(Decision Tree) 모델을 구축하여 설명 가능한(Explainable) 응급 고위험군 조기 경보 체계를 설계할 수 있다.
3. K-Means 군집화와 PCA 차원 축소를 활용하여 사전 라벨이 없는 데이터로부터 행동 패턴 기반의 3대 고령자 돌봄 페르소나를 도출할 수 있다.
4. 전처리부터 모델 학습, 평가, 차원 축소 시각화까지 이어지는 데이터 사이언스 표준 12단계 실무 파이프라인을 습득한다.

---

## 2. 💡 핵심 개념

### ① 10단원 전체 구조 로드맵

```text
[10. 백엔드 분산 데이터 전처리 및 머신러닝 파이프라인]
   │
   ├─ [10-1] 백엔드 분산 데이터 전처리 및 SQL 결합 (LEFT JOIN & 집계)
   │         - 1:N 분산 테이블 통합, GROUP BY 집계, COALESCE 결측치 정제
   │
   ├─ [10-2] 머신러닝 지도학습 분류기 구축 (Decision Tree)
   │         - train_test_split, DecisionTreeClassifier, fit, 정확도/재현율 평가
   │
   ├─ [10-3] 비지도학습 K-Means 군집화와 PCA 차원 축소 시각화
   │         - StandardScaler, KMeans, inertia_(엘보우), fit_predict, PCA 2D 투영
   │
   └─ [10-4] [실습 랩] 고령자 건강·응급 데이터 통합 분석 파이프라인 종합 실습
             - SQLite 인메모리 DB부터 PCA 군집 시각화까지 엔드투엔드 원스톱 검증
```

---

### ② 데이터 파이프라인 12단계 체크리스트

| 대분류 | 번호 | 핵심 기술/함수 | 실무 파이프라인 내 역할 |
| :--- | :---: | :--- | :--- |
| **[과제 1]<br>SQL 데이터<br>전처리** | **①** | **`LEFT JOIN`** | 활동 로그가 없는 신규 회원 및 건강 안정군 유실 방지 |
| | **②** | **`GROUP BY`** | 1:N 로그 데이터를 '사용자 1명 = 1개 행' 요약 통계량으로 압축 |
| | **③** | **`COALESCE`** | 로그 부재로 발생하는 `NULL`을 `0`으로 치환해 Scikit-learn 에러 방지 |
| **[과제 2]<br>지도학습<br>(Decision Tree)** | **④** | **`train_test_split`** | 시험 문제 사전 유출(Data Leakage) 방지를 위한 8:2 훈련/검증 분할 |
| | **⑤** | **`DecisionTreeClassifier`** | 해석 가능한 화이트박스 트리 모델 생성 (`max_depth=3` 과적합 제어) |
| | **⑥** | **`.fit()`** | 학습용 데이터로 불순도(Gini)를 최소화하는 분기 규칙 학습 |
| | **⑦** | **`accuracy_score`** | 미학습 테스트 데이터에 대한 모델의 일반화 예측 성능 정량 검증 |
| **[과제 3]<br>비지도학습<br>(K-Means & PCA)** | **⑧** | **`StandardScaler`** | 거리 기반 알고리즘의 단위 편향(혈압 vs SOS횟수) 제거 표준화 |
| | **⑨** | **`KMeans`** | K개의 중심점(Centroid) 기반 거리 최소화 군집화 모델 초기화 |
| | **⑩** | **`inertia_`** | 군집 내 거리 제곱합(WCSS)을 계산하여 엘보우 최적 K값 수학적 도출 |
| | **⑪** | **`fit_predict`** | 사전 라벨이 없는 데이터에 최적 군집 번호(0, 1, 2) 학습 및 동시 부여 |
| | **⑫** | **`PCA`** | 6차원 이상의 고차원 피처 공간을 정보 손실을 최소화하며 2차원으로 축소 |

---

## 3. 🛠️ 준비물
- Google Colab 또는 Python 3.9+ 개발 환경 (VS Code, Jupyter Notebook)
- 필수 파이썬 데이터 과학 라이브러리:
  ```bash
  pip install pandas numpy scikit-learn matplotlib seaborn
  ```
- SQLite3 (파이썬 기본 내장 라이브러리)

---

## 4. 💻 단계별 실습 코드

다음은 10단원 전체의 처리 흐름을 한눈에 파악할 수 있는 미니 통합 데모 스크립트입니다.

```python
# 10-ml-data-pipeline.py
import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# 1. 분산 DB 연결 및 데이터 준비 (SQLite)
conn = sqlite3.connect(":memory:")
conn.executescript("""
CREATE TABLE users (user_id TEXT PRIMARY KEY, age INT);
CREATE TABLE health (user_id TEXT, bp INT, bmi REAL);
CREATE TABLE logs (user_id TEXT, is_sos INT);

INSERT INTO users VALUES ('U1', 75), ('U2', 68), ('U3', 82), ('U4', 64);
INSERT INTO health VALUES ('U1', 155, 28.2), ('U2', 120, 22.0), ('U3', 160, 29.5), ('U4', 118, 21.5);
INSERT INTO logs VALUES ('U1', 1), ('U3', 1), ('U3', 1); -- U2, U4는 SOS 로그 없음
""")

# 2. [과제 1] SQL 전처리: LEFT JOIN, GROUP BY, COALESCE 결합
query = """
SELECT 
    u.user_id, u.age, h.bp, h.bmi,
    COALESCE(SUM(l.is_sos), 0) AS sos_count
FROM users u
LEFT JOIN health h ON u.user_id = h.user_id
LEFT JOIN logs l ON u.user_id = l.user_id
GROUP BY u.user_id;
"""
df = pd.read_sql_query(query, conn)
conn.close()

print("=== [1] SQL 전처리 완료 데이터 ===")
print(df)

# 3. [과제 2] 지도학습: 의사결정나무 모델 학습
X = df[['age', 'bp', 'bmi', 'sos_count']]
y = (df['bp'] >= 140).astype(int)  # 타깃 라벨 생성 (고혈압 고위험군: 1)

dt = DecisionTreeClassifier(max_depth=2, random_state=42)
dt.fit(X, y)
print("\n=== [2] 지도학습 훈련 완료 (Feature 중요도) ===")
for col, imp in zip(X.columns, dt.feature_importances_):
    print(f"- {col}: {imp:.2f}")

# 4. [과제 3] 비지도학습: 표준화 -> 군집화 -> PCA 차원 축소
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
df['cluster'] = kmeans.fit_predict(X_scaled)

pca = PCA(n_components=2)
coords = pca.fit_transform(X_scaled)
df['pc1'] = coords[:, 0]
df['pc2'] = coords[:, 1]

print("\n=== [3] 비지도학습 군집 및 PCA 좌표 결과 ===")
print(df[['user_id', 'cluster', 'pc1', 'pc2']])
```

### 실행 결과 예시
```text
=== [1] SQL 전처리 완료 데이터 ===
  user_id  age   bp   bmi  sos_count
0      U1   75  155  28.2          1
1      U2   68  120  22.0          0
2      U3   82  160  29.5          2
3      U4   64  118  21.5          0

=== [2] 지도학습 훈련 완료 (Feature 중요도) ===
- age: 0.00
- bp: 1.00
- bmi: 0.00
- sos_count: 0.00

=== [3] 비지도학습 군집 및 PCA 좌표 결과 ===
  user_id  cluster       pc1       pc2
0      U1        1  1.268713 -0.210452
1      U2        0 -1.412852 -0.320491
2      U3        1  2.125430  0.150218
3      U4        0 -1.981291  0.380725
```

---

## 5. ✅ 확인 문제

### [문제 1] 개념 확인
전체 데이터 과학 파이프라인에서 '지도학습(Supervised Learning)'과 '비지도학습(Unsupervised Learning)'을 상호 보완적으로 함께 활용할 때 얻을 수 있는 시너지 효과를 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> 지도학습(Decision Tree)은 사전에 정의된 '응급 발생 여부'나 '고위험군 라벨'을 신속하고 정확하게 판별하는 데 탁월하며, 비지도학습(K-Means & PCA)은 미처 관리자가 정의하지 못한 새로운 행동 이상치 집단이나 환자의 복합적 건강 페르소나(코호트)를 스스로 발견해 냅니다. 이 둘을 결합하면 기지의 위험 대처와 미지의 위험 탐지를 동시에 수행할 수 있습니다.
</details>

---

### [문제 2] 아키텍처 이해
백엔드 데이터베이스 서버 안에서 SQL로 전처리 및 집계(Aggregation)를 미리 수행한 뒤 머신러닝 엔진으로 데이터를 전달하는 방식이, 대용량 원시 로그 전체를 머신러닝 서버 메모리로 직접 가져와 판다스로 처리하는 것보다 우수한 이유를 설명하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> 네트워크 대역폭 절약과 메모리 효율성 때문입니다. 분산 DB 내에서 인덱스를 활용해 집계 후 압축된 요약 행만 전송하면 머신러닝 서버의 OOM(Out of Memory) 병목을 방지할 수 있고, 데이터 전송 지연 시간(Latency)을 획기적으로 줄일 수 있습니다.
</details>

---

### [문제 3] 서술형 탐구
머신러닝 파이프라인에서 수치 데이터의 분포 스케일(Scale)을 정규화하는 `StandardScaler`가 트리 기반 모델(Decision Tree)과 거리 기반 모델(K-Means)에 미치는 영향의 차이를 비교하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> 의사결정나무(Decision Tree)는 각 특성별로 대소 비교 분기(Threshold Split)를 진행하므로 스케일 변환의 영향을 거의 받지 않습니다. 반면 K-Means는 유클리디안 거리를 계산하므로 스케일이 큰 피처가 군집 형성을 일방적으로 왜곡합니다. 따라서 K-Means에서는 스케일링이 필수적인 전제 조건입니다.
</details>
