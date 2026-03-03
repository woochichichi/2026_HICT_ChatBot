# 설계 문서 — API 스펙 & 아키텍처

> 킥오프 합의용 + 설계 결정 기록. 개발하면서 함께 업데이트한다.
>
> Last Updated: 2026-03-03 (v2 — 설계 리뷰 반영, 4개 항목 확정)

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

**채점 정답 소스:** RAG 추출 정답과 수동 확정 정답(`tests/training_golden_answers.json`)을 병합하여 사용. 데모 시나리오는 반드시 수동 정답을 우선 적용.

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
3. 문서 ID 기준으로 점수 가중 병합 (가중치는 config에서 파라미터로 관리)
4. 병합 점수 상위 3~5건을 LLM 컨텍스트로 전달

**가중치 설정 (config.py):**
```python
TITLE_WEIGHT = 0.5      # 기본값
CONTENT_WEIGHT = 0.5    # 기본값
# 3주차에 [5:5, 4:6, 3:7] 그리드 서치로 최적값 확정
```

**유사 제목(similar_titles) 처리:**
- 인제스트 시 원본 title + similar_titles를 각각 별도 document로 저장
- id에 접미사 추가: `faq-account-001`, `faq-account-001_sim1`, `faq-account-001_sim2`
- 검색 결과에서 접미사 제거 후 원본 ID로 병합

---

## 4. LLM 서비스 추상화

PoC(GPT-4o) → 실도입(미정) 전환 시 코드 수정을 최소화하기 위한 인터페이스.

```python
from abc import ABC, abstractmethod

class LLMService(ABC):
    """LLM 전환 대비 추상 인터페이스. 모든 LLM 구현체는 이 3개 메서드를 구현."""

    @abstractmethod
    async def generate(self, messages: list, temperature: float = 0.1, response_format: dict | None = None) -> str:
        """메시지 기반 텍스트 생성."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 배치를 벡터로 변환."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산."""
        ...
```

**현재 구현체:** `OpenAIService(LLMService)` — PoC용
**향후 추가:** 실도입 모델 확정 시 해당 구현체 추가 (예: `Qwen3Service`, `VLLMService` 등)

**전환 시 필수 체크:**
- 임베딩 차원 변경 시 ChromaDB 컬렉션 전체 재구축 필요 → 인제스트 파이프라인을 "모델 교체 → 재인제스트" 원커맨드로 실행 가능하게 설계
- JSON 구조화 출력(채점 프롬프트) 품질은 모델별로 편차가 큼 → 전환 후 반드시 재검증
- stop token, temperature 동작, 토큰 카운팅 방식의 미묘한 차이 주의

---

## 5. 훈련 모드 정답 관리

### 문제

채점 시 "편람 기반 정답"을 RAG로 추출하는데, RAG 정확도 목표가 80%이므로 정답 자체가 틀릴 수 있음.

### 해결: 수동 확정 정답 병합

```
tests/training_golden_answers.json
```

```json
[
  {
    "question_id": "q-demo-001",
    "scenario": "초급 — 계좌 개설",
    "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
    "golden_answer": "계좌 개설에는 신분증이 필요하며, 고객확인(CDD) 서류도 함께 징구합니다. 비대면의 경우 영상통화 본인확인 절차가 추가됩니다.",
    "required_items": ["신분증", "CDD 서류", "비대면 시 영상통화"],
    "reference": "계좌업무편람 p.23 제5조"
  },
  {
    "question_id": "q-demo-002",
    "scenario": "고급 — 세금/수수료 복합",
    "question": "해외주식 매도 후 세금 신고 방법과 수수료 한도도 알려주세요",
    "golden_answer": "TODO: 편람 확인 후 작성",
    "required_items": ["TODO"],
    "reference": "TODO"
  }
]
```

**채점 로직 (scorer.py):**
1. `question_id`로 `training_golden_answers.json`에서 수동 정답 조회
2. 수동 정답이 있으면 → 수동 정답을 기준으로 채점
3. 수동 정답이 없으면 → RAG 추출 정답을 기준으로 채점 (기존 방식)

---

## 6. 2인 AI 개발 규칙

### 프롬프트 버전 관리

프롬프트(`prompts/`)는 코드와 다른 속도로 변경됨. 정확도 하락 원인 추적을 위해:

```
prompt: 챗봇 시스템 프롬프트 출처 표시 형식 변경
prompt: 채점 프롬프트 필수항목 가중치 60→70% 조정
```

프롬프트 변경과 코드 변경은 **절대 같은 커밋에 섞지 않는다.**

### AI 도구 간 컨텍스트 동기화

팀 리드(Claude) ↔ 승구리(Cursor) 간 AI 도구에 맥락이 공유되지 않음.

→ **이 문서(`docs/api-spec.md`)를 양쪽 AI 도구의 프로젝트 컨텍스트에 포함시켜 사용.** 이 문서가 single source of truth 역할.

### 코드 품질

- PR 단위를 작게 유지 (함수 1~2개)
- 머지 전 "이 함수가 왜 이렇게 동작하는지" 30초 구두 설명
- AI가 생성한 코드의 핵심 로직은 반드시 주석으로 의도 기록

---

## 7. 합의 체크리스트

킥오프 때 아래 항목을 함께 확인하고, 이견이 있으면 이 문서에 바로 수정한다.

```
□ API 요청/응답 형식 OK?
□ confidence 기준 (0.85 / 0.70) OK?
□ FAQ JSON 스키마 OK?
□ 카테고리 목록 OK?
□ ChromaDB 2개 컬렉션 분리 구조 OK?
□ 유사 제목 ID 접미사 방식 OK?
□ 검색 가중치 기본값 5:5 + 3주차 그리드 서치 OK?
□ LLM 서비스 인터페이스 3개 메서드 OK? (섹션 4)
□ 훈련 모드 수동 정답 병합 방식 OK? (섹션 5)
□ 프롬프트 커밋 컨벤션(prompt:) OK? (섹션 6)
□ 실도입 모델 "후보"로 관리, 3주차 비교 테스트 OK?
```

---

*이 문서는 개발 진행에 따라 팀원 누구나 업데이트한다.*
