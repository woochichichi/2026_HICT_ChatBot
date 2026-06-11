"""KeywordIndex(BM25) 테스트 (api-spec.md 섹션 10) — 네트워크/API 키 불필요.

검증: 토큰화(고유명사/코드 보존), BM25 순위, 컬렉션 변경 시 자동 재구축.
"""

import uuid

import chromadb
import pytest

from backend.services.keyword_index import KeywordIndex, tokenize


def test_tokenize_preserves_codes():
    """고유명사·코드가 토큰으로 보존되는지 — Hybrid의 존재 이유."""
    tokens = tokenize("K-OTC 시장 매매와 분류코드 80~89인 일반법인")
    assert "k-otc" in tokens
    assert "80~89" in tokens
    assert "매매" in tokens  # 한국어 bigram
    assert "시장" in tokens


def test_tokenize_korean_bigram_matches_with_josa():
    """조사가 붙어도("고객번호는") 질의("고객번호")와 토큰이 겹쳐야 함."""
    doc_tokens = set(tokenize("고객번호는 총8자리로 자동부여된다"))
    query_tokens = set(tokenize("고객번호"))
    assert query_tokens & doc_tokens  # 공통 bigram 존재
    assert "고객" in doc_tokens
    assert any("8" in t for t in doc_tokens)


@pytest.fixture
def cols():
    """더미 임베딩으로 채운 ChromaDB 컬렉션 (EphemeralClient 공유 → 고유 이름)."""
    suffix = uuid.uuid4().hex[:8]
    client = chromadb.EphemeralClient()
    titles = client.get_or_create_collection(f"t_{suffix}")
    contents = client.get_or_create_collection(f"c_{suffix}")

    docs = {
        "doc_a": ("매매 > K-OTC 시장", "K-OTC 시장 매매 제도에 대한 안내"),
        "doc_b": ("계좌 > 고객번호", "고객번호는 총8자리이며 자동부여된다"),
        "doc_c": ("서비스 > OTP", "스마트 OTP 발급 절차와 타기관자동등록"),
    }
    ids = list(docs.keys())
    titles.upsert(
        ids=ids,
        documents=[docs[i][0] for i in ids],
        embeddings=[[0.1, 0.2]] * len(ids),  # 더미 — BM25는 임베딩 안 씀
    )
    contents.upsert(
        ids=ids,
        documents=[docs[i][1] for i in ids],
        embeddings=[[0.1, 0.2]] * len(ids),
    )
    yield titles, contents
    client.delete_collection(titles.name)
    client.delete_collection(contents.name)


def test_bm25_ranks_exact_term_first(cols):
    titles, contents = cols
    idx = KeywordIndex(titles, contents)

    results = idx.search("K-OTC 매매")
    assert results, "검색 결과 없음"
    assert results[0][0] == "doc_a"

    results2 = idx.search("고객번호 자리수")
    assert results2[0][0] == "doc_b"


def test_rebuild_on_collection_change(cols):
    """증분 인제스트 후 count 변화 → 다음 검색에서 자동 재구축."""
    titles, contents = cols
    idx = KeywordIndex(titles, contents)
    assert idx.search("스마트 OTP")[0][0] == "doc_c"

    titles.upsert(ids=["doc_d"], documents=["청약 > 공모주"],
                  embeddings=[[0.1, 0.2]])
    contents.upsert(ids=["doc_d"], documents=["공모주 청약 일정과 균등배정"],
                    embeddings=[[0.1, 0.2]])

    results = idx.search("공모주 균등배정")
    assert results[0][0] == "doc_d"  # 재구축 없이는 불가능
