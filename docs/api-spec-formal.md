# API 명세서

> 증권 상담원 AI 코치 — REST API 정형 명세
>
> ⚠️ **단일 진실 소스(Single Source of Truth)는 [docs/api-spec.md](./api-spec.md)**.
> 본 문서는 그 내용을 표준 명세서 형식(공통 항목, 헤더, 에러 코드, 예시)으로 재정리한 산출물이다.
> 스펙 변경은 반드시 `api-spec.md`에서 먼저 반영하고, 본 문서는 그 이후 동기화한다.
>
> Last Updated: 2026-05-08
> Base URL (PoC): `http://localhost:8000`

---

## 1. 공통 사항

### 1.1 기본 정보

| 항목         | 값                                                                                |
| ------------ | --------------------------------------------------------------------------------- |
| Base URL     | `http://localhost:8000` (개발), 실도입 시 사내 도메인                              |
| API Prefix   | `/api`                                                                            |
| 인증         | **PoC 미적용** (실도입 시 SSO/JWT 검토)                                            |
| Content-Type | `application/json` (요청), `application/json` 또는 `text/event-stream` (응답)     |
| 문자 인코딩  | UTF-8                                                                             |
| OpenAPI 문서 | `GET /docs` (Swagger UI), `GET /openapi.json`                                     |
| 헬스체크     | `GET /health` → `{"status": "ok"}`                                                |

### 1.2 표준 에러 응답

FastAPI 기본 에러 포맷을 따른다.

```json
{
  "detail": "에러 메시지 (string) 또는 검증 실패 객체 배열"
}
```

| 상태 코드 | 의미                  | 발생 예시                                                    |
| --------- | --------------------- | ------------------------------------------------------------ |
| 200       | 성공                  | 정상 응답                                                    |
| 400       | Bad Request           | `ValueError`(예: 출제 가능한 콘텐츠 없음, 데모 질문 not found)|
| 422       | Validation Error      | Pydantic 스키마 위반 (필드 누락/타입 오류)                   |
| 500       | Internal Server Error | LLM/ChromaDB 예외 등 처리되지 않은 예외                      |

> 422 응답은 FastAPI 표준 형식 (`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`).

### 1.3 엔드포인트 요약

| Method | Path                       | 용도                       | 모드  | 응답 형식       | 소유자  |
| ------ | -------------------------- | -------------------------- | ----- | --------------- | ------- |
| GET    | `/health`                  | 헬스체크                   | 공통  | JSON            | 공통    |
| POST   | `/api/chat`                | 챗봇 답변 (RAG)            | 챗봇  | SSE 스트림      | 우치    |
| POST   | `/api/training/question`   | 훈련 질문 생성             | 훈련  | JSON            | 승구리  |
| POST   | `/api/training/score`      | 훈련 답변 채점             | 훈련  | JSON            | 승구리  |

---

## 2. 챗봇 모드

### 2.1 `POST /api/chat` — 질문 답변 (SSE 스트리밍)

#### 요약
사용자 질문을 받아 RAG로 관련 문서를 검색하고, LLM이 출처 기반 답변을 SSE로 스트리밍한다.

#### 요청

| 항목         | 값                                          |
| ------------ | ------------------------------------------- |
| Method       | POST                                        |
| Path         | `/api/chat`                                 |
| Content-Type | `application/json`                          |
| Accept       | `text/event-stream` (SSE 응답 시 권장)      |

**Body Schema:**

| 필드          | 타입            | 필수 | 설명                                                              |
| ------------- | --------------- | ---- | ----------------------------------------------------------------- |
| `question`    | string          | ✓    | 사용자 질문 (한국어, 1자 이상)                                    |
| `session_id`  | string \| null  | ✗    | **PoC 예약 필드** — Multi-turn 확장용. 현재는 무시됨 (ADR 시리즈) |

**예시:**

```json
{
  "question": "비대면 계좌 개설 절차가 어떻게 되나요?",
  "session_id": null
}
```

#### 응답

**Content-Type:** `text/event-stream`

SSE 이벤트 시퀀스 (api-spec.md §1):

