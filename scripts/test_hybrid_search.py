"""Hybrid Search 수동 테스트 스크립트.

벡터 검색과 BM25 키워드 검색의 단계별 점수를 출력하고,
순수 벡터 검색(alpha=1.0)과 Hybrid(alpha 기본값)의 순위 차이를 비교한다.

실행:
    # 기본 내장 쿼리 5개 실행
    python -m scripts.test_hybrid_search

    # 특정 쿼리 직접 입력
    python -m scripts.test_hybrid_search "ISA 비과세 한도"

    # alpha 오버라이드 (0.0=BM25 only, 1.0=vector only)
    python -m scripts.test_hybrid_search "비대면 계좌 개설" --alpha 0.5

이 모듈을 사용하는 곳:
  - 개발자 로컬 검색 품질 검증
  - scripts/weight_search.py: HYBRID_ALPHA 그리드 서치 기반으로 활용 예정
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.services.embedder import GeminiService
from backend.services.rag import RAGService

# --- 로깅 설정 ---
# INFO: 검색 시작/완료, BM25 빌드
# DEBUG: 단계별 점수 상세 (--verbose 옵션 시 활성화)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

# 내장 테스트 쿼리 — 자연어 vs 키워드 두 유형 혼합
DEFAULT_QUERIES = [
    "비대면 계좌 개설 절차가 어떻게 되나요?",   # 자연어 → 벡터 유리
    "ISA 비과세 한도",                         # 고유명사 키워드 → BM25 유리
    "CMA RP형 이율",                           # 약어 → BM25 유리
    "계좌 개설 서류 필요한 거 알려줘",           # 일상 구어체 → 벡터 유리
    "제5조",                                   # 조문 번호 → BM25 유리
]

SEP = "─" * 70


def _rank_label(rank: int) -> str:
    return f"#{rank}"


async def run_query(rag: RAGService, query: str, top_k: int = 5) -> None:
    """단일 쿼리 실행 후 단계별 점수와 최종 순위를 출력."""
    print(f"\n{SEP}")
    print(f"  질문: {query!r}")
    print(SEP)

    t0 = time.perf_counter()
    results = await rag.search(query, top_k=top_k)
    elapsed = (time.perf_counter() - t0) * 1000

    if not results:
        print("  결과 없음")
        return

    confidence = RAGService._calc_confidence(results[0]["score"])
    print(f"  검색 시간: {elapsed:.0f}ms  |  결과: {len(results)}건  |  confidence: {confidence}")
    print()

    # 헤더
    print(f"  {'순위':<4}  {'벡터점수':>8}  {'RRF점수':>10}  제목")
    print(f"  {'─'*4}  {'─'*8}  {'─'*10}  {'─'*40}")

    for i, r in enumerate(results, 1):
        title_short = r["title"][:42] if r["title"] else "(제목 없음)"
        src = r["source_document"]
        sp = r["source_page"]
        ref = src if (sp.startswith("http://") or sp.startswith("https://")) else f"{src} {sp}".strip()
        print(
            f"  {_rank_label(i):<4}  {r['score']:>8.3f}  {r['rrf_score']:>10.5f}  {title_short}"
        )
        if ref:
            print(f"        {'':8}  {'':10}  출처: {ref}")

    print()


async def compare_alpha(rag_hybrid: RAGService, llm: GeminiService, query: str, top_k: int = 5) -> None:
    """alpha=1.0(순수 벡터)과 hybrid alpha의 순위 차이를 나란히 출력."""
    import copy
    # 순수 벡터 버전: alpha=1.0 임시 RAGService
    rag_vec = RAGService(llm)
    rag_vec.hybrid_alpha = 1.0

    results_hybrid = await rag_hybrid.search(query, top_k=top_k)
    results_vec = await rag_vec.search(query, top_k=top_k)

    ids_hybrid = [r["id"] for r in results_hybrid]
    ids_vec = [r["id"] for r in results_vec]

    print(f"\n{SEP}")
    print(f"  [순위 비교] {query!r}")
    print(f"  {'순위':<4}  {'벡터 전용(α=1.0)':<35}  {'Hybrid(α=%.1f)' % rag_hybrid.hybrid_alpha:<35}")
    print(f"  {'─'*4}  {'─'*35}  {'─'*35}")

    max_len = max(len(ids_hybrid), len(ids_vec))
    for i in range(max_len):
        v_title = results_vec[i]["title"][:33] if i < len(results_vec) else "─"
        h_title = results_hybrid[i]["title"][:33] if i < len(results_hybrid) else "─"
        changed = "  ← 순위 변경" if (i < len(ids_vec) and i < len(ids_hybrid) and ids_vec[i] != ids_hybrid[i]) else ""
        print(f"  {_rank_label(i+1):<4}  {v_title:<35}  {h_title:<35}{changed}")
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid Search 테스트")
    parser.add_argument("query", nargs="?", help="테스트할 쿼리 (없으면 내장 쿼리 사용)")
    parser.add_argument("--alpha", type=float, default=None, help="HYBRID_ALPHA 오버라이드 (0.0~1.0)")
    parser.add_argument("--top-k", type=int, default=5, help="반환 건수 (기본 5)")
    parser.add_argument("--compare", action="store_true", help="벡터 전용 vs Hybrid 순위 비교 출력")
    parser.add_argument("--verbose", action="store_true", help="DEBUG 레벨 로그 출력 (단계별 점수 상세)")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("backend.services.rag").setLevel(logging.DEBUG)

    queries = [args.query] if args.query else DEFAULT_QUERIES

    print(f"\n{'='*70}")
    print("  Hybrid Search 테스트")
    print(f"  alpha={args.alpha if args.alpha is not None else settings.HYBRID_ALPHA}  "
          f"RRF_K={settings.RRF_K}  TOP_K={args.top_k}")
    print(f"  ChromaDB: {settings.CHROMA_DB_PATH}")
    print(f"{'='*70}")

    logger.info("GeminiService 초기화 중...")
    llm = GeminiService()

    logger.info("RAGService 초기화 중 (BM25 인덱스 빌드)...")
    rag = RAGService(llm)
    if args.alpha is not None:
        rag.hybrid_alpha = args.alpha
        logger.info("alpha 오버라이드 적용: %.2f", args.alpha)

    for query in queries:
        await run_query(rag, query, top_k=args.top_k)
        if args.compare:
            await compare_alpha(rag, llm, query, top_k=args.top_k)

    print(f"{'='*70}")
    print("  완료")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
