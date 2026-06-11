"""CLI: 위키 업무편람 → ChromaDB 증분(diff) 동기화 배치 (api-spec.md 섹션 9).

흐름 (docs/design-ingest-pipeline.html):
  1. 커넥터(--source dir|crawl)가 RawDocument 수집
  2. 문서 raw hash가 메타DB와 같으면 파싱조차 안 하고 스킵 (1차 스킵)
  3. 변경 시: confluence_html 파싱 → ingest.sync_document (변경 청크만 임베딩)
  4. --prune: 이번 실행에서 안 보인 문서의 청크 삭제 (전체 모드에서만)
  5. sync_runs에 리포트 기록 + 콘솔 출력

사용법:
    # 방식 A — 저장된 HTML 폴더
    python scripts/sync_manual.py --source dir --path data/raw/wiki_html/

    # 방식 B — 세션 쿠키 크롤링 (.env의 WIKI_* 설정 사용)
    python scripts/sync_manual.py --source crawl                 # 전체
    python scripts/sync_manual.py --source crawl --incremental   # 변경분만

    # 옵션
    --dry-run   적재 없이 변경량만 출력
    --prune     사라진 문서의 청크 삭제 (전체 모드 전용)
"""

import argparse
import asyncio
import hashlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.services.connectors.base import SourceConnector
from backend.services.connectors.local_html import LocalHtmlConnector
from backend.services.embedder import GeminiService
from backend.services.ingest import delete_document_chunks, sync_document
from backend.services.parsers.confluence_html import parse_html
from backend.services.rag import get_chroma_client, init_collections
from backend.services.stores.meta_sqlite import MetaStore, now_iso

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_connector(args: argparse.Namespace) -> SourceConnector:
    """--source 값으로 커넥터 생성. crawl 설정은 .env(WIKI_*)에서."""
    if args.source == "dir":
        if not args.path:
            raise SystemExit("--source dir 사용 시 --path 필수")
        return LocalHtmlConnector(args.path)

    if args.source == "crawl":
        # crawl 의존성(httpx)은 사용할 때만 import — dir 모드는 네트워크 무관
        from backend.services.connectors.confluence_crawl import CookieCrawlConnector

        spaces = [s.strip() for s in settings.WIKI_SPACE_KEYS.split(",") if s.strip()]
        return CookieCrawlConnector(
            base_url=settings.WIKI_BASE_URL,
            cookie=settings.WIKI_COOKIE,
            space_keys=spaces,
            page_list_template=settings.WIKI_PAGE_LIST_URL,
            recent_template=settings.WIKI_RECENT_URL,
            delay_sec=settings.WIKI_CRAWL_DELAY,
        )

    raise SystemExit(f"지원하지 않는 source: {args.source}")


async def run(args: argparse.Namespace) -> None:
    started_at = now_iso()
    connector = _build_connector(args)

    llm = GeminiService()
    client = get_chroma_client()
    titles_col, contents_col = init_collections(client)
    meta = MetaStore(args.meta_db)

    docs_total = 0
    docs_changed = 0
    docs_deleted = 0
    chunks_added = 0
    chunks_deleted = 0
    embed_calls = 0
    seen_source_ids: set[str] = set()

    try:
        for raw in connector.iter_documents(incremental=args.incremental):
            docs_total += 1
            seen_source_ids.add(raw.source_id)

            # --- 1차 스킵: 원본 HTML hash가 같으면 파싱조차 안 함 ---
            raw_hash = hashlib.sha256(raw.html.encode("utf-8")).hexdigest()
            existing = meta.get_document(raw.source_id)
            if existing and existing["raw_hash"] == raw_hash:
                meta.touch_seen(raw.source_id)
                continue

            # --- 변경된 문서만 파싱 + diff 동기화 ---
            parsed = parse_html(
                raw.html,
                source_id=raw.source_id,
                url=raw.url,
                title=raw.title,
            )
            if not parsed.blocks:
                logger.warning("블록 없음 — 스킵: %s", raw.source_id)
                continue

            result = await sync_document(
                parsed, llm, titles_col, contents_col, meta,
                dry_run=args.dry_run,
            )
            docs_changed += 1
            chunks_added += result.added
            chunks_deleted += result.removed
            embed_calls += result.embed_texts

            if not args.dry_run:
                meta.upsert_document(
                    source_id=raw.source_id,
                    doc_id=parsed.doc_id,
                    title=parsed.title,
                    url=raw.url,
                    raw_hash=raw_hash,
                )

        # --- prune: 이번 전체 실행에서 안 보인 문서 = 위키에서 삭제됨 ---
        # 증분 모드에서는 "안 보임 = 변경 없음"이므로 prune 금지
        if args.prune and not args.incremental and not args.dry_run:
            for row in meta.active_documents():
                if row["source_id"] in seen_source_ids:
                    continue
                n = delete_document_chunks(
                    row["doc_id"], titles_col, contents_col, meta
                )
                meta.mark_deleted(row["source_id"])
                docs_deleted += 1
                chunks_deleted += n
                logger.info("삭제된 문서 정리: %s (-%d 청크)", row["title"], n)

        if not args.dry_run:
            meta.record_sync_run(
                started_at=started_at,
                mode="incremental" if args.incremental else "full",
                source=args.source,
                docs_total=docs_total,
                docs_changed=docs_changed,
                docs_deleted=docs_deleted,
                chunks_added=chunks_added,
                chunks_deleted=chunks_deleted,
                embed_calls=embed_calls,
            )

        logger.info("=" * 60)
        logger.info(
            "%s완료: 문서 %d건 중 %d건 변경%s | 청크 +%d / -%d | 임베딩 %d건",
            "[dry-run] " if args.dry_run else "",
            docs_total, docs_changed,
            f", {docs_deleted}건 삭제" if docs_deleted else "",
            chunks_added, chunks_deleted, embed_calls,
        )
        logger.info(
            "컬렉션 현황: faq_titles=%d, faq_contents=%d",
            titles_col.count(), contents_col.count(),
        )
    finally:
        meta.close()
        if hasattr(connector, "close"):
            connector.close()


def main():
    parser = argparse.ArgumentParser(
        description="위키 업무편람 → ChromaDB 증분(diff) 동기화",
    )
    parser.add_argument(
        "--source", choices=["dir", "crawl"], required=True,
        help="dir=저장된 HTML 폴더, crawl=세션 쿠키 크롤링(.env WIKI_* 필요)",
    )
    parser.add_argument("--path", help="--source dir일 때 HTML 폴더 경로")
    parser.add_argument(
        "--incremental", action="store_true",
        help="변경분만 크롤 (crawl 전용 — '최근 업데이트' 화면 사용)",
    )
    parser.add_argument(
        "--prune", action="store_true",
        help="이번 실행에서 안 보인 문서의 청크 삭제 (전체 모드 전용)",
    )
    parser.add_argument("--dry-run", action="store_true", help="적재 없이 변경량만 출력")
    parser.add_argument(
        "--meta-db", default=settings.META_DB_PATH,
        help=f"메타 DB 경로 (기본: {settings.META_DB_PATH})",
    )
    args = parser.parse_args()

    if args.incremental and args.prune:
        parser.error("--incremental에서는 --prune 사용 불가 (안 보임 ≠ 삭제됨)")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
