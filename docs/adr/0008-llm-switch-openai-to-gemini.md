# ADR-0008: PoC LLM을 OpenAI → Google Gemini로 전환

- 상태: Accepted
- 작성일: 2026-03-09
- 의사결정자: 우치
- 관련: [api-spec.md §4, 변경 이력 v6](../api-spec.md), `backend/services/embedder.py`

---

## 맥락 (Context)

PoC 초기 설계는 OpenAI GPT-4o + `text-embedding-3-small`(1536-d)로 확정되어 있었다. 그러나 PoC 진행 중 OpenAI API 크레딧이 부족해져 충전 절차가 일정에 부담을 주는 상황이 발생했다.

LLM 서비스 추상화(ADR-0001) 덕분에 모델 교체는 한 곳(구현체) 변경만으로 가능하다.

## 검토한 대안 (Options)

- **A. OpenAI 크레딧 충전하고 그대로 진행**
  - 장점: 설계 변경 없음
  - 단점: 비용 부담, 결제/조달 일정 변수
- **B. Anthropic Claude API**
  - 장점: 한국어 성능 우수
  - 단점: PoC 진행 중 시점에서 무료/저비용 임베딩 API가 제한적
- **C. Google AI Studio (Gemini)** ✅
  - 장점: 무료 티어 폭이 넓음, chat + embedding 모두 제공, 한국어 양호
  - 단점: 임베딩 차원이 3072로 OpenAI(1536)와 달라 ChromaDB 재인제스트 필요

## 결정 (Decision)

옵션 C 채택. PoC 기본 LLM/임베딩을 다음으로 전환한다.

| 항목      | 변경 전                       | 변경 후                            |
| --------- | ----------------------------- | ---------------------------------- |
| Chat      | OpenAI `gpt-4o`               | Google `gemini-2.5-flash`          |
| Embedding | OpenAI `text-embedding-3-small`(1536-d) | Google `gemini-embedding-001`(3072-d) |
| SDK       | `openai` (async)              | `google-genai` (sync → `asyncio.to_thread` 래핑) |
| env       | `OPENAI_API_KEY`              | `GOOGLE_API_KEY`                   |

`OpenAIService(LLMService)`는 백업 구현체로 보존하여 전환을 원복할 수 있게 한다.

**구현 변경 범위:**
- 신규: `GeminiService(LLMService)` (`backend/services/embedder.py`)
- 신규: `requirements.txt`에 `google-genai>=1.0.0`, `tiktoken>=0.7.0`
- 신규: `backend/config.py`에 `GOOGLE_*` 설정
- 변경: 호출처는 추상 인터페이스 의존이므로 변경 없음 (DI 한 곳만 교체)

**ChromaDB 재인제스트:**

```bash
python scripts/ingest_manual.py --clear --all
```

임베딩 차원 1536 → 3072이므로 컬렉션을 삭제하고 재생성한다 (`--clear`).

## 결과 (Consequences)

- ✅ 결제/크레딧 이슈 즉시 해소
- ✅ 추상화 덕에 호출처 코드 변경 0
- ⚠️ 임베딩 차원 변경 → 기존 ChromaDB는 사용 불가, **반드시 `--clear` 재인제스트** 필요
- ⚠️ Gemini SDK는 동기 API 중심 → `asyncio.to_thread`로 래핑하여 FastAPI async 호환 (구현 완료)
- ⚠️ JSON 구조화 출력 동작이 OpenAI와 다름 → 채점 모드 구현 시 `response_format` 호환성 재검증 필요
- ⚠️ Multi-turn 도입 시 Gemini의 `contents` 형식 변환을 견고하게 유지해야 함 (`_messages_to_gemini`)
- 🔄 재검토 트리거: 폐쇄망 실도입 시 자체 호스팅 모델(Qwen3 후보)로 추가 전환. 임베딩은 bge-m3(1024-d) 후보 → 또 한번 컬렉션 재구축 필요
