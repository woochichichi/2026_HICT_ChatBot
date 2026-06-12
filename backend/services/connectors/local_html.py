"""방식 A: 로컬 HTML 폴더 커넥터 (api-spec.md 섹션 9).

브라우저 "다른 이름으로 저장"이나 위키 내보내기로 받은 HTML 파일들을
폴더째 읽는다. API/크롤링 확인 전 0순위 + 집 PC 테스트용.

사용처: scripts/sync_manual.py --source dir --path data/raw/wiki_html/
"""

import logging
from pathlib import Path
from typing import Iterator

from .base import RawDocument, SourceConnector

logger = logging.getLogger(__name__)


class LocalHtmlConnector(SourceConnector):
    """폴더 하위의 *.html / *.htm 파일을 RawDocument로 변환."""

    name = "dir"

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        if not self.root.is_dir():
            raise FileNotFoundError(f"폴더 없음: {root_dir}")

    def iter_documents(self, incremental: bool = False) -> Iterator[RawDocument]:
        # incremental은 무시 — 파일은 전부 읽고 diff 계층이 hash로 걸러냄
        paths = sorted(
            p for p in self.root.rglob("*")
            if p.suffix.lower() in (".html", ".htm")
        )
        if not paths:
            logger.warning("HTML 파일 없음: %s", self.root)
        for p in paths:
            html = self._read_text(p)
            if html is None:
                continue
            # source_id = 루트 기준 상대경로 — 파일을 다시 받아도 ID 안정
            rel = p.relative_to(self.root).as_posix()
            yield RawDocument(
                source_id=rel,
                # title=None: 파서가 HTML <title>에서 실제 페이지 제목 추출.
                # 파일명(page_<id>)을 넘기면 파서가 추출을 건너뛰어 출처가
                # 파일명으로 표시되는 버그가 있었음 (2026-06-12)
                title=None,
                html=html,
                url=None,
            )

    @staticmethod
    def _read_text(path: Path) -> str | None:
        """UTF-8 우선, 실패 시 cp949 폴백 (Windows 한글 저장 파일 대응)."""
        for enc in ("utf-8", "cp949"):
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.error("파일 읽기 실패: %s (%s)", path, e)
                return None
        logger.error("인코딩 판별 실패 (utf-8/cp949 모두 아님): %s", path)
        return None
