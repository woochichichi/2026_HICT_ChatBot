# 증권 상담원 AI 코치

> "물어보면 답하고, 답하면 채점하는 AI"
> 업무 챗봇 + 신입 교육 시뮬레이터 (PoC, 4주)

---

## 온보딩 — 이것부터 읽기

| 순서 | 문서 | 내용 | 언제 보나 |
|------|------|------|-----------|
| 1 | **이 README** | 프로젝트 개요, 세팅, 역할, 일정, 규칙 | 합류 즉시 |
| 2 | [`docs/api-spec.md`](docs/api-spec.md) | API 스펙, 데이터 스키마, ChromaDB 구조, 설계 리뷰, 리스크, 액션 아이템 | 킥오프 전 |
| 3 | `backend/prompts/*.txt` | 챗봇·훈련 모드 시스템 프롬프트 (수정 빈도 높음) | 개발 시작 전 |

> 📌 `SETUP_PROMPT.md`는 초기 폴더 생성용 AI 프롬프트. 이미 세팅 완료되어 참고용으로만 보면 됨.

---

## 프로젝트 개요

증권사 상담원을 위한 AI 지원 시스템. 두 가지 모드로 동작한다.

- **챗봇 모드**: 상담원이 질문 → FAQ/편람 기반 즉시 답변 + 출처 표시
- **훈련 모드**: AI가 고객 역할 → 신입이 답변 → AI가 채점 + 피드백

### 기술 스택

| 항목 | PoC | 실도입 (폐쇄망) |
|------|-----|------------------|
| LLM | GPT-4o API | Qwen3-30B-A3B MoE |
| 임베딩 | text-embedding-3-small | bge-m3 |
| 벡터DB | ChromaDB (파일 기반) | 동일 |
| 백엔드 | Python FastAPI | 동일 |
| 프론트엔드 | React | 동일 |

---

## 로컬 세팅

```bash
# 1. 클론
git clone <repo-url>
cd 2026_HICT_ChatBot

# 2. 환경변수
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 입력

# 3. 백엔드 (프로젝트 루트에서 실행)
pip install -r requirements.txt
uvicorn backend.main:app --reload
# → http://localhost:8000/docs 에서 Swagger 확인

# 4. 프론트엔드 (2주차~)
cd frontend
npm install
npm start
# → http://localhost:3000
```

### 환경변수 (.env)

```
OPENAI_API_KEY=your-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o
CHROMA_DB_PATH=./data/chroma_db
```

---

## 역할 분담

| 영역 | 팀 리드 (Woochi) | 개발자A |
|------|-------------------|---------|
| **백엔드** | FastAPI 골격, RAG 파이프라인, 임베딩 서비스, 채점 로직 | - |
| **데이터** | - | FAQ 정제, PDF 파싱 테스트, 인제스트 스크립트 |
| **프론트** | - | React 채팅 UI, 모드 전환, 출처 표시, 채점 결과 |
| **프롬프트** | 챗봇·훈련 모드 시스템 프롬프트 설계 및 튜닝 | - |
| **인프라** | - | 온프레미스 로드맵 문서, 발표 자료 |
| **공통** | 정확도 테스트, 데모 시나리오 | 정확도 테스트, 데모 시나리오 |

### AI 도구 사용 원칙

1. AI가 생성한 코드는 작성자가 설명할 수 있어야 한다
2. AI에 작업 위임 전 팀원 합의
3. AI 대화에서 나온 설계 결정은 반드시 문서화 (`docs/api-spec.md` 업데이트)
4. **이 리포의 `docs/api-spec.md`를 각자 AI 도구(Claude, Cursor)에 프로젝트 컨텍스트로 등록** — 양쪽 AI가 같은 스펙을 참조하게 함

---

## 개발 일정

### 1주차: 기반 구축

| 담당 | 작업 |
|------|------|
| 팀 리드 | FastAPI 골격, 임베딩 서비스, ChromaDB 셋업, RAG 파이프라인 |
| 개발자A | FAQ 데이터 정제, PDF 파싱 테스트, 인제스트 스크립트 |
| **마일스톤** | **CLI에서 질문 → 답변 + 출처 동작 확인** |

### 2주차: 챗봇 모드 완성 ← 핵심 데드라인

