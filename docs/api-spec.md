# 설계 문서 — API 스펙 & 아키텍처

> 킥오프 합의용 + 설계 결정 기록. 개발하면서 함께 업데이트.
>
> Last Updated: 2026-03-03 (v3 — 구현 리뷰 4개 항목 반영)

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

> ⚠️ **PoC는 Single-turn만 지원.** `session_id`는 향후 Multi-turn 확장용 예약 필드. 현재는 요청 간 대화 히스토리를 유지하지 않음. 실도입 시 Multi-turn 필요하면 인메모리/Redis 세션 저장 + SSE 스트리밍 도입 검토.

**Response (SSE 스트리밍):**

PoC에서도 SSE 스트리밍 응답을 기본으로 적용. RAG 검색이 끝난 시점에 sources와 confidence는 이미 확정되어 있으므로, **스트림 첫 이벤트로 출처를 먼저 전송.** 프론트에서 답변이 타이핑되는 동안 출처를 미리 렌더링하여 체감 대기 시간 단축.

```
# SSE 스트림 형식
# 1) 출처 먼저 전송 (RAG 검색 완료 직후, LLM 생성 시작 전)
event: sources
data: {"sources": [...], "confidence": "high"}

# 2) 답변 토큰 스트리밍
event: token
data: {"text": "비대면"}

event: token
data: {"text": " 계좌 개설은"}

...

# 3) 완료 신호
event: done
data: {}
```

**최종 응답 구조 (프론트엔드 조립 후):**

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

**응답 시간 목표:** 첫 토큰 1초 이내 (SSE), 전체 완료 5초 이내

---

### 훈련 모드 — 질문 생성

```
POST /api/training/question
```

**Request:**

```json
{
  "difficulty": "beginner",
  "category": "계좌",
  "solved_content_ids": ["faq-account-001", "faq-account-002"],
  "is_demo": false
}
```

> `solved_content_ids`: 프론트엔드가 로컬 state로 관리하는 이미 출제된 문서 ID 목록. 서버는 Stateless로 유지하고, 중복 방지 책임은 프론트에 둠. 빈 배열이면 아무 문서나 출제.
>
> `is_demo`: 데모 모드 여부. `true`이면 LLM 즉석 출제를 하지 않고 `training_golden_answers.json`에서 질문을 직접 꺼내서 반환.

**Response:**

```json
{
  "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
  "question_id": "q-001",
  "source_content_id": "faq-account-003",
  "difficulty": "beginner",
  "is_reset": false
}
```

> `is_reset`: 해당 카테고리의 문제를 한 바퀴 다 돌아서 전체 풀에서 재추출이 일어났을 때 `true`. 프론트엔드는 이 플래그를 보고 `solved_content_ids`를 빈 배열 `[]`로 초기화해야 함.

**difficulty 값:** `beginner` / `intermediate` / `advanced`

> ⚠️ **난이도는 데이터 속성이 아니라 LLM 프롬프트 지시.** FAQ 스키마에 난이도 필드는 없음. 문서는 카테고리로만 필터링하여 랜덤 추출하고, `question_gen.py`의 프롬프트에서 difficulty에 따라 질문 생성 방식을 조절:
>
> - `beginner`: 단일 주제, 직접적 질문
> - `intermediate`: 조건 포함 질문
> - `advanced`: 복합 주제, 꼬아서 질문

**문제 추출 로직 (question_gen.py):**

```python
import random

def select_source(category: str, solved_content_ids: list[str], is_demo: bool) -> tuple[str, bool]:
    """
    Returns: (selected_content_id, is_reset)
    """
    # 데모 모드: golden_answers에서 직접 꺼냄 (LLM 출제 안 함)
    if is_demo:
        demo_ids = get_demo_question_ids(category)
        available = [d for d in demo_ids if d not in solved_content_ids]
        if not available:
            available = demo_ids
            return random.choice(available), True  # is_reset=True
        return random.choice(available), False

    # 일반 모드: 카테고리 필터링 → 랜덤 추출
    candidates = get_faq_ids_by_category(category)
    available = [c for c in candidates if c not in solved_content_ids]
    if not available:
        available = candidates
        return random.choice(available), True  # is_reset=True → 프론트 배열 초기화
    return random.choice(available), False
```

