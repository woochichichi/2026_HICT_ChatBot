"""훈련 모드 질문 생성 — 업무편람 ChromaDB 기반"""

import json
import random
from pathlib import Path

from .embedder import GeminiService, LLMService
from .rag import get_chroma_client, init_collections

# 난이도 API값 → 프롬프트 한글
DIFFICULTY_MAP = {
    "beginner": "초급",
    "intermediate": "중급",
    "advanced": "고급",
}

# 고객 페르소나(상황) → 질문 생성 프롬프트에 주입할 말투 가이드 (api-spec.md 섹션 1·11).
# AI 코치 모드에서 "실제로 어떤 고객이 인입될지 모르는" 다양한 응대 상황을 시뮬레이션.
# general은 빈 문자열 → 기존 동작과 100% 동일(하위호환). 각 가이드는 "편람 내용:" 앞에
# 붙으므로 끝에 개행 2개를 포함해 자연스럽게 분리.
# 주의: 데모 모드(고정 질문)에서는 이 가이드를 질문 생성에 사용하지 않음(persona는 채점에만).
# 고객 상황(페르소나) 8종 — 콜센터에서 상담사가 자주 겪고 애먹는 유형
# (화남·무리한 요구·조급·혼란/고령·불안 등은 실제 콜센터 최대 스트레스 요인) + 증권 맥락.
PERSONA_GUIDES = {
    "standard": "",
    "angry": (
        "고객 상황: 손실·주문오류·서비스 불만 등으로 이미 화가 나 있습니다. 언성을 높이고 "
        "항의·짜증 섞인 어조로 따지듯 질문합니다(욕설·인신공격은 제외).\n\n"
    ),
    "impatient": (
        "고객 상황: 매우 급하고 조급합니다(장중 등). 인사·군말 없이 짧고 빠르게, 다소 "
        "퉁명스럽게 '핵심만 빨리'라는 어조로 질문합니다.\n\n"
    ),
    "elderly": (
        "고객 상황: 고령 고객입니다. 전문용어를 잘 모르고, 같은 내용을 되묻거나 천천히 "
        "이야기하며, 디지털·앱 사용을 어려워하는 어조로 질문합니다.\n\n"
    ),
    "anxious": (
        "고객 상황: 시장 급락·손실·사고 가능성 등으로 불안하고 걱정이 많습니다. 안심받고 "
        "싶어 하며 '괜찮은 거 맞냐'는 식으로 걱정 섞인 어조로 질문합니다.\n\n"
    ),
    "demanding": (
        "고객 상황: 규정상 어려운 것을 무리하게 요구합니다. '그냥 해달라', '안 되면 곤란하다'는 "
        "식으로 떼쓰듯, 예외를 강하게 요구하는 어조로 질문합니다.\n\n"
    ),
    "talkative": (
        "고객 상황: 말이 매우 길고 장황합니다. 배경 설명과 곁가지 이야기가 많고, 한 번에 "
        "여러 가지를 섞어 두서없이 묻습니다. 늘어지는 구어체로 질문합니다.\n\n"
    ),
    "skeptical": (
        "고객 상황: 의심이 많고 따집니다. '그게 확실하냐', '근거가 뭐냐'며 답변의 정확성과 "
        "출처를 꼬치꼬치 확인하려는 어조로 질문합니다.\n\n"
    ),
}


def _persona_guide(persona: str) -> str:
    """페르소나 키 → 질문 생성용 가이드 문자열(없으면 general=빈 문자열)."""
    return PERSONA_GUIDES.get(persona or "general", "")


# 데모 모드(고정 질문)용 페르소나 말투 스킨 — LLM 없이 결정적으로 적용.
# 데모는 질문이 golden_answers.json에서 고정되어 persona가 반영되지 않는 문제 해결.
# 핵심 문의 내용은 그대로(채점은 question_id 기준 golden), 말투/상황만 입힘.
PERSONA_DEMO_TEMPLATE = {
    "standard": "{q}",
    "angry": "아니, 이거 진짜 너무하네요. 몇 번을 말해야 합니까. {q} 똑바로 설명 좀 해보세요.",
    "impatient": "여보세요, 제가 지금 바빠서요. {q} 핵심만 짧고 빠르게요.",
    "elderly": "아이고… 내가 이런 건 잘 몰라서 그래요. {q} 좀 천천히 쉽게 알려주시겠어요?",
    "anxious": "저… 이거 잘못되면 큰일 나는 거 아니죠? 너무 걱정돼서 그러는데요, {q}",
    "demanding": "그건 됐고요, 그냥 좀 해주세요. {q} 안 된다고 하면 저 곤란해요.",
    "talkative": (
        "아 안녕하세요, 제가 어제부터 계속 알아보고 있는데 이게 좀 복잡하더라고요… "
        "주변에서도 말이 다 달라서요. 아무튼 그래서 여쭤보는 건데, {q}"
    ),
    "skeptical": "그게 확실한 거 맞아요? 근거가 뭔데요. {q} 정확하게 말해주세요.",
}


def _style_demo_question(question: str, persona: str) -> str:
    """데모 고정 질문에 페르소나 말투를 입힘(없으면 원문 그대로)."""
    tpl = PERSONA_DEMO_TEMPLATE.get(persona or "general", "{q}")
    return tpl.replace("{q}", question)

# golden_answers 파일 경로
GOLDEN_ANSWERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "training_golden_answers.json"


