# 증권 상담원 AI 코치

> 업무 챗봇 + 신입 교육 시뮬레이터 (PoC, 4주)

## 프로젝트 개요

증권사 상담원을 위한 AI 지원 시스템. 두 가지 모드로 동작한다.

- **챗봇 모드**: 상담원이 질문 → FAQ/편람 기반 즉시 답변 + 출처 표시
- **훈련 모드**: AI가 고객 역할 → 신입이 답변 → AI가 채점 + 피드백

## 기술 스택

| 항목 | PoC | 실도입 |
|------|-----|--------|
| LLM | GPT-4o API | Qwen3-30B-A3B MoE |
| 임베딩 | text-embedding-3-small | bge-m3 |
| 벡터DB | ChromaDB (파일 기반) | 동일 |
| 백엔드 | Python FastAPI | 동일 |
| 프론트엔드 | React | 동일 |

## 설치 및 실행

```bash
# 1. 클론
git clone <repo-url>
cd securities-ai-coach

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 입력

# 3. 백엔드 (프로젝트 루트에서 실행)
pip install -r requirements.txt
uvicorn backend.main:app --reload

# 4. 프론트엔드 (2주차~)
cd frontend
npm install
npm start
```

## 디렉토리 구조

```
project/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── data/
│   ├── raw/              # 원본 PDF, FAQ (Git 미포함)
│   ├── processed/        # 정제된 JSON
│   └── chroma_db/        # ChromaDB 저장소 (Git 미포함)
│
├── backend/
│   ├── main.py           # FastAPI 엔트리포인트
│   ├── config.py         # 설정 관리
│   ├── routers/
│   │   ├── chat.py       # 챗봇 모드 API
│   │   └── training.py   # 훈련 모드 API
│   ├── services/
│   │   ├── rag.py        # RAG 파이프라인
│   │   ├── embedder.py   # 임베딩 서비스
│   │   ├── scorer.py     # 채점 서비스
│   │   └── question_gen.py
│   ├── prompts/
│   │   ├── chat_system.txt
│   │   ├── training_customer.txt
│   │   └── training_scorer.txt
│   └── utils/
│       ├── pdf_parser.py
│       ├── multi_title.py
│       └── logger.py
│
├── frontend/             # 2주차부터 개발
│   └── ...
│
├── scripts/
│   ├── ingest_faq.py
│   ├── ingest_manual.py
│   ├── generate_titles.py
│   └── test_accuracy.py
│
├── docs/
│   ├── api-spec.md       # API 스펙 (팀 합의)
│   └── adr/              # 설계 결정 기록 (필요 시 추가)
│
└── tests/
    ├── test_rag.py
    └── test_questions.json
```

## 브랜치 전략

```
main     ← 안정 버전만
dev      ← 개발 통합 브랜치
feature/ ← 기능별 브랜치 (feature/rag-pipeline, feature/data-pipeline 등)
```

## PR 규칙 (간소화)

```
모든 PR에 아래 3줄만 필수:

1. 뭘 했는지 (한 줄)
2. AI 사용했으면: 핵심 프롬프트 한 줄 + 왜 이렇게 짰는지 한 줄
3. 테스트 방법 (한 줄)
```

**PR 예시:**

```markdown
## 변경 사항
ChromaDB 2개 컬렉션(제목/내용)에서 검색 후 점수 병합하는 RAG 검색 함수 구현

## AI 사용
- 프롬프트: "ChromaDB 2개 컬렉션 쿼리 후 document ID 기준 점수 가중 병합하는 함수"
- 핵심: 양쪽 결과를 dict로 변환 → ID 교집합에서 weighted sum → top-k 반환

## 테스트
CLI에서 "비대면 계좌 개설" 질문 → 관련 FAQ 3건 반환 확인
```

## 보안 주의

- API 키 → `.env` (절대 코드에 하드코딩 금지)
- 고객사 편람/FAQ 원본 → `.gitignore` (data/raw/, data/chroma_db/)
- 데모 시 실제 고객 정보 노출 금지

## 주차별 마일스톤

| 주차 | 목표 | 확인 방법 |
|------|------|----------|
| 1주차 | CLI에서 질문→답변+출처 동작 | 터미널 테스트 |
| 2주차 | 웹 UI 챗봇 동작 + 정확도 리포트 | 브라우저 데모 |
| 3주차 | 챗봇 정확도 80%+ | 30개 테스트셋 |
| 4주차 | 챗봇+훈련 모드 데모 완료 | 리허설 통과 |
