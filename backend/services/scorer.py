"""훈련 모드 채점 — 수동 정답 우선, 없으면 Direct Fetch (api-spec.md 섹션 5)."""

import json
from pathlib import Path

from .embedder import GeminiService, LLMService
from .question_gen import get_content_by_id

GOLDEN_ANSWERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "training_golden_answers.json"

# 페르소나(고객 상황)별 CS 채점 관점 (api-spec.md 섹션 1·11).
# ⚠️ 점수 구성(필수60/의미30/친화10)·JSON 스키마·required_items 로직은 절대 불변.
# 이 노트는 "고객 친화적 표현(10%)" 항목의 평가 관점만 구체화해 "채점 기준:" 앞에 주입.
# general은 빈 문자열 → 기존 채점과 동일(하위호환). 각 노트 끝에 개행 2개로 분리.
PERSONA_SCORING_NOTES = {
    "standard": "",
    "angry": (
        "이 답변은 '화가 난·항의하는 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "공감·사과로 감정을 먼저 누그러뜨렸는지(사과 → 사실확인 → 해결 순서), 침착하고 정중한 어조인지 보세요.\n\n"
    ),
    "impatient": (
        "이 답변은 '급하고 조급한 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "결론부터, 군더더기 없이 핵심을 빠르게 안내했는지 보세요.\n\n"
    ),
    "elderly": (
        "이 답변은 '고령 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "전문용어를 쉬운 말로 풀고, 단계적으로 천천히, 필요한 부분을 재확인·반복 안내했는지 보세요.\n\n"
    ),
    "anxious": (
        "이 답변은 '불안·걱정이 많은 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "공감으로 안심시키되, 객관적 사실·근거로 불안을 진정시켰는지 보세요.\n\n"
    ),
    "demanding": (
        "이 답변은 '규정 밖을 무리하게 요구하는 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "규정을 명확히 안내하며 정중히 거절하되, 가능한 대안을 함께 제시했는지 보세요.\n\n"
    ),
    "talkative": (
        "이 답변은 '말이 길고 장황한 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "경청하되 핵심을 짚어 간결·명확하게 정리해 안내했는지, 인내심 있는 어조인지 보세요.\n\n"
    ),
    "skeptical": (
        "이 답변은 '의심이 많고 따지는 고객'을 응대한 것입니다. '고객 친화·응대(10%)' 평가 시: "
        "단정 대신 정확한 사실과 출처·근거를 제시해 신뢰를 주었는지 보세요.\n\n"
    ),
}


def _persona_note(persona: str) -> str:
    """페르소나 키 → 채점용 관점 노트(없으면 general=빈 문자열)."""
    return PERSONA_SCORING_NOTES.get(persona or "general", "")


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
    persona: str = "general",
) -> dict:
    """training_scorer.txt 프롬프트로 LLM 채점. persona로 CS 관점 보강."""
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
        .replace("{persona_scoring_note}", _persona_note(persona))
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
        # 루브릭 분해(스코어카드 바) + 실행 코칭 팁 — 없으면 빈 리스트(하위호환)
        "criteria": data.get("criteria", []) if isinstance(data.get("criteria"), list) else [],
        "coaching_tips": data.get("coaching_tips", []) if isinstance(data.get("coaching_tips"), list) else [],
        "included_items": data.get("included_items", []),
        "missing_items": data.get("missing_items", []),
        "feedback": data.get("feedback", ""),
        "reference": data.get("reference", reference),
        "model_answer": data.get("model_answer", reference_answer),
    }


async def score_answer(
    question_id: str,
    trainee_answer: str,
    persona: str = "general",
    llm: LLMService | None = None,
) -> dict:
    """채점 메인 진입점.

    persona: 고객 상황. 데모 모드는 질문이 고정이라 출제엔 못 쓰지만, 채점은
    persona별 CS 관점을 반영(api-spec.md 섹션 1 비대칭 적용). golden required_items
    로직·점수 구성은 불변.

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
        persona=persona,
    )
