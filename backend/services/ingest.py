"""인제스트 공용 로직 — 청킹 + 증분(diff) 적재 (api-spec.md 섹션 9).

[청킹] scripts/ingest_manual.py에서 이동 (동작 100% 동일, CLI는 그대로 유지).
[diff] chunk_id = {doc_id}_{sha1(제목+내용)[:16]} — 내용이 같으면 ID도 같다.
       메타DB(stores/meta_sqlite.py)의 기존 ID 집합과 비교해
       신규 ID만 임베딩(upsert), 사라진 ID만 삭제, 동일 ID는 스킵(비용 0).

이 모듈을 사용하는 곳:
  - scripts/ingest_manual.py: chunk_blocks/build_metadata/embed_in_batches (PDF 전체 인제스트)
  - scripts/sync_manual.py: sync_document (위키 증분 인제스트 배치)
  - tests/test_diff_ingest.py: diff 동작 검증
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..models.parsed_document import Block, ParsedDocument
from .embedder import LLMService

logger = logging.getLogger(__name__)

# Gemini 무료 티어: embed 분당 100건(배치 내 텍스트 개별 카운트) — 한도 미만으로 유지
EMBED_BATCH_SIZE = 90

# ---------- 청킹 설정 (ingest_manual.py에서 이동) ----------
# merge=True인 타입은 같은 hierarchy_path 내 연속 블록을 토큰 제한까지 병합

_CHUNK_CONFIG: dict[str, dict] = {
    "heading":   {"merge": False},
    "paragraph": {"merge": True, "max_tokens": 400, "overlap": 0.12},
    "rule":      {"merge": False},
    "table":     {"merge": False},
    "table_row": {"merge": False},
    "procedure": {"merge": True, "max_tokens": 350, "overlap": 0.10},
    "faq":       {"merge": False},
    "notice":    {"merge": False},
}


def _estimate_tokens(text: str) -> int:
    """한국어 텍스트 토큰 수 근사 추정 (Korean ≈ 0.7 tokens/char)."""
    return max(1, int(len(text) * 0.7))


def _split_by_tokens(
    blocks: list[Block],
    max_tokens: int,
    overlap_pct: float,
) -> list[list[Block]]:
    """연속 블록 리스트를 max_tokens 기준으로 분할하고 overlap 적용."""
    if not blocks:
        return []

    chunks: list[list[Block]] = []
    current: list[Block] = []
    current_tokens = 0

    for block in blocks:
        text = block.canonical_text or block.text
        block_tokens = _estimate_tokens(text)

        if current and current_tokens + block_tokens > max_tokens:
            chunks.append(current)
            if overlap_pct > 0:
                target = int(current_tokens * overlap_pct)
                overlap_blocks: list[Block] = []
                overlap_tok = 0
                for b in reversed(current):
                    bt = _estimate_tokens(b.canonical_text or b.text)
                    if overlap_tok + bt > target and overlap_blocks:
                        break
                    overlap_blocks.insert(0, b)
                    overlap_tok += bt
                current = list(overlap_blocks)
                current_tokens = overlap_tok
            else:
                current = []
                current_tokens = 0

        current.append(block)
        current_tokens += block_tokens

    if current:
        chunks.append(current)

    return chunks


def _build_title_text(blocks: list[Block], doc_title: str | None) -> str:
    """청크의 heading context → title 텍스트."""
    first = blocks[0]
    if first.block_type == "heading":
        return first.text
    if first.hierarchy_path:
        return " > ".join(first.hierarchy_path)
    return doc_title or ""


def _build_content_text(blocks: list[Block]) -> str:
    """청크 내 블록 텍스트를 결합."""
    parts = []
    for b in blocks:
        text = (b.canonical_text or b.text).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def build_metadata(blocks: list[Block], parsed: ParsedDocument) -> dict:
    """청크 메타데이터 생성 — rag.py 검색 결과의 출처 표시에 사용.

    source_document 우선순위:
      1. parsed.meta["source_label"] — 위키 페이지 제목 (confluence_html.py가 설정)
      2. 파일명 — PDF 경로 (기존 동작)
    """
    first = blocks[0]
    source_label = (parsed.meta or {}).get("source_label")
    source_file = source_label or Path(parsed.source_path).name
    page_str = f"p.{first.page}" if first.page is not None else ""
    hp_json = (
        json.dumps(first.hierarchy_path, ensure_ascii=False)
        if first.hierarchy_path
        else ""
    )
    return {
        "source_document": source_file,
        "source_page": page_str,
        "category": "",
        "doc_id": parsed.doc_id,
        "block_type": first.block_type,
        "hierarchy_path": hp_json,
        # 출처 클릭용 위키 URL (confluence_html이 meta에 설정, 없으면 빈 문자열)
        "source_url": (parsed.meta or {}).get("source_url", ""),
    }


def chunk_blocks(blocks: list[Block], doc_title: str | None) -> list[dict]:
    """전체 블록을 청킹 가이드라인에 따라 chunk 리스트로 변환.

    Returns:
        [{"chunk_id_order": int, "title_text": str, "content_text": str,
          "blocks": [Block, ...]}]
    """
    chunks: list[dict] = []
    merge_buffer: list[Block] = []
    buffer_type: str | None = None
    buffer_hp: tuple = ()

    def flush():
        nonlocal merge_buffer, buffer_type, buffer_hp
        if not merge_buffer:
            return
        cfg = _CHUNK_CONFIG.get(buffer_type or "", {})
        max_tok = cfg.get("max_tokens", 400)
        overlap = cfg.get("overlap", 0.0)
        for sub in _split_by_tokens(merge_buffer, max_tok, overlap):
            content = _build_content_text(sub)
            if content.strip():
                chunks.append({
                    "blocks": sub,
                    "chunk_id_order": sub[0].order,
                    "title_text": _build_title_text(sub, doc_title),
                    "content_text": content,
                })
        merge_buffer = []
        buffer_type = None
        buffer_hp = ()

    for block in blocks:
        cfg = _CHUNK_CONFIG.get(block.block_type, {})
        hp_key = tuple(block.hierarchy_path) if block.hierarchy_path else ()

        if cfg.get("merge"):
            if block.block_type != buffer_type or hp_key != buffer_hp:
                flush()
                buffer_type = block.block_type
                buffer_hp = hp_key
            merge_buffer.append(block)
        else:
            flush()
            content = (block.canonical_text or block.text).strip()
            if content:
                chunks.append({
                    "blocks": [block],
                    "chunk_id_order": block.order,
                    "title_text": _build_title_text([block], doc_title),
                    "content_text": content,
                })

    flush()
    return chunks


# ---------- 임베딩 배치 (ingest_manual.py에서 이동) ----------


async def embed_in_batches(llm: LLMService, texts: list[str]) -> list[list[float]]:
    """Gemini API 배치 제한 대비 청크 분할 임베딩.

    무료 티어 분당 한도(embed 100건/분) 대응:
    429(RESOURCE_EXHAUSTED) 발생 시 대기 후 재시도 (지수 백오프, 최대 5회).
    영구 포기 금지 — 쿨다운 후 재시도 경로 유지 (dev-harness 규칙).
    """
    import asyncio

    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        delay = 30.0
        for attempt in range(5):
            try:
                vectors = await llm.embed(batch)
                break
            except Exception as e:
                msg = str(e)
                # 429/할당량 초과만 재시도 — 그 외 에러는 즉시 전파 (에러 분류)
                if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                    raise
                if attempt == 4:
                    raise
                logger.warning(
                    "  임베딩 한도 초과(429) — %.0f초 대기 후 재시도 (%d/4)",
                    delay, attempt + 1,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 120.0)
        all_vectors.extend(vectors)
        if i + EMBED_BATCH_SIZE < len(texts):
            logger.info("  임베딩 진행: %d / %d", i + len(batch), len(texts))
    return all_vectors


# ---------- diff 인제스트 (신규, api-spec.md 섹션 9) ----------


def compute_chunk_id(doc_id: str, title_text: str, content_text: str) -> str:
    """내용 기반 chunk_id — 내용이 같으면 ID도 같다 (diff의 열쇠).

    형식: {doc_id}_{sha1(제목 + \\x1f + 내용)[:16]}
    \\x1f(unit separator)로 제목/내용 경계를 고정해 해시 충돌 방지.
    """
    h = hashlib.sha1(
        f"{title_text}\x1f{content_text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{doc_id}_{h}"


def prepare_chunks(parsed: ParsedDocument) -> list[dict]:
    """ParsedDocument → hash ID가 부여된 청크 리스트.

    동일 내용 청크가 한 문서에 2번 나오면 ID 충돌 → "-1", "-2" 접미사로 구분
    (문서 내 등장 순서 기준이라 결정적).

    Returns:
        [{"chunk_id": str, "title_text": str, "content_text": str, "metadata": dict}]
    """
    raw_chunks = chunk_blocks(parsed.blocks, parsed.title)
    seen: dict[str, int] = {}
    result: list[dict] = []
    for ch in raw_chunks:
        base_id = compute_chunk_id(parsed.doc_id, ch["title_text"], ch["content_text"])
        n = seen.get(base_id, 0)
        seen[base_id] = n + 1
        chunk_id = base_id if n == 0 else f"{base_id}-{n}"
        result.append({
            "chunk_id": chunk_id,
            "title_text": ch["title_text"] or ch["content_text"],
            "content_text": ch["content_text"],
            "metadata": build_metadata(ch["blocks"], parsed),
        })
    return result


@dataclass
class SyncResult:
    """문서 1건 동기화 결과 — sync_manual.py 리포트 집계용."""

    doc_id: str = ""
    added: int = 0          # 신규 임베딩+upsert된 청크 수
    removed: int = 0        # 삭제된 청크 수
    unchanged: int = 0      # 스킵된 청크 수 (임베딩 비용 0)
    embed_texts: int = 0    # 임베딩 API에 보낸 텍스트 수 (title+content 합산)
    errors: list[str] = field(default_factory=list)


async def sync_document(
    parsed: ParsedDocument,
    llm: LLMService,
    titles_col,
    contents_col,
    meta_store,
    *,
    dry_run: bool = False,
) -> SyncResult:
    """단일 문서를 diff 방식으로 ChromaDB에 동기화.

    흐름 (docs/design-ingest-pipeline.html Step 4~6):
      1. 청킹 + hash ID 생성
      2. 메타DB 기존 ID 집합과 비교 → 신규/삭제/동일 분류
      3. 신규만 임베딩 → faq_titles/faq_contents upsert
      4. 사라진 ID는 양쪽 컬렉션에서 delete
      5. 메타DB 청크 목록 교체 (성공 후에만 — premature state commit 방지)
    """
    result = SyncResult(doc_id=parsed.doc_id)

    chunks = prepare_chunks(parsed)
    new_by_id = {c["chunk_id"]: c for c in chunks}
    new_ids = set(new_by_id.keys())
    old_ids: set[str] = meta_store.get_chunk_ids(parsed.doc_id)

    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    result.added = len(added_ids)
    result.removed = len(removed_ids)
    result.unchanged = len(new_ids & old_ids)

    if dry_run:
        logger.info(
            "[dry-run] %s: +%d / -%d / =%d",
            parsed.doc_id, result.added, result.removed, result.unchanged,
        )
        return result

    # 신규 청크만 임베딩 (title/content 양쪽) — 변경분만 비용 발생
    if added_ids:
        title_texts = [new_by_id[i]["title_text"] for i in added_ids]
        content_texts = [new_by_id[i]["content_text"] for i in added_ids]
        metadatas = [new_by_id[i]["metadata"] for i in added_ids]

        title_vectors = await embed_in_batches(llm, title_texts)
        content_vectors = await embed_in_batches(llm, content_texts)
        result.embed_texts = len(title_texts) + len(content_texts)

        titles_col.upsert(
            ids=added_ids,
            documents=title_texts,
            embeddings=title_vectors,
            metadatas=metadatas,
        )
        contents_col.upsert(
            ids=added_ids,
            documents=content_texts,
            embeddings=content_vectors,
            metadatas=metadatas,
        )

    # 사라진 청크는 양쪽 컬렉션에서 삭제
    if removed_ids:
        titles_col.delete(ids=removed_ids)
        contents_col.delete(ids=removed_ids)

    # ChromaDB 반영 성공 후에만 메타DB 갱신 (조기 상태 기록 금지)
    meta_store.replace_chunks(parsed.doc_id, sorted(new_ids))

    logger.info(
        "동기화: %s — +%d / -%d / =%d (임베딩 %d건)",
        parsed.doc_id, result.added, result.removed,
        result.unchanged, result.embed_texts,
    )
    return result


def delete_document_chunks(doc_id: str, titles_col, contents_col, meta_store) -> int:
    """문서가 위키에서 사라졌을 때 해당 청크 전체 삭제. 삭제 수 반환.

    sync_manual.py의 --prune 처리에서 호출.
    """
    chunk_ids = sorted(meta_store.get_chunk_ids(doc_id))
    if chunk_ids:
        titles_col.delete(ids=chunk_ids)
        contents_col.delete(ids=chunk_ids)
    meta_store.replace_chunks(doc_id, [])
    return len(chunk_ids)