> ⚠️ **데모 모드 vs 일반 모드 차이:**
>
> - **일반 모드** (`is_demo: false`): 랜덤 문서 선택 → LLM이 즉석 출제 → 채점 시 Direct Fetch
> - **데모 모드** (`is_demo: true`): golden_answers.json에서 사전 확정된 질문/정답 사용 → 채점 시 수동 정답 기준
>
> 데모 모드가 필요한 이유: LLM이 즉석 생성한 `question_id`(UUID)는 golden_answers.json의 하드코딩된 ID와 매칭될 수 없음. 데모에서 수동 정답 기반 채점을 보여주려면 질문 자체를 golden_answers에서 꺼내야 함.

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

**채점 정답 소스 (우선순위):**

1. `training_golden_answers.json`에서 수동 정답 조회 → 있으면 이걸 사용
2. 수동 정답 없으면 → `source_content_id`로 ChromaDB에서 원본 content를 **Direct Fetch** → LLM에 모범 답안 기준으로 전달

> ⚠️ **RAG 재검색 안 함.** 질문 생성 시점에 이미 출처 문서(`source_content_id`)를 알고 있으므로, 채점할 때 다시 벡터 검색을 돌리지 않음. RAG 재검색은 다른 문서를 가져올 리스크가 있고 리소스도 낭비됨.

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

**검색 로직 (rag.py) — 연산 순서 중요:**

1. 사용자 질문으로 `faq_titles` 쿼리 → 상위 10건 + 점수
2. **titles 결과 내에서 \_sim 접미사 제거 후 Max Pooling** (동일 원본 ID → 최고 점수만 채택)
3. 같은 질문으로 `faq_contents` 쿼리 → 상위 10건 + 점수 (contents는 유사 제목 없으므로 Max Pooling 불필요)
4. **Title 최종 점수와 Content 점수를 가중 병합** (가중치는 config에서 파라미터로 관리)
5. 병합 점수 상위 3~5건을 LLM 컨텍스트로 전달

> ⚠️ **순서를 뒤집으면 안 됨.** Max Pooling 전에 가중 병합을 하면, 유사 제목이 많은 문서의 title 점수가 여러 번 합산되어 수치가 왜곡됨.

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

**동일 원본 ID 중복 검색 시 처리 — Max Pooling:**

같은 원본 ID가 여러 개 검색될 경우(원본 제목 + 유사 제목 1 + 유사 제목 2가 모두 Top 10에 진입), **가장 높은 유사도 점수 1개만 채택(Max Pooling)**.

```python
# 예시: faq-account-001이 3번 검색됨
# faq-account-001      → 0.92
# faq-account-001_sim1 → 0.88
# faq-account-001_sim2 → 0.85
# → Max Pooling 결과: faq-account-001 = 0.92 (최고 점수만 사용)

def merge_scores(results: list[dict]) -> dict:
    merged = {}
    for r in results:
        original_id = r["id"].split("_sim")[0]
        if original_id not in merged or r["score"] > merged[original_id]:
            merged[original_id] = r["score"]  # Max만 유지
    return merged
```

> ⚠️ **Sum 방식을 쓰지 않는 이유:** 유사 제목이 3개인 문서가 1개인 문서보다 항상 점수가 높아지는 편향이 생김. Max Pooling은 제목을 많이 만들어도 점수에 불공정한 이득이 없음.

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
    async def generate_stream(self, messages: list, temperature: float = 0.1) -> AsyncIterator[str]:
        """메시지 기반 텍스트 스트리밍 생성. SSE 응답용."""
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

**현재 구현체:** `GeminiService(LLMService)` — PoC 기본 (Google AI Studio)

- Chat: `gemini-2.5-flash`
- Embedding: `gemini-embedding-001` (3072차원)
- SDK: `google-genai` (sync → `asyncio.to_thread` 래핑)

**백업 구현체:** `OpenAIService(LLMService)` — OpenAI 크레딧 부족으로 백업 전환

- Chat: `gpt-4o` / Embedding: `text-embedding-3-small` (1536차원)

**향후 추가:** 실도입 모델 확정 시 해당 구현체 추가 (예: `Qwen3Service`, `VLLMService` 등)

**전환 시 필수 체크:**

