# 07-2. 의료 상담 기록 CSV 및 PDF 숨김 프레임 인쇄 내보내기

환자가 응급실이나 병원 진료를 받으러 갈 때 평소 AI와 나누었던 상담 내역을 의사에게 증빙 자료로 제출할 수 있도록, **UTF-8 BOM 기반 CSV 다운로드**와 **숨김 iframe 기반 무풍 PDF 인쇄 엔진**을 구현합니다.

---

## 1. 🎯 학습 목표
1. 엑셀(Excel)에서 한글 깨짐을 완벽히 방지하는 UTF-8 BOM 인코딩의 원리를 이해합니다.
2. 클라이언트 사이드 자바스크립트를 활용하여 화면 이동 없이 다운로드되는 CSV 생성기를 작성합니다.
3. 브라우저의 숨겨진 가상 프레임(`hidden iframe`)을 동적으로 생성하여 인쇄 대화상자를 호출하는 PDF 출력 기술을 습득합니다.

---

## 2. 💡 핵심 개념

### ① 엑셀 한글 깨짐 방지의 핵심: UTF-8 BOM (`\uFEFF`)
텍스트 파일 맨 앞에 바이트 순서 표식(Byte Order Mark, `0xEF 0xBB 0xBF`)을 삽입하지 않으면, 마이크로소프트 엑셀은 파일을 ANSI로 오인하여 한글이 깨져서 열립니다.

```text
[상담 데이터 추출] ──► [CSV 문자열 변환] ──► ['\uFEFF' (BOM 헤더 추가)] ──► [Blob 생성 및 다운로드]
```
② 페이지 전환 없는 깔끔한 PDF 인쇄: 가상 iframe 기법
현재 보고 있는 웹앱 화면 전체를 인쇄하면 헤더, 내비게이션 바, 배경색까지 지저분하게 함께 인쇄됩니다. 보이지 않는 빈 프레임(iframe)을 메모리에 만들고 상담 표만 채워 넣은 뒤 iframe.contentWindow.print()를 호출하면 깨끗한 의료 리포트만 인쇄할 수 있습니다.

3. 🛠️ 준비물
웹 브라우저 (Chrome, Edge 등)
브라우저 클라이언트 자바스크립트 엔진

