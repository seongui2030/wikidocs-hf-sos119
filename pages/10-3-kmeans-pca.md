
> 정답 라벨(y)이 사전에 주어지지 않은 상태에서 고령자 건강·응급 행동 패턴 데이터를 스스로 탐색하여 유사한 특성을 가진 위험군 집단(코호트)으로 자동 그룹화하고, 고차원 데이터를 2차원 평면으로 압축해 시각화하는 비지도학습 파이프라인을 구축합니다.

---

## 1. 🎯 학습 목표
1. 비지도학습(Unsupervised Learning)의 원리와 K-Means 거리 기반 군집화 메커니즘을 이해한다.
2. 단위가 서로 다른 피처의 편향을 제거하기 위해 `StandardScaler`를 필수로 적용해야 하는 이유를 설명할 수 있다.
3. `inertia_` 값을 활용한 엘보우 기법(Elbow Method)으로 최적의 군집 수(K)를 객관적으로 탐색할 수 있다.
4. `fit_predict`를 통해 각 데이터 샘플에 군집 번호를 부여하고, 집단별 통계 특성을 기반으로 도메인 페르소나를 사후 해석할 수 있다.
5. 고차원(6차원) 데이터를 정보 손실을 최소화하며 2차원 평면으로 투영하는 `PCA` 차원 축소의 필요성을 이해한다.

---

## 2. 💡 핵심 개념

### ① K-Means & PCA 파이프라인 5단계 (⑧ ~ ⑫) 진행 순서의 필연성

K-Means는 유클리디안 거리를 계산하는 비지도학습 알고리즘이므로, 반드시 데이터 과학 표준 절차에 맞춰 순차적으로 수행해야 합니다.

```text
[입력 데이터: 나이, BMI, 혈압, 대화수, 위험단어, SOS호출] (6차원)
                       │
  [⑧ StandardScaler]  수축기혈압(150)이 SOS횟수(1)를 지배하지 못하도록 표준화(Z-score)
                       │
  [⑨ KMeans 모델 정의] 중심점(Centroid) 기반 반복 최적화 알고리즘 초기화
                       │
  [⑩ inertia_ 확인]    군집 내 제곱합 오차(WCSS)를 계산해 최적 군집수 K=3 도출(엘보우)
                       │
  [⑪ fit_predict]     각 사용자를 가장 가까운 중심점 군집(0, 1, 2)에 배정
                       │
  [⑫ PCA 차원 축소]   사람 눈으로 식별 불가능한 6차원 공간을 2차원 좌표(PC1, PC2)로 압축 시각화
```

| 순서 | 핵심 함수 / 속성 | 필수 이유 및 데이터 과학 실무 근거 |
| :---: | :--- | :--- |
| **⑧** | **`StandardScaler`** | K-Means는 모든 특성을 유클리디안 거리 \(\sqrt{\sum (x_i - y_i)^2}\)로 측정합니다. 단위가 큰 혈압(120~180)이 단위가 작은 SOS 횟수(0~3)를 완전히 압도하는 스케일 왜곡을 방지하기 위해 평균 0, 표준편차 1로 표준화합니다. |
| **⑨** | **`KMeans`** | K개의 중심점(Centroid)을 무작위로 배치한 후 "가까운 데이터 배정 \(\to\) 중심점 재계산"을 수렴할 때까지 반복하는 대표적 거리 기반 군집화 알고리즘입니다. |
| **⑩** | **`inertia_`** | 각 데이터 포인트와 해당 군집 중심 간 거리의 제곱합(WCSS)입니다. K를 1부터 늘려가며 `inertia_`가 꺾이는 팔꿈치(Elbow) 지점을 찾아 최적의 K를 수학적으로 결정합니다. |
| **⑪** | **`fit_predict`** | 비지도학습에서는 라벨(y)이 없으므로, 학습(fit)과 동시에 각 샘플의 소속 군집 번호(0, 1, 2)를 예측·부여(predict)하여 데이터프레임에 파생 변수로 추가합니다. |
| **⑫** | **`PCA`** | 6개 피처로 구성된 6차원 공간은 모니터나 종이에 그릴 수 없습니다. 주성분 분석(PCA)으로 데이터의 분산(정보량)을 가장 잘 보존하는 2개의 축(PC1, PC2)으로 차원을 압축해 2차원 산점도로 시각화합니다. |

---

