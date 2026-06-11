"""방식 B: 세션 쿠키 크롤링 커넥터 (api-spec.md 섹션 9).

브라우저로 보이는 위키 페이지를 세션 쿠키로 HTTP GET 한다.
사내 위키(wiki.hanwhawm.com) 확인된 패턴: /collector/pages.action?key=BM001

URL 템플릿은 사이트마다 달라서 전부 설정 주입:
  - page_list_template: 공간의 페이지 목록 화면 (전체 크롤 진입점)
  - recent_template:    "최근 업데이트" 화면 (증분 크롤 진입점, 회사에서 URL 확인)

주의 (docs/TROUBLESHOOTING.md 2026-05-08):
  httpx는 SSL_CERT_FILE을 자동 인식하지 않음 → 명시적으로 verify에 전달.
  사내 위키가 자체 서명 인증서면 .env의 SSL_CERT_FILE이 그대로 쓰인다.

사용처: scripts/sync_manual.py --source crawl [--incremental]
"""

import logging
import os
import re
import time
from typing import Iterator
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import RawDocument, SourceConnector

logger = logging.getLogger(__name__)

# 페이지 본문으로 인정할 링크 패턴.
# 주의: "/display/..." 패턴은 사이드바의 다른 공간 링크까지 매칭되어 크롤러가
# 다른 공간으로 새는 문제가 있어 제외 (사내 위키 목록 화면 실측 — 2026-06-11).
_PAGE_LINK_RE = re.compile(r"viewpage\.action\?pageId=\d+")
_PAGE_ID_RE = re.compile(r"viewpage\.action\?pageId=(\d+)")

# 세션 만료 감지: 로그인 화면으로 리다이렉트되면 응답 URL/본문에 흔적이 남음
_LOGIN_MARKERS = ("login.action", "loginform", "os_username")

# Confluence 페이지 트리 AJAX 엔드포인트 (목록 화면의 treeRequestId 실측값 기본)
# 목록 화면의 트리는 AJAX 로딩이라 정적 HTML에는 일부만 있음 →
# 이 엔드포인트를 재귀 호출해야 접힌 페이지까지 전체 순회 가능.
_TREE_ENDPOINT_DEFAULT = (
    "/plugins/pagetree/naturalchildren.action"
    "?decorator=none&excerpt=false&sort=position&reverse=false"
    "&disableLinks=false&expandCurrent=false"
)


class SessionExpiredError(RuntimeError):
    """쿠키 만료 — 배치를 즉시 중단하고 명확히 알린다 (경고 후 속행 금지)."""


