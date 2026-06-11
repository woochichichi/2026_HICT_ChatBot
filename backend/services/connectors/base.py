"""수집 커넥터 공통 인터페이스 (api-spec.md 섹션 9).

어떤 방식(로컬 폴더/쿠키 크롤링/REST API)으로 수집하든
출력은 동일한 RawDocument → 이후 파이프라인(파싱→diff→적재)은 한 줄도 안 바뀐다.

구현체:
  - local_html.py: LocalHtmlConnector — 저장된 HTML 폴더 (방식 A)
  - confluence_crawl.py: CookieCrawlConnector — 세션 쿠키 크롤링 (방식 B)

이 모듈을 사용하는 곳:
  - scripts/sync_manual.py: --source 옵션으로 구현체 선택
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class RawDocument:
    """수집된 원본 문서 — 파싱 전 단계의 공통 표현."""

    source_id: str        # 안정적 ID (위키 pageId, 파일 상대경로 등)
    title: str | None     # 페이지 제목 (모르면 None — 파서가 HTML에서 추출)
    html: str             # HTML 전문
    url: str | None = None  # 원본 URL (출처 표시용)


class SourceConnector(ABC):
    """수집 방식 추상화. iter_documents가 RawDocument를 순차 yield."""

    name: str = "base"

    @abstractmethod
    def iter_documents(self, incremental: bool = False) -> Iterator[RawDocument]:
        """문서 스트림 반환.

        Args:
            incremental: True면 "변경된 페이지만" 수집 시도.
                커넥터가 증분을 지원하지 않으면 전체를 반환해도 됨 —
                diff 계층(ingest.sync_document)이 hash로 걸러내므로 결과는 동일.
        """
        ...