```python
<!--
파일명: export_demo.html
기능: 상담 기록의 UTF-8 BOM CSV 내보내기 및 숨김 프레임 PDF 인쇄 실습
-->
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>스마트119 상담 기록 내보내기 실습</title>
  <style>
    body { font-family: sans-serif; padding: 20px; line-height: 1.6; }
    .btn-group { margin-bottom: 20px; }
    button { padding: 10px 16px; margin-right: 10px; cursor: pointer; border-radius: 6px; border: none; font-weight: bold; }
    .btn-csv { background: #059669; color: white; }
    .btn-pdf { background: #2563eb; color: white; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f3f4f6; }
  </style>
</head>
<body>

  <h2>📋 스마트119 의료 상담 내보내기 엔진</h2>
  <div class="btn-group">
    <button class="btn-csv" onclick="exportToCSV()">📊 CSV 파일로 저장 (Excel 호환)</button>
    <button class="btn-pdf" onclick="printToPDF()">🖨️ PDF 리포트 인쇄</button>
  </div>

  <table id="log-table">
    <thead>
      <tr>
        <th>일시</th>
        <th>환자 질문</th>
        <th>AI 의료 안내</th>
        <th>응급 여부</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>2026-10-12 14:20</td>
        <td>가슴이 쥐어짜듯이 아파요</td>
        <td>급성 심근경색 의심 징후입니다. 즉시 119에 신고하십시오.</td>
        <td>🚨 응급</td>
      </tr>
      <tr>
        <td>2026-10-12 16:05</td>
        <td>가벼운 두통이 지속되네요</td>
        <td>충분한 수분 섭취와 휴식을 취하시고 지속 시 진료를 권장합니다.</td>
        <td>일반</td>
      </tr>
    </tbody>
  </table>

  <script>
    // 샘플 데이터
    const chatLogs = [
      { created_at: "2026-10-12 14:20", message: "가슴이 쥐어짜듯이 아파요", reply: "급성 심근경색 의심 징후입니다. 즉시 119에 신고하십시오.", is_emergency: true },
      { created_at: "2026-10-12 16:05", message: "가벼운 두통이 지속되네요", reply: "충분한 수분 섭취와 휴식을 취하시고 지속 시 진료를 권장합니다.", is_emergency: false }
    ];

    // 1. 엑셀 호환 UTF-8 BOM CSV 내보내기
    function exportToCSV() {
      let csvContent = "\uFEFF"; // 한글 깨짐 방지 핵심 BOM 바이트
      csvContent += "일시,환자 증상 질문,AI 의료 상담 답변,응급 분류\n";

      chatLogs.forEach(log => {
        // 쉼표나 개행문자가 포함될 경우 따옴표로 감싸기
        const safeMsg = `"${log.message.replace(/"/g, '""')}"`;
        const safeReply = `"${log.reply.replace(/"/g, '""')}"`;
        const emergencyStr = log.is_emergency ? "긴급응급" : "일반상담";
        csvContent += `${log.created_at},${safeMsg},${safeReply},${emergencyStr}\n`;
      });

      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `smart119_consultation_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }

    // 2. 숨김 iframe을 활용한 깔끔한 PDF 인쇄
    function printToPDF() {
      const iframe = document.createElement("iframe");
      iframe.style.position = "fixed";
      iframe.style.right = "0";
      iframe.style.bottom = "0";
      iframe.style.width = "0";
      iframe.style.height = "0";
      iframe.style.border = "none";
      document.body.appendChild(iframe);

      let reportHTML = `
        <html>
        <head>
          <title>스마트119 환자 상담 기록 리포트</title>
          <style>
            body { font-family: 'Malgun Gothic', sans-serif; padding: 30px; }
            h1 { color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #333; padding: 10px; font-size: 13px; text-align: left; }
            th { background: #eee; }
            .emergency { color: red; font-weight: bold; }
          </style>
        </head>
        <body>
          <h1>스마트119 의료 상담 소견서</h1>
          <p>발행일시: ${new Date().toLocaleString()}</p>
          <table>
            <tr><th>일시</th><th>환자 호소 증상</th><th>AI 상담 및 대처 지침</th><th>상태</th></tr>
      `;

      chatLogs.forEach(l => {
        reportHTML += `
          <tr>
            <td>${l.created_at}</td>
            <td>${l.message}</td>
            <td>${l.reply}</td>
            <td class="${l.is_emergency ? 'emergency' : ''}">${l.is_emergency ? '🚨 긴급' : '일반'}</td>
          </tr>
        `;
      });

      reportHTML += `</table></body></html>`;

      iframe.contentWindow.document.open();
      iframe.contentWindow.document.write(reportHTML);
      iframe.contentWindow.document.close();

      setTimeout(() => {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
        document.body.removeChild(iframe);
      }, 500);
    }
  </script>
</body>
</html>

```
5. ✍️ 확인 문제
## [문제 1] 인코딩 분석형
자바스크립트에서 CSV 문자열의 가장 맨 첫 부분에 \uFEFF를 추가해 주는 주된 이유는 무엇일까요?

파일 용량을 압축하여 네트워크 전송 속도를 높이기 위해
마이크로소프트 엑셀(Excel) 프로그램이 UTF-8 인코딩 파일임을 자동 인식하여 한글 깨짐을 방지하기 위해
데이터베이스 해킹을 막기 위해
파일을 읽기 전용으로 보호하기 위해
<details> <summary>정답 확인하기</summary> <b>정답:</b> 2번 (Byte Order Mark를 심어주어 엑셀이 한글을 정상적인 UTF-8 텍스트로 인식하게 만듦) </details>
## [문제 2] 객관식
PDF 인쇄 시 화면의 버튼이나 복잡한 웹 레이아웃을 제외하고 오직 상담 리포트 표만 깔끔하게 출력하기 위해 사용된 기법은?

브라우저 전체 창을 캡처한 이미지 전송
메모리에 화면에 보이지 않는 iframe을 임시 생성하여 리포트 내용만 주입한 후 인쇄 명령 호출
사용자의 모바일 화면을 강제로 흑백으로 전환
파이썬 웹 서버를 강제로 재부팅
<details> <summary>정답 확인하기</summary> <b>정답:</b> 2번 (동적 숨김 iframe을 통한 격리 인쇄 기법) </details>
## [문제 3] 서술형 탐구
사용자에게 음성(TTS)으로 대화 기록을 안내하는 것과 대비하여, 병원 방문 시 의사에게 CSV나 PDF 형태로 출력된 공식 기록을 제출하는 방식이 왜 응급 진료 현장의 골든타임을 확보하는 데 더 유리한지 서술하시오.

<details> <summary>정답 확인하기</summary> <b>모범 답안:</b> 음성 안내는 실시간 청취에 시간이 소요되고 긴박한 응급실 환경에서 의료진이 일일이 듣기 어렵습니다.
반면 타임스탬프와 주요 증상이 표 형태로 일목요연하게 정리된 PDF/CSV 문서는 담당 의사가 수초 만에 환자의 발병 시각, 증상의 악화 경과, 기저 호소 사항을 시각적으로 빠르게 스캔하고 정확한 처치를 즉각 시작할 수 있어 골든타임 확보에 훨씬 유리합니다.

</details>