# 프로젝트 초기 세팅 프롬프트

아래 프롬프트를 VSCode에서 Claude AI에게 그대로 붙여넣으세요.

---

증권 상담원 AI 코치 프로젝트의 초기 폴더 구조와 기본 파일들을 생성해줘.

## 폴더 구조

```
securities-ai-coach/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── data/
│   ├── raw/              # .gitkeep만
│   ├── processed/        # .gitkeep만
│   └── chroma_db/        # .gitkeep만
│
├── backend/
│   ├── __init__.py
│   ├── main.py           # FastAPI 엔트리포인트
│   ├── config.py         # 설정 관리
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py       # 챗봇 모드 API (빈 엔드포인트)
│   │   └── training.py   # 훈련 모드 API (빈 엔드포인트)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rag.py        # RAG 파이프라인 (빈 클래스)
│   │   ├── embedder.py   # 임베딩 서비스 (빈 클래스)
│   │   ├── scorer.py     # 채점 서비스 (빈 클래스)
│   │   └── question_gen.py  # 질문 생성 (빈 클래스)
│   ├── prompts/
│   │   ├── chat_system.txt
│   │   ├── training_customer.txt
│   │   └── training_scorer.txt
│   └── utils/
│       ├── __init__.py
│       ├── pdf_parser.py    # (빈 파일)
│       ├── multi_title.py   # (빈 파일)
│       └── logger.py        # (빈 파일)
│
├── frontend/              # 2주차부터 개발, 빈 폴더
│   └── .gitkeep
│
├── scripts/
│   ├── ingest_faq.py      # (빈 파일)
│   ├── ingest_manual.py   # (빈 파일)
│   ├── generate_titles.py # (빈 파일)
│   └── test_accuracy.py   # (빈 파일)
│
├── docs/
│   ├── api-spec.md
│   └── adr/
│       └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── test_rag.py        # (빈 파일)
    └── test_questions.json # 빈 배열 []
```

## 각 파일 내용

### .env.example
```
OPENAI_API_KEY=your-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o
CHROMA_DB_PATH=./data/chroma_db
```

### .gitignore
```
# 환경변수
.env

# 데이터 (고객사 문서 보호)
data/raw/*
data/chroma_db/*
!data/raw/.gitkeep
!data/chroma_db/.gitkeep

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Node
node_modules/
frontend/build/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

### requirements.txt
```
fastapi>=0.110.0,<1.0.0
uvicorn>=0.29.0,<1.0.0
openai>=1.40.0,<2.0.0
chromadb>=0.5.0,<1.0.0
python-dotenv>=1.0.0,<2.0.0
pydantic>=2.0.0,<3.0.0
pymupdf>=1.24.0,<2.0.0
camelot-py[cv]>=0.11.0,<1.0.0
```

### .github/PULL_REQUEST_TEMPLATE.md
```markdown
## 변경 사항
- 

## AI 사용
- [ ] AI 미사용
- [ ] AI 사용
  - 프롬프트: 
  - 핵심 로직: 

## 테스트
- 
```

### backend/config.py
```python
"""프로젝트 설정 관리."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """환경변수 기반 설정."""

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")


settings = Settings()
```

### backend/main.py
```python
"""FastAPI 엔트리포인트.

실행 방법 (프로젝트 루트에서):
  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, training

app = FastAPI(title="증권 상담원 AI 코치", version="0.1.0")

# 프론트엔드 연동 대비 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(training.router, prefix="/api/training", tags=["training"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

### backend/routers/chat.py
```python
"""챗봇 모드 API."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class Source(BaseModel):
    title: str
    reference: str
    relevance_score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: str  # high / medium / low


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # TODO: RAG 파이프라인 연동
    return ChatResponse(
        answer="아직 구현되지 않았습니다.",
        sources=[],
        confidence="low",
    )
```

### backend/routers/training.py
```python
"""훈련 모드 API."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QuestionRequest(BaseModel):
    difficulty: str  # beginner / intermediate / advanced
    category: str


class QuestionResponse(BaseModel):
    question: str
    question_id: str
    source_content_id: str
    difficulty: str


class ScoreRequest(BaseModel):
    question_id: str
    trainee_answer: str


class ScoreResponse(BaseModel):
    score: int
    included_items: list[str]
    missing_items: list[str]
    feedback: str
    reference: str
    model_answer: str


@router.post("/question", response_model=QuestionResponse)
async def generate_question(request: QuestionRequest):
    # TODO: 질문 생성 서비스 연동
    return QuestionResponse(
        question="아직 구현되지 않았습니다.",
        question_id="",
        source_content_id="",
        difficulty=request.difficulty,
    )


@router.post("/score", response_model=ScoreResponse)
async def score_answer(request: ScoreRequest):
    # TODO: 채점 서비스 연동
    return ScoreResponse(
        score=0,
        included_items=[],
        missing_items=[],
        feedback="아직 구현되지 않았습니다.",
        reference="",
        model_answer="",
    )
```

