# ADR-0009: PDF 파서로 Docling 채택

- 상태: Accepted
- 작성일: 2026-03-16
- 의사결정자: 승구리
- 관련: `backend/services/parsers/docling_pdf.py`, `scripts/parse_pdf.py`, [api-spec.md 핸드오프 로그 2026-03-16](../api-spec.md)

---

## 맥락 (Context)

PoC의 문서 입력은 한화투자증권 업무편람 PDF다. 이 PDF는 다음과 같은 특징을 가진다:

- 한국어 개조식 번호 체계 (`1)`, `가.`, `ㄱ.` 등)
- 목차 깊이가 다층 (장 → 절 → 조 → 항)
- **표(table)가 매우 많고 의미 있음** (수수료율, 종목 분류, 코드 매핑 등)
- 페이지 번호/머리글/꼬리글 등 노이즈

RAG 검색 품질은 청킹/하이라키 보존/표 처리에 크게 좌우된다.

## 검토한 대안 (Options)

- **A. `pymupdf`(기존)** — 텍스트 위주 추출
  - 장점: 가벼움, 빠름
  - 단점: ❌ 표 구조를 행/열로 인식 못 함 (단일 텍스트 블록으로만 추출). 헤딩 레벨 추정 직접 구현 필요
- **B. `pdfplumber` + `camelot`**
  - 장점: 표 추출이 가능
  - 단점: 두 라이브러리 결합 복잡도, 한국어 폰트/라인 인식 부정확
- **C. `Docling`(IBM 오픈소스)** ✅
  - 장점: TableFormer로 표 구조 추출, OCR 옵션, SectionHeaderItem 등 의미 있는 노드 모델 제공
  - 단점: 패키지가 무겁고 의존성 많음. 설치 시간 김

## 결정 (Decision)

옵션 C(Docling) 채택. 다음 정책으로 운영한다:

**구성:**
```python
ThreadedPdfPipelineOptions(
    do_table_structure=True,
    table_structure_options=TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    ),
    do_ocr=True,
)
```

**한국어 헤딩 깊이 추정:** 정규식으로 보강 (Docling이 모델 결과로 주는 깊이는 한국어 개조식에서 부정확).

```
^\d+[\)\.]\s   → depth 1   (예: "3) ...", "1. ...")
^[가-힣][\.\)]\s → depth 2  (예: "가. ...")
^[ㄱ-ㅎ][\.\)]\s → depth 3  (예: "ㄱ. ...")
```

**Block 모델 (`backend/models/parsed_document.py`):**
- `block_type`: `heading | paragraph | rule | table | table_row | procedure | faq | notice`
- `hierarchy_path`: heading stack을 1-depth 제외하고 누적
- `canonical_text`: 검색 최적화 평문 (표 행은 `"{subject}의 {ctx}는 {value}이다."` 패턴)

**표 처리 — 두 단계로 적재:**
1. `block_type=table`: 전체 마크다운 표 (전체 컨텍스트 검색용)
2. `block_type=table_row`: 행별 분리 + canonical_text (행 단위 검색용)

이중 적재로 "표 전체에서 어떤 컬럼이 있는지" 검색과 "특정 값이 어디에 있는지" 검색 모두 지원한다.

**파일 구조:**
```
data/raw/manual.pdf
  → scripts/parse_pdf.py
  → data/processed/{doc_id}/docling.json  (ParsedDocument 직렬화)
  → scripts/ingest_manual.py
  → ChromaDB
```

`doc_id = sha1(resolved_path)[:16]`로 결정하여 같은 파일을 같은 ID로 안정 관리한다.

## 결과 (Consequences)

- ✅ 표 구조가 보존되어 "수수료" 같은 표 기반 정보 검색 품질 향상
- ✅ heading hierarchy로 출처 표시 품질 향상 (예: `["계좌개설", "가. 신규개설"]`)
- ✅ 파서 종류와 무관한 공통 스키마(`ParsedDocument`)로 향후 다른 파서 추가 용이
- ⚠️ Docling 패키지가 무거움 → CI/배포 시간 증가
- ⚠️ OCR이 켜져 있어 처리 시간 김. PoC 데이터 규모(편람 20건)에서는 허용 가능
- ⚠️ 한국어 헤딩 깊이는 정규식 휴리스틱 — 비표준 번호 체계 등장 시 패턴 추가 필요
- ⚠️ 표 행 canonical_text 생성은 단순 휴리스틱. 복잡한 병합 셀에서는 부정확 가능
- 🔄 재검토 트리거: 편람 외 데이터(공지/FAQ JSON 등) 비중이 커지면 doc_type별 별도 파서 분기 추가