- 임베딩 차원 변경 시 ChromaDB 컬렉션 전체 재구축 필요 → 인제스트 파이프라인을 "모델 교체 → 재인제스트" 원커맨드로 실행 가능하게 설계
- JSON 구조화 출력(채점 프롬프트) 품질은 모델별로 편차가 큼 → 전환 후 반드시 재검증
- stop token, temperature 동작, 토큰 카운팅 방식의 미묘한 차이 주의

---

## 5. 훈련 모드 정답 관리

### 문제

채점 시 정답이 필요한데, 두 가지 소스가 있음:

- 수동 확정 정답 (golden answer) — 정확하지만 수동 작업 필요
- 출처 문서 Direct Fetch — `source_content_id`로 원본 content를 직접 가져옴

### 채점 로직 (scorer.py)

```
1. question_id로 training_golden_answers.json에서 수동 정답 조회
2. 수동 정답이 있으면 → 수동 정답을 기준으로 채점
3. 수동 정답이 없으면 → source_content_id로 ChromaDB에서 원본 content Direct Fetch
   → LLM에 "이 내용을 기준으로 모범 답안을 만들고 채점해"로 전달
```

> ~~기존: 수동 정답 없으면 RAG 재검색~~ → **변경: Direct Fetch로 확정된 문서를 바로 가져옴.** 출제 시점에 출처를 이미 알고 있으므로 재검색은 불필요하고 동문서답 리스크만 있음.

### 수동 확정 정답 파일

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

---

## 6. 2인 AI 개발 규칙

### 프롬프트 버전 관리

프롬프트(`prompts/`)는 코드와 다른 속도로 변경됨. 정확도 하락 원인 추적을 위해:

```
prompt: 챗봇 시스템 프롬프트 출처 표시 형식 변경
prompt: 채점 프롬프트 필수항목 가중치 60→70% 조정
```

프롬프트 변경과 코드 변경은 **절대 같은 커밋에 섞지 않음.**

### AI 도구 간 컨텍스트 동기화

우치(Claude) ↔ 승구리(Cursor) 간 AI 도구에 맥락이 공유되지 않음.

→ **이 문서(`docs/api-spec.md`)를 양쪽 AI 도구의 프로젝트 컨텍스트에 포함시켜 사용.** 이 문서가 single source of truth 역할.

### 코드 품질

- PR 단위를 작게 유지 (함수 1~2개)
- 머지 전 "이 함수가 왜 이렇게 동작하는지" 30초 구두 설명
- AI가 생성한 코드의 핵심 로직은 반드시 주석으로 의도 기록

---

## 7. 합의 체크리스트

킥오프 때 아래 항목을 함께 확인하고, 이견이 있으면 이 문서에 바로 수정.

```
□ API 요청/응답 형식 OK?
□ PoC Single-turn + SSE 스트리밍 OK? (섹션 1)
□ SSE sources 선전송 순서 OK? (섹션 1)
□ confidence 기준 (0.85 / 0.70) OK?
□ FAQ JSON 스키마 OK?
□ 카테고리 목록 OK?
□ ChromaDB 2개 컬렉션 분리 구조 OK?
□ 유사 제목 ID 접미사 + Max Pooling OK? (섹션 3)
□ Max Pooling → 가중 병합 연산 순서 OK? (섹션 3)
□ 검색 가중치 기본값 5:5 + 3주차 그리드 서치 OK?
□ LLM 서비스 인터페이스 4개 메서드 OK? (섹션 4, generate_stream 추가)
□ 훈련 모드 채점 시 Direct Fetch 방식 OK? (섹션 5)
□ 문제 추출: random.choice + solved_content_ids로 중복 방지 OK? (섹션 1)
□ 난이도는 LLM 프롬프트 지시 (데이터 속성 아님) OK? (섹션 1)
□ 프롬프트 커밋 컨벤션(prompt:) OK? (섹션 6)
□ 실도입 모델 "후보"로 관리, 3주차 비교 테스트 OK?
```

---

## 8. 이슈 백로그

설계·구현 중 발견한 빈틈을 즉시 기록하는 곳. **발견 즉시 한 줄로 적고, 주 1회 같이 검토하여 반영/이월/제외 판단.**

### 운영 규칙

