# ADR-0005: 훈련 채점은 Direct Fetch (RAG 재검색 금지)

- 상태: Accepted
- 작성일: 2026-03-03 (api-spec v3에서 확정)
- 의사결정자: 승구리, Gemini(설계 리뷰)
- 관련: [api-spec.md §1, §5 백로그 #1](../api-spec.md), `backend/services/scorer.py`(TODO)

---

## 맥락 (Context)

훈련 모드 채점에는 정답 텍스트가 필요하다. 정답 소스 후보:

- 수동 확정 정답 (`tests/training_golden_answers.json`) — 정확하지만 작성 비용 있음
- 출제 시점에 사용된 출처 문서

질문 생성 단계(`question_gen.py`)에서 이미 출처 `source_content_id`를 알고 있다. 채점 시 이걸 어떻게 활용할지 두 가지 접근이 있다.

## 검토한 대안 (Options)

- **A. 채점 시 RAG 재검색** (api-spec v2까지의 초안)
  - 장점: 채점 코드가 챗봇 RAG 코드를 재사용 가능
  - 단점:
    - ❌ 출제 시 사용한 문서와 **다른 문서**를 가져올 가능성 (정답 기준이 달라짐)
    - ❌ 추가 임베딩 호출 비용/지연
    - ❌ 동문서답 리스크 (질문이 의도와 다르게 해석될 수 있음)
- **B. 출처 문서 Direct Fetch** ✅
  - 장점: 출제 시 확정된 문서를 그대로 사용. 정답 기준 일관성 보장
  - 단점: 같은 문서로 채점하므로 다양성 없음 (단, 채점에는 다양성이 필요 없음)
- **C. 수동 정답 우선 + 없으면 Direct Fetch** ✅✅
  - 장점: 데모 시나리오는 수동 정답으로 정확성 보장, 일반은 Direct Fetch로 일관성 유지
  - 단점: 두 분기 관리 필요

## 결정 (Decision)

옵션 C 채택. 채점 정답 우선순위는 다음과 같이 고정한다 (api-spec §5):

```
1. tests/training_golden_answers.json 에서 question_id로 수동 정답 조회
   → 있으면 수동 정답 기준으로 LLM 채점
2. 수동 정답 없으면
   → source_content_id 로 ChromaDB에서 본문 Direct Fetch
   → LLM 에 "이 본문 기반 모범 답안 + 채점" 위임
```

> ❌ **RAG 재검색은 금지**. 출제 시점에 출처가 확정되어 있으므로 재검색은 정답 기준의 일관성을 무너뜨린다.

`question_id` ↔ `source_content_id` 매핑 규약:
- 일반 모드: `question_id = "q-" + source_content_id`
- 데모 모드: `question_id`가 곧 골든답 ID. `source_content_id`는 골든답 항목의 `source_content_id` 또는 fallback으로 `question_id`

## 결과 (Consequences)

- ✅ 출제와 채점이 동일한 출처 문서를 사용 → 채점 일관성 보장
- ✅ RAG 재검색 비용/지연 절약
- ✅ 동문서답 리스크 제거
- ⚠️ `source_content_id`가 ChromaDB에 존재하지 않으면 채점 불가 → 인제스트 정합성 모니터링 필요
- ⚠️ 일반 모드에서 LLM이 출제한 질문이 본문과 어긋나면 Direct Fetch 본문이 실제 정답과 괴리 가능 → 출제 프롬프트 품질이 중요
- 🔄 재검토 트리거: LLM 출제 품질이 낮아 채점 신뢰도 하락 시 골든답 의존도를 높이는 방향으로 정책 변경
