# 데이터 흐름도

> 증권 상담원 AI 코치 PoC — DFD 및 주요 시나리오 시퀀스
>
> Last Updated: 2026-05-08

---

## 1. 데이터 흐름 개요 (Level 0 — Context Diagram)

```mermaid
flowchart LR
  Operator([상담원])
  Trainee([신입 상담원])
  Admin([관리자])
  System(((증권 상담원<br/>AI 코치)))
  Manuals[(업무편람 PDF)]
  Goldens[(수동 정답<br/>golden answers)]
  LLM([Google AI Studio])

  Operator -->|질문| System
  System -->|답변+출처| Operator

  Trainee -->|난이도/카테고리,<br/>답변 입력| System
  System -->|고객 질문,<br/>채점 결과| Trainee

  Admin -->|편람 PDF 업로드| Manuals
  Admin -->|정답 작성| Goldens
  Manuals -->|인제스트 (배치)| System
  Goldens -->|로딩| System

  System <-->|임베딩/생성<br/>HTTPS| LLM
```

---

## 2. Level 1 — 주요 데이터 처리 단위 (DFD)

```mermaid
flowchart LR
  subgraph S0["[1.0] 인제스트 파이프라인 (배치)"]
    direction LR
    P1["1.1 PDF 파싱<br/>(docling_pdf.py)"] --> P2["1.2 블록 청킹<br/>(ingest_manual.py)"]
    P2 --> P3["1.3 임베딩 호출<br/>(GeminiService.embed)"]
    P3 --> P4["1.4 ChromaDB upsert<br/>(faq_titles/contents)"]
  end

  PDF[("data/raw/*.pdf")] --> P1
  P1 --> Docling[("data/processed/<br/>{doc_id}/docling.json")]
  Docling --> P2
  P3 -->|3072-d 벡터| P4
  P4 --> Chroma[("ChromaDB")]

  subgraph S1["[2.0] 챗봇 모드 (실시간)"]
    direction LR
    C1["2.1 질문 임베딩"] --> C2["2.2 dual-collection 검색<br/>(titles+contents)"]
    C2 --> C3["2.3 Max Pooling<br/>+ 가중 병합"]
    C3 --> C4["2.4 LLM 답변 생성<br/>(stream)"]
  end

  Operator([상담원 질문]) --> C1
  Chroma --> C2
  Prompt1[("prompts/<br/>chat_system.txt")] --> C4
  C3 -->|sources, confidence| AnsOut1[/SSE: event=sources/]
  C4 -->|token chunks| AnsOut2[/SSE: event=token/]
  AnsOut1 & AnsOut2 --> Operator2([상담원 화면])

  subgraph S2["[3.0] 훈련 — 출제 (실시간)"]
    direction LR
    Q1["3.1 source 선택<br/>(데모/일반 분기)"] --> Q2["3.2 Direct Fetch<br/>(content_id로 본문)"]
    Q2 --> Q3["3.3 LLM 질문 생성<br/>(고객 역할)"]
  end

  Trainee1([신입: 카테고리/난이도]) --> Q1
  Goldens[("training_golden_<br/>answers.json")] -.is_demo=true.-> Q1
  Chroma -.is_demo=false.-> Q1
  Chroma --> Q2
  Prompt2[("prompts/<br/>training_customer.txt")] --> Q3
  Q3 --> QOut[/question, question_id,<br/>source_content_id, is_reset/] --> Trainee2([신입 화면])

  subgraph S3["[4.0] 훈련 — 채점 (실시간) — TODO"]
    direction LR
    SC1["4.1 정답 소스 선택<br/>(수동 우선)"] --> SC2["4.2 Direct Fetch<br/>(RAG 재검색 안 함)"]
    SC2 --> SC3["4.3 LLM 채점<br/>(JSON 구조화 출력)"]
  end

  Trainee3([신입 답변]) --> SC1
  Goldens --> SC1
  Chroma --> SC2
  Prompt3[("prompts/<br/>training_scorer.txt")] --> SC3
  SC3 --> SCOut[/score, included/missing,<br/>feedback, model_answer/] --> Trainee4([신입 화면])
```

> 4.0 채점 흐름은 `services/scorer.py`가 현재 TODO 상태이며, [docs/api-spec.md 섹션 5](./api-spec.md) 명세 기준으로 구현될 예정.

---

## 3. 주요 시퀀스 다이어그램

### 3.1 챗봇 모드 — 단일 질문 처리 (SSE 스트리밍)