class CookieCrawlConnector(SourceConnector):
    """세션 쿠키 기반 위키 크롤러.

    전체 모드: page_list_template 화면에서 페이지 링크 추출 → 각각 GET
    증분 모드: recent_template 화면에서 링크 추출 → 그 페이지만 GET
    """

    name = "crawl"

    def __init__(
        self,
        base_url: str,
        cookie: str,
        space_keys: list[str],
        *,
        page_list_template: str = "{base}/pages.action?key={space}",
        recent_template: str = "{base}/pages/recentlyupdated.action?key={space}",
        delay_sec: float = 0.5,
        max_pages: int = 2000,
        timeout_sec: float = 20.0,
    ):
        if not base_url or not cookie or not space_keys:
            raise ValueError("base_url, cookie, space_keys는 필수입니다")
        self.base_url = base_url.rstrip("/")
        self.space_keys = space_keys
        self.page_list_template = page_list_template
        self.recent_template = recent_template
        self.delay_sec = delay_sec
        self.max_pages = max_pages

        # httpx는 SSL_CERT_FILE 자동 인식 안 함 → 명시 전달 (TROUBLESHOOTING 참조)
        verify = os.environ.get("SSL_CERT_FILE") or True
        self.client = httpx.Client(
            headers={
                "Cookie": cookie,
                "User-Agent": "hict-chatbot-sync/0.1 (internal PoC)",
            },
            verify=verify,
            follow_redirects=True,
            timeout=timeout_sec,
        )

    # --- 공개 API ---

    def iter_documents(self, incremental: bool = False) -> Iterator[RawDocument]:
        seen: set[str] = set()
        fetched = 0

        for space in self.space_keys:
            if incremental:
                # 증분: "최근 업데이트" 화면의 링크만
                entry_url = self.recent_template.format(base=self.base_url, space=space)
                logger.info("[증분] 진입점: %s", entry_url)
                page_urls = self._extract_page_links(self._get(entry_url), entry_url)
            else:
                # 전체: 목록 화면에서 페이지 트리 파라미터 추출 → AJAX 재귀 순회
                entry_url = self.page_list_template.format(base=self.base_url, space=space)
                logger.info("[전체] 진입점: %s", entry_url)
                entry_html = self._get(entry_url)
                tree = self._extract_tree_params(entry_html)
                if tree:
                    logger.info(
                        "  페이지 트리 발견: rootPageId=%s — 전체 트리 순회",
                        tree["root_page_id"],
                    )
                    page_urls = [
                        f"{self.base_url}/pages/viewpage.action?pageId={pid}"
                        for pid in self._iter_tree_page_ids(
                            tree["root_page_id"], tree["endpoint"], space,
                        )
                    ]
                else:
                    # 트리 없으면 화면 내 링크 추출로 폴백
                    logger.warning("  페이지 트리 없음 — 화면 링크 추출로 폴백")
                    page_urls = self._extract_page_links(entry_html, entry_url)

            logger.info("  → 페이지 %d건", len(page_urls))

            for url in page_urls:
                source_id = self._source_id_of(url)
                if source_id in seen:
                    continue
                seen.add(source_id)

                if fetched >= self.max_pages:
                    logger.warning("max_pages(%d) 도달 — 크롤 중단", self.max_pages)
                    return

                html = self._get(url)
                fetched += 1
                yield RawDocument(
                    source_id=source_id,
                    title=None,  # 파서가 <title>에서 추출
                    html=html,
                    url=url,
                )
                time.sleep(self.delay_sec)  # 사내 서버 부하 방지

    def close(self) -> None:
        self.client.close()

    # --- 내부 ---

    def _get(self, url: str) -> str:
        resp = self.client.get(url)
        resp.raise_for_status()
        final_url = str(resp.url)
        # 세션 만료 → 로그인 화면 리다이렉트 감지 (조용히 빈 데이터 적재 방지)
        if any(m in final_url.lower() for m in _LOGIN_MARKERS):
            raise SessionExpiredError(
                f"세션 만료로 추정 — 로그인 화면으로 리다이렉트됨: {final_url}\n"
                "브라우저에서 쿠키를 다시 복사해 .env의 WIKI_COOKIE를 갱신하세요."
            )
        return resp.text

    def _extract_page_links(self, html: str, entry_url: str) -> list[str]:
        """화면에서 페이지 본문 링크를 추출 (순서 유지, 중복 제거).

        사이드바·드롭다운의 다른 공간 링크가 섞이지 않도록
        본문 영역(#content)이 있으면 그 안에서만 추출한다 (실측 — 2026-06-11).
        """
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one("#content") or soup
        urls: list[str] = []
        seen: set[str] = set()
        for a in root.find_all("a", href=True):
            href = a["href"]
            if not _PAGE_LINK_RE.search(href):
                continue
            absolute = urljoin(entry_url, href)
            sid = self._source_id_of(absolute)
            if sid in seen:
                continue
            seen.add(sid)
            urls.append(absolute)
        return urls

    @staticmethod
    def _extract_tree_params(html: str) -> dict | None:
        """목록 화면의 plugin_pagetree fieldset에서 트리 순회 파라미터 추출.

        실측 (wiki.hanwhawm.com/collector/pages.action?key=BM001):
          rootPageId=23069356, spaceKey=BM001,
          treeRequestId=/plugins/pagetree/naturalchildren.action?...
        """
        soup = BeautifulSoup(html, "html.parser")
        root_input = soup.find("input", attrs={"name": "rootPageId"})
        if root_input is None or not root_input.get("value"):
            return None
        endpoint_input = soup.find("input", attrs={"name": "treeRequestId"})
        endpoint = (
            endpoint_input.get("value") if endpoint_input and endpoint_input.get("value")
            else _TREE_ENDPOINT_DEFAULT
        )
        return {
            "root_page_id": root_input["value"],
            "endpoint": endpoint,
        }

    def _iter_tree_page_ids(
        self, root_page_id: str, endpoint: str, space: str,
    ) -> list[str]:
        """naturalchildren.action을 BFS 재귀 호출해 트리 전체 pageId 수집.

        목록 화면의 정적 HTML에는 펼쳐진 노드만 있으므로(AJAX 트리),
        노드별로 자식 조회를 호출해야 접힌 페이지까지 발견된다.
        """
        ordered: list[str] = [root_page_id]
        visited: set[str] = {root_page_id}
        queue: list[str] = [root_page_id]

        while queue:
            pid = queue.pop(0)
            if len(ordered) >= self.max_pages:
                logger.warning("트리 순회 max_pages(%d) 도달", self.max_pages)
                break
            url = (
                f"{self.base_url}{endpoint}"
                f"&hasRoot=true&pageId={pid}&treeId=0&startDepth=0&spaceKey={space}"
            )
            try:
                fragment = self._get(url)
            except httpx.HTTPStatusError as e:
                logger.warning("자식 조회 실패 (pageId=%s): %s", pid, e)
                continue
            for child_id in _PAGE_ID_RE.findall(fragment):
                if child_id not in visited:
                    visited.add(child_id)
                    ordered.append(child_id)
                    queue.append(child_id)
            time.sleep(self.delay_sec)

        return ordered

    @staticmethod
    def _source_id_of(url: str) -> str:
        """URL → 안정적 source_id. pageId가 있으면 그것, 없으면 경로."""
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "pageId" in qs:
            return f"pageId:{qs['pageId'][0]}"
        return parsed.path
