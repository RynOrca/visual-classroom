"""V3 virtual classroom practice API: quiz generation, quiz sessions, mistake book."""

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.exceptions import NotFoundError
from open_notebook.virtual_classroom.domain import (
    MistakeBook,
    QuizSession,
)

router = APIRouter()


# ---------- Schemas ----------

class QuizQuestion(BaseModel):
    id: str = ""
    type: str = "single_choice"
    question: str
    options: List[str] = []
    correct_index: int = 0
    correct_answer: str = ""
    explanation: str = ""


class GenerateQuizRequest(BaseModel):
    source_id: str
    notebook_id: Optional[str] = None
    chapter_id: Optional[str] = None
    count: int = 5
    question_types: List[str] = ["single_choice"]


class QuizSessionCreate(BaseModel):
    source_id: str
    notebook_id: Optional[str] = None
    chapter_id: Optional[str] = None
    questions: List[QuizQuestion]


class QuizAnswerItem(BaseModel):
    index: int
    user_answer: str


class QuizSubmitRequest(BaseModel):
    answers: List[QuizAnswerItem]


class QuestionResult(BaseModel):
    index: int
    correct: bool
    user_answer: str
    correct_answer: str
    explanation: str


class QuizSubmitResponse(BaseModel):
    session_id: str
    total_questions: int
    correct_count: int
    score: float
    results: List[QuestionResult]


class QuizSessionResponse(BaseModel):
    id: str
    source: Optional[str] = None
    notebook: Optional[str] = None
    total_questions: int
    correct_count: int
    score: float
    details: Optional[str] = None


class MistakeCreate(BaseModel):
    source_id: str
    notebook_id: Optional[str] = None
    knowledge_point_id: Optional[str] = None
    page_number: Optional[int] = None
    quiz_type: str = "single_choice"
    question: str
    options: Optional[List[str]] = None
    correct_answer: str
    user_answer: str
    tags: List[str] = []


class MistakeUpdate(BaseModel):
    mastered: bool = False


class MistakeResponse(BaseModel):
    id: str
    source: str
    notebook: Optional[str] = None
    knowledge_point: Optional[str] = None
    page_number: Optional[int] = None
    quiz_type: str = "single_choice"
    question: str
    options: Optional[List[str]] = None
    correct_answer: str
    user_answer: str
    is_correct: bool
    mastered_at: Optional[str] = None
    tags: List[str] = []


# ---------- Helpers ----------

def _question_id(q: QuizQuestion) -> str:
    return q.id or f"q-{uuid.uuid4().hex[:8]}"


def _normalize_answer(value: str) -> str:
    return value.strip().lower()


def _is_answer_correct(q: QuizQuestion, user_answer: str) -> bool:
    user = _normalize_answer(user_answer)
    if not user:
        return False
    if q.type == "single_choice":
        # Accept "a", "a. xxx", or the option text itself.
        if user in {"a", "b", "c", "d", "e"}:
            return q.correct_index == ord(user) - ord("a")
        correct = _normalize_answer(q.correct_answer or "")
        return user == correct or user in _normalize_answer(q.correct_answer or "")
    correct = _normalize_answer(q.correct_answer or "")
    return user == correct


def _mistake_response(m: MistakeBook) -> MistakeResponse:
    return MistakeResponse(
        id=m.id or "",
        source=m.source,
        notebook=m.notebook,
        knowledge_point=m.knowledge_point,
        page_number=m.page_number,
        quiz_type=m.quiz_type or "single_choice",
        question=m.question,
        options=m.options,
        correct_answer=m.correct_answer,
        user_answer=m.user_answer,
        is_correct=m.is_correct or False,
        mastered_at=str(m.mastered_at) if m.mastered_at else None,
        tags=m.tags or [],
    )


