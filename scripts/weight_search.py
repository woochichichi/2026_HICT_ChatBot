"""가중치 그리드 서치 — TITLE_WEIGHT:CONTENT_WEIGHT 최적값 탐색 (WBS 3.1).

api-spec.md 섹션 3: RAG 검색 가중치를 [5:5, 4:6, 3:7]로 비교 테스트.
config.py의 TITLE_WEIGHT/CONTENT_WEIGHT 기본값 확정을 위한 스크립트.

사용법:
    python scripts/weight_search.py

출력: 각 가중치 조합별 검색 품질 비교표
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.embedder import GeminiService
from backend.services.rag import RAGService, get_chroma_client, init_collections

# 가중치 조합 (api-spec.md 섹션 3: 3주차에 그리드 서치로 최적값 확정)
WEIGHT_COMBOS = [
    (0.5, 0.5),  # 5:5
    (0.4, 0.6),  # 4:6
    (0.3, 0.7),  # 3:7
]

# 테스트 질문 — 인제스트된 업무편람 내용 기반
# 질문은 실제 상담원이 할 법한 자연어 형태로 작성
TEST_QUESTIONS = [
    "고객정보 등록할 때 기본정보에 뭐가 필요해?",
    "실명확인 절차가 어떻게 되나요?",
    "비대면 계좌 개설 시 필요한 서류",
    "고객 정보 변경은 어떻게 하나요?",
    "자금세탁방지 관련 확인 사항",
]


async def run_search(rag: RAGService, question: str) -> list[dict]:
    """단일 질문에 대해 RAG 검색 수행."""
    return await rag.search(question)


async def evaluate_weights(title_w: float, content_w: float) -> dict:
    """특정 가중치 조합으로 전체 테스트 질문 평가."""
    llm = GeminiService()
    rag = RAGService(llm=llm)

    # 가중치 오버라이드 (config.py 기본값 대신)
    rag.title_weight = title_w
    rag.content_weight = content_w

    total_score = 0.0
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    results = []

    for q in TEST_QUESTIONS:
        contexts = await run_search(rag, q)
        if contexts:
            top_score = contexts[0]["score"]
            confidence = rag._calc_confidence(top_score)
        else:
            top_score = 0.0
            confidence = "low"

        total_score += top_score
        confidence_counts[confidence] += 1
        results.append({
            "question": q,
            "top_score": round(top_score, 4),
            "confidence": confidence,
            "top_title": contexts[0]["title"][:40] if contexts else "N/A",
        })

    return {
        "weights": f"{title_w}:{content_w}",
        "avg_score": round(total_score / len(TEST_QUESTIONS), 4),
        "confidence_dist": confidence_counts,
        "details": results,
    }


async def main():
    # ChromaDB 데이터 확인
    client = get_chroma_client()
    _, contents_col = init_collections(client)
    doc_count = contents_col.count()
    if doc_count == 0:
        print("ChromaDB에 데이터 없음. 먼저 인제스트를 실행하세요:")
        print("  python scripts/ingest_manual.py --all")
        return

    print(f"ChromaDB 문서 수: {doc_count}")
    print(f"테스트 질문 수: {len(TEST_QUESTIONS)}")
    print("=" * 70)

    all_results = []
    for title_w, content_w in WEIGHT_COMBOS:
        print(f"\n--- 가중치 {title_w}:{content_w} 테스트 중... ---")
        result = await evaluate_weights(title_w, content_w)
        all_results.append(result)

        # 개별 결과 출력
        for d in result["details"]:
            print(f"  Q: {d['question'][:30]}... → {d['confidence']} ({d['top_score']}) | {d['top_title']}")

    # 비교표 출력
    print("\n" + "=" * 70)
    print("가중치 비교 결과")
    print("=" * 70)
    print(f"{'가중치':<12} {'평균점수':<10} {'high':<8} {'medium':<8} {'low':<8}")
    print("-" * 46)
    for r in all_results:
        c = r["confidence_dist"]
        print(f"{r['weights']:<12} {r['avg_score']:<10} {c['high']:<8} {c['medium']:<8} {c['low']:<8}")

    # 최적 가중치 추천
    best = max(all_results, key=lambda x: x["avg_score"])
    print(f"\n추천 가중치: {best['weights']} (평균 점수: {best['avg_score']})")


if __name__ == "__main__":
    asyncio.run(main())
