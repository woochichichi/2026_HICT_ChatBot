# ADR-0002: ChromaDB Dual-Collection (제목+내용 분리)

- 상태: Accepted
- 작성일: 2026-02-28
- 의사결정자: 우치
- 관련: [api-spec.md §3](../api-spec.md), [db-design.md](../db-design.md), `backend/services/rag.py`

---

## 맥락 (Context)

증권 업무 편람/FAQ는 두 가지 매칭 신호가 있다:

1. **제목/소제목 매칭**: "비대면 계좌 개설 절차" 같은 주제어가 질문과 일치할 때
2. **본문 매칭**: 본문 안의 구체적인 단어/숫자/조건이 일치할 때

단일 컬렉션에 본문 전체를 임베딩하면 긴 본문에서 주제어 신호가 희석된다. 사람인HR 챗봇 사례에서 제목+본문 분리 임베딩으로 정확도 87%를 달성한 선례가 있다 (README §용어집).

## 검토한 대안 (Options)

- **A. 단일 컬렉션 (본문만 임베딩)**
  - 장점: 단순. 1회 임베딩
  - 단점: 긴 본문에서 주제 매칭 약화. "양도세" 같은 짧은 질의에 취약
- **B. 단일 컬렉션 (제목+본문 합쳐서 임베딩)**
  - 장점: 단순
  - 단점: 가중치 조절 불가. 본문이 길어질수록 제목 영향력 감소
- **C. 두 컬렉션 분리(`faq_titles`, `faq_contents`) + 가중 병합** ✅
  - 장점: 가중치 파라미터화 가능, 그리드 서치로 최적화 가능, 도메인 신호 분리
  - 단점: 임베딩 2배, 컬렉션 관리 복잡도 증가

## 결정 (Decision)

옵션 C 채택. ChromaDB 컬렉션 두 개를 동일 ID로 1:1 매칭하여 운영한다.

```
faq_titles    : id={doc_id}_{order}, document=heading|hierarchy_path, embedding(3072)
faq_contents  : id={doc_id}_{order}, document=canonical_text|text,    embedding(3072)
```

검색은 다음 순서로 진행한다 ([api-spec §3](../api-spec.md), 순서 엄수):

1. `faq_titles.query(top=10)` → 점수 추출
2. Max Pooling — `_sim` 접미사 제거 후 동일 원본 ID는 최고 점수 1개만 (ADR-0003)
3. `faq_contents.query(top=10)` → 점수 추출
4. **Max Pooling 후** 가중 병합 (`TITLE_WEIGHT * t + CONTENT_WEIGHT * c`)
5. score 내림차순 → 상위 `TOP_K`(5)

기본 가중치는 5:5, 3주차에 그리드 서치(`[5:5, 4:6, 3:7]`)로 튜닝한다.

## 결과 (Consequences)

- ✅ 제목 매칭과 본문 매칭의 기여도를 독립 조절 가능
- ✅ 같은 ID로 양 컬렉션이 묶여 메타 부착이 단순
- ⚠️ 임베딩 비용/시간 2배
- ⚠️ ID 정합성 책임이 인제스트 스크립트에 있음 (한쪽만 적재되면 검색 시 한쪽 점수 0)
- ⚠️ Max Pooling을 가중 병합 **앞에** 적용해야 함. 순서 뒤집으면 유사 제목이 많은 문서가 부당한 가중을 받음 (ADR-0003)
- 🔄 재검토 트리거: 데이터 100건 이상으로 확장 시 Reranking 단계 추가 검토 (api-spec T2)
