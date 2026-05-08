# ADR-0004: SSE 스트리밍 + sources 선전송

- 상태: Accepted
- 작성일: 2026-03-03 (api-spec v3, v4에서 확정)
- 의사결정자: 우치
- 관련: [api-spec.md §1 백로그 #8](../api-spec.md), `backend/routers/chat.py`

---

## 맥락 (Context)

챗봇 모드의 응답 시간 목표는 "첫 토큰 1초 이내, 전체 5초 이내"이다 (api-spec §1).

LLM이 답변 전체를 생성한 뒤 출처(sources)와 함께 한 번에 응답하면 사용자는 5초간 빈 화면을 본다.
RAG 검색이 완료되는 시점에 출처와 confidence는 이미 확정되어 있다 — LLM 생성을 기다릴 필요가 없다.

## 검토한 대안 (Options)

- **A. 동기 JSON 응답 (생성 완료 후 한 번에)**
  - 장점: 단순. 프론트 처리 쉬움
  - 단점: 사용자 체감 대기 시간이 모델 생성 시간 전체에 비례. 첫 토큰 1초 목표 미달
- **B. SSE 스트리밍 (sources를 마지막 또는 token에 섞어 전송)**
  - 장점: 답변 토큰을 점진 표시 가능
  - 단점: 출처를 미리 보여주지 못함. 답변 끝나야 출처 확인
- **C. SSE 스트리밍 + sources 선전송** ✅
  - 장점: RAG 검색 직후 출처 즉시 렌더, 답변은 점진 렌더 → 체감 대기 시간 최소화
  - 단점: 클라이언트 구현이 다소 복잡 (이벤트 타입 분기)

## 결정 (Decision)

옵션 C 채택. SSE 이벤트 시퀀스는 다음과 같이 고정한다 (api-spec §1):

```
event: sources       ← RAG 검색 완료 직후. confidence 포함
data: {"sources":[...],"confidence":"high"}

event: token         ← LLM 생성마다 (반복)
data: {"text":"..."}

event: token
data: {"text":"..."}

...

event: done          ← 종료 신호
data: {}
```

**규칙:**

1. `sources`는 항상 첫 이벤트로 전송한다 (LLM 생성 시작 전).
2. 토큰은 `event: token`으로만 전송한다 (`message` 기본 이벤트 사용 금지 — 클라이언트 분기 단순화).
3. 종료는 반드시 `event: done`으로 명시한다 (HTTP close 만으로 종료 판단 금지).

프론트는 `sources` 이벤트 수신 즉시 출처 카드를 렌더하고, 이후 `token`을 누적하여 답변 영역에 점진 표시한다.

## 결과 (Consequences)

- ✅ 첫 토큰 1초 이내 목표 달성에 필수 (출처가 곧 첫 응답 신호)
- ✅ 사용자 신뢰성 향상 — "어떤 문서를 참고하는지"가 답변보다 먼저 보임
- ✅ confidence가 `low`이면 답변 진행 전 사용자가 인지 가능
- ⚠️ 클라이언트가 SSE 분기 처리 필수. WebSocket 등으로 마이그레이션 시 호환성 재검토
- ⚠️ Multi-turn 도입 시 세션 단위로 SSE 채널을 유지할지, 매 턴 재연결할지 별도 결정 필요 (실도입 T1)
- 🔄 재검토 트리거: ChatGPT-style "stop generation" 기능 도입 시 양방향 채널(WebSocket) 검토
