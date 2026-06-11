"""CLI: docling 파싱 결과(업무편람 PDF)를 ChromaDB에 적재.

청킹 로직은 backend/services/ingest.py로 이동 (위키 동기화와 공용 — api-spec.md 섹션 9).
이 스크립트의 CLI·동작·chunk_id 형식({doc_id}_{블록순번})은 기존과 100% 동일.

블록 타입별 청킹 가이드라인: backend/services/ingest.py의 _CHUNK_CONFIG 참조.

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
from backend.models.parsed_document import ParsedDocument
from backend.services.embedder import GeminiService
from backend.services.ingest import build_metadata, chunk_blocks, embed_in_batches
from backend.services.rag import get_chroma_client, init_collections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


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
        metadatas.append(build_metadata(ch["blocks"], parsed))

    logger.info(
        "임베딩 시작: %s — %d 블록 → %d 청크",
        parsed.doc_id, len(parsed.blocks), len(ids),
    )

    title_vectors = await embed_in_batches(llm, title_texts)
    content_vectors = await embed_in_batches(llm, content_texts)

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
