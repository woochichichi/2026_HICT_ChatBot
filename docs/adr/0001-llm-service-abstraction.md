# ADR-0001: LLM 서비스 추상화 인터페이스 도입

- 상태: Accepted
- 작성일: 2026-02-28
- 의사결정자: 우치, 승구리
- 관련: [api-spec.md §4](../api-spec.md), `backend/services/embedder.py`

---

## 맥락 (Context)

PoC는 OpenAI GPT-4o(이후 Google Gemini로 변경 — ADR-0008)를 사용하지만, 실도입은 폐쇄망 요구사항으로 자체 호스팅 모델(Qwen3-30B-A3B 후보, bge-m3 임베딩 등) 전환 가능성이 높다.
모델별로 다음이 다르다:

- 인터페이스 (chat completions vs `generate_content` vs vLLM OpenAI-compatible)
- 메시지 형식 (OpenAI `messages` vs Gemini `contents`)
- 스트리밍 방식
- JSON 구조화 출력 옵션
- 토큰 카운팅 방식
- 임베딩 차원 (1536/1024/3072 등)

각 호출처(`rag.py`, `question_gen.py`, `scorer.py`)에서 SDK를 직접 사용하면, 모델 교체 시 호출처 전부를 수정해야 한다.

## 검토한 대안 (Options)

- **A. 호출처에서 SDK 직접 사용**
  - 장점: 단순, 즉시 작성 가능
  - 단점: 모델 교체 시 N개 파일 수정. 인터페이스 차이로 인한 버그 분산
- **B. LangChain 등 프레임워크 의존**
  - 장점: 멀티 LLM 지원이 풍부
  - 단점: 4주 PoC에 종속성/추상화 비용 과대. 디버깅 난이도 상승
- **C. 자체 추상 인터페이스(`ABC`)** ✅
  - 장점: 4개 메서드만 정의하면 됨, 디버깅 용이
  - 단점: 신규 모델 추가 시 직접 구현 필요

## 결정 (Decision)

옵션 C 채택. `LLMService(ABC)`에 다음 4개 메서드를 정의한다:

| 메서드             | 시그니처                                                                  | 용도                          |
| ------------------ | ------------------------------------------------------------------------- | ----------------------------- |
| `generate`         | `(messages, temperature=0.1, response_format=None) -> str`                | 비스트리밍 생성, JSON 모드 옵션 |
| `generate_stream`  | `(messages, temperature=0.1) -> AsyncIterator[str]`                       | SSE용 스트리밍 생성            |
| `embed`            | `(texts: list[str]) -> list[list[float]]`                                 | 배치 임베딩                    |
| `count_tokens`     | `(text: str) -> int`                                                      | 토큰 추정                      |

구현체:
- `GeminiService` — PoC 기본 (ADR-0008 이후)
- `OpenAIService` — 백업 보관

호출처는 `LLMService` 타입 의존성만 사용한다 (예: `RAGService.__init__(self, llm: LLMService)`).

## 결과 (Consequences)

- ✅ 모델 교체 시 새 구현체 1개 추가 + DI 한 곳 수정
- ✅ 단위 테스트 시 모킹 용이
- ⚠️ 메시지 형식 차이는 구현체 내부에서 변환 (`GeminiService._messages_to_gemini`)
- ⚠️ JSON 구조화 출력 품질은 모델별 편차가 있어 채점 모드 전환 시 재검증 필수 (api-spec.md §4)
- 🔄 재검토 트리거: function calling/tool use 지원이 필요해지면 인터페이스 확장 필요