def get_all_content_ids(category: str | None = None) -> list[str]:
    """ChromaDB faq_contents에서 ID 목록 조회.

    PoC: 업무편람 metadata의 category가 비어 있으므로 전체 반환.
    추후 인제스트 시 category 추가되면 where 필터 적용 가능.
    """
    client = get_chroma_client()
    _, contents_col = init_collections(client)

    result = contents_col.get(limit=10000, include=["metadatas"])
    ids = result.get("ids") or []

    if category and category.strip():
        metadatas = result.get("metadatas") or []
        filtered = [
            i for i, m in zip(ids, metadatas)
            if isinstance(m, dict) and m.get("category") == category
        ]
        if filtered:
            return filtered

    return list(ids)


def select_source(
    category: str,
    solved_content_ids: list[str],
    is_demo: bool,
) -> tuple[str, bool]:
    """출제용 content_id 선택. api-spec.md 문제 추출 로직.

    Returns:
        (selected_id, is_reset): is_reset=True이면 프론트에서 solved_content_ids 초기화 필요.
    """
    if is_demo:
        demo_ids = _get_demo_question_ids(category)
        available = [d for d in demo_ids if d not in solved_content_ids]
        if not available:
            available = demo_ids
            return random.choice(available), True
        return random.choice(available), False

    candidates = get_all_content_ids(category)
    if not candidates:
        raise ValueError("ChromaDB에 출제 가능한 콘텐츠가 없습니다. 인제스트를 먼저 실행하세요.")

    available = [c for c in candidates if c not in solved_content_ids]
    if not available:
        available = candidates
        return random.choice(available), True
    return random.choice(available), False


def get_content_by_id(content_id: str) -> dict:
    """ChromaDB에서 content_id로 Direct Fetch. title + content 조합 반환."""
    client = get_chroma_client()
    titles_col, contents_col = init_collections(client)

    doc = contents_col.get(ids=[content_id], include=["documents", "metadatas"])
    title_doc = titles_col.get(ids=[content_id], include=["documents"])

    content = doc["documents"][0] if doc.get("documents") else ""
    meta = doc["metadatas"][0] if doc.get("metadatas") else {}
    title = title_doc["documents"][0] if title_doc.get("documents") else ""

    return {
        "id": content_id,
        "title": title,
        "content": content,
        "source_document": meta.get("source_document", ""),
        "source_page": meta.get("source_page", ""),
        "source_url": meta.get("source_url", ""),  # 편람 위치 링크용
    }


async def generate_question_from_content(
    content: dict,
    difficulty: str,
    persona: str = "general",
    llm: LLMService | None = None,
) -> str:
    """편람 내용을 LLM에 전달해 고객 질문 1개 생성.

    persona: 고객 상황(general/verbose/hasty/angry/novice). 말투 가이드를
    프롬프트 {persona_guide}에 주입. general이면 빈 문자열(기존 동작 동일).
    """
    llm = llm or GeminiService()

    difficulty_ko = DIFFICULTY_MAP.get(difficulty, "초급")
    ctx = f"{content.get('title', '')}\n\n{content.get('content', '')}".strip()

    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "training_customer.txt"
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    prompt = (
        template.replace("{persona_guide}", _persona_guide(persona))
        .replace("{content}", ctx)
        .replace("{difficulty}", difficulty_ko)
    )

    answer = await llm.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return (answer or "").strip()


def _get_demo_question_ids(category: str) -> list[str]:
    """training_golden_answers.json에서 question_id 목록 반환. category 무시(전체)."""
    if not GOLDEN_ANSWERS_PATH.exists():
        return []
    with open(GOLDEN_ANSWERS_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return [item["question_id"] for item in items if isinstance(item, dict)]


def _get_demo_question_by_id(question_id: str) -> dict | None:
    """golden_answers에서 question_id로 항목 조회."""
    if not GOLDEN_ANSWERS_PATH.exists():
        return None
    with open(GOLDEN_ANSWERS_PATH, encoding="utf-8") as f:
        items = json.load(f)
    for item in items:
        if isinstance(item, dict) and item.get("question_id") == question_id:
            return item
    return None


async def generate_training_question(
    difficulty: str,
    category: str,
    solved_content_ids: list[str],
    is_demo: bool = False,
    persona: str = "general",
    llm: LLMService | None = None,
) -> dict:
    """훈련 모드(AI 코치) 질문 생성 메인 진입점.

    persona: 고객 상황. 일반 출제에서만 질문 생성에 반영하고,
    데모 모드(고정 질문)에서는 미사용(질문은 그대로) — api-spec.md 섹션 1 비대칭 적용.

    Returns:
        {
            "question": str,
            "question_id": str,
            "source_content_id": str,
            "difficulty": str,
            "is_reset": bool,
        }
    """
    selected_id, is_reset = select_source(category, solved_content_ids, is_demo)

    if is_demo:
        demo_item = _get_demo_question_by_id(selected_id)
        if not demo_item:
            raise ValueError(f"데모 질문을 찾을 수 없습니다: {selected_id}")
        return {
            # 데모도 페르소나 말투를 입혀 시나리오가 상황별로 달라지게 (LLM 미사용)
            "question": _style_demo_question(demo_item["question"], persona),
            "question_id": demo_item["question_id"],
            "source_content_id": demo_item.get("source_content_id", demo_item["question_id"]),
            "reference": demo_item.get("reference", ""),
            "source_url": demo_item.get("source_url", ""),
            "difficulty": difficulty,
            "is_reset": is_reset,
        }

    content = get_content_by_id(selected_id)
    question = await generate_question_from_content(content, difficulty, persona, llm)

    # question_id: 채점 시 Direct Fetch용. source_content_id와 동일 형식으로 매핑
    question_id = f"q-{selected_id}"

    reference = f"{content.get('source_document', '')} {content.get('source_page', '')}".strip()

    return {
        "question": question,
        "question_id": question_id,
        "source_content_id": selected_id,
        "reference": reference,
        "source_url": content.get("source_url", ""),
        "difficulty": difficulty,
        "is_reset": is_reset,
    }
