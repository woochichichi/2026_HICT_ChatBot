"""CLI: RAG 정확도 진단 — 검색 적중률과 답변 정확도 분리 측정 (api-spec.md 섹션 9).

"답변이 제대로 안 됨"의 원인을 가르는 도구:
  [검색 단계] retrieval hit@k — 정답 키워드가 top-k 검색 결과 안에 있는가?
  [생성 단계] answer keyword — 정답 키워드가 LLM 답변 안에 있는가? (--answers)

  검색 hit인데 답변 miss → 프롬프트/생성 문제 (과제 4b)
  검색 자체가 miss      → 검색 문제 → Hybrid Search 등으로 개선 (과제 2)

리포트는 data/eval/ 에 JSON 저장 — 베이스라인 vs Hybrid Search 비교용.

사용법:
    python scripts/test_accuracy.py                  # 검색만 (임베딩 호출 N회)
    python scripts/test_accuracy.py --answers        # 답변 생성까지 (LLM 호출 추가)
    python scripts/test_accuracy.py --top-k 5 --tag baseline

테스트셋: tests/test_questions.json
    [{"id", "category", "question",
      "expect": {"doc_contains": "...", "keywords": ["..."]}}]
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.services.embedder import GeminiService
from backend.services.rag import RAGService

logging.basicConfig(level=logging.WARNING)  # 진행 출력은 print로 깔끔하게

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "tests" / "test_questions.json"
EVAL_DIR = Path(settings.DATA_DIR) / "eval"


def _load_questions() -> list[dict]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    if not questions:
        raise SystemExit(
            f"테스트 질문이 없습니다: {QUESTIONS_PATH}\n"
            "tests/test_questions.json에 질문을 추가하세요."
        )
    return questions


def _judge_retrieval(results: list[dict], expect: dict) -> dict:
    """검색 결과 판정 — 정답 키워드/출처가 몇 위에 처음 등장하는지.

    keyword_rank: 정답 키워드 중 하나라도 content에 포함된 첫 순위 (1-base, 없으면 None)
    doc_rank:     기대 출처 문자열이 source_document에 포함된 첫 순위
    """
    keywords = expect.get("keywords", [])
    doc_sub = expect.get("doc_contains", "")

    keyword_rank = None
    doc_rank = None
    for rank, r in enumerate(results, 1):
        haystack = f"{r['title']}\n{r['content']}"
        if keyword_rank is None and keywords and any(k in haystack for k in keywords):
            keyword_rank = rank
        if doc_rank is None and doc_sub and doc_sub in r["source_document"]:
            doc_rank = rank
    return {"keyword_rank": keyword_rank, "doc_rank": doc_rank}


def _judge_answer(answer: str, expect: dict) -> dict:
    """답변 판정 — 정답 키워드 포함률 (간이 휴리스틱, 최종 판단은 사람이 리뷰)."""
    keywords = expect.get("keywords", [])
    if not keywords:
        return {"matched": [], "missed": [], "rate": None}
    matched = [k for k in keywords if k in answer]
    missed = [k for k in keywords if k not in answer]
    return {
        "matched": matched,
        "missed": missed,
        "rate": len(matched) / len(keywords),
    }


async def run(args: argparse.Namespace) -> None:
    questions = _load_questions()
    rag = RAGService(GeminiService())

    n = len(questions)
    print(f"질문 {n}건 | top_k={args.top_k} | 답변 생성={'ON' if args.answers else 'OFF'}")
    print("=" * 78)

    details: list[dict] = []
    for q in questions:
        results = await rag.search(q["question"], top_k=args.top_k)
        retrieval = _judge_retrieval(results, q["expect"])

        row: dict = {
            "id": q["id"],
            "category": q.get("category", ""),
            "question": q["question"],
            "top_score": round(results[0]["score"], 4) if results else 0.0,
            **retrieval,
        }

        if args.answers:
            gen = await rag.generate_answer(q["question"], results)
            row["confidence"] = gen["confidence"]
            row["answer"] = gen["answer"]
            row["answer_judge"] = _judge_answer(gen["answer"], q["expect"])

        details.append(row)

        kr = retrieval["keyword_rank"]
        mark = f"hit@{kr}" if kr else "MISS "
        ans_mark = ""
        if args.answers:
            rate = row["answer_judge"]["rate"]
            ans_mark = f" | 답변 {rate:.0%}" if rate is not None else ""
        print(f"  [{mark:6s}] {q['id']} {q['question'][:40]:42s}"
              f" score={row['top_score']:.3f}{ans_mark}")

    # --- 요약 ---
    def hit_at(k: int) -> float:
        return sum(
            1 for d in details
            if d["keyword_rank"] is not None and d["keyword_rank"] <= k
        ) / n

    mrr = sum(
        1.0 / d["keyword_rank"] for d in details if d["keyword_rank"] is not None
    ) / n

    summary = {
        "n": n,
        "hit@1": round(hit_at(1), 4),
        "hit@3": round(hit_at(3), 4),
        "hit@5": round(hit_at(5), 4),
        "mrr": round(mrr, 4),
    }
    if args.answers:
        rates = [
            d["answer_judge"]["rate"] for d in details
            if d["answer_judge"]["rate"] is not None
        ]
        summary["answer_keyword_rate"] = (
            round(sum(rates) / len(rates), 4) if rates else None
        )

    print("=" * 78)
    print(f"검색:  hit@1={summary['hit@1']:.0%}  hit@3={summary['hit@3']:.0%}"
          f"  hit@5={summary['hit@5']:.0%}  MRR={summary['mrr']:.3f}  (n={n})")
    if args.answers and summary.get("answer_keyword_rate") is not None:
        print(f"답변:  키워드 포함률={summary['answer_keyword_rate']:.0%}")

    # --- 리포트 저장 (베이스라인 vs 개선 비교용) ---
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tag": args.tag,
        "top_k": args.top_k,
        "title_weight": settings.TITLE_WEIGHT,
        "content_weight": settings.CONTENT_WEIGHT,
        "with_answers": args.answers,
        "summary": summary,
        "details": details,
    }
    out = EVAL_DIR / f"accuracy_{args.tag}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"리포트 저장: {out}")


def main():
    parser = argparse.ArgumentParser(description="RAG 정확도 진단 (검색/답변 분리)")
    parser.add_argument("--top-k", type=int, default=settings.TOP_K)
    parser.add_argument(
        "--answers", action="store_true",
        help="LLM 답변 생성까지 측정 (호출 비용 추가)",
    )
    parser.add_argument(
        "--tag", default="baseline",
        help="리포트 파일명 태그 (예: baseline, hybrid)",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