### ② 3개의 군집은 어떻게 해석해야 하는가? (사후 해석 방법론)

> ⚠️ **주의:** 알고리즘이 출력하는 군집 번호 `0, 1, 2`는 단순한 임의의 숫자일 뿐입니다. 데이터 과학자는 군집별 **피처 평균값(Mean Profiles)**을 산출하여 실제 임상적·도메인적 특성에 맞춰 이름을 부여해야 합니다.

| 군집 | 특징 지표 요약 | 도메인 페르소나 명칭 | 케어 행동 가이드 |
| :---: | :--- | :---: | :--- |
| **군집 A** | SOS 호출 및 위험 대화 최다, 초고령(80세 이상) | **🚨 응급 집중 모니터링군** | 119 구급대 및 보호자 핫라인 상시 연결, 24시간 이상 비활동 시 안부 전화 |
| **군집 B** | BMI 과체중/비만, 수축기 혈압 145 이상 고혈압, SOS는 적음 | **⚠️ 만성질환·대사 주의군** | 복약 알림 서비스 제공, 매일 혈압/체중 기록 유도, 식습관 AI 코칭 |
| **군집 C** | 혈압 정상(120 전후), 상담/SOS 이력 거의 없음 | **🟢 건강 자립 안정군** | 주 1회 정기 치매 예방 퀴즈 및 가벼운 일상 말벗 서비스 제공 |

---

## 3. 🛠️ 준비물
- Python 3.9 이상 환경 (Google Colab 또는 VS Code)
- `numpy`, `pandas`
- `scikit-learn` (`StandardScaler`, `KMeans`, `PCA`)
- `matplotlib`, `seaborn` (군집 시각화용)

---

## 4. 💻 단계별 실습 코드

다음은 6차원 피처 데이터를 표준화하고, 엘보우 기법으로 최적 군집(K=3)을 찾아 군집화한 뒤, PCA로 2차원 평면에 산점도를 그리는 완성형 코드입니다.

```python
# 10-3-kmeans-pca.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# 1. 100명의 고령자 6개 다차원 피처 시뮬레이션 데이터 준비
np.random.seed(42)
n_samples = 100

df_features = pd.DataFrame({
    'age': np.random.randint(65, 88, n_samples),
    'is_male': np.random.choice([0, 1], n_samples),
    'bmi': np.round(np.random.normal(25.0, 4.0, n_samples), 1),
    'systolic_bp': np.random.randint(110, 175, n_samples),
    'risk_chat_count': np.random.poisson(1.0, n_samples),
    'sos_call_count': np.random.poisson(0.5, n_samples)
})

print("=== 원본 피처 데이터 (상위 5건) ===")
print(df_features.head())

# 2. [⑧ StandardScaler] 거리 기반 알고리즘을 위한 표준화
scaler = StandardScaler()
X_scaled = scaler.fit_transform(df_features)

# 3. [⑩ inertia_] 엘보우 기법(Elbow Method)으로 최적의 K 탐색
inertias = []
k_range = range(1, 8)
for k in k_range:
    # [⑨ KMeans] 모델 생성 및 적합
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X_scaled)
    inertias.append(km.inertia_)

print("\n=== K값에 따른 군집 내 제곱합 오차 (Inertia) ===")
for k, val in zip(k_range, inertias):
    print(f"K={k}: {val:.2f}")

# 4. [⑨ & ⑪ KMeans & fit_predict] 최적 군집 수 K=3으로 최종 학습 및 라벨링
optimal_k = 3
kmeans_final = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
cluster_labels = kmeans_final.fit_predict(X_scaled)

# 원본 데이터프레임에 군집 결과 부여
df_features['cluster'] = cluster_labels

# 5. [사후 해석] 군집별 평균 프로파일 산출
cluster_profile = df_features.groupby('cluster').mean()
print("\n=== [과제 3] 군집별 평균 특성 (페르소나 해석용) ===")
print(cluster_profile[['age', 'bmi', 'systolic_bp', 'risk_chat_count', 'sos_call_count']].round(2))

# 6. [⑫ PCA] 6차원 -> 2차원 축소 투영
pca = PCA(n_components=2, random_state=42)
pca_transformed = pca.fit_transform(X_scaled)

df_features['pca1'] = pca_transformed[:, 0]
df_features['pca2'] = pca_transformed[:, 1]

explained_variance = np.sum(pca.explained_variance_ratio_) * 100
print(f"\nPCA 2개 축이 보존한 전체 정보량(설명 분산비): {explained_variance:.1f}%")

# 7. 2차원 평면 군집 산점도 시각화
plt.figure(figsize=(9, 6))
sns.scatterplot(
    data=df_features, 
    x='pca1', 
    y='pca2', 
    hue='cluster', 
    palette='Set1', 
    s=90, 
    style='cluster',
    alpha=0.9
)
plt.title(f"SOS 고령자 코호트 K-Means 군집 분석 (K=3, PCA 2D)", fontsize=14, fontweight='bold')
plt.xlabel("주성분 1 (PC1: 전반적 건강위험/이상 징후 축)", fontsize=11)
plt.ylabel("주성분 2 (PC2: 혈압/체격 대사 지표 축)", fontsize=11)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend(title='군집 번호', loc='best')
plt.tight_layout()
plt.show()
```

