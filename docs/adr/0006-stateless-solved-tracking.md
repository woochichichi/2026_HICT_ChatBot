# ADR-0006: solved_content_ids 클라이언트 상태 관리 (Stateless 서버)

- 상태: Accepted
- 작성일: 2026-03-03 (api-spec v4, v5에서 확정)
- 의사결정자: 승구리, Gemini(설계 리뷰)
- 관련: [api-spec.md §1 백로그 #5, #10](../api-spec.md), `backend/services/question_gen.py`

---

## 맥락 (Context)

훈련 모드는 같은 신입에게 같은 문제를 반복 출제하지 말아야 한다. 즉 "이미 풀어본 문서 ID 목록"을 추적해서 다음 출제 시 제외해야 한다.

PoC는 인증/세션 시스템이 없고, 4주 일정 안에 백엔드에 세션 스토리지를 도입하는 것은 부담이다.

## 검토한 대안 (Options)

- **A. 서버 측 세션 스토리지 (인메모리 dict 또는 Redis)**
  - 장점: 클라이언트 상태 단순화. 멀티 디바이스 동기화 가능
  - 단점:
    - ❌ 인증/사용자 식별이 없으므로 세션 키 정의가 모호
    - ❌ 서버 재시작 시 상태 소실 (인메모리)
    - ❌ Redis 도입은 PoC 범위 밖
- **B. 클라이언트가 `solved_content_ids` 보유, 매 요청에 송신** ✅
  - 장점: 서버 Stateless, 인증 불필요, 구현 단순
  - 단점: 클라이언트가 상태 책임. 풀 소진 시 초기화 책임도 클라이언트
- **C. session_id로 상태 묶기**
  - 장점: 추후 Multi-turn과 통일된 모델
  - 단점: PoC에 즉시 도입 어려움. 미정의 시간 동안 빈 슬롯

## 결정 (Decision)

옵션 B 채택. 서버는 Stateless로 유지하고 중복 방지 책임은 프론트에 둔다.

**프로토콜:**

1. 프론트는 로컬 state로 `solvedContentIds: string[]` 보유
2. `/api/training/question` 요청에 매번 그 배열을 포함하여 송신
3. 서버는 `solved_content_ids`에 없는 ID 중에서 랜덤 추출
4. **풀 소진 시**: 서버는 전체 풀에서 재추출하고 응답에 `is_reset: true` 반환
5. 프론트는 `is_reset === true`이면 `solvedContentIds`를 `[방금 받은 source_content_id]`로 초기화

**서버 의사 코드** (api-spec §1):

```python
def select_source(category, solved_ids, is_demo):
    candidates = ... # 데모/일반 분기
    available = [c for c in candidates if c not in solved_ids]
    if not available:
        available = candidates
        return random.choice(available), True   # is_reset=True
    return random.choice(available), False
```

**클라이언트 처리** (`TrainingScreen.jsx`):

```js
setSolvedContentIds(prev =>
  data.is_reset
    ? [data.source_content_id]
    : [...prev, data.source_content_id].filter(Boolean)
);
```

## 결과 (Consequences)

- ✅ 서버 무상태 — 재시작/스케일아웃 부담 없음
- ✅ 인증 시스템 없이 동작
- ✅ `is_reset` 플래그로 풀 소진 상황도 명시적으로 처리 (api-spec 백로그 #10)
- ⚠️ 클라이언트가 배열을 잘못 관리하면 중복 출제 발생 (테스트 커버리지 필요)
- ⚠️ 한 사용자가 여러 디바이스를 쓰면 풀 추적이 디바이스별로 분리됨 (PoC 범위에서 허용)
- ⚠️ 카테고리 변경 시 배열을 비울지 유지할지는 UX 결정 (현재는 유지 — 카테고리 무관 추적)
- 🔄 재검토 트리거: 실도입에서 사용자 인증 도입 시 서버 측 진척도 추적으로 마이그레이션