| 담당 | 작업 |
|------|------|
| 팀 리드 | 다중 제목 생성, 프롬프트 튜닝, 정확도 테스트 |
| 개발자A | React 채팅 UI, 출처 표시 컴포넌트, API 연동 |
| **마일스톤** | **웹 UI에서 챗봇 동작 + 정확도 리포트** |

### 3주차: 챗봇 강화 + 훈련 모드 설계

| 담당 | 작업 |
|------|------|
| 팀 리드 | 임베딩 가중치 튜닝, 엣지케이스, 로깅, 채점 프롬프트 설계 |
| 개발자A | 출처 하이라이트 UI, 모드 전환 UI, 훈련 모드 결과 화면 |
| **마일스톤** | **챗봇 정확도 80%+, 채점 프롬프트 초안 완성** |

### 4주차: 훈련 모드 + 데모

| 담당 | 작업 |
|------|------|
| 팀 리드 | 훈련 모드 백엔드 (질문 생성 + 채점), 데모 시나리오 |
| 개발자A | 훈련 모드 UI 연동, 발표 자료, 온프레미스 로드맵 문서 |
| **마일스톤** | **챗봇 + 훈련 모드 데모 리허설 완료** |

---

## 디렉토리 구조

```
2026_HICT_ChatBot/
├── README.md                 ← 지금 보는 파일
├── SETUP_PROMPT.md           ← 초기 세팅용 (참고용)
├── requirements.txt
├── .env.example
│
├── docs/
│   ├── api-spec.md           ← API 스펙 + 설계 리뷰 (핵심 문서)
│   └── adr/                  ← 설계 결정 기록 (필요 시)
│
├── backend/
│   ├── main.py               ← FastAPI 엔트리포인트
│   ├── config.py
│   ├── routers/
│   │   ├── chat.py           ← 챗봇 모드 API
│   │   └── training.py       ← 훈련 모드 API
│   ├── services/
│   │   ├── rag.py            ← RAG 파이프라인
│   │   ├── embedder.py       ← 임베딩 서비스 (추상화)
│   │   ├── scorer.py         ← 채점 서비스
│   │   └── question_gen.py   ← 질문 생성
│   ├── prompts/              ← 프롬프트 (변경 빈번, 별도 커밋)
│   │   ├── chat_system.txt
│   │   ├── training_customer.txt
│   │   └── training_scorer.txt
│   └── utils/
│
├── frontend/                 ← 2주차부터
├── scripts/                  ← 인제스트, 정확도 테스트
├── data/
│   ├── raw/                  ← 원본 PDF/FAQ (Git 미포함)
│   ├── processed/            ← 정제된 JSON
│   └── chroma_db/            ← 벡터DB (Git 미포함)
│
└── tests/
    ├── test_rag.py
    └── test_questions.json   ← 정확도 테스트 30개 세트
```

---

## 브랜치 & 커밋 규칙

### 브랜치

```
main     ← 안정 버전만
dev      ← 개발 통합
feature/ ← 기능별 (feature/rag-pipeline, feature/chat-ui 등)
```

### 커밋 메시지

```
feat:    새 기능
fix:     버그 수정
docs:    문서 수정
prompt:  프롬프트 변경 (코드 변경과 절대 같은 커밋에 섞지 않기)
chore:   기타
```

### PR 규칙

모든 PR에 아래 3줄만 필수 (`.github/PULL_REQUEST_TEMPLATE.md` 자동 적용):

```
1. 뭘 했는지 (한 줄)
2. AI 사용했으면: 핵심 프롬프트 + 왜 이렇게 짰는지 (한 줄)
3. 테스트 방법 (한 줄)
```

---

## 보안 주의

- API 키 → `.env` (절대 하드코딩 금지)
- 고객사 편람/FAQ 원본 → `.gitignore` (`data/raw/`, `data/chroma_db/`)
- 데모 시 실제 고객 정보 노출 금지
- 로깅 시 개인정보 마스킹

---

## 성공 기준

| 모드 | 지표 | 목표 |
|------|------|------|
| 챗봇 | 답변 정확도 | 80%+ (30개 테스트셋) |
| 챗봇 | 출처 정확도 | 90%+ |
| 챗봇 | 응답 시간 | 3초 이내 |
| 챗봇 | 할루시네이션율 | 5% 미만 |
| 훈련 | 채점 일치율 | 75%+ (전문가 대비) |