```mermaid
sequenceDiagram
    autonumber
    participant U as 상담원 (브라우저)
    participant FE as React (Vite :3000)
    participant API as FastAPI (:8000)
    participant RAG as RAGService
    participant LLM as GeminiService
    participant CDB as ChromaDB

    U->>FE: 질문 입력
    FE->>API: POST /api/chat {question}
    activate API
    API->>RAG: search(query)
    activate RAG
    RAG->>LLM: embed([query])
    LLM-->>RAG: query 벡터 (3072-d)
    RAG->>CDB: faq_titles.query(top=10)
    CDB-->>RAG: ids, distances
    RAG->>RAG: _max_pool_titles<br/>(_sim 접미사 제거)
    RAG->>CDB: faq_contents.query(top=10)
    CDB-->>RAG: ids, distances
    RAG->>RAG: 가중 병합<br/>(TITLE_WEIGHT*t + CONTENT_WEIGHT*c)
    RAG->>CDB: titles.get / contents.get<br/>(top_k에 메타 부착)
    CDB-->>RAG: documents, metadatas
    RAG-->>API: contexts[]  (top_k=5)
    deactivate RAG

    Note over API,FE: ⓐ sources 우선 전송 (api-spec 섹션 1)
    API-->>FE: SSE event=sources<br/>{sources, confidence}
    FE-->>U: 출처/신뢰도 즉시 렌더

    API->>LLM: generate_stream(messages)
    activate LLM
    loop chunk 수신마다
      LLM-->>API: 토큰 청크
      API-->>FE: SSE event=token {text}
      FE-->>U: 답변 점진 렌더
    end
    deactivate LLM

    API-->>FE: SSE event=done
    deactivate API
```

**성능 목표:** 첫 토큰 1초 이내, 전체 5초 이내 (api-spec.md §1).

---

### 3.2 훈련 모드 — 일반 출제 (LLM 즉석 생성)

```mermaid
sequenceDiagram
    autonumber
    participant U as 신입 (브라우저)
    participant FE as React
    participant API as FastAPI
    participant Q as question_gen
    participant CDB as ChromaDB
    participant LLM as GeminiService

    U->>FE: 난이도/카테고리 선택, "새 질문" 클릭
    FE->>API: POST /api/training/question<br/>{difficulty, category,<br/>solved_content_ids: [...], is_demo: false}
    API->>Q: generate_training_question(...)
    Q->>CDB: contents_col.get(limit=10000)
    CDB-->>Q: 모든 ID + metadata
    Q->>Q: select_source<br/>(solved_content_ids 제외 후 random)

    alt 소진되어 재추출 발생
        Q-->>Q: is_reset = true
    else 정상 추출
        Q-->>Q: is_reset = false
    end

    Q->>CDB: titles/contents.get(ids=[selected])
    CDB-->>Q: title, content
    Q->>LLM: generate(training_customer 프롬프트<br/>+ {content, difficulty})
    LLM-->>Q: 고객 질문 텍스트
    Q-->>API: {question, question_id, source_content_id,<br/>difficulty, is_reset}
    API-->>FE: 200 OK
    FE->>FE: solved_content_ids 갱신<br/>(is_reset이면 [source_content_id]로 초기화)
    FE-->>U: 질문 표시 + 답변 입력란
```

---

### 3.3 훈련 모드 — 데모 출제 (수동 정답 사전 매칭)

```mermaid
sequenceDiagram
    autonumber
    participant FE as React
    participant API as FastAPI
    participant Q as question_gen
    participant FS as training_golden_answers.json

    FE->>API: POST /api/training/question {is_demo: true, ...}
    API->>Q: generate_training_question(is_demo=true)
    Q->>FS: 파일 로드
    FS-->>Q: [{question_id, question, golden_answer, ...}]
    Q->>Q: select_source<br/>(solved 제외 random.choice)
    Q-->>API: {question, question_id, source_content_id, is_reset}
    Note right of Q: ⚠ LLM 미호출.<br/>question_id가 golden_answers와<br/>일치하므로 채점 시 수동 정답 사용 가능
    API-->>FE: 200 OK
```

---

### 3.4 훈련 모드 — 채점 (TODO 명세 기준)

```mermaid
sequenceDiagram
    autonumber
    participant FE as React
    participant API as FastAPI
    participant S as scorer (TODO)
    participant FS as golden_answers
    participant CDB as ChromaDB
    participant LLM as GeminiService

    FE->>API: POST /api/training/score<br/>{question_id, trainee_answer}
    API->>S: score(question_id, trainee_answer)
    S->>FS: 파일 조회
    alt 수동 정답 존재
        FS-->>S: golden_answer, required_items, reference
        S->>LLM: generate(scorer 프롬프트,<br/>golden 기준, JSON mode)
    else 수동 정답 없음 (일반 모드 question_id)
        S->>S: question_id → source_content_id 매핑<br/>("q-{id}" prefix 제거)
        S->>CDB: contents_col.get(ids=[source_content_id])
        Note right of CDB: Direct Fetch — RAG 재검색 안 함<br/>(api-spec.md §5)
        CDB-->>S: title, content
        S->>LLM: generate(scorer 프롬프트,<br/>본문 기준, JSON mode)
    end
    LLM-->>S: {score, included_items,<br/>missing_items, feedback,<br/>model_answer}
    S-->>API: ScoreResponse
    API-->>FE: 200 OK
```

