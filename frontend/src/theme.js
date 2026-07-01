/**
 * 한화투자증권 AI 상담 어시스턴트 — 디자인 토큰(테마) 중앙화.
 *
 * 목적: 상담사 대면용 전문적 화면 + 한화 브랜딩을 위해 색/간격을 한 곳에서 관리.
 * 기존 화면들의 흩어진 inline 색상값(파랑 #2563eb 등)을 이 토큰으로 통일.
 *
 * 연관:
 *   - App.jsx — 헤더/탭 브랜딩
 *   - components/chat/ChatScreen.jsx — 버튼·뱃지·말풍선
 *   - components/training/TrainingScreen.jsx — 채점 카드
 *   - components/review/ReviewScreen.jsx — 제보 검토
 * 참고: docs/presentation/make_ppt.py 디자인 토큰과 색 계열 정렬(한화 오렌지).
 */

// 한화 브랜드 컬러 — 공식 로고 오렌지 계열(#F37321). 주 강조색.
export const COLORS = {
  // 브랜드
  orange: "#F37321", // 한화 오렌지 — 주 강조(버튼/포인트/선택)
  orangeDark: "#D85C12", // hover/press
  orangeSoft: "#FFF3EC", // 오렌지 연한 배경(카드/뱃지)
  navy: "#13294B", // 한화 네이비 — 헤더/제목 텍스트
  navySoft: "#1E3A5F",

  // 중립
  ink: "#1E293B", // 본문 텍스트
  gray: "#64748B", // 보조 텍스트
  grayLight: "#94A3B8", // 흐린 텍스트(메타)
  line: "#E2E8F0", // 경계선
  bg: "#F5F6F8", // 페이지 배경
  surface: "#FFFFFF", // 카드 표면
  surfaceMuted: "#F8FAFC", // 약한 카드 배경

  // 상태
  good: "#15803D",
  goodBg: "#F0FDF4",
  bad: "#B91C1C",
  badBg: "#FEF2F2",
  warn: "#CA8A04",
  warnBg: "#FEFCE8",
  white: "#FFFFFF",
};

// confidence 뱃지(high/medium/low) — ChatScreen에서 사용.
export const CONFIDENCE_STYLE = {
  high: { label: "높음", color: COLORS.good, bg: COLORS.goodBg },
  medium: { label: "보통", color: COLORS.warn, bg: COLORS.warnBg },
  low: { label: "낮음", color: COLORS.bad, bg: COLORS.badBg },
};

// 공통 모양 토큰
export const RADIUS = { sm: 6, md: 8, lg: 12 };
export const SHADOW = {
  card: "0 1px 3px rgba(0,0,0,0.08)",
  pop: "0 8px 24px rgba(15,23,42,0.18)",
};

// 제품 명칭(한 곳에서 관리 — 헤더/문서 일관성)
export const PRODUCT_NAME = "한화투자증권 AI 상담 어시스턴트";
