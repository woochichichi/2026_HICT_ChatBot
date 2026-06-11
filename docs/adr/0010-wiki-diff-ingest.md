# ADR 0010: 위키 수집 + hash 기반 증분(diff) 인제스트

- **상태**: 승인 (2026-06-10)
- **관련**: api-spec.md 섹션 9, [design-ingest-pipeline.html](../design-ingest-pipeline.html), ADR 0009(Docling PDF 파서)

## 맥락

업무편람 원본이 사내 위키(Confluence)에 있다. 기존 파이프라인(PDF 수동 출력 → docling
파싱 → 전체 재인제스트)은 두 가지 문제가 있다:

1. 위키 페이지를 하나씩 PDF로 출력하는 작업이 비현실적 (수집 문제)
2. 데이터가 늘면 매번 전체 재임베딩 비용 발생 (증분 문제)

추가 제약: 회사 폐쇄망에서 Confluence REST API 사용 가능 여부가 불확실.
확인된 것은 브라우저 접근 가능한 화면뿐 (`wiki.hanwhawm.com/collector/pages.action?key=BM001`).

## 결정

### 1. 수집 계층 추상화 (`SourceConnector`)

로컬 HTML 폴더(A) / 세션 쿠키 크롤링(B) / REST API(C, 미구현) 모두
`RawDocument(source_id, title, html, url)`를 출력 → 수집 방식 교체 시 파이프라인 무수정.
회사 환경에서 되는 방식부터 쓰고 점진적으로 자동화 수준을 올린다.

### 2. chunk_id = 내용 hash

`{doc_id}_{sha1(제목 + \x1f + 내용)[:16]}` — 내용이 같으면 ID도 같다.

- 변경 감지 = 메타DB의 기존 ID 집합과 새 ID 집합 비교 (신규=임베딩, 사라짐=삭제, 동일=스킵)
- 순번 기반 ID(`{doc_id}_{order}`)는 문단 삽입 시 뒤 순번이 전부 밀려 전체 재임베딩되는 문제
- 기존 PDF 인제스트(ingest_manual.py)는 순번 ID 유지 — 동작 불변, 신규 파이프라인에만 적용
- rag.py 검색은 ID 형식 무관이라 무수정

### 3. 문서 단위 1차 스킵

원본 HTML sha256이 메타DB와 같으면 파싱·청킹조차 생략.
"diff의 본질은 수집 절감이 아니라 임베딩 절감" — 매일 전체를 크롤해도
임베딩 호출은 변경분만큼만 발생하므로, 증분 화면(최근 업데이트) 확보 전에도 운영 가능.

### 4. SQLite 메타 DB (`data/meta.db`)

documents(raw_hash, last_seen_at) / chunks(chunk_id) / sync_runs(배치 리포트).
ChromaDB와 분리해 동기화 상태 추적·감사를 가능하게 함.

## 대안 검토

| 대안 | 기각 사유 |
|------|----------|
| Confluence REST API 단독 | 폐쇄망 정책상 가용 불확실 — 커넥터의 한 구현체로만 보류 |
| 위키 → PDF 출력 유지 | 페이지별 수동 출력 비용 + 렌더링 손실. HTML이 구조 보존에 우월 |
| 매일 전체 재인제스트 | 임베딩 API 비용·시간이 데이터 증가에 비례. PoC 이후 지속 불가 |
| ChromaDB 메타데이터로 버전 관리 | 동기화 이력·삭제 추적이 불가능, 쿼리 불편 |

## 결과

- 변경분만 임베딩: 일일 변경률 1~5% 가정 시 호출 95%+ 절감
- 테스트: `tests/test_diff_ingest.py` — 재동기화 임베딩 0건, 변경분만 반영, dry-run 무변경 검증
- 트레이드오프: 내용이 같으면 메타데이터만 바뀐 청크는 갱신 안 됨 (hash가 내용 기준).
  출처 표시용 메타데이터가 내용에서 파생되므로 실용상 문제 없음