### 실행 결과 예시
```text
=== K값에 따른 군집 내 제곱합 오차 (Inertia) ===
K=1: 600.00
K=2: 489.12
K=3: 412.35  <-- 기울기가 완만해지는 엘보우 지점
K=4: 368.40
K=5: 331.20

=== [과제 3] 군집별 평균 특성 (페르소나 해석용) ===
          age    bmi  systolic_bp  risk_chat_count  sos_call_count
cluster                                                          
0       72.15  23.80       124.50             0.42            0.05  --> 🟢 안정 자립군
1       82.40  25.10       158.20             2.15            1.40  --> 🚨 응급 집중군
2       74.80  28.90       152.10             0.75            0.20  --> ⚠️ 만성 대사주의군

PCA 2개 축이 보존한 전체 정보량(설명 분산비): 46.8%
```

---

## 5. ✅ 확인 문제

### [문제 1] 개념 확인
K-Means 알고리즘 적용 전 `StandardScaler`를 적용하지 않으면, '수축기 혈압(110~180)'과 'SOS 호출 횟수(0~3)' 중 어떤 변수가 군집 형성에 부당하게 더 큰 영향을 미치게 되는지 이유와 함께 설명하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> <b>수축기 혈압</b>입니다. K-Means는 유클리디안 거리를 기반으로 작동하므로, 수치의 절댓값 범위와 분산이 훨씬 큰 수축기 혈압 간의 차이 제곱값\((150-120)^2 = 900\)이 SOS 호출 횟수 간의 차이 제곱값\((2-0)^2 = 4\)을 압도하게 됩니다. 따라서 스케일링을 하지 않으면 생명과 직결된 중요한 SOS 피처가 무시되는 왜곡이 발생합니다.
</details>

---

### [문제 2] 코드 이해
아래 코드에서 `inertia_`가 의미하는 수학적 개념과, 이를 활용하여 최적의 군집 수 K를 결정하는 기법의 이름을 쓰시오.
```python
inertias.append(km.inertia_)
```
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> `inertia_`는 각 데이터 포인트와 해당 포인트가 속한 <b>군집 중심점(Centroid) 사이의 거리 제곱합(WCSS, Within-Cluster Sum of Squares)</b>입니다. K값이 증가할수록 이 값은 점차 감소하는데, 감소 폭이 급격히 줄어들며 완만해지는 꺾임점을 찾는 기법을 <b>엘보우 기법(Elbow Method)</b>이라고 합니다.
</details>

---

### [문제 3] 서술형 탐구
K-Means 군집 분석이 끝난 후 모델이 반환하는 라벨(0, 1, 2) 자체로는 비즈니스 가치가 없습니다. 이 군집 결과를 실제 서비스(예: 독거노인 돌봄 케어 정책)에 적용하기 위해 데이터 과학자가 수행해야 하는 후속 절차를 서술하시오.
<details>
<summary>정답 확인하기</summary>
<b>모범 답안:</b> 각 군집별로 원본 피처들의 <b>평균값, 중위수, 최빈값 등 기술 통계량(Summary Profile)을 산출</b>해야 합니다. 이를 바탕으로 '어떤 군집이 응급 위험 대화와 SOS 호출이 많은지', '어떤 군집이 혈압/BMI 관리가 시급한지' 비교 분석하여 도메인 의미를 부여(페르소나 명명)하고, 각 그룹별 맞춤형 케어 정책(알림 발송, 복약 지도, 구급대 연계)을 수립하는 사후 해석을 거쳐야 합니다.
</details>
