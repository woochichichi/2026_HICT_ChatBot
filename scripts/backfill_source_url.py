"""기존 ChromaDB 청크 메타데이터 백필 (재임베딩 없음).

두 가지를 보정한다 (파서 수정 전 적재분 대상):
  1. source_url — 파일명(page_<id>.html)에서 위키 URL 복원
  2. source_document/source_label — 파일명 대신 HTML <title>의 실제 페이지 제목

ChromaDB metadata만 update(임베딩 재계산 X)하므로 한도 영향 없음.

사용법:
    python scripts/backfill_source_url.py --path data/raw/wiki_subset/
"""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.parsers.confluence_html import _derive_source_url, parse_html
from backend.services.rag import get_chroma_client, init_collections


def main():
    parser = argparse.ArgumentParser(description="ChromaDB 청크에 source_url 백필")
    parser.add_argument("--path", required=True, help="수집 HTML 폴더 (page_*.html)")
    args = parser.parse_args()

    files = sorted(Path(args.path).glob("*.html"))
    if not files:
        raise SystemExit(f"HTML 파일 없음: {args.path}")

    client = get_chroma_client()
    titles_col, contents_col = init_collections(client)

    updated_docs = 0
    updated_chunks = 0
    for f in files:
        source_id = f.name
        doc_id = hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:16]
        url = _derive_source_url(source_id, None)
        # HTML <title>에서 실제 페이지 제목 추출 (파일명 대체)
        parsed = parse_html(
            f.read_text(encoding="utf-8", errors="replace"),
            source_id=source_id, title=None,
        )
        real_title = parsed.title or ""

        # 두 컬렉션 모두 같은 doc_id 청크의 metadata 보정
        touched = False
        for col in (titles_col, contents_col):
            got = col.get(where={"doc_id": doc_id}, include=["metadatas"])
            ids = got["ids"]
            if not ids:
                continue
            metas = got["metadatas"]
            for m in metas:
                if url:
                    m["source_url"] = url
                # source_document가 파일명(page_<id>)이면 실제 제목으로 교체
                if real_title and str(m.get("source_document", "")).startswith("page_"):
                    m["source_document"] = real_title
            col.update(ids=ids, metadatas=metas)
            updated_chunks += len(ids)
            touched = True
        if touched:
            updated_docs += 1

    print(f"백필 완료: 문서 {updated_docs}건, 청크 {updated_chunks}건 메타데이터 보정")


if __name__ == "__main__":
    main()
