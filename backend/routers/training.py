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


class ScoreResponse(BaseModel):
    score: int
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
        )
        return ScoreResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