### backend/services/embedder.py
```python
"""임베딩 서비스 — LLM 전환 대비 추상화."""

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """임베딩 서비스 인터페이스."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 변환."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """텍스트 배치를 벡터 배치로 변환."""
        ...


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI 임베딩 구현체. PoC용."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        # TODO: OpenAI 클라이언트 초기화

    async def embed(self, text: str) -> list[float]:
        # TODO: 구현
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # TODO: 구현
        raise NotImplementedError
```

### backend/services/rag.py
```python
"""RAG 파이프라인 — 검색 + 답변 생성."""


class RAGService:
    """
    검색 흐름:
    1. 사용자 질문으로 faq_titles 컬렉션 쿼리 → 상위 10건 + 점수
    2. 같은 질문으로 faq_contents 컬렉션 쿼리 → 상위 10건 + 점수
    3. 문서 ID 기준 점수 가중 병합 (제목 50% + 내용 50%)
    4. 상위 3~5건을 LLM 컨텍스트로 전달
    """

    def __init__(self, embedder, chroma_client):
        self.embedder = embedder
        self.chroma_client = chroma_client
        self.title_weight = 0.5
        self.content_weight = 0.5

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """제목+내용 컬렉션에서 검색 후 점수 병합."""
        # TODO: 구현
        raise NotImplementedError

    async def generate_answer(self, query: str, contexts: list[dict]) -> dict:
        """검색된 컨텍스트 기반 LLM 답변 생성."""
        # TODO: 구현
        raise NotImplementedError
```

### prompts/chat_system.txt
```
당신은 증권사 업무 편람 기반 상담 지원 AI입니다.

규칙:
1. 반드시 제공된 컨텍스트(편람/FAQ) 내에서만 답변하세요.
2. 컨텍스트에 없는 내용은 "해당 내용은 업무 편람에 포함되어 있지 않습니다"라고 답변하세요.
3. 모든 답변에 출처를 표시하세요. (예: [계좌업무편람 p.23])
4. 추측이나 일반 지식으로 답변하지 마세요.
5. 한국어로 답변하되, 증권 전문 용어 사용 시 쉬운 설명을 병기하세요.

컨텍스트:
{context}

질문: {question}
```

### prompts/training_customer.txt
```
당신은 증권사에 전화한 고객입니다.

아래 편람 내용을 기반으로, 지정된 난이도에 맞는 자연스러운 질문을 1개 생성하세요.

난이도:
- 초급: 단일 주제, 직접적인 질문 (예: "계좌 개설 어떻게 해요?")
- 중급: 조건 포함 질문 (예: "미성년자도 비대면 계좌 개설 가능한가요?")
- 고급: 복합 주제 (예: "해외주식 매도 후 세금 신고 방법과 수수료 한도도 알려주세요")

편람 내용:
{content}

난이도: {difficulty}

고객 질문:
```

### prompts/training_scorer.txt
```
당신은 증권사 상담 품질 평가 전문가입니다.

아래 정보를 기반으로 신입 상담원의 답변을 채점하세요.

고객 질문: {question}
편람 기반 정답: {reference_answer}
신입 상담원 답변: {trainee_answer}

채점 기준:
1. 필수 항목 포함 여부 (60%)
2. 의미적 정확성 (30%)
3. 고객 친화적 표현 (10%)

아래 JSON 형식으로만 응답하세요:
{
  "score": 0-100,
  "included_items": ["포함된 핵심 항목들"],
  "missing_items": ["누락된 핵심 항목들"],
  "feedback": "구체적인 피드백",
  "reference": "출처 정보",
  "model_answer": "모범 답변"
}
```

## 주의사항

1. 모든 빈 파일(scripts/, utils/, tests/)에는 아래 내용만 넣어줘:
```python
"""TODO: 구현 예정."""
```

2. data/raw/, data/processed/, data/chroma_db/, frontend/, docs/adr/ 폴더에는 .gitkeep 빈 파일만 생성

3. tests/test_questions.json은 빈 배열 `[]`로 생성

4. __init__.py 파일은 모두 빈 파일로 생성

5. README.md와 docs/api-spec.md는 내용을 넣지 말고 아래 플레이스홀더만 넣어줘. 별도로 준비한 파일로 교체할 예정이야:
```markdown
# TODO: 별도 파일로 교체 예정
```

6. backend/main.py는 상대 import(`from .routers import ...`)를 사용하므로, 반드시 프로젝트 루트에서 아래 명령으로 실행해야 해:
```bash
uvicorn backend.main:app --reload
```

7. 파일 생성 후 아래 명령으로 확인:
```bash
git init
git add .
git status
```
