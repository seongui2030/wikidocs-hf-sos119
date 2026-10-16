
> SQL로 결합한 고령자 건강 지표와 비상 호출 이력을 바탕으로, 즉각적인 응급 개입이 필요한 고위험군 사용자를 사전에 자동 판별하는 의사결정나무(Decision Tree) 지도학습 파이프라인을 구축합니다.

---

## 1. 🎯 학습 목표
1. 머신러닝 지도학습(Supervised Learning)의 피처(X)와 정답 라벨(y) 분리 원리를 이해한다.
2. `train_test_split`을 이용해 훈련용 데이터와 검증용 평가 데이터를 공정하게 분할할 수 있다.
3. `DecisionTreeClassifier` 모델을 학습(`fit`)시키고, 과적합(Overfitting)을 방지하기 위한 `max_depth` 하이퍼파라미터의 역할을 설명할 수 있다.
4. `accuracy_score` 및 분류 리포트를 통해 모델의 예측 정확도를 정량적으로 측정할 수 있다.

---

## 2. 💡 핵심 개념

### ① 지도학습 4단계 표준 파이프라인 (④ ~ ⑦)

머신러닝 지도학습 분류기는 데이터 준비부터 평가까지 엄격한 순서로 진행됩니다.

```text
[전처리 데이터 df_ml]
         │
   ① 피처/타깃 분리 (X: 나이/혈압/채팅수/SOS이력, y: 고위험군 여부)
         │
   ② [④ train_test_split] ──> Train Set (80%) + Test Set (20%)
         │
   ③ [⑤ DecisionTreeClassifier] ──> 모델 객체 생성 (max_depth=3)
         │
   ④ [⑥ .fit(X_train, y_train)] ──> 의사결정 규칙 자동 학습
         │
   ⑤ .predict(X_test) ──> 테스트 데이터 예측 수행
         │
   ⑥ [⑦ accuracy_score] ──> 예측값 vs 실제값 비교 평가
```

---

### ② 핵심 함수 및 매개변수 역할

| 단계 | 함수 / 문법 | 실무적 역할 및 필수 이유 |
| :---: | :--- | :--- |
| **④** | **`train_test_split`** | 모델이 학습 중에 시험 문제를 미리 외워버리는 데이터 누수(Data Leakage)를 막기 위해 데이터셋을 학습용과 테스트용으로 완전 분리합니다. |
| **⑤** | **`DecisionTreeClassifier`** | "만약 수축기 혈압 > 140 이고 위험 대화 > 1건이면 위험"과 같은 스무고개 형태의 논리 규칙을 만드는 화이트박스(White-box) 분류 모델입니다. |
| - | **`max_depth`** | 트리의 최대 깊이를 제한하여 노이즈까지 암기하는 **과적합(Overfitting)**을 억제합니다. |
| **⑥** | **`.fit()`** | 훈련용 데이터(X_train)와 정답 라벨(y_train)을 바탕으로 불순도(Gini/Entropy)를 최소화하는 분기 규칙을 최적화합니다. |
| **⑦** | **`accuracy_score`** | 모델이 보지 못했던 테스트 데이터(X_test)에 대한 예측값과 실제 정답(y_test)의 일치율을 0.0 ~ 1.0(또는 %) 단위로 평가합니다. |

---

## 3. 🛠️ 준비물
- Python 3.9 이상 환경 (Google Colab 또는 VS Code)
- `pandas`, `numpy`
- `scikit-learn` 라이브러리 (`pip install scikit-learn`)
- `matplotlib` (트리 시각화용, 선택)

---

## 4. 💻 단계별 실습 코드

다음은 10-1절에서 정제한 데이터를 기반으로 고위험군 판별 모델을 훈련하고 평가하는 완성형 파이썬 스크립트입니다.

