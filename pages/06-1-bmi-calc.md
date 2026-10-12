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