```
1. 발견 즉시  → 아래 테이블에 한 줄 추가 (30초). 해결책까지 쓸 필요 없음.
2. 주 1회     → 우치 + 승구리가 백로그 같이 보면서 판단:
                 - 🔥 이번 주 코딩에서 실제로 막힌 것 → 스펙에 반영
                 - ⏳ 아직 안 막힌 것 → 다음 주로 이월
                 - 🚫 PoC 범위 밖 → 실도입 TODO로 이동
3. 반영 후    → 상태를 ✅로 바꾸고 반영된 섹션 번호 기록. 행을 삭제하지 않음.
```

### 현재 백로그

| #   | 상태 | 발견일 | 발견자 | 내용                                                     | 관련 섹션 | 비고                             |
| --- | ---- | ------ | ------ | -------------------------------------------------------- | --------- | -------------------------------- |
| 1   | ✅   | 03-03  | Gemini | 채점 시 RAG 재검색 불필요, Direct Fetch로 변경           | 섹션 1, 5 | v3에서 반영                      |
| 2   | ✅   | 03-03  | Gemini | 다중 제목 중복 검색 시 점수 처리 기준 누락 (Max Pooling) | 섹션 3    | v3에서 반영                      |
| 3   | ✅   | 03-03  | Gemini | session_id 있으나 Multi-turn 메커니즘 없음               | 섹션 1    | v3에서 Single-turn 확정          |
| 4   | ✅   | 03-03  | Gemini | 문제 추출 방식(랜덤/순차) 미정의                         | 섹션 1    | v3에서 반영                      |
| 5   | ✅   | 03-03  | Gemini | 훈련 모드 session_history 상태 관리 누락                 | 섹션 1    | v4에서 solved_content_ids로 해결 |
| 6   | ✅   | 03-03  | Gemini | 난이도가 데이터 속성인지 프롬프트 지시인지 모호          | 섹션 1    | v4에서 프롬프트 지시로 확정      |
| 7   | ✅   | 03-03  | Gemini | Max Pooling과 가중 병합 연산 순서 모호                   | 섹션 3    | v4에서 순서 명시                 |
| 8   | ✅   | 03-03  | Gemini | SSE sources를 마지막에 보내면 UX 낭비                    | 섹션 1    | v4에서 선전송으로 변경           |
| 9   | ✅   | 03-03  | Gemini | 데모 수동 정답과 동적 출제 question_id 매칭 불가         | 섹션 1, 5 | v5에서 is_demo 분기 추가         |
| 10  | ✅   | 03-03  | Gemini | 문제 소진 시 프론트 solved_content_ids 상태 꼬임         | 섹션 1    | v5에서 is_reset 플래그 추가      |
| 11  | ⏳   | 04-14  | Claude | WBS 2.2 다중 제목 생성: 인제스트가 편람 청크 기반으로 변경되어 `_sim` 방식 불필요. 승구리와 이월/제외 협의 필요 | 섹션 3 | 보류 중, 현재 검색 품질 충분(0.94) |
| -   |      |        |        |                                                          |           |                                  |

> 새 이슈 추가 시 `#` 번호를 이어서 매기고, 상태는 `⬚`(미처리)로 시작.

### 실도입 TODO (PoC 범위 밖)

PoC에서 다루지 않지만, 실도입 시 반드시 검토해야 할 항목.

| #   | 내용                                           | 이유                                                         |
| --- | ---------------------------------------------- | ------------------------------------------------------------ |
| T1  | Multi-turn 대화 히스토리 관리 (Redis/인메모리) | PoC는 Single-turn, 실도입 시 후속 질문 지원 필요             |
| T2  | 검색 결과 Reranking + 상위 N개만 LLM 전달      | 데이터 확장 시 컨텍스트 길이 → 응답 시간 초과 우려           |
| T3  | 2단계 RAG (LangGraph)                          | PoC는 순차 파이프라인, 복잡한 질문은 멀티스텝 필요           |
| T4  | 전체 편람 자동 전처리 파이프라인               | PoC는 수동 20건, 실도입은 전체 편람 (6~12개월 별도 프로젝트) |
| T5  | GPT-4o vs 실도입 모델 성능 비교표              | 3주차 비교 테스트 결과로 작성                                |

---

## 변경 이력