```python
# 10-2-decision-tree.py
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, classification_report

# 1. 시뮬레이션 데이터셋 생성 (10-1 전처리 파이프라인 확장: 100명 사용자)
np.random.seed(42)
n_samples = 100

ages = np.random.randint(60, 90, n_samples)
is_male = np.random.choice([0, 1], n_samples)
bmi = np.round(np.random.normal(24.5, 3.5, n_samples), 1)
systolic_bp = np.random.randint(110, 175, n_samples)
risk_chat_count = np.random.poisson(0.8, n_samples)
sos_call_count = np.random.poisson(0.4, n_samples)

# 실제 응급 고위험군 라벨 (1: 고위험군, 0: 일반/안정군)
# 비즈니스 규칙 모의: (수축기혈압 >= 150 이거나 SOS 호출 >= 2) 혹은 (위험대화 >= 2 이고 혈압 >= 140)
is_high_risk = (
    ((systolic_bp >= 150) | (sos_call_count >= 2)) | 
    ((risk_chat_count >= 2) & (systolic_bp >= 140))
).astype(int)

df = pd.DataFrame({
    'age': ages,
    'is_male': is_male,
    'bmi': bmi,
    'systolic_bp': systolic_bp,
    'risk_chat_count': risk_chat_count,
    'sos_call_count': sos_call_count,
    'is_high_risk': is_high_risk
})

# 2. 독립변수(X: 피처 매트릭스)와 종속변수(y: 타깃 라벨) 분리
feature_cols = ['age', 'is_male', 'bmi', 'systolic_bp', 'risk_chat_count', 'sos_call_count']
X = df[feature_cols]
y = df['is_high_risk']

# 3. [④ train_test_split] 데이터셋 분할 (8:2 비율, 재현성을 위해 random_state 고정)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"학습용 데이터 수: {X_train.shape[0]}명 | 테스트용 데이터 수: {X_test.shape[0]}명")

# 4. [⑤ DecisionTreeClassifier] 모델 생성 (과적합 방지를 위해 max_depth=3 제한)
dt_model = DecisionTreeClassifier(max_depth=3, random_state=42)

# 5. [⑥ fit] 학습용 데이터셋으로 의사결정 규칙 학습
dt_model.fit(X_train, y_train)

# 6. 테스트 데이터셋 예측
y_pred = dt_model.predict(X_test)

# 7. [⑦ accuracy_score] 정확도 및 평가 지표 출력
acc = accuracy_score(y_test, y_pred)
print(f"\n=== [과제 2] 모델 테스트 정확도: {acc * 100:.1f}% ===")
print("\n--- 세부 분류 리포트 ---")
print(classification_report(y_test, y_pred, target_names=['일반군(0)', '고위험군(1)']))

# 8. 학습된 의사결정나무 텍스트 규칙 시각화
print("--- 학습된 의사결정 규칙 (Tree Logic) ---")
print(export_text(dt_model, feature_names=feature_cols))
```

### 실행 결과 예시
```text
학습용 데이터 수: 80명 | 테스트용 데이터 수: 20명

=== [과제 2] 모델 테스트 정확도: 95.0% ===

--- 세부 분류 리포트 ---
              precision    recall  f1-score   support

      일반군(0)       0.93      1.00      0.97        14
     고위험군(1)       1.00      0.83      0.91         6

    accuracy                           0.95        20
   macro avg       0.97      0.92      0.94        20
weighted avg       0.95      0.95      0.95        20

--- 학습된 의사결정 규칙 (Tree Logic) ---
|--- systolic_bp <= 149.50
|   |--- sos_call_count <= 1.50
|   |   |--- risk_chat_count <= 1.50
|   |   |   |--- class: 0
|   |   |--- risk_chat_count >  1.50
|   |   |   |--- class: 1
|   |--- sos_call_count >  1.50
|   |   |--- class: 1
|--- systolic_bp >  149.50
|   |--- class: 1
```

---

## 5. ✅ 확인 문제

### [문제 1] 개념 확인
전체 데이터를 훈련 데이터셋(Train)과 테스트 데이터셋(Test)으로 분할하지 않고 전체 데이터로 학습과 평가를 동시에 진행했을 때 발생하는 치명적인 머신러닝 문제는 무엇인가요?
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> <b>과적합(Overfitting)과 평가 신뢰도 상실</b>입니다. 모델이 학습용 데이터를 단순 암기하여 훈련 데이터에 대한 정확도는 100%에 달하지만, 실제 운영 환경에서 새로 인입되는 환자 데이터에 대해서는 올바른 예측을 하지 못하는 일반화 성능 저하 문제가 발생합니다.
</details>

---

### [문제 2] 코드 이해
`DecisionTreeClassifier(max_depth=3)`에서 `max_depth` 옵션을 설정하지 않고 `None`으로 두었을 때 트리가 깊어지면서 생기는 부작용을 설명하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> `max_depth`를 제한하지 않으면 리프 노드의 불순도가 0이 될 때까지 무한정 가지를 뻗어 나가게 됩니다. 이로 인해 극단적인 예외 케이스나 이상치(Outlier) 잡음까지 규칙으로 학습하여 모델이 복잡해지고, 테스트 데이터에 대한 예측 오차가 급격히 증가하게 됩니다.
</details>

---

### [문제 3] 서술형 탐구
의료·응급 관리 서비스에서 고위험군(1) 환자를 일반군(0)으로 잘못 예측하는 경우(False Negative, 미탐)의 위험성을 고려할 때, 단순 `Accuracy(정확도)` 외에 추가로 확인해야 하는 핵심 평가 지표는 무엇인지 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> <b>재현율(Recall, 민감도)</b>입니다. 재현율은 실제 고위험군 환자 전체 중에서 모델이 위험하다고 올바르게 찾아낸 비율을 뜻합니다. 응급 의료 도메인에서는 위험한 환자를 한 명이라도 놓치면 골든타임을 넘겨 인명 사고로 이어질 수 있으므로, 재현율을 최우선 지표로 모니터링해야 합니다.
</details>