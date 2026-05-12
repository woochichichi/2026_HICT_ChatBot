# Architecture Decision Records (ADR)

> 증권 상담원 AI 코치 — 설계 결정 기록
>
> 본 폴더는 [Michael Nygard 형식](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)을 한국어로 간소화한 ADR을 보관한다.
>
> Last Updated: 2026-05-08

---

## 작성 규칙

- 파일명: `{NNNN}-{kebab-case-제목}.md` (예: `0001-llm-service-abstraction.md`)
- **상태(Status)**: `Proposed` → `Accepted` → (필요 시) `Deprecated` / `Superseded by NNNN`
- 한 ADR은 **하나의 결정만** 다룬다.
- 결정이 변경되면 기존 ADR을 수정하지 말고 새 ADR을 추가하여 `Supersedes`로 연결한다.
- ADR은 `docs/api-spec.md` 변경 이력의 **근거 문서**로 작용한다.

## 템플릿

```markdown
# ADR-NNNN: 제목

- 상태: Accepted
- 작성일: YYYY-MM-DD
- 의사결정자: 우치 / 승구리
- 관련 이슈: api-spec.md 백로그 #N (있다면)

## 맥락 (Context)
무엇을 결정해야 했는가? 어떤 제약/요구사항이 있었는가?

## 검토한 대안 (Options)
- 옵션 A — 장단점
- 옵션 B — 장단점
- 옵션 C — 장단점

## 결정 (Decision)
무엇을 선택했는가? 왜 그것이 최선인가?

## 결과 (Consequences)
- ✅ 이로 인해 얻는 것
- ⚠️ 감수해야 하는 것
- 🔄 추후 재검토 트리거
```

---

## 인덱스

| 번호 | 제목                                                                          | 상태     | 작성일      |
| ---- | ----------------------------------------------------------------------------- | -------- | ----------- |
| 0001 | [LLM 서비스 추상화 인터페이스 도입](./0001-llm-service-abstraction.md)         | Accepted | 2026-02-28 |
| 0002 | [ChromaDB Dual-Collection (제목+내용 분리)](./0002-chromadb-dual-collection.md) | Accepted | 2026-02-28 |
| 0003 | [다중 제목 + Max Pooling 채택](./0003-multi-title-max-pooling.md)              | Accepted | 2026-03-03 |
| 0004 | [SSE 스트리밍 + sources 선전송](./0004-sse-streaming-sources-first.md)         | Accepted | 2026-03-03 |
| 0005 | [훈련 채점은 Direct Fetch (RAG 재검색 금지)](./0005-training-direct-fetch.md)  | Accepted | 2026-03-03 |
| 0006 | [solved_content_ids 클라이언트 상태 관리 (Stateless 서버)](./0006-stateless-solved-tracking.md) | Accepted | 2026-03-03 |
| 0007 | [데모 모드(is_demo) 분기 도입](./0007-demo-mode-flag.md)                       | Accepted | 2026-03-03 |
| 0008 | [PoC LLM을 OpenAI → Google Gemini로 전환](./0008-llm-switch-openai-to-gemini.md)| Accepted | 2026-03-09 |
| 0009 | [PDF 파서로 Docling 채택](./0009-docling-pdf-parser.md)                        | Accepted | 2026-03-16 |

---

## 관련 문서

- [docs/api-spec.md](../api-spec.md) — 단일 진실 소스
- [docs/architecture.md](../architecture.md)
- [docs/data-flow.md](../data-flow.md)
- [docs/db-design.md](../db-design.md)
