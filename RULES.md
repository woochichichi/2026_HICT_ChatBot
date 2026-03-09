# 프로젝트 규칙 (AI 공유)

> 이 파일은 모든 AI 도구(Claude Code, Cursor 등)가 공통으로 따르는 규칙입니다.
> 규칙 수정은 반드시 이 파일에서만 하고, `.cursorrules`에도 동기화하세요.

---

## 프로젝트 개요

- **이름**: 증권 상담원 AI 코치
- **목적**: 업무 챗봇(FAQ/편람 기반 즉시 답변) + 신입 교육 시뮬레이터(AI 고객 역할 → 채점)
- **기간**: PoC 4주 (2026-03-03 ~ 03-28)
- **팀**: 우치(챗봇 모드), 승구리(훈련 모드)

---

## 필수 참조 문서

코드를 작성하기 전에 반드시 아래 문서를 읽고 따를 것:

- **`docs/api-spec.md`** — API 스펙, 데이터 스키마, ChromaDB 구조, LLM 추상화, 설계 결정 기록
- **`README.md`** — 프로젝트 개요, 세팅, 역할, 일정

---

## 기술 스택

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **LLM**: Google Gemini (gemini-2.5-flash), 백업 OpenAI GPT-4o, 프로덕션 후보 Qwen3-30B-A3B
- **Embedding**: gemini-embedding-001 (3072차원)
- **Vector DB**: ChromaDB
- **Frontend**: React (2주차부터)
- **데이터 처리**: PyMuPDF (PDF 파싱)

---

## 파일 소유권

수정 전 소유자를 반드시 확인할 것. 타인 소유 파일은 무단 수정 금지.

| 파일/폴더 | 소유자 | 비고 |
|-----------|--------|------|
| `routers/chat.py` | 우치 | 챗봇 API |
| `services/rag.py` | 우치 | RAG 파이프라인 |
| `frontend/` 챗봇 관련 | 우치 | 채팅 UI, 출처 표시 |
| `routers/training.py` | 승구리 | 훈련 API |
| `services/question_gen.py` | 승구리 | 질문 생성 |
| `services/scorer.py` | 승구리 | 채점 서비스 |
| `frontend/` 훈련 관련 | 승구리 | 훈련 UI, 채점 결과 |
| `services/embedder.py` | 공통 | 수정 시 합의 필요 |
| `config.py`, `main.py` | 공통 | 수정 시 합의 필요 |
| `prompts/*.txt` | 공통 | 같이 작성, 상호 리뷰 |

---

## 커밋 컨벤션

```
feat:    새 기능
fix:     버그 수정
docs:    문서
prompt:  프롬프트 변경 (코드 커밋과 반드시 분리)
chore:   기타
```

---

## 금지 사항

1. **`docs/api-spec.md` 스펙과 다른 API 형식 생성 금지** — 요청/응답 구조는 api-spec.md가 단일 진실 소스
2. **민감 파일 수정/커밋 금지** — `.env`, `data/raw/`, `data/chroma_db/`
3. **타인 소유 파일 무단 수정 금지** — 위 소유권 매트릭스 참조
4. **`prompt:` 커밋에 코드 변경 포함 금지** — 프롬프트와 코드는 별도 커밋
5. **AI 생성 코드를 설명 없이 커밋 금지** — 작성자가 설명할 수 있어야 함

---

## 아키텍처 핵심 규칙

- `routers/` — API 엔드포인트만, 비즈니스 로직 넣지 않음
- `services/` — 비즈니스 로직 담당
- `prompts/*.txt` — 시스템 프롬프트 (버전 관리 대상)
- LLM 호출은 반드시 `services/embedder.py`의 추상화 인터페이스를 통해 수행 (모델 교체 대비)
