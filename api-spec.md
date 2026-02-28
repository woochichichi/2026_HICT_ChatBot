# API 스펙 & 데이터 스키마

> 킥오프 시 합의용. 개발하면서 함께 업데이트한다.

---

## 1. API 엔드포인트

### 챗봇 모드

```
POST /api/chat
```

**Request:**
```json
{
  "question": "비대면 계좌 개설 절차가 어떻게 되나요?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "비대면 계좌 개설은 다음 절차로 진행됩니다...",
  "sources": [
    {
      "title": "계좌업무편람 제5조 비대면 계좌 개설",
      "reference": "계좌업무편람 p.23",
      "relevance_score": 0.92
    }
  ],
  "confidence": "high"
}
```

**confidence 기준:**
- `high`: 유사도 0.85 이상, 출처 명확
- `medium`: 유사도 0.70~0.85
- `low`: 유사도 0.70 미만 → "편람에 포함되어 있지 않습니다" 안내

---

### 훈련 모드 — 질문 생성

```
POST /api/training/question
```

**Request:**
```json
{
  "difficulty": "beginner",
  "category": "계좌"
}
```

**Response:**
```json
{
  "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
  "question_id": "q-001",
  "source_content_id": "faq-account-003",
  "difficulty": "beginner"
}
```

**difficulty 값:** `beginner` / `intermediate` / `advanced`

---

### 훈련 모드 — 채점

```
POST /api/training/score
```

**Request:**
```json
{
  "question_id": "q-001",
  "trainee_answer": "신분증이랑 통장 가져오시면 됩니다."
}
```

**Response:**
```json
{
  "score": 65,
  "included_items": ["신분증 필요"],
  "missing_items": ["CDD 서류", "비대면 시 영상통화 필요"],
  "feedback": "신분증 안내는 정확하지만, CDD 서류와 비대면 절차 안내가 누락되었습니다.",
  "reference": "계좌업무편람 p.23 제5조",
  "model_answer": "계좌 개설에는 신분증이 필요하며, 고객확인(CDD) 서류도 함께 징구합니다. 비대면의 경우 영상통화 본인확인 절차가 추가됩니다."
}
```

---

## 2. FAQ 데이터 스키마

```json
{
  "id": "faq-account-001",
  "category": "계좌",
  "title": "비대면 계좌 개설 절차",
  "similar_titles": [
    "온라인으로 계좌 만드는 방법",
    "비대면 계좌 개설 어떻게 하나요"
  ],
  "content": "비대면 계좌 개설은 모바일앱에서 신분증 촬영 → 영상통화 본인확인 → 계좌 개설 완료 순서로 진행됩니다. 소요시간은 약 10~15분이며, 영상통화 가능 시간은 평일 09:00~16:00입니다.",
  "source": {
    "document": "계좌업무편람",
    "page": "p.23",
    "section": "제5조"
  }
}
```

**카테고리 목록:** 계좌, 매매, 수수료, 상품, IT장애

**파일 위치:** `data/processed/faq.json` (배열 형태)

---

## 3. ChromaDB 컬렉션 구조

```
컬렉션 2개로 분리:

1. faq_titles
   - id: "faq-account-001"  (FAQ id와 동일)
   - document: "비대면 계좌 개설 절차"  (title)
   - metadata: { category, source_document, source_page }

2. faq_contents
   - id: "faq-account-001"  (FAQ id와 동일, titles와 매핑)
   - document: "비대면 계좌 개설은 모바일앱에서..."  (content)
   - metadata: { category, source_document, source_page }
```

**검색 로직 (rag.py):**
1. 사용자 질문으로 `faq_titles` 쿼리 → 상위 10건 + 점수
2. 같은 질문으로 `faq_contents` 쿼리 → 상위 10건 + 점수
3. 문서 ID 기준으로 점수 가중 병합 (제목 50% + 내용 50%)
4. 병합 점수 상위 3~5건을 LLM 컨텍스트로 전달

**유사 제목(similar_titles) 처리:**
- 인제스트 시 원본 title + similar_titles를 각각 별도 document로 저장
- id에 접미사 추가: `faq-account-001`, `faq-account-001_sim1`, `faq-account-001_sim2`
- 검색 결과에서 접미사 제거 후 원본 ID로 병합

---

## 4. 합의 체크리스트

킥오프 때 아래 항목을 함께 확인하고, 이견이 있으면 이 문서에 바로 수정한다.

```
□ API 요청/응답 형식 OK?
□ confidence 기준 (0.85 / 0.70) OK?
□ FAQ JSON 스키마 OK?
□ 카테고리 목록 OK?
□ ChromaDB 2개 컬렉션 분리 구조 OK?
□ 유사 제목 ID 접미사 방식 OK?
□ 검색 가중치 50:50 OK? (3주차에 튜닝 예정)
```

---

*이 문서는 개발 진행에 따라 팀원 누구나 업데이트한다.*
*Last Updated: 2026-02-28*