| 순서 | event 이름 | data 페이로드                                                   | 설명                                            |
| ---- | ---------- | --------------------------------------------------------------- | ----------------------------------------------- |
| 1    | `sources`  | `{ "sources": Source[], "confidence": "high"\|"medium"\|"low" }` | RAG 검색 직후 즉시 전송 (LLM 생성 시작 전)      |
| 2..n | `token`    | `{ "text": "..." }`                                             | LLM 토큰 청크 (반복 발생)                       |
| 마지막| `done`     | `{}`                                                            | 완료 신호                                        |

**`Source` 객체:**

| 필드              | 타입    | 설명                                                  |
| ----------------- | ------- | ----------------------------------------------------- |
| `title`           | string  | 출처 문서 + 페이지 + 섹션 (예: "계좌업무편람 p.23 …") |
| `reference`       | string  | 짧은 출처 표기 (예: "계좌업무편람 p.23")              |
| `relevance_score` | number  | 가중 병합 후 유사도 (0.0 ~ 1.0)                        |

**`confidence` 기준 (api-spec.md §1):**

| 값       | 조건                          | 권장 동작                                 |
| -------- | ----------------------------- | ----------------------------------------- |
| `high`   | 최상위 score ≥ 0.85           | 답변 그대로 표시                          |
| `medium` | 0.70 ≤ score < 0.85           | 답변 + "참고용" 힌트 표시                 |
| `low`    | score < 0.70                  | "편람에 포함되지 않음" 안내               |

**SSE 응답 예시:**

```
event: sources
data: {"sources":[{"title":"계좌업무편람 p.23 비대면 계좌 개설","reference":"계좌업무편람 p.23","relevance_score":0.92}],"confidence":"high"}

event: token
data: {"text":"비대면"}

event: token
data: {"text":" 계좌 개설은"}

event: done
data: {}
```

**최종 조립 형태(프론트 처리 후, 참고용):**

```json
{
  "answer": "비대면 계좌 개설은 다음 절차로 진행됩니다...",
  "sources": [
    {
      "title": "계좌업무편람 p.23 비대면 계좌 개설",
      "reference": "계좌업무편람 p.23",
      "relevance_score": 0.92
    }
  ],
  "confidence": "high"
}
```

#### 성능 목표

| 지표        | 목표             |
| ----------- | ---------------- |
| 첫 토큰     | 1초 이내 (SSE)   |
| 전체 완료   | 5초 이내         |
| 응답 정확도 | 80%+ (테스트 30) |

> ⚠️ 현재 `routers/chat.py`는 placeholder. 상기 SSE 명세는 `api-spec.md` 기준이며 RAG 파이프라인(`services/rag.py`)에 SSE 연결 작업이 필요하다.

---

## 3. 훈련 모드

### 3.1 `POST /api/training/question` — 질문 생성

#### 요약
신입 상담원에게 출제할 고객 질문을 생성한다. 일반 모드는 ChromaDB 청크에서 LLM이 즉석 출제, 데모 모드는 사전 확정 골든답에서 직접 반환.

#### 요청

| 항목         | 값                          |
| ------------ | --------------------------- |
| Method       | POST                        |
| Path         | `/api/training/question`    |
| Content-Type | `application/json`          |

**Body Schema (`QuestionRequest`):**

| 필드                  | 타입       | 필수 | 기본 | 설명                                                                                |
| --------------------- | ---------- | ---- | ---- | ----------------------------------------------------------------------------------- |
| `difficulty`          | enum       | ✓    | —    | `beginner` \| `intermediate` \| `advanced` (LLM 프롬프트 지시용, 데이터 속성 아님)   |
| `category`            | string     | ✓    | —    | 카테고리 (예: `계좌`, `매매`). 빈 문자열이면 카테고리 무시. PoC에서는 ChromaDB metadata `category`가 비어 있어 사실상 전체 풀에서 추출 |
| `solved_content_ids`  | string[]   | ✗    | `[]` | 클라이언트가 보유한 이미 출제된 source_content_id 목록 (Stateless 서버 — ADR-0006)   |
| `is_demo`             | boolean    | ✗    | `false` | true → `tests/training_golden_answers.json`에서 직접 출제 (LLM 미호출)          |