def _session_response(s: QuizSession) -> QuizSessionResponse:
    return QuizSessionResponse(
        id=s.id or "",
        source=s.source,
        notebook=s.notebook,
        total_questions=s.total_questions or 0,
        correct_count=s.correct_count or 0,
        score=s.score or 0,
        details=s.details,
    )


async def _verify_source(source_id: str) -> None:
    source = await Source.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")


async def _verify_notebook(notebook_id: Optional[str]) -> None:
    if not notebook_id:
        return
    notebook = await Notebook.get(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")


# ---------- Quiz Generation ----------

@router.post("/virtual-classroom/quiz/generate")
async def generate_quiz(data: GenerateQuizRequest):
    """Generate quiz questions from a source using the configured LLM."""
    await _verify_source(data.source_id)
    await _verify_notebook(data.notebook_id)

    source = await Source.get(data.source_id)
    if not source or not source.full_text:
        raise HTTPException(status_code=400, detail="Source has no text content")

    type_hint = ",".join(data.question_types or ["single_choice"])
    system_prompt = SystemMessage(
        content=(
            "你是一个课件出题助手。请根据课件内容生成题目。\n"
            f"题目数量：{data.count}\n"
            f"题型：{type_hint}\n"
            "要求：\n"
            "1. 单选/多选题 options 为 4 个选项，correct_index 为正确选项下标（从0开始）\n"
            "2. 填空/简答题 options 可为空，correct_answer 填参考答案\n"
            "3. 每题都要有 explanation 解析\n"
            "4. 只输出 JSON，不要 Markdown\n"
            'JSON 格式：{"questions":[{"type":"single_choice","question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct_index":0,"correct_answer":"A. ...","explanation":"..."}]}'
        )
    )
    human_message = HumanMessage(content=f"课件内容：\n\n{source.full_text[:12000]}")
    chain = await provision_langchain_model(
        str([system_prompt, human_message]),
        None,
        "chat",
        max_tokens=8192,
    )
    response = await chain.ainvoke([system_prompt, human_message])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        questions = parsed.get("questions", [])
    except Exception:
        raise HTTPException(status_code=500, detail=f"Failed to parse quiz output: {raw[:200]}")

    result = []
    for item in questions:
        q = QuizQuestion(
            id=_question_id(QuizQuestion(**item)),
            type=item.get("type", "single_choice"),
            question=item.get("question", ""),
            options=item.get("options") or [],
            correct_index=int(item.get("correct_index", 0) or 0),
            correct_answer=item.get("correct_answer") or "",
            explanation=item.get("explanation") or "",
        )
        result.append(q)
    return {"questions": result}


# ---------- Quiz Sessions ----------

@router.post("/virtual-classroom/quiz/sessions", response_model=QuizSessionResponse)
async def create_quiz_session(data: QuizSessionCreate):
    """Create a quiz session from a set of questions."""
    await _verify_source(data.source_id)
    await _verify_notebook(data.notebook_id)
    session = QuizSession(
        source=data.source_id,
        notebook=data.notebook_id,
        total_questions=len(data.questions),
        correct_count=0,
        score=0,
        details=json.dumps([q.model_dump() for q in data.questions], ensure_ascii=False),
    )
    await session.save()
    return _session_response(session)


@router.get("/virtual-classroom/quiz/sessions", response_model=List[QuizSessionResponse])
async def list_quiz_sessions(
    source_id: Optional[str] = Query(None, description="Filter by source"),
    notebook_id: Optional[str] = Query(None, description="Filter by notebook"),
):
    conditions = []
    vars = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await repo_query(f"SELECT * FROM quiz_session {where} ORDER BY created DESC", vars)
    return [_session_response(QuizSession(**row)) for row in rows]


@router.get("/virtual-classroom/quiz/sessions/{session_id}", response_model=QuizSessionResponse)
async def get_quiz_session(session_id: str):
    try:
        session = await QuizSession.get(session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    return _session_response(session)


@router.post("/virtual-classroom/quiz/sessions/{session_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz_session(session_id: str, data: QuizSubmitRequest):
    """Submit answers for a quiz session, grade them, and record mistakes."""
    try:
        session = await QuizSession.get(session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    if not session.details:
        raise HTTPException(status_code=400, detail="Quiz session has no questions")

    try:
        questions_data = json.loads(session.details)
        questions = [QuizQuestion(**q) for q in questions_data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load quiz session questions")

    answer_map = {a.index: a.user_answer for a in data.answers}
    results = []
    correct_count = 0
    for idx, q in enumerate(questions):
        user_answer = answer_map.get(idx, "")
        correct = _is_answer_correct(q, user_answer)
        if correct:
            correct_count += 1
        results.append(
            QuestionResult(
                index=idx,
                correct=correct,
                user_answer=user_answer,
                correct_answer=q.correct_answer or (q.options[q.correct_index] if q.options else ""),
                explanation=q.explanation,
            )
        )
        if not correct:
            mistake = MistakeBook(
                source=session.source or "",
                notebook=session.notebook,
                knowledge_point=None,
                page_number=None,
                quiz_type=q.type,
                question=q.question,
                options=q.options or None,
                correct_answer=q.correct_answer or (q.options[q.correct_index] if q.options else ""),
                user_answer=user_answer,
                is_correct=False,
                tags=[],
            )
            await mistake.save()

    total = len(questions)
    score = round((correct_count / total) * 100, 2) if total else 0
    session.correct_count = correct_count
    session.score = score
    session.details = json.dumps(
        [r.model_dump() for r in results],
        ensure_ascii=False,
    )
    await session.save()

    return QuizSubmitResponse(
        session_id=session_id,
        total_questions=total,
        correct_count=correct_count,
        score=score,
        results=results,
    )


# ---------- Mistake Book ----------

@router.post("/virtual-classroom/mistakes", response_model=MistakeResponse)
async def create_mistake(data: MistakeCreate):
    """Manually add a mistake to the mistake book."""
    await _verify_source(data.source_id)
    await _verify_notebook(data.notebook_id)
    mistake = MistakeBook(
        source=data.source_id,
        notebook=data.notebook_id,
        knowledge_point=data.knowledge_point_id,
        page_number=data.page_number,
        quiz_type=data.quiz_type,
        question=data.question,
        options=data.options,
        correct_answer=data.correct_answer,
        user_answer=data.user_answer,
        is_correct=False,
        tags=data.tags,
    )
    await mistake.save()
    return _mistake_response(mistake)


@router.get("/virtual-classroom/mistakes", response_model=List[MistakeResponse])
async def list_mistakes(
    source_id: Optional[str] = Query(None, description="Filter by source"),
    notebook_id: Optional[str] = Query(None, description="Filter by notebook"),
    mastered: Optional[bool] = Query(None, description="Filter by mastered status"),
):
    conditions = []
    vars = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if mastered is not None:
        if mastered:
            conditions.append("mastered_at != NONE")
        else:
            conditions.append("mastered_at = NONE")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await repo_query(f"SELECT * FROM mistake_book {where} ORDER BY created DESC", vars)
    return [_mistake_response(MistakeBook(**row)) for row in rows]


@router.put("/virtual-classroom/mistakes/{mistake_id}", response_model=MistakeResponse)
async def update_mistake(mistake_id: str, data: MistakeUpdate):
    """Mark a mistake as mastered / not mastered."""
    try:
        mistake = await MistakeBook.get(mistake_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Mistake not found")
    if data.mastered:
        from datetime import datetime
        mistake.mastered_at = datetime.now()
    else:
        mistake.mastered_at = None
    await mistake.save()
    return _mistake_response(mistake)


@router.delete("/virtual-classroom/mistakes/{mistake_id}")
async def delete_mistake(mistake_id: str):
    try:
        mistake = await MistakeBook.get(mistake_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Mistake not found")
    await mistake.delete()
    return {"ok": True}
