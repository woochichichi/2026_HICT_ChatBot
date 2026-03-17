"""훈련 모드 채점 — 수동 정답 우선, 없으면 Direct Fetch (api-spec.md 섹션 5)."""

import json
from pathlib import Path

from .embedder import GeminiService, LLMService
from .question_gen import get_content_by_id

GOLDEN_ANSWERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "training_golden_answers.json"


def _load_golden_answer(question_id: str) -> dict | None:
    """training_golden_answers.json에서 question_id로 수동 정답 조회."""
    if not GOLDEN_ANSWERS_PATH.exists():
        return None
    with open(GOLDEN_ANSWERS_PATH, encoding="utf-8") as f:
        items = json.load(f)
    for item in items:
        if isinstance(item, dict) and item.get("question_id") == question_id:
            return item
    return None


def _derive_source_content_id(question_id: str) -> str:
    """question_id에서 source_content_id 유도. question_gen: question_id = f'q-{selected_id}'."""
    if question_id.startswith("q-"):
        return question_id[2:]
    return question_id


async def _call_scorer_llm(
    question: str,
    reference_answer: str,
    required_items: list[str],
    reference: str,
    trainee_answer: str,
    llm: LLMService,
) -> dict:
    """training_scorer.txt 프롬프트로 LLM 채점."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "training_scorer.txt"
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    items_hint = ""
    if required_items:
        items_hint = f"\n필수 포함 항목: {', '.join(required_items)}\n\n"

    prompt = (
        template.replace("{question}", question)
        .replace("{reference_answer}", reference_answer)
        .replace("{trainee_answer}", trainee_answer)
    )
    prompt = prompt.replace("채점 기준:", f"{items_hint}채점 기준:")

    resp = await llm.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        raise ValueError("채점 LLM 응답 파싱에 실패했습니다.")

    return {
        "score": int(data.get("score", 0)),
        "included_items": data.get("included_items", []),
        "missing_items": data.get("missing_items", []),
        "feedback": data.get("feedback", ""),
        "reference": data.get("reference", reference),
        "model_answer": data.get("model_answer", reference_answer),
    }


async def score_answer(
    question_id: str,
    trainee_answer: str,
    llm: LLMService | None = None,
) -> dict:
    """채점 메인 진입점.

    Returns:
        { score, included_items, missing_items, feedback, reference, model_answer }
    """
    llm = llm or GeminiService()

    # 1. 수동 정답 우선 조회
    golden = _load_golden_answer(question_id)
    if golden:
        question = golden.get("question", "")
        reference_answer = golden.get("golden_answer", "")
        required_items = golden.get("required_items", [])
        reference = golden.get("reference", "")
    else:
        # 2. Direct Fetch
        source_content_id = _derive_source_content_id(question_id)
        content = get_content_by_id(source_content_id)
        if not content.get("content"):
            raise ValueError(f"출처 문서를 찾을 수 없습니다: {source_content_id}")
        question = content.get("title", "") or "(편람 출처 문서 기반)"
        reference_answer = content["content"]
        required_items = []
        reference = f"{content.get('source_document', '')} {content.get('source_page', '')}".strip()

    # 3. LLM 채점
    return await _call_scorer_llm(
        question=question,
        reference_answer=reference_answer,
        required_items=required_items,
        reference=reference,
        trainee_answer=trainee_answer,
        llm=llm,
    )
