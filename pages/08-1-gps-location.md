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