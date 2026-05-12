# ADR-0003: 다중 제목 + Max Pooling 채택

- 상태: Accepted
- 작성일: 2026-03-03 (api-spec v3에서 명시)
- 의사결정자: 우치, 승구리, Gemini(설계 리뷰)
- 관련: [api-spec.md §3 백로그 #2, #7](../api-spec.md), `backend/services/rag.py:_max_pool_titles`

---

## 맥락 (Context)

같은 문서를 다양한 동의어 표현으로 검색되도록 하기 위해 한 문서당 여러 개의 제목을 임베딩한다. 예:

```
faq-account-001       → "비대면 계좌 개설 절차"
faq-account-001_sim1  → "온라인으로 계좌 만드는 방법"
faq-account-001_sim2  → "비대면 계좌 개설 어떻게 하나요"
```

이 경우 한 질의에 동일 원본 문서가 Top 10에서 여러 번 등장할 수 있다. 점수 처리 방식이 모호하면 데이터 편향이 발생한다.

## 검토한 대안 (Options)

- **A. 합산(Sum) — 등장한 모든 제목의 유사도 합산**
  - 장점: 직관적
  - 단점: ❌ 유사 제목이 많은 문서가 항상 점수가 높아짐. 제목을 많이 만들수록 부당한 이득
- **B. 평균(Mean) — 모든 제목의 평균**
  - 장점: 합산 편향 회피
  - 단점: 1번만 일치한 강한 신호가 다른 약한 신호로 희석됨
- **C. 최댓값(Max Pooling) — 동일 원본 ID는 최고 점수 1개만 채택** ✅
  - 장점: 제목 개수와 무관하게 공정. 가장 잘 맞는 표현 1개만 신호로 사용
  - 단점: 동일 문서가 여러 표현으로 일치하더라도 가중되지 않음 (반대로 이는 장점)

## 결정 (Decision)

옵션 C(Max Pooling) 채택. `_sim` 접미사를 제거한 원본 ID 단위로 그룹핑한 뒤 최고 유사도만 채택한다.

```python
def _max_pool_titles(ids, distances):
    pooled = {}
    for doc_id, dist in zip(ids, distances):
        original_id = doc_id.split("_sim")[0]
        sim = max(0.0, 1.0 - dist)
        if original_id not in pooled or sim > pooled[original_id]:
            pooled[original_id] = sim
    return pooled
```

**연산 순서 엄수** (api-spec §3): Max Pooling은 가중 병합 **앞에** 수행한다.
순서를 뒤집으면 유사 제목이 N개인 문서의 title 점수가 N번 합산되어 본문 점수와의 비율이 왜곡된다.

```
✅ titles 검색 → Max Pool → contents 검색 → 가중 병합
❌ titles 검색 → contents 검색 → 가중 병합 → Max Pool
```

ID 접미사 규약은 `{원본 ID}_sim{N}` 형식 (`_sim` 토큰을 split key로 사용).

## 결과 (Consequences)

- ✅ 제목 개수에 따른 편향 없음. 유사 제목 추가가 무해
- ✅ 동의어 커버리지 확장이 안전 (제목을 늘려도 점수가 부당히 오르지 않음)
- ⚠️ "강한 신호 1개"만 살아남으므로, 동일 문서가 약하게 여러 번 일치하는 케이스는 불리
- ⚠️ 현재 PoC는 `_sim` 접미사 인제스트가 미적용 상태. Max Pooling 코드는 identity 동작 (무해, 향후 다중 제목 인제스트 시 자동 활성화)
- 🔄 재검토 트리거: 동의어 커버리지가 부족하다는 지표가 나오면 `scripts/generate_titles.py`로 LLM 자동 생성 + 인제스트 활성화
