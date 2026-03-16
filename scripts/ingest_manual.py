"""CLI: docling 파싱 결과(업무편람)를 ChromaDB에 적재.

블록 타입별 청킹 가이드라인:
    heading:   제목 1개, overlap 0
    paragraph: 2~4문장 병합, 150~400 tokens, overlap 10~15%
    rule:      규칙 1개, overlap 0
    table:     표 전체 1개
    table_row: 행 1개, overlap 0
    procedure: 1~3단계 병합, 150~350 tokens, overlap 10%
    faq:       질문+답변 1쌍
    notice:    공지 항목 1개

사용법:
    python scripts/ingest_manual.py -i data/processed/<doc_id>/docling.json
    python scripts/ingest_manual.py --all
    python scripts/ingest_manual.py --clear --all
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.models.parsed_document import Block, ParsedDocument
from backend.services.embedder import GeminiService
from backend.services.rag import get_chroma_client, init_collections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100

# ---------- 청킹 설정 ----------
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


# ---------- 청킹 로직 ----------


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


def _build_metadata(blocks: list[Block], parsed: ParsedDocument) -> dict:
    first = blocks[0]
    source_file = Path(parsed.source_path).name
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


# ---------- 파일 로드 ----------


def _load_parsed_document(path: str) -> ParsedDocument:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ParsedDocument(**data)


def _discover_all_docling_jsons() -> list[Path]:
    """data/processed/ 하위의 모든 docling.json 경로를 반환."""
    base = Path(settings.DATA_DIR) / "processed"
    if not base.exists():
        return []
    return sorted(base.rglob("docling.json"))


# ---------- 임베딩 + 적재 ----------


async def _embed_in_chunks(llm: GeminiService, texts: list[str]) -> list[list[float]]:
    """Gemini API 배치 제한 대비 청크 분할 임베딩."""
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        vectors = await llm.embed(batch)
        all_vectors.extend(vectors)
        if i + EMBED_BATCH_SIZE < len(texts):
            logger.info("  임베딩 진행: %d / %d", i + len(batch), len(texts))
    return all_vectors


async def ingest_document(
    parsed: ParsedDocument,
    llm: GeminiService,
    titles_col,
    contents_col,
) -> int:
    """단일 ParsedDocument를 청킹 후 ChromaDB에 적재. 적재 청크 수 반환."""
    if not parsed.blocks:
        logger.warning("블록 없음: %s", parsed.doc_id)
        return 0

    chunks = chunk_blocks(parsed.blocks, parsed.title)
    if not chunks:
        logger.warning("유효한 청크 없음: %s", parsed.doc_id)
        return 0

    ids: list[str] = []
    title_texts: list[str] = []
    content_texts: list[str] = []
    metadatas: list[dict] = []

    for ch in chunks:
        chunk_id = f"{parsed.doc_id}_{ch['chunk_id_order']}"
        ids.append(chunk_id)
        title_texts.append(ch["title_text"] or ch["content_text"])
        content_texts.append(ch["content_text"])
        metadatas.append(_build_metadata(ch["blocks"], parsed))

    logger.info(
        "임베딩 시작: %s — %d 블록 → %d 청크",
        parsed.doc_id, len(parsed.blocks), len(ids),
    )

    title_vectors = await _embed_in_chunks(llm, title_texts)
    content_vectors = await _embed_in_chunks(llm, content_texts)

    titles_col.upsert(
        ids=ids,
        documents=title_texts,
        embeddings=title_vectors,
        metadatas=metadatas,
    )
    contents_col.upsert(
        ids=ids,
        documents=content_texts,
        embeddings=content_vectors,
        metadatas=metadatas,
    )

    logger.info("적재 완료: %s — %d 청크", parsed.doc_id, len(ids))
    return len(ids)


# ---------- CLI ----------


async def run(args: argparse.Namespace) -> None:
    llm = GeminiService()
    client = get_chroma_client()

    if args.clear:
        for name in ("faq_titles", "faq_contents"):
            try:
                client.delete_collection(name)
                logger.info("컬렉션 삭제: %s", name)
            except Exception:
                pass

    titles_col, contents_col = init_collections(client)

    paths: list[Path] = []
    if args.all:
        paths = _discover_all_docling_jsons()
        if not paths:
            logger.error("data/processed/ 에 docling.json 파일 없음")
            return
        logger.info("발견된 문서: %d개", len(paths))
    elif args.input:
        p = Path(args.input)
        if not p.is_file():
            logger.error("파일 없음: %s", args.input)
            return
        paths = [p]
    else:
        logger.error("-i 또는 --all 옵션을 지정하세요")
        return

    total_chunks = 0
    for path in paths:
        parsed = _load_parsed_document(str(path))
        count = await ingest_document(parsed, llm, titles_col, contents_col)
        total_chunks += count

    logger.info("전체 완료: %d개 문서, %d개 청크 적재", len(paths), total_chunks)
    logger.info(
        "컬렉션 현황: faq_titles=%d, faq_contents=%d",
        titles_col.count(),
        contents_col.count(),
    )


def main():
    parser = argparse.ArgumentParser(
        description="docling 파싱 결과(업무편람)를 ChromaDB에 적재",
    )
    parser.add_argument("--input", "-i", help="docling.json 경로")
    parser.add_argument(
        "--all", action="store_true", help="data/processed/ 전체 인제스트",
    )
    parser.add_argument(
        "--clear", action="store_true", help="기존 컬렉션 삭제 후 재생성",
    )
    args = parser.parse_args()

    if not args.input and not args.all:
        parser.error("-i 또는 --all 옵션이 필요합니다")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