| 버전 | 날짜       | 변경 내용                                                                                                              |
| ---- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| v1   | 2026-02-28 | 초기 API 스펙 + 데이터 스키마                                                                                          |
| v2   | 2026-03-03 | 설계 리뷰 반영 — Qwen3 후보화, 가중치 파라미터화, 수동 정답 병합, LLM 인터페이스                                       |
| v3   | 2026-03-03 | 구현 리뷰 1차 — 채점 Direct Fetch, Max Pooling, SSE 스트리밍, 문제 추출 로직                                           |
| v4   | 2026-03-03 | 구현 리뷰 2차 — solved_content_ids 상태관리, 난이도=프롬프트 지시 확정, Max Pooling→병합 순서 명시, SSE sources 선전송 |
| v5   | 2026-03-03 | 구현 리뷰 3차 (Gemini) — is_demo 데모/일반 모드 분기, is_reset 프론트 상태 초기화 플래그                               |
| v6   | 2026-03-09 | PoC LLM을 OpenAI → Google Gemini로 전환. GeminiService 구현, 임베딩 3072차원, RAG 가중치 config 추가                   |
| v7   | 2026-04-14 | 챗봇 모드 SSE 스트리밍 구현. chat.py 전면 교체, rag.py에 generate_answer_stream 추가, 챗봇 프론트엔드(ChatScreen) 구현   |

---

## 협업 핸드오프 로그

작업 완료 후 상대방이 확인해야 할 사항을 여기에 기록. 확인 완료 시 `✅` 표시.

### 2026-03-09 | 우치 → 승구리 | WBS 1.5 + 1.6 완료

**커밋**: `fe91692`

#### 변경 요약

- `backend/services/embedder.py` — `LLMService(ABC)` + `GeminiService`(기본) + `OpenAIService`(백업) 구현
- `backend/services/rag.py` — ChromaDB 초기화 + `RAGService` 검색 파이프라인
- `backend/config.py` — Google AI Studio 설정, RAG 검색 가중치 추가
- `requirements.txt` — `google-genai`, `tiktoken` 추가

#### 확인사항

- [ ] **LLM이 OpenAI → Gemini로 바뀜**: OpenAI 크레딧 부족으로 전환. `.env`에 `GOOGLE_API_KEY` 필요
- [ ] **임베딩 3072차원**: `gemini-embedding-001` 사용 (기존 OpenAI 1536차원 → 3072차원)
- [ ] **인제스트 시 반드시 `GeminiService.embed()` 사용할 것**: 다른 모델 임베딩 시 차원 불일치 에러
  ```python
  from backend.services.embedder import GeminiService
  llm = GeminiService()
  vectors = await llm.embed(["텍스트1", "텍스트2"])  # 3072차원
  ```
- [ ] **ChromaDB 컬렉션 2개**: `faq_titles`(제목), `faq_contents`(본문) — `hnsw:space: cosine`
  ```python
  from backend.services.rag import get_chroma_client, init_collections
  client = get_chroma_client()
  titles_col, contents_col = init_collections(client)
  ```
- [ ] **패키지 재설치 필요**: `pip install -r requirements.txt`

---

### 2026-03-16 | 승구리 → 우치 | Docling PDF 파서 구현

**커밋**: `cc12efa` ~ `85d8628` (8 commits)

#### 변경 요약

- `backend/services/parsers/docling_pdf.py` (신규) — Docling 기반 PDF 파서. 텍스트·표 추출, 한국어 개조식 번호 패턴(`1)`, `가.`, `ㄱ.`)으로 heading 깊이 감지, 계층 구조(hierarchy_path) 자동 생성
- `backend/models/parsed_document.py` (신규) — `Block`, `ParsedDocument` Pydantic 공통 스키마. 파서 종류(docling/pymupdf)와 무관하게 통일된 출력 구조
- `scripts/parse_pdf.py` (신규) — CLI 파싱 스크립트 (`python scripts/parse_pdf.py -i <PDF경로>`)
- `tests/test_docling_parser.py` (신규) — 파서 최소 테스트 (`data/raw/sample.pdf` 있을 때 실행)
- `backend/config.py` — `DATA_DIR` 설정 추가
- `requirements.txt` — `docling>=2.0.0`, `pytest>=8.0.0` 추가, 기존 camelot 주석 제거
- `backend/utils/pdf_parser.py` — 기존 유틸 삭제