**예시:**

```json
{
  "difficulty": "beginner",
  "category": "계좌",
  "solved_content_ids": ["faq-account-001", "faq-account-002"],
  "is_demo": false
}
```

#### 응답

**상태 코드:** 200 OK
**Content-Type:** `application/json`

**Body Schema (`QuestionResponse`):**

| 필드                  | 타입    | 설명                                                                            |
| --------------------- | ------- | ------------------------------------------------------------------------------- |
| `question`            | string  | 생성된 고객 질문 텍스트                                                          |
| `question_id`         | string  | 채점 시 식별자. 일반 모드: `q-{source_content_id}`. 데모 모드: 골든답 ID 그대로   |
| `source_content_id`   | string  | 출처 ChromaDB content ID. 채점 시 Direct Fetch에 사용                            |
| `difficulty`          | string  | 요청한 난이도를 그대로 echo                                                      |
| `is_reset`            | boolean | 풀 소진 후 재추출 발생 여부. true이면 프론트는 `solved_content_ids`를 비워야 함  |

**예시 (일반 모드):**

```json
{
  "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
  "question_id": "q-{doc_id}_{block_order}",
  "source_content_id": "{doc_id}_{block_order}",
  "difficulty": "beginner",
  "is_reset": false
}
```

**예시 (데모 모드):**

```json
{
  "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
  "question_id": "q-demo-001",
  "source_content_id": "q-demo-001",
  "difficulty": "beginner",
  "is_reset": false
}
```

#### 에러

| 상태 | detail 예시                                                       | 원인                                                          |
| ---- | ----------------------------------------------------------------- | ------------------------------------------------------------- |
| 400  | `"ChromaDB에 출제 가능한 콘텐츠가 없습니다. 인제스트를 먼저 실행하세요."` | 일반 모드 + 인제스트 미수행                                   |
| 400  | `"데모 질문을 찾을 수 없습니다: {id}"`                            | 데모 모드 내부 매칭 실패                                      |
| 422  | (FastAPI 표준)                                                    | `difficulty` enum 위반 등                                     |

#### 클라이언트 처리 가이드

```text
응답 수신
 └─ data.is_reset === true 이면
       solvedContentIds = [data.source_content_id]
    else
       solvedContentIds = [...solvedContentIds, data.source_content_id]
```

(현재 구현: `frontend/src/components/training/TrainingScreen.jsx`)

---

### 3.2 `POST /api/training/score` — 답변 채점

#### 요약
신입의 답변을 수동 정답(우선) 또는 출처 문서 Direct Fetch 기준으로 LLM 채점한다.

> ⚠️ **현재 구현 상태:** `services/scorer.py`는 placeholder. 라우터(`routers/training.py`)는 0점/빈 값 응답을 반환. 본 명세는 `api-spec.md` §1, §5의 확정 스펙이며 구현 시 본 형식을 준수해야 한다.

#### 요청

| 항목         | 값                       |
| ------------ | ------------------------ |
| Method       | POST                     |
| Path         | `/api/training/score`    |
| Content-Type | `application/json`       |

**Body Schema (`ScoreRequest`):**

| 필드             | 타입   | 필수 | 설명                                                |
| ---------------- | ------ | ---- | --------------------------------------------------- |
| `question_id`    | string | ✓    | `/training/question` 응답의 `question_id`           |
| `trainee_answer` | string | ✓    | 신입이 입력한 답변 (1자 이상)                        |

**예시:**

```json
{
  "question_id": "q-001",
  "trainee_answer": "신분증이랑 통장 가져오시면 됩니다."
}
```

#### 응답

**상태 코드:** 200 OK
**Content-Type:** `application/json`

**Body Schema (`ScoreResponse`):**

| 필드             | 타입       | 설명                                                          |
| ---------------- | ---------- | ------------------------------------------------------------- |
| `score`          | int (0~100)| 종합 점수                                                      |
| `included_items` | string[]   | 답변에 포함된 필수 항목 목록                                   |
| `missing_items`  | string[]   | 누락된 필수 항목 목록                                          |
| `feedback`       | string     | 자연어 피드백 (장점/개선점)                                    |
| `reference`      | string     | 출처 표시 (예: "계좌업무편람 p.23 제5조")                      |
| `model_answer`   | string     | 모범 답안 텍스트 (수동 정답 우선, 없으면 LLM이 본문 기반 생성) |

