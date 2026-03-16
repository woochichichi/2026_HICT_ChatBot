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
    }


async def generate_question_from_content(
    content: dict,
    difficulty: str,
    llm: LLMService | None = None,
) -> str:
    """편람 내용을 LLM에 전달해 고객 질문 1개 생성."""
    llm = llm or GeminiService()

    difficulty_ko = DIFFICULTY_MAP.get(difficulty, "초급")
    ctx = f"{content.get('title', '')}\n\n{content.get('content', '')}".strip()

    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "training_customer.txt"
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    prompt = template.replace("{content}", ctx).replace("{difficulty}", difficulty_ko)

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
    llm: LLMService | None = None,
) -> dict:
    """훈련 모드 질문 생성 메인 진입점.

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
            "question": demo_item["question"],
            "question_id": demo_item["question_id"],
            "source_content_id": demo_item.get("source_content_id", demo_item["question_id"]),
            "difficulty": difficulty,
            "is_reset": is_reset,
        }

    content = get_content_by_id(selected_id)
    question = await generate_question_from_content(content, difficulty, llm)

    # question_id: 채점 시 Direct Fetch용. source_content_id와 동일 형식으로 매핑
    question_id = f"q-{selected_id}"

    return {
        "question": question,
        "question_id": question_id,
        "source_content_id": selected_id,
        "difficulty": difficulty,
        "is_reset": is_reset,
    }