#### 확인사항

- [ ] **패키지 재설치 필요**: `pip install -r requirements.txt` — docling은 무거운 패키지이므로 설치 시간 주의
- [ ] **파서 출력 스키마 확인**: `ParsedDocument` → `blocks[]` 구조. 각 Block에 `block_type`(heading/paragraph/table/table_row/rule), `hierarchy_path`, `canonical_text` 포함
- [ ] **ChromaDB 인제스트 시 `canonical_text` 사용 권장**: 검색 최적화용 평문이 `block.canonical_text`에 생성됨. RAG 파이프라인에서 이 필드를 임베딩 대상으로 활용할 것
- [ ] **표(table) 추출**: Docling `TableFormerMode`로 표 구조 추출 → `block_type: "table"` (전체 HTML/마크다운) + `"table_row"` (행 단위 분리). RAG 검색 시 행 단위 블록 활용 가능
- [ ] **계층 구조**: `hierarchy_path`에 문서 소제목 경로가 리스트로 담김 (예: `["계좌개설", "가. 신규개설"]`). 검색 결과 출처 표시에 활용 가능
- [ ] **기존 `pdf_parser.py` 삭제됨**: `backend/utils/pdf_parser.py` 제거. 기존 참조가 있으면 `backend.services.parsers.docling_pdf`로 교체 필요

---

### 2026-03-16 | 승구리 → 우치 | 업무편람 ChromaDB 인제스트 스크립트

**커밋**: `9abd40c`

#### 변경 요약

- `scripts/ingest_manual.py` (신규) — docling 파싱 결과(`ParsedDocument`)를 ChromaDB `faq_titles`/`faq_contents` 컬렉션에 적재하는 CLI 스크립트
- `scripts/ingest_faq.py` — 삭제 (ingest_manual.py로 대체)

#### 핵심 설계

- **기존 dual-collection 구조 그대로 활용** (`rag.py` 수정 없음)
  - `faq_titles`: 블록의 heading context (`hierarchy_path` join) 저장
  - `faq_contents`: 블록의 `canonical_text` (없으면 `text`) 저장
  - 양쪽 동일 ID: `{doc_id}_{block_order}`
- **블록 타입별 청킹 가이드라인 적용**:
  - `paragraph`: 같은 `hierarchy_path` 내 연속 블록을 150~400 tokens까지 병합, 12% overlap
  - `procedure`: 연속 블록 150~350 tokens 병합, 10% overlap
  - `heading`, `rule`, `table`, `table_row`, `faq`, `notice`: 블록 1개 = 청크 1개 (병합 없음)
- **토큰 추정**: `len(text) * 0.7` 휴리스틱 (한국어 근사)
- **임베딩**: `GeminiService.embed()` 100건 배치 호출
- **`_sim` 접미사 미사용**: `rag.py`의 Max Pooling은 identity 동작 (무해)

#### 확인사항

- [ ] **실행 방법**:
  ```bash
  python scripts/ingest_manual.py -i data/processed/<doc_id>/docling.json  # 단일 문서
  python scripts/ingest_manual.py --all                                     # 전체 문서
  python scripts/ingest_manual.py --clear --all                             # 컬렉션 초기화 후 재인제스트
  ```
- [ ] **`.env`에 `GOOGLE_API_KEY` 필요**: `GeminiService.embed()` 호출 시 API 키 없으면 `ValueError` 발생
- [ ] **metadata 구조**: `source_document`(PDF 파일명), `source_page`(`p.{N}`), `doc_id`, `block_type`, `hierarchy_path`(JSON 문자열), `category`(빈 문자열). RAG 검색 결과에서 `category`가 비어 있으므로, 챗봇 모드에서 카테고리 필터가 필요하면 추후 협의
- [ ] **청킹 파라미터 튜닝**: `_CHUNK_CONFIG`의 `max_tokens`, `overlap` 값은 현재 가이드라인 기준. 검색 품질 테스트 후 조정 가능

---

### 2026-03-16 | 승구리 → 우치 | feature/training-question 브랜치 작업

**브랜치**: `feature/training-question`

#### 변경 요약

**백엔드 (훈련 모드 질문 생성)**

