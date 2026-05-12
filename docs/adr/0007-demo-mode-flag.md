# ADR-0007: 데모 모드(is_demo) 분기 도입

- 상태: Accepted
- 작성일: 2026-03-03 (api-spec v5에서 도입)
- 의사결정자: 승구리, Gemini(설계 리뷰)
- 관련: [api-spec.md §1, §5 백로그 #9](../api-spec.md), `backend/services/question_gen.py`

---

## 맥락 (Context)

훈련 모드 채점에는 수동 확정 정답(`tests/training_golden_answers.json`)을 우선 사용한다 (ADR-0005). 그런데 일반 출제 흐름은 다음과 같다:

1. ChromaDB에서 랜덤 청크 선택 → `source_content_id` 결정
2. LLM이 그 본문 기반으로 즉석 질문 생성 → `question_id`는 `q-{source_content_id}` (UUID와 동등한 동적 식별자)
3. 채점 시 `question_id`로 골든답 매칭

문제는 (2)에서 동적 생성된 `question_id`가 골든답에 하드코딩된 ID(`q-demo-001` 등)와 **절대 매칭되지 않는다**는 점이다.

따라서 "수동 정답 기반 채점"을 데모로 보여주려면, 질문 자체를 골든답에서 꺼내야 한다.

## 검토한 대안 (Options)

- **A. 일반 출제 결과의 `question_id`를 사용자가 골든답으로 옮겨 적기**
  - 장점: 추가 코드 없음
  - 단점: ❌ 데모 직전 매번 수동 작업. 시연 안정성 낮음
- **B. 출제 시 골든답 우선 매칭 (모든 모드에서)**
  - 장점: 단순한 단일 흐름
  - 단점: 일반 모드에서도 골든답에 매칭되면 LLM 생성을 건너뛰게 됨 → "AI가 즉석 출제" 데모 시나리오 약화
- **C. `is_demo` 플래그로 분기** ✅
  - 장점: 두 데모 시나리오를 명확히 분리. 일반 모드는 LLM 즉석 출제, 데모 모드는 사전 확정
  - 단점: 클라이언트가 분기를 인지해야 함

## 결정 (Decision)

옵션 C 채택. 요청 본문에 `is_demo: boolean` 필드를 추가한다 (기본 `false`).

| `is_demo` | 출제 동작                                                                                | 채점 동작                  |
| --------- | ---------------------------------------------------------------------------------------- | -------------------------- |
| `false`   | ChromaDB에서 랜덤 청크 → LLM 즉석 질문 생성. `question_id = "q-{source_content_id}"`     | Direct Fetch (수동 정답 매칭 불가) |
| `true`    | `training_golden_answers.json`에서 직접 출제. `question_id`는 골든답 ID 그대로            | 수동 정답 기준 채점 (ADR-0005 §1) |

**구현** (`question_gen.py:select_source`):

```python
if is_demo:
    demo_ids = _get_demo_question_ids(category)
    available = [d for d in demo_ids if d not in solved_content_ids]
    if not available:
        return random.choice(demo_ids), True   # is_reset=True
    return random.choice(available), False
# 일반 모드는 ChromaDB 풀에서 추출 (생략)
```

**`is_demo: true`이면 LLM 호출하지 않는다** — 골든답의 `question` 필드를 그대로 반환.

## 결과 (Consequences)

- ✅ 데모 시나리오에서 수동 정답 기반 정확한 채점이 보장됨 (시연 안정성)
- ✅ 일반 모드는 "AI가 즉석 출제"라는 PoC 핵심 메시지를 유지
- ✅ 골든답이 비어 있어도 일반 모드는 정상 동작
- ⚠️ 데모 모드에서 카테고리 필터는 현재 무시 (`_get_demo_question_ids`는 `category` 파라미터를 사용하지 않음). 골든답이 늘어나면 카테고리 필터 도입 필요
- ⚠️ 두 모드를 섞어 호출할 경우 `solvedContentIds`에 일반 모드의 `q-{...}`와 데모 모드의 `q-demo-NNN`이 같이 들어감 — 충돌하지 않으나 UX 일관성을 위해 모드 전환 시 배열 초기화 검토
- 🔄 재검토 트리거: 골든답이 풍부해져 데모/일반 경계가 흐려지면 통합된 골든답 우선 매칭 정책으로 회귀 검토
