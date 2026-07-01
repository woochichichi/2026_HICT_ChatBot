/**
 * 응대 모드 예시 칩 — 사전 제작 답변(LLM 미사용).
 *
 * 목적: 시연 안정성(일일 한도·지연 무관) + 즉시 표시. 답변/출처는 실제 업무편람
 * ChromaDB 상위 검색 결과(로컬 bge-m3, 2026-06-20)에 근거. source url은 실제 위키 URL.
 * 답변은 가독성을 위해 마크다운(개행/번호목록/불릿/**볼드**) 사용 — ChatScreen Markdown 렌더.
 * 키 = ChatScreen SUGGESTIONS 칩 문구.
 *
 * 연관: components/chat/ChatScreen.jsx (CANNED_ANSWERS 사용)
 */
export const CANNED_ANSWERS = {
  "비대면 계좌개설은 어떻게 진행되나요?": {
    confidence: "high",
    answer:
      "비대면 계좌개설은 다음 순서로 진행됩니다 [1].\n\n" +
      "1. 모바일 앱에서 **신분증 촬영·본인확인**\n" +
      "2. 본인 명의 **기존 계좌 → 신규 계좌로 지정 금액 이체** (실명확인)\n" +
      "3. **개설 완료**\n\n" +
      "**참고**\n" +
      "- 계좌이체가 어려우면 **영업점 내점**으로 실명확인할 수 있습니다.\n" +
      "- 개설 직후 ‘실명미확인 계좌’로 조회될 수 있으나, 이체 실명확인이 끝나면 정상 처리됩니다.",
    sources: [
      {
        title: "자주하는 질문(서비스) — 비대면 계좌개설/실명확인",
        url: "https://wiki.hanwhawm.com/pages/viewpage.action?pageId=23069606",
        relevance_score: 0.74,
      },
    ],
  },
  "해외주식은 어떻게 거래하나요?": {
    confidence: "high",
    answer:
      "해외 거래소(미국·홍콩·중국·일본 등) 상장 주식을 매매하려면, 먼저 종합계좌에 **‘해외주식거래신청’ 서비스**를 등록해야 합니다 [1].\n\n" +
      "- **거래 범위**: 등록된 계좌에서 국내주식·해외주식 **모두 거래 가능**\n" +
      "- **수수료·세금**: 거래소와 채널(온라인/오프라인)에 따라 다르며 **당사 수수료 규정** 적용",
    sources: [
      {
        title: "(1) 해외주식 매매 개요 및 제도",
        url: "https://wiki.hanwhawm.com/pages/viewpage.action?pageId=23071334",
        relevance_score: 0.69,
      },
    ],
  },
  "고객번호는 어떻게 부여되나요?": {
    confidence: "medium",
    answer:
      "고객번호는 **실명번호(주민등록번호 등) 1개당 유일하게** 부여됩니다 [1].\n\n" +
      "- 보유 계좌 수와 **무관** — 여러 계좌를 보유해도 고객번호는 **하나**로 관리됩니다.",
    sources: [
      {
        title: "고객번호 부여 기준 — 실명번호당 유일 부여",
        url: "https://wiki.hanwhawm.com/pages/viewpage.action?pageId=23069748",
        relevance_score: 0.66,
      },
    ],
  },
  "ELW는 어떻게 거래 신청하나요?": {
    confidence: "medium",
    answer:
      "ELW(주식워런트증권) 거래는 **ELW 거래신청** 절차를 완료해야 이용할 수 있습니다 [1].\n\n" +
      "- **매매·결제 방식**: 일반 ELW와 **동일**하게 처리\n" +
      "- 신청 화면·자격 요건은 **ELW 매매제도 안내**를 따릅니다.",
    sources: [
      {
        title: "2) ELW거래신청",
        url: "https://wiki.hanwhawm.com/pages/viewpage.action?pageId=23071094",
        relevance_score: 0.76,
      },
    ],
  },
};
