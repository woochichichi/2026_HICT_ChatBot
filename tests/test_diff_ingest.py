"""diff 인제스트 테스트 (api-spec.md 섹션 9) — 변경분만 임베딩되는지 검증.

시나리오 (픽스처 v1 → v2: 문단 1개 수정 + 섹션 1개 삭제):
  1. v1 최초 동기화  → 전 청크 임베딩
  2. v1 재동기화     → 임베딩 0건 (전부 스킵)
  3. v2 동기화       → 변경 청크만 임베딩 + 삭제 청크 제거
  4. 문서 삭제       → 청크 전체 제거

FakeLLM: 임베딩 호출 수를 세는 가짜 임베더 (네트워크/API 키 불필요 — 집 PC 검증용).
"""

import hashlib
from pathlib import Path

import chromadb
import pytest

from backend.services.ingest import (
    delete_document_chunks,
    prepare_chunks,
    sync_document,
)
from backend.services.parsers.confluence_html import parse_html
from backend.services.stores.meta_sqlite import MetaStore

FIXTURES = Path(__file__).parent / "fixtures"


class FakeLLM:
    """결정적 가짜 임베더 — 텍스트 sha1 기반 8차원 벡터, 호출 텍스트 수 기록."""

    def __init__(self):
        self.embedded_texts = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded_texts += len(texts)
        vectors = []
        for t in texts:
            h = hashlib.sha1(t.encode("utf-8")).digest()
            vectors.append([b / 255.0 for b in h[:8]])
        return vectors


@pytest.fixture
def env(tmp_path):
    """EphemeralClient + 임시 메타DB — 실제 ChromaDB 파일/네트워크 비의존.

    주의: EphemeralClient는 같은 프로세스 내에서 인메모리 저장소를 공유하므로
    테스트 간 격리를 위해 컬렉션 이름을 테스트마다 고유하게 생성한다.
    """
    import uuid

    suffix = uuid.uuid4().hex[:8]
    client = chromadb.EphemeralClient()
    titles = client.get_or_create_collection(
        f"faq_titles_{suffix}", metadata={"hnsw:space": "cosine"}
    )
    contents = client.get_or_create_collection(
        f"faq_contents_{suffix}", metadata={"hnsw:space": "cosine"}
    )
    meta = MetaStore(str(tmp_path / "meta.db"))
    llm = FakeLLM()
    yield llm, titles, contents, meta
    meta.close()
    client.delete_collection(titles.name)
    client.delete_collection(contents.name)


def _parse(fixture_name: str):
    html = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    return parse_html(html, source_id="pageId:12345")


@pytest.mark.asyncio
async def test_initial_sync_embeds_all(env):
    llm, titles, contents, meta = env
    parsed = _parse("wiki_sample_v1.html")

    result = await sync_document(parsed, llm, titles, contents, meta)

    assert result.added > 0
    assert result.removed == 0
    assert result.unchanged == 0
    # title + content 양쪽 임베딩
    assert result.embed_texts == result.added * 2
    assert titles.count() == result.added
    assert contents.count() == result.added
    assert len(meta.get_chunk_ids(parsed.doc_id)) == result.added


@pytest.mark.asyncio
async def test_resync_same_content_embeds_nothing(env):
    """핵심 검증: 같은 내용 재동기화 시 임베딩 비용 0."""
    llm, titles, contents, meta = env
    parsed = _parse("wiki_sample_v1.html")

    first = await sync_document(parsed, llm, titles, contents, meta)
    llm.embedded_texts = 0

    second = await sync_document(parsed, llm, titles, contents, meta)

    assert second.added == 0
    assert second.removed == 0
    assert second.unchanged == first.added
    assert llm.embedded_texts == 0          # 임베딩 호출 자체가 없어야 함
    assert titles.count() == first.added    # 컬렉션 변화 없음


@pytest.mark.asyncio
async def test_modified_doc_embeds_only_changed(env):
    """v1→v2: 문단 1개 수정 + 섹션 1개 삭제 → 변경분만 반영."""
    llm, titles, contents, meta = env
    v1 = _parse("wiki_sample_v1.html")
    v2 = _parse("wiki_sample_v2.html")
    assert v1.doc_id == v2.doc_id  # 같은 페이지 (source_id 동일)

    first = await sync_document(v1, llm, titles, contents, meta)
    result = await sync_document(v2, llm, titles, contents, meta)

    # 변경분만: 추가/삭제가 전체보다 훨씬 적어야 함
    assert 0 < result.added < first.added
    assert 0 < result.removed < first.added
    assert result.unchanged > 0
    # 표/notice/절차 등 안 바뀐 청크는 그대로 → 스킵 비율이 더 커야 정상
    assert result.unchanged >= result.added

    # 정합성: 컬렉션 수 == 메타DB 청크 수 == v2 청크 수
    expected = len(prepare_chunks(v2))
    assert titles.count() == expected
    assert contents.count() == expected
    assert len(meta.get_chunk_ids(v2.doc_id)) == expected

    # 삭제된 섹션("유의사항")의 내용이 검색 대상에서 사라졌는지
    remaining = contents.get(include=["documents"])["documents"]
    assert not any("해외 거주자" in d for d in remaining)
    # 수정된 문단의 새 내용이 들어갔는지
    assert any("2026년 개정" in d for d in remaining)


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(env):
    llm, titles, contents, meta = env
    parsed = _parse("wiki_sample_v1.html")

    result = await sync_document(parsed, llm, titles, contents, meta, dry_run=True)

    assert result.added > 0           # 변경량은 계산되지만
    assert llm.embedded_texts == 0    # 임베딩 없음
    assert titles.count() == 0        # 적재 없음
    assert len(meta.get_chunk_ids(parsed.doc_id)) == 0  # 메타 기록 없음


@pytest.mark.asyncio
async def test_delete_document_chunks(env):
    llm, titles, contents, meta = env
    parsed = _parse("wiki_sample_v1.html")

    first = await sync_document(parsed, llm, titles, contents, meta)
    deleted = delete_document_chunks(parsed.doc_id, titles, contents, meta)

    assert deleted == first.added
    assert titles.count() == 0
    assert contents.count() == 0
    assert len(meta.get_chunk_ids(parsed.doc_id)) == 0


def test_chunk_id_is_content_based():
    """내용이 같으면 chunk_id 동일 — diff의 전제."""
    v1 = _parse("wiki_sample_v1.html")
    ids_a = {c["chunk_id"] for c in prepare_chunks(v1)}
    ids_b = {c["chunk_id"] for c in prepare_chunks(v1)}
    assert ids_a == ids_b