---

### 3.5 인제스트 파이프라인 (배치)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as 관리자
    participant CLI1 as scripts/parse_pdf.py
    participant Doc as docling_pdf.py
    participant FS as 파일 시스템
    participant CLI2 as scripts/ingest_manual.py
    participant LLM as GeminiService
    participant CDB as ChromaDB

    Admin->>CLI1: -i data/raw/manual.pdf
    CLI1->>Doc: parse_pdf(path)
    Doc->>Doc: Docling Converter 실행<br/>(table_structure, OCR)
    Doc->>Doc: 블록 수집<br/>(heading/paragraph/table/table_row)
    Doc-->>CLI1: ParsedDocument
    CLI1->>FS: data/processed/{doc_id}/docling.json

    Admin->>CLI2: --all (또는 -i)
    CLI2->>FS: docling.json 로드
    CLI2->>CLI2: chunk_blocks(<br/>paragraph: 150~400 tokens, 12% overlap<br/>procedure: 150~350, 10%<br/>그 외: 1블록=1청크)
    CLI2->>CLI2: title_text/content_text 분리
    CLI2->>LLM: embed(titles, batch=100)
    LLM-->>CLI2: title 벡터
    CLI2->>LLM: embed(contents, batch=100)
    LLM-->>CLI2: content 벡터
    CLI2->>CDB: faq_titles.upsert(ids, docs, embeddings, metas)
    CLI2->>CDB: faq_contents.upsert(ids, docs, embeddings, metas)
    CDB-->>CLI2: OK
    CLI2-->>Admin: 적재 청크 수 로그
```

---

## 4. 데이터 객체 흐름표

| # | 객체              | 생성 위치                          | 형식                              | 소비처                              |
| - | ----------------- | ---------------------------------- | --------------------------------- | ----------------------------------- |
| 1 | PDF 원본          | `data/raw/`                        | PDF                               | `parse_pdf.py`                      |
| 2 | `ParsedDocument`  | `docling_pdf.py`                   | Pydantic / JSON                   | `ingest_manual.py`                  |
| 3 | docling.json      | `data/processed/{doc_id}/`         | JSON                              | `ingest_manual.py`                  |
| 4 | Chunk             | `ingest_manual.chunk_blocks`       | dict (title_text, content_text)   | embedder, ChromaDB                  |
| 5 | 임베딩 벡터        | `GeminiService.embed`              | `list[float]` (3072-d)            | ChromaDB upsert/query               |
| 6 | RAG contexts       | `RAGService.search`                | `list[{id, title, content, score, source_*}]` | LLM 프롬프트 빌더, 응답 sources |
| 7 | SSE 이벤트         | `routers/chat.py`(예정)            | `event: sources/token/done`       | 프론트 렌더링                        |
| 8 | golden_answer      | `tests/training_golden_answers.json` | JSON                              | `question_gen`(데모), `scorer`     |
| 9 | ScoreResponse      | `scorer.py`(TODO)                  | JSON                              | 프론트                                |

---

## 5. 흐름상 주의 사항

| 흐름             | 주의                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------ |
| RAG 점수 계산    | **Max Pooling 후 가중 병합** 순서 엄수 (api-spec.md §3, ADR-0003)                          |
| SSE              | sources를 **첫 이벤트로** 전송. 답변 토큰보다 먼저 (ADR-0004)                              |
| 출제→채점 연계   | 출제 시점 `source_content_id`로 채점 시 Direct Fetch. **RAG 재검색 금지** (ADR-0005)        |
| 데모/일반 분기   | `is_demo=true`이면 LLM 미호출. `question_id`가 골든답과 매칭 가능해야 함 (ADR-0007)         |
| solved 상태       | 서버는 Stateless. 프론트가 `solved_content_ids` 보유, `is_reset=true`이면 클라이언트 초기화 (ADR-0006) |
| 임베딩 차원       | 모델 교체 시 ChromaDB 전체 재인제스트 필요 (3072-d ↔ 1536-d 등) (ADR-0008)                |

---

## 6. 관련 문서

- [docs/architecture.md](./architecture.md) — 컴포넌트 구조
- [docs/api-spec.md](./api-spec.md) — API/스키마 single source of truth
- [docs/api-spec-formal.md](./api-spec-formal.md) — 정형화된 API 명세
- [docs/db-design.md](./db-design.md) — 스토리지 설계
- [docs/adr/](./adr/) — 설계 결정 기록