**예시:**

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

#### 채점 정답 우선순위 (api-spec.md §5)

```
1. tests/training_golden_answers.json 에서 question_id로 수동 정답 조회
   → 있으면 그 정답을 기준으로 채점
2. 수동 정답이 없으면
   → source_content_id 로 ChromaDB 에서 원본 content Direct Fetch
   → LLM 에 "본문 기반 모범 답안 + 채점" 위임
```

> ❌ 채점 시 RAG **재검색을 하지 않는다**. 출제 시점에 출처가 확정되어 있으므로 재검색은 동문서답 리스크와 비용 낭비를 초래한다 (ADR-0005).

#### 에러 (예상)

| 상태 | 발생 시점                                              |
| ---- | ------------------------------------------------------ |
| 400  | `question_id`로 수동 정답/source_content_id 둘 다 매칭 실패 |
| 422  | 스키마 위반                                            |
| 500  | LLM JSON 파싱 실패 등                                  |

---

## 4. 헬스체크

### 4.1 `GET /health`

| 항목   | 값      |
| ------ | ------- |
| Method | GET     |
| Path   | `/health` |

**응답:**
```json
{ "status": "ok" }
```

---

## 5. 데이터 형식 카탈로그

### 5.1 FAQ JSON (입력 데이터, `data/processed/faq.json` 형식)

```json
{
  "id": "faq-account-001",
  "category": "계좌",
  "title": "비대면 계좌 개설 절차",
  "similar_titles": [
    "온라인으로 계좌 만드는 방법",
    "비대면 계좌 개설 어떻게 하나요"
  ],
  "content": "...",
  "source": {
    "document": "계좌업무편람",
    "page": "p.23",
    "section": "제5조"
  }
}
```

### 5.2 ParsedDocument (PDF 파싱 산출물, `data/processed/{doc_id}/docling.json`)

`backend/models/parsed_document.py`:

```python
class Block(BaseModel):
    text: str
    block_type: str = "paragraph"   # heading | paragraph | rule | table | table_row
    page: int | None = None
    order: int
    heading_level: int | None = None
    hierarchy_path: list[str] | None = None
    canonical_text: str | None = None

class ParsedDocument(BaseModel):
    doc_id: str
    source_path: str
    doc_type: str = "manual"       # manual | notice | faq
    title: str | None = None
    document_path: list[str] | None = None
    page_count: int | None = None
    blocks: list[Block]
    meta: dict
```

### 5.3 Golden Answer (`tests/training_golden_answers.json`)

```json
[
  {
    "question_id": "q-demo-001",
    "scenario": "초급 — 계좌 개설",
    "question": "계좌 개설하려면 어떤 서류가 필요한가요?",
    "golden_answer": "...",
    "required_items": ["신분증", "CDD 서류", "비대면 시 영상통화"],
    "reference": "계좌업무편람 p.23 제5조"
  }
]
```

---

## 6. 변경 절차

1. **API 변경이 필요하면**: `docs/api-spec.md`에 먼저 반영하고 변경 이력 갱신.
2. **본 문서(`api-spec-formal.md`)**: 그 후 동기화. 양 문서가 어긋나면 `api-spec.md`가 우선한다.
3. **코드 반영**: `routers/*.py`, `services/*.py` 순서로 수정. Pydantic 모델은 본 명세와 1:1 매칭.
4. **커밋 컨벤션**: 코드 변경은 `feat:`/`fix:`, 프롬프트 변경은 `prompt:` (RULES.md §커밋 컨벤션).

---

## 7. 관련 문서

- [docs/api-spec.md](./api-spec.md) — **단일 진실 소스**, 설계 결정 로그 포함
- [docs/architecture.md](./architecture.md) — 시스템 구성도
- [docs/data-flow.md](./data-flow.md) — 시퀀스/DFD
- [docs/db-design.md](./db-design.md) — 스토리지 스키마
- [docs/adr/](./adr/) — 설계 결정 기록
