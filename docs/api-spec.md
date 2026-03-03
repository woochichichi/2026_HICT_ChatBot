# 설계 문서 — API 스펙 & 아키텍처 & 리뷰

> 킥오프 합의용 + 설계 결정 기록. 개발하면서 함께 업데이트한다.
> 
> Last Updated: 2026-03-03 (v2 — 설계 리뷰 반영)

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

## 4. LLM 서비스 추상화 (폐쇄망 전환 대비)

PoC(GPT-4o) → 실도입(Qwen3-30B-A3B) 전환 시 코드 수정을 최소화하기 위한 인터페이스.

```python
class LLMService(ABC):
    @abstractmethod
    async def generate(self, messages: list, temperature: float, response_format: dict) -> str: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def count_tokens(self, text: str) -> int: ...
```

**전환 시 주의사항:**
- 임베딩 차원 불일치: text-embedding-3-small(1536) → bge-m3(1024)로 전환하면 ChromaDB 컬렉션 전체 재구축 필요. 인제스트 파이프라인을 "모델 교체 → 재인제스트" 원커맨드로 실행 가능하게 설계할 것.
- Qwen3의 JSON 구조화 출력 품질이 GPT-4o와 다를 수 있음. 특히 채점 프롬프트(`training_scorer.txt`)는 모델 전환 후 반드시 재검증.
- OpenAI는 function calling 네이티브, Qwen3은 vLLM/Ollama 위 OpenAI-compatible API — stop token, temperature 동작, 토큰 카운팅 방식에 미묘한 차이 있음.

**권장 액션:** 3주차에 반나절 투자하여 Qwen3 로컬 비교 테스트 실시. 동일 프롬프트로 GPT-4o vs Qwen3 출력 품질 비교표를 만들면 폐쇄망 도입 제안서 설득력 강화.

---

## 5. 설계 리뷰 & 리스크 (2026-03-03)

### 5.1 제목+내용 가중치 최적화

현재 5:5로 설정. 사람인HR은 채용 FAQ(제목 정보 밀도 높음)에서 검증된 수치이나, 증권 편람은 "제42조 양도소득세 과세표준"처럼 제목이 형식적이라 정보 밀도가 낮음.

→ 4:6 또는 3:7(내용 쪽 상향)이 더 나을 가능성 있음.
→ 정확도 테스트 30개 세트 실행 시 가중치를 파라미터로 분리하여 `[5:5, 4:6, 3:7]` 그리드 서치. 반나절이면 최적값 도출 가능.

### 5.2 훈련 모드 정답의 순환 의존

현재 설계에서 채점 시 "편람 기반 정답"을 RAG로 추출하는데, RAG 정확도 목표가 80%이므로 정답 자체가 20% 확률로 오류 가능. 데모에서 노출되면 치명적.

→ 데모 시나리오 2개에 대해 정답을 사전에 수동 확정하여 `tests/training_golden_answers.json`에 저장.
→ 채점 시 RAG 결과와 수동 정답을 병합하여 사용.

### 5.3 다중 제목과 응답 시간 트레이드오프

유사 제목 2~3개 × 원래 제목 × 요약 제목 = 문서당 4~5개 임베딩. PoC 범위(FAQ + 편람 20건)에서는 문제 없으나, 확장 시 LLM 전달 컨텍스트 양이 늘어나 응답 시간 초과 우려.

→ 실도입 시 검색 결과 reranking + 상위 N개만 LLM 전달하는 파이프라인 필요.
→ 2단계 RAG(LangGraph) 도입 시점과 연계 검토.

---

## 6. 2인 AI 개발 주의사항

### 6.1 코드 품질

Cursor가 생성한 코드에서 자주 발생하는 문제: ChromaDB deprecated 메서드, 임베딩 배치 처리 비효율, 에러 핸들링 누락.

→ PR 단위를 작게(함수 1~2개), 머지 전 "이 함수가 왜 이렇게 동작하는지" 30초 구두 설명.

### 6.2 프롬프트 버전 관리

프롬프트(`prompts/`)는 코드와 다른 속도로 변경됨. 정확도 하락 원인이 코드인지 프롬프트인지 추적 불가 방지.

→ 커밋 컨벤션에 `prompt:` 접두사 추가. 프롬프트 변경과 코드 변경을 절대 같은 커밋에 섞지 않을 것.

```
prompt: 챗봇 시스템 프롬프트 출처 표시 형식 변경
prompt: 채점 프롬프트 필수항목 가중치 60→70% 조정
```

### 6.3 AI 도구 간 컨텍스트 단절

팀 리드(Claude) ↔ 개발자A(Cursor) 간 AI 도구에 맥락 공유 안 됨. 각자의 AI가 서로 다른 방향으로 코드 생성하는 문제 발생.

→ **이 문서(`api-spec.md`)를 양쪽 AI 도구의 프로젝트 컨텍스트에 포함시켜 사용.** API 스펙이 single source of truth 역할.

---

## 7. 액션 아이템

| 순위 | 액션 | 소요 | 시점 |
|------|------|------|------|
| 1 | LLM 서비스 인터페이스 3개 메서드 구현 (섹션 4) | 2시간 | 1주차 |
| 2 | 훈련 모드 데모 시나리오 2개 수동 정답 확정 | 3시간 | 3주차 |
| 3 | 커밋 컨벤션에 `prompt:` 접두사 추가 | 30분 | 즉시 |
| 4 | 임베딩 가중치 그리드 서치 파라미터화 | 반나절 | 3주차 |
| 5 | Qwen3 로컬 비교 테스트 | 반나절 | 3주차 |

---

## 8. 합의 체크리스트

킥오프 때 아래 항목을 함께 확인하고, 이견이 있으면 이 문서에 바로 수정한다.

```
□ API 요청/응답 형식 OK?
□ confidence 기준 (0.85 / 0.70) OK?
□ FAQ JSON 스키마 OK?
□ 카테고리 목록 OK?
□ ChromaDB 2개 컬렉션 분리 구조 OK?
□ 유사 제목 ID 접미사 방식 OK?
□ 검색 가중치 50:50 OK? (3주차에 그리드 서치 예정)
□ LLM 서비스 인터페이스 OK? (섹션 4)
□ 프롬프트 커밋 컨벤션 OK? (섹션 6.2)
```

---

*이 문서는 개발 진행에 따라 팀원 누구나 업데이트한다.*