- `backend/services/question_gen.py` — 업무편람 ChromaDB 기반 질문 생성 서비스 구현
  - 데모 모드: `training_golden_answers.json`에서 직접 반환
  - 일반 모드: ChromaDB에서 청크 선택 → LLM으로 고객 질문 생성
- `tests/training_golden_answers.json` — 데모 모드용 golden answer 1건 추가

**프론트엔드**

- `frontend/` — React + Vite 프로젝트 구성, 훈련 모드 UI 기초
  - `package.json`, `vite.config.js`, `index.html`, `src/` 구조
  - `TrainingScreen`: 난이도·카테고리·데모 모드 선택, 질문 표시, 답변 입력 textarea
  - `App.jsx`: 챗봇 모드 / 훈련 모드 탭 전환 (챗봇 모드는 "준비 중" 안내만)
  - `POST /api/training/question` API 연동

#### 확인사항

- [ ] **프론트엔드 화면은 논의 후 다시 제작 예정**: `frontend/index.html` 일단 챗봇/훈련 모드를 탭으로 분리해 둔 상태
- [ ] **실행 순서**: 백엔드(`uvicorn`) → 프론트(`npm run dev`), Vite proxy로 `/api` → `localhost:8000`

```
# 백엔드
uvicorn backend.main:app --reload

# 프론트엔드 (다른 터미널에서)
cd frontend
npm run dev
```

---

### 2026-04-14 | 우치 → 승구리 | 챗봇 모드 2~3주차 구현 완료

**브랜치**: `feature/chatbot`

#### 변경 요약

**백엔드 (챗봇 모드)**

- `backend/services/rag.py` — `generate_answer_stream()` 추가. SSE용 스트리밍 답변 생성 (sources 선반환 + 토큰 AsyncIterator). `_build_system_prompt`에서 불필요한 `{question}` replace 제거
- `backend/routers/chat.py` — 기존 스텁 → SSE 스트리밍 API 전면 구현. FastAPI `StreamingResponse` 사용 (추가 패키지 없음). 이벤트 순서: sources → token → done
- `backend/prompts/chat_system.txt` — v2: 출처 번호 [1][2] 인용 형식, 엣지케이스 처리 지시 (모호한 질문, 부분 매칭, 편람 외 질문)

**프론트엔드 (챗봇 UI)**

- `frontend/src/api/chat.js` (신규) — SSE 스트리밍 API 헬퍼. fetch + ReadableStream으로 POST SSE 소비
- `frontend/src/components/chat/ChatScreen.jsx` (신규) — 챗봇 UI. 메시지 히스토리, 실시간 스트리밍 표시, SourcePanel (출처 목록 + confidence 뱃지)
- `frontend/src/App.jsx` — "준비 중" placeholder → ChatScreen 교체

**스크립트**

- `scripts/weight_search.py` (신규) — 가중치 그리드 서치 [5:5, 4:6, 3:7] 비교

**문서 인프라**

- `docs/INDEX.md`, `docs/TROUBLESHOOTING.md`, `docs/PROMPT_HISTORY.md`, `docs/TEST_CHECKLIST.md` (신규) — AI 도구용 문서 체계
- `scripts/pre-commit-check.sh` (신규) — pre-commit hook (.env 차단, API 키 하드코딩 검사, 소유권 경고)
- `CLAUDE.md`, `.cursorrules`, `RULES.md` — 문서 참조 + 주석 규칙 추가

#### 확인사항

- [ ] **챗봇 모드 동작 확인**: `uvicorn backend.main:app --reload` → `cd frontend && npm run dev` → 브라우저 `localhost:3000` → 챗봇 모드 탭
- [ ] **SSE 스트리밍 정상**: sources 선전송 → 토큰 실시간 → done 순서
- [ ] **App.jsx 변경**: 훈련 모드 동작에 영향 없음 (import 추가 + placeholder 교체만)
- [ ] **pre-commit hook**: `scripts/pre-commit-check.sh`를 `.git/hooks/pre-commit`에 복사해서 사용. 승구리 로컬에서도 설치 필요:
  ```bash
  cp scripts/pre-commit-check.sh .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  ```
- [ ] **문서 확인**: `docs/INDEX.md` → 전체 문서 인덱스. Cursor에서도 동일하게 참조 가능

---

_이 문서는 개발 진행에 따라 팀원 누구나 업데이트._
