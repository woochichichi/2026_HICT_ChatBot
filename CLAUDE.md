# Claude Code Rules

이 프로젝트의 AI 규칙은 `RULES.md`에 정의되어 있습니다.
**반드시 `RULES.md`를 읽고 모든 규칙을 따르세요.**

## Claude 전용 추가 지침

- 코드 작성 전 반드시 `docs/api-spec.md`를 읽고 스펙을 확인할 것
- 한국어로 응답
- 설계 결정이 발생하면 `docs/api-spec.md`에 기록할 것

## 필수 참조 문서 (작업 전 확인)

- `docs/INDEX.md` — 전체 문서 인덱스
- `docs/TROUBLESHOOTING.md` — 에러 발생 시 기존 해결책 먼저 확인
- `docs/PROMPT_HISTORY.md` — 프롬프트 수정 시 이력 기록 필수
- `docs/TEST_CHECKLIST.md` — 개발 완료 후 체크리스트 검증

## 코드 주석 규칙

- 수정/생성하는 모든 소스에 맥락 설명 주석 작성
- api-spec.md 섹션 참조 명시 (예: `# api-spec.md 섹션 3: 검색 로직`)
- 다른 파일과의 연관관계 기록 (예: `# chat.py에서 이 메서드를 SSE 스트리밍에 사용`)

## 시행착오 기록 규칙

- 에러 발생 + 해결 시 `docs/TROUBLESHOOTING.md`에 기록
- 프롬프트 변경 시 `docs/PROMPT_HISTORY.md`에 버전 추가
