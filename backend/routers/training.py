"""훈련 모드 API."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QuestionRequest(BaseModel):
    difficulty: str  # beginner / intermediate / advanced
    category: str


class QuestionResponse(BaseModel):
    question: str
    question_id: str
    source_content_id: str
    difficulty: str


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
    # TODO: 질문 생성 서비스 연동
    return QuestionResponse(
        question="아직 구현되지 않았습니다.",
        question_id="",
        source_content_id="",
        difficulty=request.difficulty,
    )


@router.post("/score", response_model=ScoreResponse)
async def score_answer(request: ScoreRequest):
    # TODO: 채점 서비스 연동
    return ScoreResponse(
        score=0,
        included_items=[],
        missing_items=[],
        feedback="아직 구현되지 않았습니다.",
        reference="",
        model_answer="",
    )
