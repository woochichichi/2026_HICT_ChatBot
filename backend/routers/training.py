"""훈련 모드 API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import question_gen, scorer

router = APIRouter()


class QuestionRequest(BaseModel):
    difficulty: str  # beginner / intermediate / advanced
    category: str
    solved_content_ids: list[str] = []
    is_demo: bool = False
    # 고객 상황(페르소나) — general/verbose/hasty/angry/novice (api-spec.md 섹션 1)
    persona: str = "general"


class QuestionResponse(BaseModel):
    question: str
    question_id: str
    source_content_id: str
    reference: str = ""
    difficulty: str
    is_reset: bool


class ScoreRequest(BaseModel):
    question_id: str
    trainee_answer: str
    # 채점 시에도 persona 전달 — 데모(고정질문)도 채점은 CS 관점 반영 (api-spec.md 섹션 1)
    persona: str = "general"


class ScoreResponse(BaseModel):
    score: int
    # 루브릭 분해(스코어카드) + 코칭 팁 — AI 코치 강화(api-spec.md 섹션 1). 기본 빈 리스트.
    criteria: list[dict] = []
    coaching_tips: list[str] = []
    included_items: list[str]
    missing_items: list[str]
    feedback: str
    reference: str
    model_answer: str


@router.post("/question", response_model=QuestionResponse)
async def generate_question(request: QuestionRequest):
    try:
        result = await question_gen.generate_training_question(
            difficulty=request.difficulty,
            category=request.category,
            solved_content_ids=request.solved_content_ids,
            is_demo=request.is_demo,
            persona=request.persona,
        )
        return QuestionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/score", response_model=ScoreResponse)
async def score_answer(request: ScoreRequest):
    try:
        result = await scorer.score_answer(
            question_id=request.question_id,
            trainee_answer=request.trainee_answer,
            persona=request.persona,
        )
        return ScoreResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
